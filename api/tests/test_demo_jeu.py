"""Le jeu de données de la démo (spec `mode-demo.md` §6, lot D4 #1904).

Le jeu est chargé UNE fois, par la vraie commande (`app.demo.charger.charger`),
dans une copropriété d'essai sur fichier — le seed compris, comme la remise à zéro
nocturne le fera. Puis chaque écran principal doit avoir du contenu, et les dates
doivent tomber là où la démo les annonce : du passé récent, des rendez-vous à venir.
"""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, func, select

from app import contexte
from app.config import get_settings

from app.demo.charger import BaseNonVierge, charger
from app.auth.jwt import creer_jeton_acces, verify_password
from app.demo.comptes import HABITANTS
from app.demo.personnages import PERSONNAGES
from app.main import app
from app.models.acces import Telecommande, Vigik
from app.models.communaute import Idee, PetiteAnnonce, Sondage, VoteSondage
from app.models.core import CategorieTicket, StatutTicket, Ticket, Utilisateur
from app.models.copropriete import Batiment, Copropriete
from app.models.gouvernance import AgCsInfo, MembreCS
from app.models.perimetre import Perimetre
from app.models.roles import ROLE_OPERATEUR
from app.models.prestataires import ContratEntretien, Prestataire
from app.models.tickets import MessageTicket, TicketEvolution
from app.utils import horloge
from app.utils.config_site import config_site
from app.utils.stockage import stockage
from tests.aides_base import adresse_de_test
from tests.aides_pdf import DISPONIBLE, besoin_weasyprint


@pytest.fixture(scope="module")
def copro(tmp_path_factory):
    dossier = tmp_path_factory.mktemp("demo")
    adresse, retirer = adresse_de_test()
    copro = replace(
        contexte.courante(),
        identifiant="essai-demo",
        url_base=adresse,
        racine_fichiers=dossier / "fichiers",
        secret="d" * 40,
    )
    copro.racine_fichiers.mkdir()
    with contexte.dans(copro):
        #  Sans les PDF : WeasyPrint manque au poste ; `test_les_documents_de_la_demo`
        #  les rend là où il est (CI).
        bilan = charger(documents=DISPONIBLE)
    yield copro, bilan
    with contexte.dans(copro):
        contexte.moteur().dispose()
    retirer()


@pytest.fixture
def s(copro):
    with contexte.dans(copro[0]), Session(contexte.moteur()) as session:
        yield session


def _compte(s, modele, *conditions) -> int:
    return s.exec(select(func.count()).select_from(modele).where(*conditions)).one()


# ── Le chargement ────────────────────────────────────────────────────────────


def test_le_bilan_dit_ce_qui_a_ete_pose(copro):
    _, bilan = copro
    assert bilan["comptes"] == len(PERSONNAGES) + len(HABITANTS)
    assert bilan["lots"] >= 30 and bilan["affaires"] >= 15


def test_une_base_deja_peuplee_est_refusee(copro):
    with contexte.dans(copro[0]), pytest.raises(BaseNonVierge):
        charger(documents=False)


# ── Les écrans ont du contenu ────────────────────────────────────────────────


def test_la_residence_est_inventee_et_nommee(s):
    copros = s.exec(select(Copropriete)).all()
    assert [c.nom for c in copros] == ["Résidence Les Glycines"], "pas de « Ma Résidence » du seed"
    assert config_site(s, "site_nom")["site_nom"] == "Résidence Les Glycines"
    assert _compte(s, Batiment) == 3


def test_les_textes_legaux_sont_ceux_de_la_demo(s):
    """Posés après le seed, ils remplacent ses gabarits « À RENSEIGNER » (#1907)."""
    textes = config_site(s, "mentions_legales", "politique_confidentialite")
    assert "Oracle" in textes["mentions_legales"]
    assert "effacées chaque nuit" in textes["politique_confidentialite"]


def test_chaque_batiment_a_son_noeud_de_perimetre(s):
    for bat in s.exec(select(Batiment)).all():
        assert s.exec(select(Perimetre).where(Perimetre.code == f"bat:{bat.id}")).first()


def test_les_comptes_publics_existent_avec_leurs_roles(s):
    for p in PERSONNAGES.values():
        u = s.exec(select(Utilisateur).where(Utilisateur.email == p.adresse)).one()
        assert u.actif and u.email_verifie
        assert verify_password(p.mot_de_passe, u.hashed_password), p.code
        assert u.roles_json == p.roles_json


