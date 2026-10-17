"""La conservation des affaires, lots L2 et L3 : le geste, l'archive, la copie (#2014).

À l'échéance, et seulement case cochée, une affaire perd ses pièces jointes —
archivées, l'archive RELUE avant tout retrait — et ses auteurs ; elle garde son
texte. L'archive part sur le PC, qui l'accuse ; le serveur retire sa copie
30 jours plus tard. Spécification : `specs/architecture/conservation-affaires.md`.
"""

from __future__ import annotations

import csv
import io
import json
import zipfile
from datetime import date, datetime, timedelta

import pytest
from sqlmodel import Session, select

from app.models.conservation import ArchiveAffaires
from app.models.core import (
    ConfigSite,
    MessageTicket,
    RoleUtilisateur,
    Ticket,
    TicketEvolution,
    Utilisateur,
)
from app.models.documents import Document
from app.models.exploitation import HistoriqueMaintenance
from app.utils import conservation_application as app_cons
from app.utils import conservation_archive as archive_mod
from app.utils.conservation_application import appliquer_conservation
from app.utils.conservation_copie import (
    accuser_copies,
    archives_en_retard,
    retirer_copies_echues,
)
from app.utils.noms import nom_auteur
from app.utils.services import cle_actif, SERVICE_CONSERVATION
from tests.aides_base import compte
from tests.aides_http import base_http, client_http

#: Une affaire du bâti close en 2025 échoit au 1er janvier 2036 (10 exercices).
ECHUE = date(2036, 1, 2)
MAINTENANT = datetime(2036, 1, 2, 4, 45)

#: Des noms d'archive et des empreintes, en constantes : écrits après `nom=`, le
#: contrôle des identités fictives les lirait comme des noms de personne.
ARCHIVE_TRAVAUX = "affaires-principale-2025-travaux.zip"
ARCHIVE_BREVES = "affaires-principale-2025-breves.zip"
BONNE = "bonne"
FAUSSE = "fausse"


def _cocher(session: Session, valeur: str = "1") -> None:
    session.merge(ConfigSite(cle=cle_actif(SERVICE_CONSERVATION), valeur=valeur))
    session.commit()


def _affaire_complete(session: Session, disque) -> Ticket:
    """Une affaire du bâti close en 2025, avec ses fichiers partout où ils se joignent."""
    (disque / "photo.jpg").write_bytes(b"photo")
    (disque / "devis.pdf").write_bytes(b"devis")
    (disque / "prive").mkdir(exist_ok=True)
    (disque / "prive" / "rapport.pdf").write_bytes(b"rapport")
    resident = compte(session, prenom="Camille", nom="Durand", roles_json="résident")
    conseil = compte(
        session, prenom="Paul", nom="Martin", roles_json=RoleUtilisateur.conseil_syndical.value
    )
    ticket = Ticket(
        numero="TK-900",
        titre="Fissure du mur de la cour",
        description="Le texte reste.",
        categorie="etude_travaux",
        statut="résolu",
        ferme_le=datetime(2025, 5, 2, 9),
        auteur_id=resident.id,
        saisi_pour_nom="Alice Leroy",
        saisi_pour_email="alice@exemple.test",
        photos_urls='["/uploads/photo.jpg"]',
        perimetre_cible='["résidence"]',
    )
    session.add(ticket)
    session.commit()
    session.refresh(ticket)
    session.add(
        MessageTicket(
            ticket_id=ticket.id,
            auteur_id=conseil.id,
            contenu="Devis reçu.",
            fichiers_urls='["/uploads/devis.pdf"]',
        )
    )
    session.add(
        TicketEvolution(
            ticket_id=ticket.id,
            type="reponse",
            auteur_id=resident.id,
            contenu="Réponse mise en forme",
            contenu_origine="De : alice@exemple.test — le courriel brut",
        )
    )
    session.add(
        Document(
            titre="Rapport",
            fichier_nom="rapport.pdf",
            fichier_cle="prive/rapport.pdf",
            ticket_id=ticket.id,
        )
    )
    session.commit()
    return ticket


