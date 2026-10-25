"""Ce qu'un objet PORTE, sa lecture le REND — les huit lectures de #1563.

## Le défaut (audit du 02/10/2026)

#1092 avait corrigé `ticket_read`, qui construisait `TicketRead` colonne par
colonne : un champ déclaré au schéma et oublié dans l'appel part à sa valeur par
défaut, sans un mot. Le garde-fou de #1092 ne regardait que `TicketRead`, et
huit autres lectures recopiaient encore leurs colonnes une à une — dont deux
écrites deux fois (`patrimoine`, `diagnostics`).

L'une perdait déjà quelque chose : `evol_read` ne rendait ni `assiste_ia` ni
`contenu_origine`. Le fil d'une affaire n'a donc jamais montré la marque
« rédigé avec l'assistant » ni le « Message d'origine » d'une réponse reçue
par courriel, alors que l'écran (`RubriqueHistorique`) les affiche tous deux.

## Ce que ce fichier vérifie

Pour chaque lecture convertie, sur un objet représentatif — chaque colonne
posée à une valeur qui n'est pas son défaut —, la sortie JSON ENTIÈRE, champ par
champ. Les valeurs attendues sont celles de l'ancienne écriture, relevées avant
la conversion ; seuls `assiste_ia` et `contenu_origine` de l'historique
diffèrent, et c'est le correctif.

La règle qui empêche la recopie de revenir est un contrôle de forme :
`test_lecture_colonne_par_colonne.py`.
"""

from __future__ import annotations

from datetime import date, datetime

from app.models.core import (
    Batiment,
    ContratEntretien,
    Copropriete,
    DiagnosticRapport,
    DiagnosticType,
    LocationBail,
    Lot,
    Prestataire,
    StatutBail,
    TicketEvolution,
    TypeEquipement,
    TypeLot,
    Vigik,
)
from app.models.perimetre import Perimetre
from tests.aides_base import compte

QUAND = datetime(2026, 10, 1, 9, 30)


def _json(lu) -> object:
    if isinstance(lu, list):
        return [_json(x) for x in lu]
    return lu.model_dump(mode="json")


def _poser(session, *objets):
    for o in objets:
        session.add(o)
    session.commit()
    for o in objets:
        session.refresh(o)
    return objets


# ── patrimoine : PerimetreRead (deux écritures, dont l'orphelin) ──────────────


def test_perimetre_read_arbre_et_orphelin():
    from app.routers.patrimoine import _en_lecture

    racine = Perimetre(
        id=1,
        code="residence",
        libelle="Résidence",
        libelle_court="Rés.",
        description="Tout",
        icone="maison",
        portee_globale=True,
        selectionnable=False,
        ordre=0,
    )
    enfant = Perimetre(
        id=2,
        code="Bat-A",
        parent_id=1,
        libelle="Bâtiment A",
        libelle_court=None,
        description=None,
        batiment_id=7,
        privatif=True,
        hors_copropriete=True,
        actif=False,
        ordre=3,
    )
    orphelin = Perimetre(
        id=3, code="perdu", parent_id=999, libelle="Perdu", description="", portee_globale=True
    )
    lus = _json(_en_lecture([racine, enfant, orphelin], {"bat-a"}))
    assert lus == ATTENDU_PERIMETRES, lus


# ── diagnostics : DiagnosticTypeRead (liste et bascule) ───────────────────────


def _type_diagnostic(session):
    admin = compte(session, prefixe="admin")
    t = DiagnosticType(
        code="dpe",
        nom="Essai",
        texte_legislatif="Art. L126-26",
        frequence="10 ans",
        ordre=4,
        non_applicable=False,
    )
    _poser(session, t)
    r = DiagnosticRapport(
        diagnostic_type_id=t.id,
        titre="Rapport 2025",
        date_rapport=date(2025, 6, 1),
        fichier_nom="dpe.pdf",
        taille_octets=1234,
        mime_type="application/pdf",
        synthese="Classe C",
        publie_par_id=admin.id,
        publie_le=QUAND,
    )
    _poser(session, r)
    return admin, t


