"""Ce qu'une affaire sert aux deux clients, au lieu que chacun le recalcule (#2508).

Une règle par test, le cas fautif d'abord — celui que la copie du front ou de
l'app aurait rendu faux : l'énumération qui fuit (`CategorieTicket.panne`), le
rédacteur nommé à la place de la personne « saisie pour », un statut inconnu rangé
dans une colonne, une catégorie réservée offerte à un résident.
"""

from __future__ import annotations

from types import SimpleNamespace

from app.models.core import RoleUtilisateur
from app.models.tickets import CategorieTicket, StatutTicket
from app.routers.tickets import crud
from app.routers.tickets.referentiels import referentiels_pour
from app.schemas import TicketRead
from tests.aides_affaire import _compte, _corriger, _creer, session  # noqa: F401

CS = RoleUtilisateur.conseil_syndical


def _servie(**colonnes) -> TicketRead:
    """Un `TicketRead` minimal : les champs calculés ne lisent que ses colonnes."""
    base = {
        "id": 1,
        "numero": "TK-1",
        "titre": "t",
        "description": "d",
        "categorie": "panne",
        "statut": "ouvert",
        "priorite": "normale",
        "cree_le": "2026-11-04T10:00:00",
    }
    return TicketRead.model_validate({**base, **colonnes})


# ── ⚡ urgente — `ticketUrgent` ────────────────────────────────────────────────


def test_urgente_la_priorite_haute_et_elle_seule():
    #  Le cas fautif : la catégorie « urgence » (retirée, migration 0177) ne presse pas.
    assert _servie(categorie="urgence").urgente is False
    assert _servie(priorite="haute").urgente is True
    assert _servie(priorite="normale").urgente is False


def test_urgente_est_servie_avec_la_ligne_du_fil():
    """`pastilles_affaire` rend la ligne par `TicketRead` : le champ y est, sans appelant."""
    from app.routers.flux.commun import CHAMPS_PASTILLES, pastilles_affaire

    assert "urgente" in CHAMPS_PASTILLES
    ligne = pastilles_affaire(
        SimpleNamespace(**{**_servie(priorite="haute").model_dump(), "perimetre_cible": None})
    )
    assert ligne["urgente"] is True


# ── nom_proprietaire — `nomProprietaire` ──────────────────────────────────────


def test_nom_proprietaire_la_personne_saisie_pour_jamais_le_redacteur(session):
    conseil = _compte(session, role=CS)
    lu = _creer(session, conseil, categorie="panne", saisi_pour_nom="Mme Durand")
    #  Le cas fautif : la carte nommait le rédacteur (#1104).
    assert lu.nom_proprietaire != lu.auteur_nom
    assert lu.nom_proprietaire == lu.proprietaire_nom
    assert "Durand" in lu.nom_proprietaire


def test_nom_proprietaire_sans_saisi_pour_le_redacteur_et_jamais_none():
    assert _servie(auteur_nom="Jean DUPONT").nom_proprietaire == "Jean DUPONT"
    assert _servie().nom_proprietaire == ""


# ── colonne_kanban — `colonneDuTicket` ────────────────────────────────────────


def test_colonne_kanban_un_statut_inconnu_sort_du_tableau():
    #  Le cas fautif : un repli sur « cs » rangerait la carte arbitrairement.
    assert _servie(statut="fermé").colonne_kanban is None
    assert _servie(statut="publie").colonne_kanban is None
    assert _servie(statut="en_ag").colonne_kanban == "ag"
    assert _servie(statut="chez_prestataire").colonne_kanban == "fournisseur"


def test_colonne_kanban_suit_l_etat_que_la_suite_pose(session):
    conseil = _compte(session, role=CS)
    etude = _creer(session, conseil, categorie="etude_travaux")
    assert etude.colonne_kanban == "cs"
    assert _corriger(session, conseil, etude.id, statut="en_cours").colonne_kanban == "syndic"


# ── libellés, affaire close ────────────────────────────────────────────────────


def test_categorie_libelle_l_enumeration_ne_fuit_pas():
    lu = TicketRead.model_validate(
        {**_servie().model_dump(), "categorie": CategorieTicket.etude_travaux}
    )
    assert lu.categorie_libelle == "Étude & travaux"
    assert "CategorieTicket" not in lu.categorie_libelle
    assert _servie(categorie="inventee").categorie_libelle == "inventee"


def test_statut_libelle_et_close():
    assert _servie(statut=StatutTicket.en_cours.value).statut_libelle == "Chez le syndic"
    assert _servie(statut="inventé").statut_libelle == "inventé"
    #  `fermé` s'affiche (le fil d'une affaire ancienne), il ne clôt plus rien.
    assert _servie(statut="fermé").statut_libelle == "Fermé"
    assert _servie(statut="résolu").close is True
    assert _servie(statut="annulé").close is True
    assert _servie(statut="publie").close is False