def test_case_coupee_rien_n_est_retire(session, disque_jetable):
    ticket = _affaire_complete(session, disque_jetable)
    rendu = appliquer_conservation(session, aujourd_hui=ECHUE, maintenant=MAINTENANT)
    session.refresh(ticket)
    assert rendu["active"] is False and rendu["groupes"] == []
    assert ticket.auteur_id is not None and ticket.conservee_le is None
    assert (disque_jetable / "photo.jpg").is_file()
    assert session.exec(select(ArchiveAffaires)).all() == []


def test_avant_l_echeance_rien_ne_part(session, disque_jetable):
    ticket = _affaire_complete(session, disque_jetable)
    _cocher(session)
    appliquer_conservation(session, aujourd_hui=date(2035, 12, 31), maintenant=MAINTENANT)
    session.refresh(ticket)
    assert ticket.conservee_le is None and (disque_jetable / "photo.jpg").is_file()


def test_a_l_echeance_l_affaire_perd_pieces_et_auteurs_et_garde_son_texte(session, disque_jetable):
    ticket = _affaire_complete(session, disque_jetable)
    _cocher(session)

    rendu = appliquer_conservation(session, aujourd_hui=ECHUE, maintenant=MAINTENANT)

    assert rendu["echecs"] == 0
    [groupe] = rendu["groupes"]
    assert (groupe["type"], groupe["exercice"], groupe["affaires"], groupe["fichiers"]) == (
        "travaux",
        "2025",
        1,
        3,
    )
    session.refresh(ticket)
    assert ticket.conservee_le == MAINTENANT
    assert (ticket.titre, ticket.description) == ("Fissure du mur de la cour", "Le texte reste.")
    assert ticket.auteur_id is None and ticket.auteur_qualite == "resident"
    assert (ticket.saisi_pour_nom, ticket.saisi_pour_email, ticket.lot_id) == (None, None, None)
    assert ticket.photos_urls is None and ticket.fichiers_urls == "[]"
    [message] = session.exec(select(MessageTicket)).all()
    assert (message.auteur_id, message.auteur_qualite, message.fichiers_urls) == (
        None,
        "conseil",
        "[]",
    )
    assert message.contenu == "Devis reçu."
    [suite] = session.exec(select(TicketEvolution)).all()
    assert suite.contenu_origine is None and suite.contenu == "Réponse mise en forme"
    assert session.exec(select(Document)).all() == []
    #  Les fichiers d'origine sont retirés ; l'archive, elle, est là.
    assert not (disque_jetable / "photo.jpg").exists()
    assert not (disque_jetable / "devis.pdf").exists()
    assert not (disque_jetable / "prive" / "rapport.pdf").exists()
    [archive] = session.exec(select(ArchiveAffaires)).all()
    assert archive.nom == ARCHIVE_TRAVAUX
    assert archive.cle == f"{archive_mod.DOSSIER}/{archive.nom}"
    assert archive_mod.MOTIF_NOM.match(archive.nom)
    #  Le journal : des nombres, jamais un nom.
    [ligne] = session.exec(
        select(HistoriqueMaintenance).where(HistoriqueMaintenance.tache == "conservation_affaires")
    ).all()
    assert json.loads(ligne.details)["empreinte"] == archive.empreinte


def test_l_archive_porte_chaque_fichier_et_un_sommaire_sans_nom(session, disque_jetable):
    _affaire_complete(session, disque_jetable)
    _cocher(session)
    appliquer_conservation(session, aujourd_hui=ECHUE, maintenant=MAINTENANT)
    [archive] = session.exec(select(ArchiveAffaires)).all()

    with zipfile.ZipFile(disque_jetable / archive.cle) as z:
        noms = set(z.namelist())
        assert {"TK-900/photo.jpg", "TK-900/devis.pdf", "TK-900/rapport.pdf"} <= noms
        assert z.read("TK-900/devis.pdf") == b"devis"
        html = z.read("sommaire.html").decode("utf-8")
        tableur = z.read("sommaire.csv").decode("utf-8-sig")
    lignes = list(csv.reader(io.StringIO(tableur), delimiter=";"))
    assert lignes[1][:2] == ["TK-900", "Fissure du mur de la cour"]
    for sommaire in (html, tableur):
        assert "TK-900" in sommaire
        for nom in ("Durand", "Martin", "Camille", "Leroy", "alice@"):
            assert nom not in sommaire, f"« {nom} » figure dans le sommaire"


