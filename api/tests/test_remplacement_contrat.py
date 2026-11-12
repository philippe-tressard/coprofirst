"""Un contrat résilié et remplacé par celui d'un autre prestataire (12/11/2026).

Demandé à l'écran : *« comment préciser qu'un prestataire est remplacé par un autre ?
Après vérification, la résiliation de SPEM est effective au 17 novembre : lancez votre
contrat au 18 novembre (BOUVIER). »*

## Ce que ce fichier tient

- la résiliation FIXE le terme : plus de reconduction tacite, plus de préavis, et plus
  de visite en retard une fois passée — le dernier jour, lui, court encore ;
- le renvoi « remplacé par » ne vaut que DATÉ, et ne désigne ni lui-même, ni un contrat
  d'une autre copropriété, ni un contrat qui le remplace déjà (cycle) ;
- le sens inverse (« remplace… ») est DÉDUIT à la lecture, jamais stocké : les deux
  pastilles ne peuvent pas diverger ;
- la fiche de la copropriété montre la SUITE dès que l'ancien contrat a cessé ;
- le reporting ne relance pas un contrat déjà renouvelé.

⚠️ Tous les cas fixent `aujourdhui` : un test qui dépend du jour d'exécution passe au
vert ou au rouge selon le mois (`standards/04`).
"""

from __future__ import annotations

from datetime import date

import pytest
from fastapi import HTTPException

from app.routers.prestataires import ContratCreate, create_contrat, update_contrat
from app.routers.prestataires_lecture import lire_contrat
from app.routers.reporting_renouvellements import _contrats
from app.utils.echeance_contrat import echeance_du_contrat, resiliation_effective
from app.utils.remplacement_contrat import successeur_en_vigueur, verifier_remplacement
from tests.aides_affaire import _contrat, _prestataire

DERNIER_JOUR = date(2026, 11, 17)  # « résiliation effective au 17 novembre »
LENDEMAIN = date(2026, 11, 18)  # « lancez votre contrat au 18 novembre »


class _Contrat:
    def __init__(self, debut, resilie_le=None, valeur=None, unite=None):
        self.date_debut = debut
        self.resilie_le = resilie_le
        self.duree_initiale_valeur = valeur
        self.duree_initiale_unite = unite
        self.type_equipement = "extincteur"


#  ── la règle pure ──────────────────────────────────────────────────────────


def test_la_resiliation_fixe_le_terme_sans_reconduction():
    """🔴 Sans elle, un contrat de 2009 se reconduirait chaque année pour toujours."""
    e = echeance_du_contrat(_Contrat(date(2009, 2, 28), resilie_le=DERNIER_JOUR), LENDEMAIN)
    assert e.date == DERNIER_JOUR
    assert e.resilie is True
    assert e.reconduit is False and e.echu is False


def test_le_dernier_jour_court_encore_le_lendemain_non():
    c = _Contrat(date(2009, 2, 28), resilie_le=DERNIER_JOUR)
    assert resiliation_effective(c, DERNIER_JOUR) is False
    assert resiliation_effective(c, LENDEMAIN) is True


def test_un_contrat_sans_resiliation_n_est_jamais_resilie():
    assert resiliation_effective(_Contrat(date(2020, 1, 1)), LENDEMAIN) is False


#  ── ce que l'API refuse ────────────────────────────────────────────────────


def test_un_renvoi_sans_date_est_refuse(session):
    """Sans « résilié le », on ne saurait pas quand la suite commence."""
    ancien = _contrat(session, _prestataire(session, "SPEM"))
    nouveau = _contrat(session, _prestataire(session, "BOUVIER"))
    with pytest.raises(HTTPException) as e:
        verifier_remplacement(session, ancien, None, nouveau.id)
    assert e.value.status_code == 400 and "date de résiliation" in e.value.detail


def test_une_resiliation_ne_precede_pas_le_debut(session):
    ancien = _contrat(session, _prestataire(session), date_debut=date(2026, 6, 1))
    with pytest.raises(HTTPException) as e:
        verifier_remplacement(session, ancien, date(2026, 5, 31), None)
    assert e.value.status_code == 400


def test_un_contrat_ne_se_remplace_pas_lui_meme(session):
    c = _contrat(session, _prestataire(session))
    with pytest.raises(HTTPException) as e:
        verifier_remplacement(session, c, DERNIER_JOUR, c.id)
    assert e.value.status_code == 400


