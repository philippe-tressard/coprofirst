"""L'intervenant, la récurrence d'un Entretien, et les catégories du conseil (#1092, lot 5).

Arbitrages de l'utilisateur, 23/09/2026 :

- la section « Intervenant » est construite — le conseil y désigne le
  prestataire ; la récurrence (« tous les N mois ») ne vaut que pour la
  catégorie **Entretien**, née pour recevoir les maintenances du calendrier ;
- **Étude & travaux** et **Entretien** sont réservées au conseil, comme
  Actualité ;
- le suivi gagne deux états, **À l'AG** et **Chez le prestataire** — les deux
  colonnes du kanban qu'aucun état ne disait.

Les règles vivent dans `utils/intervenant` et `utils/nature_affaire` ; ces
tests passent par les vraies routes de création et de correction.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi import BackgroundTasks, HTTPException

from app.models.core import RoleUtilisateur, Ticket
from app.models.prestataires import ContratEntretien, Prestataire
from app.models.tickets import StatutTicket
from app.utils.kanban_tickets import colonne_du_ticket
from tests.aides_affaire import _compte, _corriger, _creer, session  # noqa: F401


def _prestataire(session) -> Prestataire:
    p = Prestataire(nom=f"Ascenseurs {uuid.uuid4().hex[:4]}", specialite="ascenseur")
    session.add(p)
    session.commit()
    session.refresh(p)
    return p


# ── L'intervenant et la récurrence ──────────────────────────────────────────


def test_le_conseil_designe_l_intervenant_et_la_recurrence(session):
    cs = _compte(session, role=RoleUtilisateur.conseil_syndical)
    p = _prestataire(session)
    lu = _creer(
        session,
        cs,
        categorie="entretien",
        prestataire_id=p.id,
        frequence_type="mois",
        frequence_valeur=3,
    )
    assert (lu.prestataire_id, lu.prestataire_nom) == (p.id, p.nom)
    assert (lu.frequence_type, lu.frequence_valeur) == ("mois", 3)
    #  Le rythme en clair est SERVI (#2633) : le front ne le compose plus.
    assert (lu.frequence_libelle, lu.contrat) == ("↺ Mensuel", None)


def test_mensuelle_n_attend_pas_de_nombre(session):
    cs = _compte(session, role=RoleUtilisateur.conseil_syndical)
    lu = _creer(session, cs, categorie="entretien", frequence_type="mois")
    assert (lu.frequence_type, lu.frequence_valeur) == ("mois", 1)


def test_un_prestataire_inconnu_est_refuse(session):
    cs = _compte(session, role=RoleUtilisateur.conseil_syndical)
    with pytest.raises(HTTPException) as refus:
        _creer(session, cs, categorie="panne", prestataire_id=987654)
    assert refus.value.status_code == 404


def test_la_recurrence_ne_vaut_que_pour_un_entretien(session):
    """Hors Entretien elle est effacée — même à la recatégorisation."""
    cs = _compte(session, role=RoleUtilisateur.conseil_syndical)
    lu = _creer(session, cs, categorie="panne", frequence_type="mois", frequence_valeur=3)
    assert (lu.frequence_type, lu.frequence_valeur) == (None, None)

    entretien = _creer(
        session, cs, categorie="entretien", frequence_type="mois", frequence_valeur=6
    )
    lu = _corriger(session, cs, entretien.id, categorie="panne")
    assert (lu.frequence_type, lu.frequence_valeur) == (None, None)


def test_une_recurrence_inventee_est_refusee(session):
    cs = _compte(session, role=RoleUtilisateur.conseil_syndical)
    with pytest.raises(HTTPException) as refus:
        _creer(session, cs, categorie="entretien", frequence_type="lunes", frequence_valeur=2)
    assert refus.value.status_code == 422


# ── Les catégories du conseil ───────────────────────────────────────────────


@pytest.mark.parametrize("categorie", ["etude_travaux", "entretien", "actualite"])
def test_un_resident_ne_cree_pas_une_categorie_du_conseil(session, categorie):
    resident = _compte(session)
    with pytest.raises(HTTPException) as refus:
        _creer(session, resident, categorie=categorie)
    assert refus.value.status_code == 403


def test_un_resident_ne_passe_pas_vers_une_categorie_du_conseil(session):
    resident = _compte(session)
    t = _creer(session, resident, categorie="panne")
    with pytest.raises(HTTPException) as refus:
        _corriger(session, resident, t.id, categorie="etude_travaux")
    assert refus.value.status_code == 403


def test_l_auteur_d_une_etude_corrige_son_texte_sans_rien_demander(session):
    """GARDER sa catégorie n'est pas y passer : une ancienne étude reste corrigeable."""
    cs = _compte(session, role=RoleUtilisateur.conseil_syndical)
    resident = _compte(session)
    t = _creer(session, cs, categorie="etude_travaux")
    session.get(Ticket, t.id).auteur_id = resident.id
    session.commit()
    lu = _corriger(session, resident, t.id, categorie="etude_travaux", titre="Étude — corrigée")
    assert lu.titre == "Étude — corrigée"


