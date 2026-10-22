"""Ce qui est réservé à un périmètre ne part pas en entier sur le groupe (22/10/2026).

## L'incident

Signalé par l'utilisateur : une affaire « nouveau code de l'ascenseur », ciblée
sur un bâtiment, l'écran affichant « Réservé au périmètre sélectionné » coché.
Le groupe WhatsApp de la résidence — TOUS les résidents — a reçu la description,
c'est-à-dire le code. La diffusion a dû être coupée.

L'actualité réservée partait bien réduite au titre et au lien ; l'affaire suivie
ne transmettait jamais la réserve à `diffuser` (création, Suite), et l'aperçu ne
la transmettait pour aucune des deux natures. Les tests de diffusion vérifiaient
qu'un message PARTAIT, jamais ce qu'il CONTENAIT.

## Ce qu'on regarde

Le texte que le groupe reçoit, composé comme le canal le compose
(`construire_message`) — par les vraies routes : création, Suite, aperçu. Et une
seule porte : `contenu_hors_du_groupe` décide, `diffuser_l_affaire` l'applique.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from fastapi import BackgroundTasks
from sqlmodel import Session

import app.routers.tickets.apercu as apercu
import app.routers.tickets.crud as crud
import app.routers.tickets.evolutions as evolutions
import app.utils.diffusion as diffusion
from app.database import engine
from app.models.core import RoleUtilisateur
from app.schemas import TicketCreate
from app.schemas_tickets import TicketEvolutionCreate
from app.utils.perimetres import arbre
from app.utils.whatsapp_message import construire_message
from tests.aides_adresse import poser_adresse_du_site
from tests.aides_base import compte

SECRET = "Code du portail : 4821B"
SUITE = "Nouveau code à partir de lundi : 7730A"
PHOTO = "/uploads/tickets/code.jpg"


@pytest.fixture()
def contexte(monkeypatch, batiments):
    #  Le canal de la résidence, allumé : la couture est le registre (#1060).
    monkeypatch.setattr(diffusion, "config_diffusion", lambda s, *a: {})
    poser_adresse_du_site(monkeypatch, "https://5hostachy.fr")
    arbre()
    with Session(engine) as s:
        cs = compte(
            s,
            prefixe="cs",
            prenom="C",
            nom="S",
            roles_json=RoleUtilisateur.conseil_syndical.value,
        )
        yield s, cs, batiments


def _recu(taches: BackgroundTasks) -> tuple[str, str | None, bool]:
    """Le texte que le groupe reçoit, l'image demandée, et si le message est amputé."""
    (envoi,) = [t for t in taches.tasks if t.func.__name__ == "envoyer_whatsapp_avec_log"]
    titre, contenu, urgente, perimetre, image, config, public, confidentiel = envoi.args
    texte = construire_message(
        titre,
        contenu,
        urgente,
        perimetre,
        config,
        public,
        confidentiel,
        lien=envoi.kwargs.get("lien"),
    )
    return texte, image, bool(confidentiel)


def _creer(s, cs, categorie, perimetre, **champs):
    taches = BackgroundTasks()
    corps = TicketCreate(
        titre="Nouveau code de l'ascenseur",
        description=SECRET,
        categorie=categorie,
        partager_whatsapp=True,
        perimetre_cible=perimetre,
        photos_urls=[PHOTO],
        **champs,
    )
    return crud.create_ticket(corps, taches, session=s, user=cs), taches


# ── À la création ───────────────────────────────────────────────────────────


@pytest.mark.parametrize("categorie", ["panne", "entretien", "espaces_verts"])
def test_une_affaire_d_un_batiment_ne_part_qu_avec_son_titre(contexte, categorie):
    """L'incident : l'écran la dit réservée au périmètre, le groupe lisait tout."""
    s, cs, batiments = contexte
    _lu, taches = _creer(s, cs, categorie, [f"bat:{batiments[0]}"])
    texte, _image, ampute = _recu(taches)
    assert "Nouveau code de l'ascenseur" in texte, "le titre part"
    assert SECRET not in texte, "la description d'une affaire réservée a fui sur le groupe"
    assert ampute, "la photo ne doit pas partir non plus (`message_sans_contenu`)"


