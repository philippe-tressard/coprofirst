"""Un sondage ciblé ne part pas en entier sur le groupe de la résidence (22/10/2026).

## Le défaut

Relevé par l'audit qui a suivi la fuite des affaires du même jour : un sondage
« Bât. 4 › propriétaires », « Partager sur le groupe » coché, envoyait sa
question ET sa description au groupe WhatsApp de TOUTE la résidence. La création
appelait `diffuser` sans rien de son ciblage, et `diffuser` avait une réserve à
défaut ouvert. Or un sondage n'est lu que de sa cible (`sondage_accessible`).

## Ce qu'on regarde

Le texte que le groupe reçoit, composé comme le canal le compose
(`construire_message`), par la vraie route de création. Aligné sur l'affaire
réservée : la question (son titre), le périmètre et le lien partent ; la
description et les options, jamais.
"""

from __future__ import annotations

import pytest
from fastapi import BackgroundTasks
from sqlmodel import Session

import app.routers.sondages.crud as crud
from app.database import engine
from app.models.core import RoleUtilisateur
from app.routers.sondages.commun import OptionCreate, SondageCreate
from app.utils.perimetres import arbre
from app.utils.whatsapp_message import construire_message
from tests.aides_adresse import poser_adresse_du_site
from tests.aides_base import compte

QUESTION = "Faut-il changer le digicode ?"
SECRET = "Le code actuel, 4821B, a circulé hors du bâtiment."


@pytest.fixture()
def contexte(monkeypatch, batiments):
    #  Le canal de la résidence, allumé — lu là où la route le lit.
    monkeypatch.setattr(crud, "config_diffusion", lambda s, *a: {})
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


def _recu(taches: BackgroundTasks) -> tuple[str, bool]:
    """Le texte que le groupe reçoit, et si le message est amputé."""
    (envoi,) = [t for t in taches.tasks if t.func.__name__ == "envoyer_whatsapp_avec_log"]
    titre, contenu, urgente, perimetre, _image, config, public, confidentiel = envoi.args
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
    return texte, bool(confidentiel)


def _creer(s, cs, **cible):
    taches = BackgroundTasks()
    corps = SondageCreate(
        question=QUESTION,
        description=SECRET,
        options=[OptionCreate(libelle="Oui"), OptionCreate(libelle="Non")],
        partager_whatsapp=True,
        **cible,
    )
    return crud.create_sondage(corps, taches, session=s, user=cs), taches


@pytest.mark.parametrize(
    "cible",
    [
        {"perimetre_cible": ["bat:{b}"], "public_cible": ["copropriétaires"]},
        {"perimetre_cible": ["bat:{b}"]},
        {"public_cible": ["copropriétaires"]},
    ],
    ids=["batiment-et-proprietaires", "batiment", "proprietaires"],
)
def test_un_sondage_cible_ne_part_qu_avec_sa_question(contexte, cible):
    """Le défaut : la description d'un sondage ciblé partait à toute la résidence."""
    s, cs, batiments = contexte
    cible = {k: [c.format(b=batiments[3]) for c in v] for k, v in cible.items()}
    lu, taches = _creer(s, cs, **cible)
    texte, ampute = _recu(taches)
    assert QUESTION in texte, "la question part, comme le titre d'une affaire réservée"
    assert SECRET not in texte, "la description d'un sondage ciblé a fui sur le groupe"
    assert ampute
    assert f"/sondages/{lu.id}" in texte, "le lien du sondage, pour qui peut le lire"


def test_un_sondage_cible_dit_son_perimetre(contexte):
    """Le groupe lit à qui le sondage s'adresse — son périmètre, par son libellé."""
    s, cs, batiments = contexte
    _lu, taches = _creer(s, cs, perimetre_cible=[f"bat:{batiments[3]}"])
    texte, _ampute = _recu(taches)
    assert "Copropriété" not in texte.splitlines()[0], "le périmètre du sondage est tu"


def test_un_sondage_de_toute_la_residence_part_en_entier(contexte):
    """Le cas zéro : sans ciblage, tous peuvent le lire — le groupe reçoit tout."""
    s, cs, _batiments = contexte
    _lu, taches = _creer(s, cs)
    texte, ampute = _recu(taches)
    assert SECRET in texte
    assert not ampute


def test_destinataires_tous_les_residents_n_amputent_rien(contexte):
    s, cs, _batiments = contexte
    _lu, taches = _creer(s, cs, public_cible=["résidents"])
    texte, ampute = _recu(taches)
    assert SECRET in texte and not ampute