def test_diagnostic_type_read_liste_et_bascule(session):
    from app.routers.diagnostics import (
        DiagnosticTypeNonApplicableUpdate,
        list_types,
        toggle_non_applicable,
    )

    admin, t = _type_diagnostic(session)
    liste = _json(list_types(session=session, _=admin))
    bascule = _json(
        toggle_non_applicable(
            t.id, DiagnosticTypeNonApplicableUpdate(non_applicable=True), session=session, _=admin
        )
    )
    assert liste == [ATTENDU_DIAGNOSTIC], liste
    assert bascule == {**ATTENDU_DIAGNOSTIC, "non_applicable": True}, bascule


# ── tickets : TicketEvolutionRead ─────────────────────────────────────────────


def test_evolution_read_rend_toutes_ses_colonnes(session):
    from app.routers.tickets.commun import evol_read

    auteur = compte(session, prefixe="auteur", prenom="Jeanne", nom="DURAND")
    (e,) = _poser(
        session,
        TicketEvolution(
            ticket_id=41,
            type="commentaire",
            contenu="Voici",
            ancien_statut="ouvert",
            nouveau_statut="en_cours",
            auteur_id=auteur.id,
            cree_le=QUAND,
            fichiers_urls='["/uploads/a.pdf"]',
            perimetre_cible='["bat-a"]',
            contenu_origine="Bonjour, voici le devis.",
            assiste_ia=True,
        ),
    )
    lu = _json(evol_read(e, session, statut_avant="ouvert"))
    assert lu == {**ATTENDU_EVOLUTION, "id": e.id, "auteur_id": auteur.id}, lu


def test_evolution_read_sans_perimetre_rend_none_et_non_liste_vide(session):
    """#497 : « n'en parle pas » (`None`) n'est pas « plus aucun périmètre »."""
    from app.routers.tickets.commun import evol_read

    auteur = compte(session, prefixe="auteur")
    (e,) = _poser(session, TicketEvolution(ticket_id=1, type="etat", auteur_id=auteur.id))
    lu = evol_read(e, session)
    assert lu.perimetre_cible is None and lu.fichiers_urls == []


# ── L'aide elle-même : `utils/lecture.lire_objet` ─────────────────────────────


def test_lire_objet_refuse_un_derive_que_le_schema_ne_declare_pas():
    """Pydantic ignorerait la clé : le champ n'atteindrait jamais l'API."""
    import pytest

    from app.routers.lots import LotRead
    from app.utils.lecture import lire_objet

    lot = Lot(id=1, numero="12", type=TypeLot.cave)
    with pytest.raises(TypeError, match="batiment_libelle"):
        lire_objet(LotRead, lot, type="cave", batiment_libelle="Bât. B")


def test_lire_objet_le_derive_prime_sur_l_attribut_et_se_valide():
    from app.routers.lots import LotRead
    from app.utils.lecture import lire_objet

    lot = Lot(id=1, numero="12", type=TypeLot.cave, etage=3)
    lu = lire_objet(LotRead, lot, type="parking", etage="4")
    assert (lu.type, lu.etage, lu.numero) == ("parking", 4, "12")


# ── lots et bailleur : LotRead, AccesOut, BailLocataireOut, LocataireInfo ─────


def _lot_et_batiment(session):
    (bat,) = _poser(session, Batiment(copropriete_id=1, numero="B"))
    (lot,) = _poser(
        session,
        Lot(
            batiment_id=bat.id,
            numero="12",
            type=TypeLot.appartement,
            type_appartement="T3",
            etage=2,
            superficie=61.5,
        ),
    )
    return bat, lot


def test_lot_read(session):
    from app.routers.lots import _lot_read

    _, lot = _lot_et_batiment(session)
    assert _json(_lot_read(lot)) == {**ATTENDU_LOT, "id": lot.id, "batiment_id": lot.batiment_id}


def _bail(session):
    bailleur = compte(session, prefixe="bailleur", prenom="Paul", nom="BAILLEUR", telephone="0102")
    locataire = compte(session, prefixe="locataire", prenom="Alice", nom="LOCATAIRE")
    bat, lot = _lot_et_batiment(session)
    (bail,) = _poser(
        session,
        LocationBail(
            lot_id=lot.id,
            bailleur_id=bailleur.id,
            locataire_id=locataire.id,
            date_entree=date(2026, 1, 1),
            date_sortie_prevue=date(2027, 1, 1),
            statut=StatutBail.actif,
        ),
    )
    (badge,) = _poser(
        session,
        Vigik(code="V-9", lot_id=lot.id, chez_locataire=True, bail_id=bail.id, cree_le=QUAND),
    )
    return bailleur, locataire, lot, bail, badge