def test_les_administrateurs_sont_ceux_du_seed(s):
    """Ni un compte public, ni un habitant (D8 #1932) : les deux comptes techniques
    d'une installation standard (#1985). L'administrateur, que l'auteur peut confier
    aux visiteurs, n'est PAS opérateur ; c'est lui le gestionnaire du site."""
    admins = {u.email: u for u in s.exec(select(Utilisateur)).all() if u.has_role("admin")}
    assert sorted(admins) == ["admin@localhost", "operateur@localhost"]
    assert not admins["admin@localhost"].has_role(ROLE_OPERATEUR)
    assert admins["operateur@localhost"].has_role(ROLE_OPERATEUR)
    gestionnaire = config_site(s, "site_manager_user_id")["site_manager_user_id"]
    assert gestionnaire == str(admins["admin@localhost"].id)


def test_les_habitants_ont_des_prenoms_uniques():
    """Ils sont la clé des comptes du jeu (`comptes.poser`)."""
    from app.demo.comptes import HABITANTS

    prenoms = [h.prenom for h in HABITANTS]
    assert len(set(prenoms)) == len(prenoms)


def test_aucune_adresse_ne_peut_recevoir_de_courriel(s):
    """Habitants en `.invalid` ; comptes publics sur un sous-domaine sans serveur de
    courrier ; les comptes techniques du seed en `localhost`."""
    publics = {p.adresse for p in PERSONNAGES.values()}
    for u in s.exec(select(Utilisateur)).all():
        assert u.email.endswith((".invalid", "@localhost")) or u.email in publics


def test_les_affaires_couvrent_categories_et_etats(s):
    tickets = s.exec(select(Ticket)).all()
    categories = {t.categorie for t in tickets}
    assert {
        CategorieTicket.panne,
        CategorieTicket.etude_travaux,
        CategorieTicket.actualite,
    } <= categories
    assert len(categories) >= 8
    statuts = {t.statut for t in tickets}
    assert {
        StatutTicket.ouvert,
        StatutTicket.en_cours,
        StatutTicket.résolu,
        StatutTicket.publie,
    } <= statuts
    assert _compte(s, MessageTicket) >= 2 and _compte(s, TicketEvolution) >= 10


def test_les_dates_sont_relatives_au_jour(s):
    maintenant = horloge.maintenant()
    tickets = s.exec(select(Ticket)).all()
    assert all(t.cree_le <= maintenant for t in tickets)
    assert any(t.debut and t.debut > maintenant for t in tickets), "un rendez-vous à venir"
    actualites = [t for t in tickets if t.categorie == CategorieTicket.actualite]
    assert all((maintenant - t.cree_le).days < 30 for t in actualites), "non archivées"
    clos = [t for t in tickets if t.statut == StatutTicket.résolu]
    assert clos and all(t.ferme_le for t in clos)
    ag = s.exec(select(AgCsInfo)).one()
    assert ag.ag_date > horloge.aujourd_hui()


def test_les_perimetres_des_affaires_sont_des_codes_connus(s):
    connus = set(s.exec(select(Perimetre.code)).all())
    for t in s.exec(select(Ticket)).all():
        assert set(json.loads(t.perimetre_cible)) <= connus, t.titre


def test_la_vie_collective(s):
    sondages = s.exec(select(Sondage)).all()
    maintenant = horloge.maintenant()
    assert {s_.cloture_le > maintenant for s_ in sondages} == {True, False}, "un ouvert, un clos"
    assert _compte(s, VoteSondage) >= 10
    assert _compte(s, Idee) >= 3 and _compte(s, PetiteAnnonce) >= 3


def test_prestataires_contrats_et_annuaire(s):
    assert _compte(s, Prestataire) >= 4 and _compte(s, ContratEntretien) >= 4
    copro = s.exec(select(Copropriete)).one()
    assert copro.syndic_contrat_id, "le nom du syndic de l'annuaire suit ce contrat"
    assert _compte(s, MembreCS) >= 3


def test_badges_et_telecommandes_rattaches(s):
    assert _compte(s, Vigik) >= 20
    assert _compte(s, Telecommande) >= 3
    assert _compte(s, Vigik, Vigik.lot_id == None) == 0  # noqa: E711