def test_un_remplacant_inconnu_est_un_404(session):
    c = _contrat(session, _prestataire(session))
    with pytest.raises(HTTPException) as e:
        verifier_remplacement(session, c, DERNIER_JOUR, 987654)
    assert e.value.status_code == 404


def test_un_cycle_est_refuse(session):
    """A est remplacé par B : B ne peut plus l'être par A (la chaîne bouclerait)."""
    a = _contrat(session, _prestataire(session, "A"))
    b = _contrat(session, _prestataire(session, "B"))
    a.resilie_le, a.remplace_par_id = DERNIER_JOUR, b.id
    session.add(a)
    session.commit()
    with pytest.raises(HTTPException) as e:
        verifier_remplacement(session, b, date(2027, 1, 1), a.id)
    assert e.value.status_code == 400 and "boucle" in e.value.detail


def test_un_remplacant_d_une_autre_copropriete_est_refuse(session):
    from app.models.core import Copropriete

    #  Deux copropriétés réelles : `copropriete_id=1` des aides peut désigner n'importe
    #  quelle ligne d'une base neuve, et la comparaison serait alors celle de `1` à `1`.
    copros = [Copropriete(nom=f"Résidence {i}", adresse="1 rue des Tests") for i in (1, 2)]
    session.add_all(copros)
    session.commit()
    a = _contrat(session, _prestataire(session), copropriete_id=copros[0].id)
    etranger = _contrat(session, _prestataire(session), copropriete_id=copros[1].id)
    with pytest.raises(HTTPException) as e:
        verifier_remplacement(session, a, DERNIER_JOUR, etranger.id)
    assert e.value.status_code == 400


#  ── le geste, de bout en bout ──────────────────────────────────────────────


def _poser_le_remplacement(session, ancien, nouveau):
    """Le geste de l'écran : corriger l'ANCIEN contrat (date + renvoi)."""
    return update_contrat(
        ancien.id,
        ContratCreate.model_validate(
            {
                "copropriete_id": ancien.copropriete_id,
                "prestataire_id": ancien.prestataire_id,
                "libelle": ancien.libelle,
                "date_debut": ancien.date_debut.isoformat(),
                "resilie_le": DERNIER_JOUR.isoformat(),
                "remplace_par_id": nouveau.id,
            }
        ),
        session=session,
    )


def test_les_deux_cartes_se_lisent_d_un_seul_renvoi(session):
    """🔴 LE CŒUR DE LA DEMANDE : SPEM → BOUVIER, une saisie, deux pastilles."""
    spem = _prestataire(session, "SPEM")
    bouvier = _prestataire(session, "BOUVIER SAGEX BATISANTE")
    ancien = _contrat(
        session, spem, libelle="Désenfumage & Extincteurs", date_debut=date(2009, 2, 28)
    )
    nouveau = _contrat(
        session, bouvier, libelle="Contrat de maintenance d'extincteurs", date_debut=LENDEMAIN
    )

    lu_ancien = _poser_le_remplacement(session, ancien, nouveau)

    assert lu_ancien.resilie_le == DERNIER_JOUR
    assert lu_ancien.remplace_par.prestataire_nom == "BOUVIER SAGEX BATISANTE"
    assert lu_ancien.remplace_par.date_debut == LENDEMAIN
    assert lu_ancien.date_fin == DERNIER_JOUR and lu_ancien.reconduit is False
    #  Le terme est posé : aucun préavis à relancer.
    assert lu_ancien.date_preavis is None and lu_ancien.urgence_echeance is None

    lu_nouveau = lire_contrat(session, nouveau)
    assert [a.prestataire_nom for a in lu_nouveau.remplace] == ["SPEM"]
    assert lu_nouveau.remplace[0].resilie_le == DERNIER_JOUR
    assert lu_nouveau.remplace_par is None and lu_nouveau.remplace_par_id is None


def test_retirer_le_renvoi_remet_le_contrat_comme_avant(session):
    """Un `null` explicite efface — la correction d'une erreur de saisie."""
    ancien = _contrat(session, _prestataire(session, "SPEM"))
    nouveau = _contrat(session, _prestataire(session, "BOUVIER"))
    _poser_le_remplacement(session, ancien, nouveau)

    lu = update_contrat(
        ancien.id,
        ContratCreate.model_validate(
            {
                "copropriete_id": ancien.copropriete_id,
                "prestataire_id": ancien.prestataire_id,
                "libelle": ancien.libelle,
                "date_debut": ancien.date_debut.isoformat(),
                "resilie_le": None,
                "remplace_par_id": None,
            }
        ),
        session=session,
    )
    assert lu.resilie_le is None and lu.remplace_par is None
    assert lire_contrat(session, nouveau).remplace == []