def test_une_categorie_du_conseil_ne_fait_pas_une_actualite(session):
    """🔴 La nature se lit sur « Actualité », pas sur « réservée au conseil ».

    Le test de changement de nature était écrit sur `categorie_reservee` :
    Étude & travaux, réservée depuis ce lot, aurait fait passer une panne à
    l'état `publie` d'une actualité.
    """
    cs = _compte(session, role=RoleUtilisateur.conseil_syndical)
    t = _creer(session, cs, categorie="panne")
    lu = _corriger(session, cs, t.id, categorie="etude_travaux")
    assert lu.statut == StatutTicket.ouvert.value


# ── Les deux états nés des colonnes du kanban ───────────────────────────────


@pytest.mark.parametrize("statut, colonne", [("en_ag", "ag"), ("chez_prestataire", "fournisseur")])
def test_les_deux_nouveaux_etats_ont_leur_colonne(session, statut, colonne):
    cs = _compte(session, role=RoleUtilisateur.conseil_syndical)
    t = _creer(session, cs, categorie="entretien", statut=statut)
    assert t.statut == statut
    assert colonne_du_ticket(t.statut) == colonne


# ── Le glissement au kanban : une Suite d'état, sans avertir personne ───────


@pytest.mark.parametrize("notifier, attendu", [(True, 1), (False, 0)])
def test_un_glissement_au_kanban_n_avertit_personne(session, monkeypatch, notifier, attendu):
    """Arbitré le 23/09/2026 : déplacer une carte inscrit l'état au fil, et rien ne part.

    Le témoin (`notifier=True`) prouve que l'espion est bien appelé sur une
    Suite ordinaire — sans lui, un zéro ne dirait rien (socle 04 §2).
    """
    from app.routers.tickets import evolutions
    from app.schemas_tickets import TicketEvolutionCreate

    appels = []
    monkeypatch.setattr(evolutions, "_notifier_auteur", lambda *a, **k: appels.append(1))
    cs = _compte(session, role=RoleUtilisateur.conseil_syndical)
    auteur = _compte(session)
    t = _creer(session, cs, categorie="etude_travaux")
    session.get(Ticket, t.id).auteur_id = auteur.id
    session.commit()
    corps = TicketEvolutionCreate(type="etat", nouveau_statut="chez_prestataire", notifier=notifier)
    evolutions.add_evolution(t.id, corps, BackgroundTasks(), session=session, user=cs)
    assert session.get(Ticket, t.id).statut == "chez_prestataire"
    assert len(appels) == attendu


# ── « Quand » : planifié par le conseil syndical seul (23/09/2026) ──────────


def test_un_resident_ne_planifie_pas_a_la_creation(session):
    """Ignoré, pas refusé : son affaire se crée, sans date."""
    from datetime import datetime

    resident = _compte(session)
    lu = _creer(session, resident, categorie="panne", debut=datetime(2026, 10, 1, 9, 0))
    assert lu.debut is None


def test_le_conseil_planifie_l_affaire_d_un_resident(session):
    """Il ne réécrit pas la demande, mais il en fixe la date : ce n'est pas du contenu."""
    from datetime import datetime

    resident = _compte(session)
    cs = _compte(session, role=RoleUtilisateur.conseil_syndical)
    t = _creer(session, resident, categorie="panne")
    lu = _corriger(session, cs, t.id, debut=datetime(2026, 10, 1, 9, 0))
    assert lu.debut == datetime(2026, 10, 1, 9, 0)


def test_cas_zero_la_correction_d_un_resident_laisse_la_date(session):
    from datetime import datetime

    resident = _compte(session)
    cs = _compte(session, role=RoleUtilisateur.conseil_syndical)
    t = _creer(session, resident, categorie="panne")
    _corriger(session, cs, t.id, debut=datetime(2026, 10, 1, 9, 0))
    lu = _corriger(session, resident, t.id, titre="Fuite au 2e", debut=None)
    assert lu.titre == "Fuite au 2e"
    assert lu.debut == datetime(2026, 10, 1, 9, 0), "un résident a effacé la date planifiée"