# ── 🔹 perimetre_libelle ───────────────────────────────────────────────────────


def test_perimetre_libelle_tait_le_perimetre_par_defaut(session):
    auteur = _compte(session)
    lu = _creer(session, auteur, categorie="panne")
    assert lu.perimetre_libelle == ""
    batiment = next(c for c in _codes_de_batiment(session))
    lu = _corriger(session, auteur, lu.id, perimetre_cible=[batiment])
    assert lu.perimetre_libelle and lu.perimetre_libelle != batiment


def _codes_de_batiment(session):
    from app.utils.perimetres import arbre

    return [code for code in arbre() if code.startswith("bat:")]


# ── GET /tickets/referentiels ──────────────────────────────────────────────────


def test_referentiels_une_categorie_reservee_n_est_pas_permise_au_resident(session):
    resident = _compte(session)
    conseil = _compte(session, role=CS)
    permises = {c.code: c.permise for c in referentiels_pour(resident).categories}
    #  Le cas fautif : la grille de l'app offrait « Actualité » à tous.
    assert permises["actualite"] is False
    assert permises["etude_travaux"] is False
    assert permises["panne"] is True
    assert all(c.permise for c in referentiels_pour(conseil).categories)


def test_referentiels_la_grille_dit_ce_que_la_creation_accepte(session):
    """`permise` n'est pas une seconde règle : la création refuse ce qu'elle tait."""
    from fastapi import HTTPException

    resident = _compte(session)
    for c in referentiels_pour(resident).categories:
        try:
            _creer(session, resident, categorie=c.code)
            accepte = True
        except HTTPException as e:
            assert e.status_code == 403
            accepte = False
        assert accepte is c.permise, c.code


def test_referentiels_couvrent_les_enumerations(session):
    r = referentiels_pour(_compte(session))
    assert [c.code for c in r.categories][0] == "panne"
    assert {c.code for c in r.categories} == {c.value for c in CategorieTicket}
    assert {s.code for s in r.statuts} >= {s.value for s in StatutTicket}
    proposables = {s.code for s in r.statuts if s.proposable}
    assert "publie" not in proposables and "fermé" not in proposables
    assert {s.code for s in r.statuts if s.clos} == {"résolu", "annulé"}
    colonnes = {c.code for c in r.colonnes_kanban}
    assert {s.colonne_kanban for s in r.statuts if s.colonne_kanban} <= colonnes
    assert [n.code for n in r.natures] == ["actualite", "calendrier", "activite"]


def test_referentiels_route_montee_avant_le_motif_ticket_id():
    """`/referentiels` est littéral : `/{ticket_id}` le capterait en 422 (#1151)."""
    from app.main import app
    from tests.aides_sources import operations_montees

    gets = [chemin for methode, chemin, _ in operations_montees(app) if methode == "GET"]
    assert gets.index("/tickets/referentiels") < gets.index("/tickets/{ticket_id}")


def test_la_liste_porte_les_champs_servis_pour_son_lecteur(session):
    auteur = _compte(session)
    cree = _creer(session, auteur, categorie="panne", urgente=True)
    lu = next(t for t in crud.list_tickets(session=session, user=auteur) if t.id == cree.id)
    assert lu.urgente is True
    assert lu.peut_repondre is True and lu.peut_archiver is False


# ── POST /uploads/fichier, pour un client natif ───────────────────────────────


def test_l_envoi_de_fichier_est_type_et_decrit_par_la_regle_meme():
    """L'app joint ses pièces avant la création : le contrat dit ce qui est rendu,
    et ce qui est accepté — lu dans `FAMILLES`, la règle qui refuse."""
    from app.main import app
    from app.utils.fichiers import FAMILLES

    operation = app.openapi()["paths"]["/uploads/fichier"]["post"]
    reponse = operation["responses"]["200"]["content"]["application/json"]["schema"]
    assert reponse["$ref"].endswith("/PieceJointeRecue")
    for famille in ("image", "document"):
        assert f"{FAMILLES[famille].plafond_mo} Mo" in operation["description"]
        assert all(ext in operation["description"] for ext in FAMILLES[famille].extensions)


# ── nouveau — `isNouveau` ──────────────────────────────────────────────────────


def test_nouveau_une_affaire_de_trois_jours_n_a_plus_de_badge():
    from datetime import timedelta

    from app.utils import horloge

    il_y_a = lambda heures: (horloge.maintenant() - timedelta(hours=heures)).isoformat()  # noqa: E731
    #  Le cas fautif : la carte jugeait l'horloge du NAVIGATEUR, l'app la sienne.
    assert _servie(cree_le=il_y_a(72)).nouveau is False
    assert _servie(cree_le=il_y_a(49)).nouveau is False
    assert _servie(cree_le=il_y_a(1)).nouveau is True