def test_a_la_creation_le_renvoi_est_verifie_aussi(session, monkeypatch):
    #  Le catalogue d'équipements n'est pas semé dans la base de test : ce n'est pas ce que
    #  ce cas éprouve.
    monkeypatch.setattr("app.routers.prestataires.exiger_equipement", lambda *a, **k: None)
    existant = _contrat(session, _prestataire(session))
    with pytest.raises(HTTPException) as e:
        create_contrat(
            ContratCreate(
                copropriete_id=existant.copropriete_id,
                prestataire_id=existant.prestataire_id,
                libelle="Nouveau",
                date_debut=date(2026, 1, 1),
                remplace_par_id=existant.id,  # sans date de résiliation
            ),
            session=session,
        )
    assert e.value.status_code == 400


#  ── ce que la résiliation change autour ────────────────────────────────────


def test_une_resiliation_passee_cesse_de_relancer_la_visite(session):
    """Une fois le 17 passé, plus de « visite en retard » : le contrat a cessé."""
    ancien = _contrat(session, _prestataire(session), prochaine_visite=date(2026, 1, 10))
    assert lire_contrat(session, ancien).en_retard is True

    ancien.resilie_le = date(2026, 2, 1)
    session.add(ancien)
    session.commit()
    lu = lire_contrat(session, ancien)
    assert lu.resilie is True and lu.en_retard is False


def test_le_successeur_prend_la_main_quand_l_ancien_a_cesse(session):
    ancien = _contrat(session, _prestataire(session, "SPEM"))
    nouveau = _contrat(session, _prestataire(session, "BOUVIER"))
    ancien.resilie_le, ancien.remplace_par_id = DERNIER_JOUR, nouveau.id
    session.add(ancien)
    session.commit()

    assert successeur_en_vigueur(session, ancien, DERNIER_JOUR).id == ancien.id
    assert successeur_en_vigueur(session, ancien, LENDEMAIN).id == nouveau.id


def test_le_successeur_suit_la_chaine(session):
    a, b, c = (_contrat(session, _prestataire(session)) for _ in range(3))
    a.resilie_le, a.remplace_par_id = date(2026, 3, 1), b.id
    b.resilie_le, b.remplace_par_id = date(2026, 9, 1), c.id
    session.add_all([a, b])
    session.commit()
    assert successeur_en_vigueur(session, a, date(2026, 10, 1)).id == c.id
    assert successeur_en_vigueur(session, a, date(2026, 5, 1)).id == b.id


def test_le_reporting_ne_relance_pas_un_contrat_deja_remplace(session):
    """Le renouvellement est fait : le successeur porte la question, pas l'ancien."""
    ancien = _contrat(session, _prestataire(session, "SPEM"), libelle="Ancien extincteurs")
    nouveau = _contrat(session, _prestataire(session, "BOUVIER"), libelle="Nouveau extincteurs")
    assert {c.libelle for c in _contrats(session, 2026)} >= {
        "Ancien extincteurs",
        "Nouveau extincteurs",
    }

    _poser_le_remplacement(session, ancien, nouveau)
    libelles = {c.libelle for c in _contrats(session, 2026)}
    assert "Ancien extincteurs" not in libelles and "Nouveau extincteurs" in libelles


def test_le_carnet_dit_la_resiliation_et_se_tait_sur_la_visite(session):
    """Le carnet nomme la résiliation, et un contrat cessé ne crie plus « visite en retard »."""
    from app.utils.carnet_entretien import _entrees_contrats

    ancien = _contrat(
        session,
        _prestataire(session, "Sécurité Beta"),
        date_debut=date(2020, 1, 1),
        prochaine_visite=date(2020, 6, 1),
        resilie_le=date(2021, 1, 1),
    )
    entrees = [e for e in _entrees_contrats(session, None) if e.libelle == ancien.libelle]
    assert entrees and "résilié au 01/01/2021" in entrees[0].detail
    assert entrees[0].alerte is None