# ── Sous contrat ou hors contrat (#1445) ────────────────────────────────────


def _contrat(session, p: Prestataire, **champs) -> ContratEntretien:
    defaut = dict(
        copropriete_id=1,
        prestataire_id=p.id,
        libelle="Ascenseur",
        numero_contrat="C-42",
        type_equipement="ascenseur",
        frequence_type="mois",
        frequence_valeur=3,
        actif=True,
    )
    c = ContratEntretien(**{**defaut, **champs})
    session.add(c)
    session.commit()
    session.refresh(c)
    return c


def test_sous_contrat_le_rythme_est_celui_du_contrat(session):
    """La fréquence envoyée est ignorée : elle se lit sur le contrat."""
    cs = _compte(session, role=RoleUtilisateur.conseil_syndical)
    p = _prestataire(session)
    c = _contrat(session, p)
    lu = _creer(
        session,
        cs,
        categorie="entretien",
        prestataire_id=p.id,
        contrat_id=c.id,
        frequence_type="semaines",
        frequence_valeur=2,
    )
    assert lu.contrat_id == c.id
    assert (lu.frequence_type, lu.frequence_valeur) == (None, None)
    assert (lu.contrat.frequence_type, lu.contrat.frequence_valeur) == ("mois", 3)
    #  Servi des deux côtés (#2633) : celui du contrat fait foi, l'affaire n'en a pas.
    assert (lu.contrat.frequence_libelle, lu.frequence_libelle) == ("↺ Mensuel", "")


@pytest.mark.parametrize(
    "cas",
    ["autre_prestataire", "archive", "assurance"],
)
def test_un_contrat_qui_ne_cadre_pas_l_intervention_est_refuse(session, cas):
    cs = _compte(session, role=RoleUtilisateur.conseil_syndical)
    p = _prestataire(session)
    if cas == "autre_prestataire":
        c = _contrat(session, _prestataire(session))
    elif cas == "archive":
        c = _contrat(session, p, actif=False)
    else:
        c = _contrat(session, p, type_equipement="assurance")
    with pytest.raises(HTTPException) as refus:
        _creer(session, cs, categorie="entretien", prestataire_id=p.id, contrat_id=c.id)
    assert refus.value.status_code == 422


def test_changer_d_intervenant_efface_le_contrat(session):
    cs = _compte(session, role=RoleUtilisateur.conseil_syndical)
    p = _prestataire(session)
    c = _contrat(session, p)
    t = _creer(session, cs, categorie="entretien", prestataire_id=p.id, contrat_id=c.id)
    lu = _corriger(session, cs, t.id, prestataire_id=_prestataire(session).id)
    assert lu.contrat_id is None, "un contrat d'un autre prestataire cadrait encore l'intervention"


def test_le_resident_lit_le_rythme_pas_le_contrat(session):
    """Le libellé et le numéro restent au conseil, comme la liste des contrats."""
    from app.routers.tickets.commun import contrat_de_l_affaire

    cs = _compte(session, role=RoleUtilisateur.conseil_syndical)
    resident = _compte(session)
    c = _contrat(session, _prestataire(session))
    pour_cs = contrat_de_l_affaire(session, c.id, cs)
    pour_resident = contrat_de_l_affaire(session, c.id, resident)
    assert (pour_cs.libelle, pour_cs.numero_contrat) == ("Ascenseur", "C-42")
    assert (pour_resident.libelle, pour_resident.numero_contrat) == (None, None)
    assert pour_resident.frequence_type == "mois"


def test_poser_le_contrat_et_resoudre_d_un_geste_avance_ce_contrat(session):
    """🔴 `apres_cloture` passait AVANT l'intervenant : le contrat posé dans la
    même correction que « Résolu » n'était pas encore sur l'affaire."""
    from datetime import date, datetime

    cs = _compte(session, role=RoleUtilisateur.conseil_syndical)
    p = _prestataire(session)
    c = _contrat(session, p)
    t = _creer(
        session,
        cs,
        categorie="entretien",
        prestataire_id=p.id,
        debut=datetime(2026, 9, 23, 10, 0),
    )
    _corriger(session, cs, t.id, contrat_id=c.id, statut=StatutTicket.résolu)
    session.refresh(c)
    assert c.prochaine_visite == date(2026, 12, 23)