def test_acces_out(session):
    from app.routers.bailleur.acces import _sortie

    _, _, lot, bail, badge = _bail(session)
    lu = _json(_sortie(session, {lot.id: lot}, "vigik", badge, recommande=True))
    attendu = {**ATTENDU_ACCES, "id": badge.id, "lot_id": lot.id, "bail_id": bail.id}
    assert lu == {**attendu, "recommande": True}, lu


def test_bail_locataire_out(session):
    from app.routers.bailleur.acces import mon_bail

    bailleur, locataire, lot, bail, badge = _bail(session)
    lu = _json(mon_bail(user=locataire, session=session))
    acces = {**ATTENDU_ACCES, "id": badge.id, "lot_id": lot.id, "bail_id": bail.id}
    #  `mon-bail` passe une carte de lots VIDE : le badge y sort sans type ni
    #  libellé de lot. C'est l'existant, relevé tel quel — pas l'objet de #1563.
    acces |= {"lot_type": None, "lot_label": None}
    attendu = {
        **ATTENDU_BAIL,
        "id": bail.id,
        "lot_id": lot.id,
        "bailleur_email": bailleur.email,
        "acces": [acces],
    }
    assert lu == attendu, lu


def test_locataire_info(session):
    from app.auth.adresse_compte import adresse_masquee
    from app.models.core import StatutUtilisateur
    from app.routers.bailleur.baux import search_locataire
    from tests.conftest import requete_de_test

    bailleur = compte(session, prefixe="bailleur")
    locataire = compte(
        session,
        prefixe="loc",
        prenom="Alice",
        nom="LOCATAIRE",
        actif=False,
        statut=StatutUtilisateur.locataire,
    )
    requete = requete_de_test("/bailleur/search-locataire", "GET")
    lus = _json(search_locataire(requete, q=locataire.email, user=bailleur, session=session))
    attendu = {
        "id": locataire.id,
        "nom": "LOCATAIRE",
        "prenom": "Alice",
        "email_masque": adresse_masquee(locataire.email),
    }
    assert lus == [{**attendu, "actif": False}], lus


# ── copropriété : ContratCandidat ─────────────────────────────────────────────


def test_contrat_candidat(session):
    from app.routers.copropriete import contrats_candidats

    admin = compte(session, prefixe="admin")
    (copro,) = _poser(session, Copropriete(nom="Copro", adresse="1 rue"))
    (presta,) = _poser(session, Prestataire(nom="Assureur", specialite="assurance"))
    (contrat,) = _poser(
        session,
        ContratEntretien(
            copropriete_id=copro.id,
            prestataire_id=presta.id,
            type_equipement=TypeEquipement.assurance,
            libelle="Multirisque",
            numero_contrat="MR-42",
            date_debut=date(2025, 3, 1),
            actif=False,
        ),
    )
    lus = _json(contrats_candidats("assurance", session=session, _=admin))
    assert lus == [{**ATTENDU_CONTRAT, "id": contrat.id}], lus


# ── Les sorties attendues — relevées sur l'ancienne écriture ──────────────────