def test_une_actualite_reservee_ne_part_qu_avec_son_titre(contexte):
    s, cs, batiments = contexte
    _lu, taches = _creer(s, cs, "actualite", [f"bat:{batiments[0]}"], reserve_perimetre=True)
    texte, _image, _ampute = _recu(taches)
    assert "Nouveau code de l'ascenseur" in texte
    assert SECRET not in texte


@pytest.mark.parametrize("categorie", ["panne", "actualite"])
def test_ce_qui_concerne_toute_la_residence_part_en_entier(contexte, categorie):
    """Le cas zéro : la réserve ne doit pas amputer ce que tout le monde lit."""
    s, cs, _batiments = contexte
    _lu, taches = _creer(s, cs, categorie, [])
    texte, image, ampute = _recu(taches)
    assert SECRET in texte
    assert not ampute and image == PHOTO


# ── Une Suite ───────────────────────────────────────────────────────────────


def _suite(s, cs, ticket_id) -> str:
    taches = BackgroundTasks()
    corps = TicketEvolutionCreate(type="commentaire", contenu=SUITE, partager_whatsapp=True)
    evolutions.add_evolution(ticket_id, corps, taches, session=s, user=cs)
    return _recu(taches)[0]


@pytest.mark.parametrize(
    ("categorie", "champs"),
    [("panne", {}), ("actualite", {"reserve_perimetre": True})],
)
def test_la_suite_d_une_affaire_reservee_ne_part_qu_avec_son_titre(contexte, categorie, champs):
    s, cs, batiments = contexte
    lu, _ = _creer(s, cs, categorie, [f"bat:{batiments[0]}"], **champs)
    texte = _suite(s, cs, lu.id)
    assert SUITE not in texte, "la Suite d'une affaire réservée a fui sur le groupe"
    assert f"/tickets/{lu.id}" in texte, "le lien de la fiche, pour qui peut la lire"


# ── L'aperçu montre ce qui partira ──────────────────────────────────────────


@pytest.mark.parametrize(
    ("categorie", "champs"),
    [("panne", {}), ("actualite", {"reserve_perimetre": True})],
)
def test_l_apercu_d_une_affaire_reservee_montre_le_message_ampute(contexte, categorie, champs):
    s, cs, batiments = contexte
    brouillon = apercu.BrouillonTicket(
        titre="Nouveau code de l'ascenseur",
        description=SECRET,
        categorie=categorie,
        partager_whatsapp=True,
        perimetre_cible=[f"bat:{batiments[0]}"],
        **champs,
    )
    rendu = apercu.apercu_diffusion(brouillon, session=s, user=cs)
    (wa,) = [c for c in rendu.canaux if c.canal == "whatsapp"]
    assert SECRET not in wa.texte, "l'aperçu montrait la description qui, elle, allait partir"
    assert wa.ampute and not wa.avec_photo


# ── Une seule porte ─────────────────────────────────────────────────────────

TICKETS = Path(__file__).resolve().parents[1] / "app" / "routers" / "tickets"
PORTE = "groupe.py"


def test_une_affaire_ne_se_diffuse_que_par_diffuser_l_affaire():
    """Trois points d'envoi, dont un seul transmettait la réserve : il n'en reste qu'un.

    Un appel direct à `diffuser` depuis le paquet des affaires est refusé hors de
    la porte — c'est par là que la réserve s'oubliait.
    """
    fautifs = []
    for chemin in sorted(TICKETS.glob("*.py")):
        if chemin.name == PORTE:
            continue
        for noeud in ast.walk(ast.parse(chemin.read_text(encoding="utf-8"))):
            if isinstance(noeud, ast.Call):
                nom = getattr(noeud.func, "id", None) or getattr(noeud.func, "attr", None)
                if nom == "diffuser":
                    fautifs.append(f"{chemin.name}:{noeud.lineno}")
    assert not fautifs, (
        "Une affaire part sur le groupe par `diffuser_l_affaire` (tickets/groupe.py), "
        f"qui seule applique la réserve : {fautifs}"
    )
    porte = (TICKETS / PORTE).read_text(encoding="utf-8")
    assert "diffuser(" in porte and "contenu_hors_du_groupe(" in porte, "témoin : la porte sert"