# ── Les champs du conseil : intervenant, contrat, équipement ────────────────
#
#  Trois champs, trois mêmes règles : ils ne valent que pour le BÂTI, un
#  résident qui les envoie est IGNORÉ (pas refusé : son signalement doit
#  passer), et le conseil les change et les efface. Ces règles s'écrivaient
#  champ par champ, ici et dans `test_equipement_affaire.py` (#1097) ; une
#  table les pose une fois, et l'échec nomme chaque champ en défaut.
#
#  Chaque fabrique rend les valeurs à envoyer, et le n-ième appel une valeur
#  DIFFÉRENTE du précédent — sans quoi « le conseil change » ne changerait rien.


def _intervenant(session, n):
    return {"prestataire_id": _prestataire(session).id}


def _contrat_pose(session, n):
    #  Un contrat ne cadre que l'intervention de SON prestataire (#1445).
    p = _prestataire(session)
    return {"prestataire_id": p.id, "contrat_id": _contrat(session, p).id}


def _equipement(session, n):
    return {"equipement": ("toiture", "vmc")[n]}


CHAMPS_DU_CONSEIL = {
    "intervenant": _intervenant,
    "contrat": _contrat_pose,
    "équipement": _equipement,
}


def _verifier(cas):
    """Joue `cas(champ, fabrique)` pour chaque champ ; rend la liste des écarts.

    Un refus du serveur est un écart comme un autre : il ne doit pas masquer
    les champs suivants.
    """
    ecarts = []
    for champ, fabrique in CHAMPS_DU_CONSEIL.items():
        try:
            ecarts += [f"  {champ} : {e}" for e in cas(fabrique)]
        except HTTPException as refus:
            ecarts.append(f"  {champ} : refusé ({refus.status_code} {refus.detail})")
    return ecarts


def _differences(lu, attendu: dict) -> list[str]:
    return [
        f"{cle} = {getattr(lu, cle)!r} au lieu de {valeur!r}"
        for cle, valeur in attendu.items()
        if getattr(lu, cle) != valeur
    ]


def _effaces(valeurs: dict) -> dict:
    return dict.fromkeys(valeurs)


def test_hors_du_bati_les_champs_du_conseil_sont_effaces(session):
    """Une question n'a ni intervenant, ni contrat, ni équipement ; recatégorisée
    hors du bâti, l'affaire perd les siens."""
    cs = _compte(session, role=RoleUtilisateur.conseil_syndical)

    def cas(fabrique):
        valeurs = fabrique(session, 0)
        ecarts = [
            f"créée en question, {d}"
            for d in _differences(
                _creer(session, cs, categorie="question", **valeurs), _effaces(valeurs)
            )
        ]
        t = _creer(session, cs, categorie="panne", **valeurs)
        ecarts += [f"créée en panne, {d}" for d in _differences(t, valeurs)]
        lu = _corriger(session, cs, t.id, categorie="question")
        return ecarts + [
            f"recatégorisée en question, {d}" for d in _differences(lu, _effaces(valeurs))
        ]

    ecarts = _verifier(cas)
    assert not ecarts, "Hors du bâti, un champ du conseil survit :\n" + "\n".join(ecarts)


def test_un_resident_ne_designe_aucun_champ_du_conseil(session):
    """Ignoré, pas refusé : son signalement doit passer."""
    resident = _compte(session)

    def cas(fabrique):
        valeurs = fabrique(session, 0)
        lu = _creer(session, resident, categorie="panne", **valeurs)
        return _differences(lu, _effaces(valeurs))

    ecarts = _verifier(cas)
    assert not ecarts, "Un résident a désigné un champ du conseil :\n" + "\n".join(ecarts)


@pytest.mark.parametrize("categorie", ["panne", "entretien"])
def test_le_conseil_change_et_efface_chaque_champ(session, categorie):
    cs = _compte(session, role=RoleUtilisateur.conseil_syndical)

    def cas(fabrique):
        premier, second = fabrique(session, 0), fabrique(session, 1)
        t = _creer(session, cs, categorie=categorie, **premier)
        ecarts = [
            f"changé, {d}" for d in _differences(_corriger(session, cs, t.id, **second), second)
        ]
        efface = _effaces(second)
        return ecarts + [
            f"effacé, {d}" for d in _differences(_corriger(session, cs, t.id, **efface), efface)
        ]

    ecarts = _verifier(cas)
    assert not ecarts, (
        f"Le conseil ne change ou n'efface pas un champ ({categorie}) :\n" + "\n".join(ecarts)
    )