# ── Ce que le site vitrine promet au compte Locataire (#2027) ───────────────
#
#  La page « Démo » de `coprofirst-site` annonce au locataire « les badges que
#  votre bailleur vous confie » et « coupures, pannes et travaux de votre
#  bâtiment ». Ces deux tests gardent ces phrases vraies : ils lisent ce que ses
#  écrans lisent, par les routes, avec sa session.


def _session_de(copro, monkeypatch, code: str) -> TestClient:
    """Un client connecté comme ce compte public — le jeton par la porte d'émission."""
    monkeypatch.setattr(contexte, "resoudre", lambda scope: copro[0])
    with contexte.dans(copro[0]), Session(contexte.moteur()) as s:
        u = s.exec(select(Utilisateur).where(Utilisateur.email == PERSONNAGES[code].adresse)).one()
        jeton = creer_jeton_acces(u.id, u.hashed_password)
    http = TestClient(app)
    http.cookies.set("access_token", jeton)
    return http


def test_le_locataire_porte_un_badge_confie_par_son_bail(copro, monkeypatch):
    http = _session_de(copro, monkeypatch, "user-loc")
    bail = http.get("/bailleur/mon-bail").json()
    assert bail and bail["acces"], "un bail en cours, et au moins un badge confié"
    assert bail["bailleur_prenom"] in {h.prenom for h in HABITANTS}, "un habitant, pas un public"
    portes = {v["code"] for v in http.get("/acces/mes-vigiks").json()}
    assert {a["code"] for a in bail["acces"]} <= portes, "l'onglet Badges les montre"


def test_le_locataire_lit_une_coupure_a_venir_dans_son_batiment(copro, monkeypatch, s):
    loc = s.exec(
        select(Utilisateur).where(Utilisateur.email == PERSONNAGES["user-loc"].adresse)
    ).one()
    son_batiment = f"bat:{loc.batiment_id}"
    http = _session_de(copro, monkeypatch, "user-loc")
    maintenant = horloge.maintenant()
    a_venir = [
        t
        for t in http.get("/tickets").json()
        if t["categorie"] == CategorieTicket.actualite.value
        and t["debut"]
        and datetime.fromisoformat(t["debut"]).replace(tzinfo=None) > maintenant
        and any(c.split("/")[0] == son_batiment for c in t["perimetre_cible"] or [])
    ]
    assert a_venir, "une actualité datée, ciblée sur son bâtiment, qu'il lit"


# ── De bout en bout : la connexion par le formulaire ─────────────────────────


@pytest.mark.parametrize("code", sorted(PERSONNAGES))
def test_chaque_compte_publie_se_connecte_en_demo(copro, monkeypatch, code):
    """Les identifiants de la page « Démo » du site vitrine ouvrent une session (#1932)."""
    monkeypatch.setattr(get_settings(), "mode_demo", "oui")
    #  Chaque requête est servie pour la copropriété d'essai (même geste que le test
    #  d'étanchéité) : la connexion doit trouver le compte que le jeu a posé.
    monkeypatch.setattr(contexte, "resoudre", lambda scope: copro[0])
    p = PERSONNAGES[code]
    reponse = TestClient(app).post(
        "/auth/login", json={"email": p.adresse, "password": p.mot_de_passe}
    )
    assert reponse.status_code == 200, reponse.text
    assert "access_token" in reponse.cookies


# ── Les fichiers produits ────────────────────────────────────────────────────


def test_le_logo_et_l_illustration_sont_ecrits(copro, s):
    with contexte.dans(copro[0]):
        nom = config_site(s, "site_logo")["site_logo"]
        assert stockage().existe(f"logo/{nom}")
        ascenseur = s.exec(select(Ticket).where(Ticket.titre.startswith("L'ascenseur"))).one()
        (url,) = json.loads(ascenseur.photos_urls)
        assert stockage().existe(url.removeprefix("/uploads/"))


@besoin_weasyprint
def test_les_documents_de_la_demo(copro, s):
    """Deux PDF, chacun rangé dans sa catégorie et lisible sur disque."""
    from app.models.documents import Document

    documents = s.exec(select(Document)).all()
    assert len(documents) == 2
    with contexte.dans(copro[0]):
        for doc in documents:
            assert doc.categorie_id and doc.mime_type == "application/pdf"
            assert stockage().lire(doc.fichier_cle).startswith(b"%PDF")