def test_un_auteur_detache_se_lit_par_sa_qualite():
    assert nom_auteur(None, "resident") == "Un résident"
    assert nom_auteur(None, "conseil") == "Le conseil syndical"
    assert nom_auteur(None) == "Ancien résident"


def test_un_second_passage_ne_retraite_rien(session, disque_jetable):
    _affaire_complete(session, disque_jetable)
    _cocher(session)
    appliquer_conservation(session, aujourd_hui=ECHUE, maintenant=MAINTENANT)
    rendu = appliquer_conservation(
        session, aujourd_hui=ECHUE, maintenant=MAINTENANT + timedelta(days=1)
    )
    assert rendu["groupes"] == []
    assert len(session.exec(select(ArchiveAffaires)).all()) == 1


def test_une_archive_invalide_n_efface_rien(session, disque_jetable, monkeypatch):
    ticket = _affaire_complete(session, disque_jetable)
    _cocher(session)

    def tronquee(chemin, pieces):
        raise archive_mod.ArchiveInvalide("tronquée")

    monkeypatch.setattr(archive_mod, "_verifier", tronquee)
    rendu = appliquer_conservation(session, aujourd_hui=ECHUE, maintenant=MAINTENANT)

    assert rendu["echecs"] == 1 and rendu["groupes"] == []
    session.refresh(ticket)
    assert ticket.auteur_id is not None and ticket.conservee_le is None
    assert (disque_jetable / "photo.jpg").is_file()
    assert session.exec(select(ArchiveAffaires)).all() == []
    assert not list((disque_jetable / "prive").glob("archives-affaires/*.zip"))


def test_une_affaire_sans_fichier_se_detache_sans_archive(session, disque_jetable):
    auteur = compte(session, roles_json="résident")
    session.add(
        Ticket(
            numero="TK-901",
            titre="Question",
            description="d",
            categorie="question",
            statut="résolu",
            ferme_le=datetime(2025, 5, 2, 9),
            auteur_id=auteur.id,
        )
    )
    session.commit()
    _cocher(session)
    appliquer_conservation(session, aujourd_hui=date(2028, 1, 1), maintenant=MAINTENANT)
    [ticket] = session.exec(select(Ticket)).all()
    assert ticket.auteur_id is None and ticket.conservee_le is not None
    assert session.exec(select(ArchiveAffaires)).all() == []


def test_le_nom_ne_se_reutilise_jamais(session, disque_jetable):
    session.add(
        ArchiveAffaires(
            nom=ARCHIVE_TRAVAUX,
            cle="x",
            exercice="2025",
            type="travaux",
            empreinte="e",
        )
    )
    session.commit()
    _affaire_complete(session, disque_jetable)
    _cocher(session)
    appliquer_conservation(session, aujourd_hui=ECHUE, maintenant=MAINTENANT)
    noms = {a.nom for a in session.exec(select(ArchiveAffaires)).all()}
    assert "affaires-principale-2025-travaux-2.zip" in noms
    assert all(archive_mod.MOTIF_NOM.match(n) for n in noms)


@pytest.mark.parametrize(
    "nom, valide",
    [
        ("affaires-principale-2025-travaux.zip", True),
        ("affaires-principale-2024-2025-breves-3.zip", True),
        ("affaires-../etc.zip", False),
        ("affaires-a b.zip", False),
        ("affaires-a_b.zip", False),
        ("autre-2025.zip", False),
    ],
)
def test_la_liste_blanche_des_noms(nom, valide):
    assert bool(archive_mod.MOTIF_NOM.match(nom)) is valide


# ── L3 : la copie sur le PC ──────────────────────────────────────────────────


def _archive_ecrite(session: Session, disque, cree_le: datetime) -> ArchiveAffaires:
    (disque / "prive" / "archives-affaires").mkdir(parents=True, exist_ok=True)
    cle = f"{archive_mod.DOSSIER}/{ARCHIVE_BREVES}"
    (disque / cle).write_bytes(b"zip")
    archive = ArchiveAffaires(
        nom=ARCHIVE_BREVES,
        cle=cle,
        exercice="2025",
        type="breves",
        empreinte=BONNE,
        cree_le=cree_le,
    )
    session.add(archive)
    session.commit()
    session.refresh(archive)
    return archive