#: Un nœud tel que l'ancienne écriture le rendait, puis ce qui change par nœud.
_NOEUD = {
    "parent": None,
    "icone": None,
    "batiment_id": None,
    "profondeur": 0,
    "ordre": 0,
    "actif": True,
    "portee_globale": False,
    "concerne_tous": False,
    "selectionnable": True,
    "privatif": False,
    "hors_copropriete": False,
    "utilise": False,
    #  Ajoutés le 13/10/2026 (dupliquer, supprimer une branche) : lus sur
    #  `utils/perimetres/branche`, pas sur une colonne.
    "nb_descendants": 0,
    "dupliquable": False,
    #  Ajouté le 17/10/2026 (#2060) : lu dans la configuration des accès fixes.
    "acces_fixes": [],
}
ATTENDU_PERIMETRES = [
    {
        **_NOEUD,
        "id": 1,
        "code": "residence",
        "libelle": "Résidence",
        "libelle_court": "Rés.",
        "description": "Tout",
        "icone": "maison",
        "portee_globale": True,
        "concerne_tous": True,
        "selectionnable": False,
        #  Sa branche porte un bâtiment (Bat-A) : elle ne se duplique pas d'un bloc.
        "nb_descendants": 1,
    },
    {
        **_NOEUD,
        "id": 2,
        "code": "Bat-A",
        "parent": "residence",
        "libelle": "Bâtiment A",
        #  Les deux replis : un libellé court absent prend le libellé, une
        #  description absente sort en chaîne vide.
        "libelle_court": "Bâtiment A",
        "description": "",
        "batiment_id": 7,
        "profondeur": 1,
        "ordre": 3,
        "actif": False,
        "concerne_tous": True,  # hérité de la racine
        "privatif": True,
        "hors_copropriete": True,
        "utilise": True,  # cité ; la casse du code n'y fait rien
    },
    {
        #  L'orphelin : rendu quand même, sans parent ni profondeur.
        **_NOEUD,
        "id": 3,
        "code": "perdu",
        "libelle": "Perdu",
        "libelle_court": "Perdu",
        "description": "",
        "portee_globale": True,
        "concerne_tous": True,
    },
]
ATTENDU_DIAGNOSTIC = {
    "id": 1,
    "code": "dpe",
    "nom": "Essai",
    "texte_legislatif": "Art. L126-26",
    "frequence": "10 ans",
    "ordre": 4,
    "non_applicable": False,
    "rapports": [
        {
            "id": 1,
            "diagnostic_type_id": 1,
            "titre": "Rapport 2025",
            "date_rapport": "2025-06-01",
            "fichier_nom": "dpe.pdf",
            "taille_octets": 1234,
            "mime_type": "application/pdf",
            "synthese": "Classe C",
            "publie_le": "2026-10-01T09:30:00",
        }
    ],
}
ATTENDU_EVOLUTION = {
    "type": "commentaire",
    "contenu": "Voici",
    "ancien_statut": "ouvert",
    "nouveau_statut": "en_cours",
    "auteur_nom": "Jeanne DURAND",
    "cree_le": "2026-10-01T09:30:00",
    "fichiers_urls": ["/uploads/a.pdf"],
    #  🔴 Les deux champs que l'ancienne écriture perdait (`None` et `False`).
    "contenu_origine": "Bonjour, voici le devis.",
    "assiste_ia": True,
    "ticket_id": 41,
    "perimetre_cible": ["bat-a"],
    "statut_avant": "ouvert",
}
ATTENDU_LOT = {
    "numero": "12",
    "type": "appartement",
    "type_appartement": "T3",
    "etage": 2,
    "superficie": 61.5,
    "batiment_nom": "Bât. B",
    "est_logement_de_reference": False,
    "type_lien": None,
    #  La désignation du règlement (#2212) : la nature se déduit du type tant que
    #  l'état descriptif ne l'a pas posée ; les tantièmes ne se montrent qu'à qui
    #  les lit (`None`, jamais une liste vide trompeuse).
    "nature": "logement",
    "numero_usage": None,
    "circulation": None,
    "perimetres": [],
    "quotes_parts": None,
    "explication": None,
    "alertes": [],
}
ATTENDU_ACCES = {
    "code": "V-9",
    "type": "vigik",
    "lot_type": "appartement",
    "lot_label": "Bât. B — Lot 12",
    "statut": "actif",
    "chez_locataire": True,
    "eligible_transfert": False,
    "recommande": False,
    "motif_non_eligible": None,
    "cree_le": "2026-10-01T09:30:00",
}
ATTENDU_BAIL = {
    "lot_numero": "12",
    "lot_type": "appartement",
    "lot_type_appartement": "T3",
    "lot_etage": 2,
    "lot_superficie": 61.5,
    #  🔴 L'ancienne écriture lisait `Batiment.nom`, qui n'existe pas : la route
    #  levait (500) dès que le lot du bail avait un bâtiment.
    "lot_batiment_nom": "Bât. B",
    "bailleur_nom": "BAILLEUR",
    "bailleur_prenom": "Paul",
    "bailleur_telephone": "0102",
    "date_entree": "2026-01-01",
    "date_sortie_prevue": "2027-01-01",
    "statut": "actif",
}
ATTENDU_CONTRAT = {
    "libelle": "Multirisque",
    "prestataire": "Assureur",
    "numero_contrat": "MR-42",
    "date_debut": "2025-03-01",
    "actif": False,
}