def test_seule_la_bonne_empreinte_accuse_la_copie(session, disque_jetable):
    archive = _archive_ecrite(session, disque_jetable, MAINTENANT)
    rendu = accuser_copies(session, {archive.nom: FAUSSE, "affaires-inconnue.zip": "x"}, MAINTENANT)
    assert rendu == {
        "accusees": [],
        "refusees": [archive.nom],
        "inconnues": ["affaires-inconnue.zip"],
    }
    session.refresh(archive)
    assert archive.copiee_le is None
    accuser_copies(session, {archive.nom: BONNE}, MAINTENANT)
    session.refresh(archive)
    assert archive.copiee_le == MAINTENANT


def test_le_serveur_retire_sa_copie_trente_jours_apres_l_accuse(session, disque_jetable):
    archive = _archive_ecrite(session, disque_jetable, MAINTENANT)
    accuser_copies(session, {archive.nom: BONNE}, MAINTENANT)
    assert retirer_copies_echues(session, MAINTENANT + timedelta(days=29)) == 0
    assert (disque_jetable / archive.cle).is_file()
    assert retirer_copies_echues(session, MAINTENANT + timedelta(days=30)) == 1
    session.refresh(archive)
    assert archive.retiree_le is not None and not (disque_jetable / archive.cle).exists()


def test_une_archive_non_copiee_depuis_trente_jours_est_un_constat(session, disque_jetable):
    archive = _archive_ecrite(session, disque_jetable, MAINTENANT)
    assert archives_en_retard(session, MAINTENANT + timedelta(days=29)) == []
    [constat] = archives_en_retard(session, MAINTENANT + timedelta(days=31))
    assert archive.nom in constat and "31 jours" in constat
    accuser_copies(session, {archive.nom: BONNE}, MAINTENANT)
    assert archives_en_retard(session, MAINTENANT + timedelta(days=31)) == []


def test_une_archive_disparue_avant_sa_copie_est_un_constat(session, disque_jetable):
    archive = _archive_ecrite(session, disque_jetable, MAINTENANT)
    (disque_jetable / archive.cle).unlink()
    [constat] = archives_en_retard(session, MAINTENANT)
    assert "absente du serveur" in constat


def test_les_routes(monkeypatch, tmp_path):
    """L'archive se télécharge par l'administrateur seul ; l'accusé exige la clé."""
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "uploads_dir", str(tmp_path))
    with base_http() as moteur:
        with Session(moteur) as s:
            archive = _archive_ecrite(s, tmp_path, MAINTENANT)
            ident, nom = archive.id, archive.nom
        url = f"/admin/conservation-affaires/archives/{ident}/fichier"
        cs, _ = client_http(moteur, RoleUtilisateur.conseil_syndical)
        assert cs.get(url).status_code == 403
        admin, _ = client_http(moteur, RoleUtilisateur.admin)
        assert admin.get(url).content == b"zip"
        lu = admin.get("/admin/conservation-affaires").json()
        assert [a["nom"] for a in lu["archives"]] == [nom]
        assert lu["delai_retrait_jours"] == 30

        accuse = "/admin/maintenance/archives-affaires/copiees"
        monkeypatch.setattr(get_settings(), "maintenance_key", "cle-de-test-assez-longue")
        #  Une session d'administrateur ne suffit pas : c'est le canal des scripts.
        assert admin.post(accuse, json={"copies": {nom: BONNE}}).status_code in (401, 403)
        reponse = admin.post(
            accuse,
            json={"copies": {nom: BONNE}},
            headers={"x-maintenance-key": "cle-de-test-assez-longue"},
        )
        assert reponse.json()["accusees"] == [nom]


def test_la_tache_est_declaree_et_enregistree_par_copropriete():
    from app.utils.taches import TACHES_DE_LA_PLATEFORME, TACHES_PERMANENTES

    assert app_cons.ID_TACHE in TACHES_PERMANENTES
    assert app_cons.ID_TACHE not in TACHES_DE_LA_PLATEFORME


def test_l_auteur_supprime_reste_un_ancien_resident(session, disque_jetable):
    """Un compte déjà supprimé n'a pas de qualité : il reste « Ancien résident »."""
    assert app_cons.qualite(session, None) is None
    u = compte(session, roles_json="résident")
    assert app_cons.qualite(session, u.id) == "resident"
    assert session.get(Utilisateur, u.id) is not None
