"""« Afficher mes coordonnées » : une seule règle, lue par la page ET par le fil (#2145).

## Le défaut (audit du 22/10/2026)

La case décochée, le fil d'actualité taisait le NOM de l'auteur
(`flux/communaute.py` : `auteur … if a.contact_visible else None`) pendant que
la page de l'annonce le servait à tout lecteur et ne retenait que l'adresse
(`annonces._enrich`). Rien ne fuyait ; le même objet disait deux choses selon
l'écran (`standards/11` §7).

## L'arbitrage

Règle majoritaire du dépôt (`traiter-issues` §1.2) : la page, sa carte et
l'historique du hall nomment l'auteur ; seul le fil le taisait. Les
« coordonnées » sont le moyen de JOINDRE l'auteur — son adresse —, pas son nom,
que toute carte porte (« ✍️ Nom », `ux-patterns` §3). La règle s'écrit donc une
fois, `visibility.adresse_de_contact`, et c'est la seule lecture de
`contact_visible` dans l'application.

## Ce qu'on regarde

1. Ce que les DEUX sorties rendent pour une annonce aux coordonnées masquées.
2. Sur l'AST, aucune lecture de `contact_visible` hors de la règle — sauf le
   corps de requête qui l'ÉCRIT, déclaré.
"""

from __future__ import annotations

import ast

import pytest
from sqlmodel import Session

from app.models.core import PetiteAnnonce, RoleUtilisateur
from app.routers.annonces import _enrich
from app.routers.flux.commun import ContexteFlux
from app.routers.flux.communaute import collecter
from app.utils import horloge
from tests.aides_base import compte
from tests.aides_sources import modules_app

#: La seule fonction qui lit le drapeau sur une annonce.
REGLE = ("utils/visibility/objets.py", "adresse_de_contact")

#: Lectures du drapeau qui ne JUGENT pas une annonce, et pourquoi.
LECTURES_DECLAREES = {
    ("routers/annonces.py", "create_annonce"): "recopie le corps de la requête dans la ligne",
}


def lectures_du_drapeau(modules: list[tuple[str, ast.AST]]) -> list[tuple[str, str]]:
    """(fichier, fonction) de chaque `x.contact_visible` lu dans ces modules."""
    trouvees = []
    for rel, arbre in modules:
        for fonction in ast.walk(arbre):
            if not isinstance(fonction, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for n in ast.walk(fonction):
                if (
                    isinstance(n, ast.Attribute)
                    and n.attr == "contact_visible"
                    and isinstance(n.ctx, ast.Load)
                ):
                    trouvees.append((rel, fonction.name))
    return sorted(set(trouvees))


def ecarts(modules: list[tuple[str, ast.AST]]) -> list[str]:
    return [
        f"{f}:{fn} lit contact_visible hors de la règle"
        for f, fn in lectures_du_drapeau(modules)
        if (f, fn) != REGLE and (f, fn) not in LECTURES_DECLAREES
    ]


def _app() -> list[tuple[str, ast.AST]]:
    return [(m.rel, m.arbre) for m in modules_app()]


def test_contact_visible_ne_se_lit_que_par_la_regle():
    assert not ecarts(_app()), ecarts(_app())


def test_la_regle_et_ses_exceptions_servent_encore():
    """Une exception qui ne sert plus — ou une règle disparue — fait échouer."""
    lues = set(lectures_du_drapeau(_app()))
    assert REGLE in lues
    assert set(LECTURES_DECLAREES) <= lues, set(LECTURES_DECLAREES) - lues


def test_le_controle_attrape_une_seconde_lecture():
    """Le cas zéro : l'état du 22/10/2026 — le fil jugeait le drapeau lui-même."""
    fil = ast.parse(
        "def _collecter_annonces(a):\n    return a.auteur if a.contact_visible else None\n"
    )
    assert ecarts([("fil.py", fil)]) == [
        "fil.py:_collecter_annonces lit contact_visible hors de la règle"
    ]


# ── Ce que les deux sorties rendent ─────────────────────────────────────────


@pytest.fixture()
def annonce_discrete(session: Session):
    s = session
    auteur = compte(
        s,
        prefixe="auteur",
        prenom="Odile",
        nom="Sorel",
        roles_json=RoleUtilisateur.propriétaire.value,
    )
    lecteur = compte(s, prefixe="lecteur", roles_json=RoleUtilisateur.propriétaire.value)
    annonce = PetiteAnnonce(
        titre="Vélo à donner",
        description="Bon état.",
        type_annonce="don",
        auteur_id=auteur.id,
        contact_visible=False,
    )
    s.add(annonce)
    s.commit()
    s.refresh(annonce)
    yield s, annonce, auteur, lecteur


def _du_fil(s: Session, lecteur, titre: str):
    maintenant = horloge.maintenant()
    ctx = ContexteFlux(
        session=s,
        user=lecteur,
        since=maintenant.replace(year=maintenant.year - 1),
        now=maintenant,
    )
    return next(c for c in collecter(ctx) if c.titre == titre)


def test_coordonnees_masquees_le_nom_reste_l_adresse_part_pas(annonce_discrete):
    s, annonce, auteur, lecteur = annonce_discrete
    page = _enrich(annonce, lecteur, s)
    fil = _du_fil(s, lecteur, "Vélo à donner")
    #  La page : le nom, pas l'adresse.
    assert (page["auteur_prenom"], page["auteur_nom"]) == ("Odile", "Sorel")
    assert page["auteur_email"] is None
    #  Le fil : le MÊME nom — il le taisait.
    assert fil.meta["auteur"], fil.meta
    assert "SOREL" in fil.meta["auteur"].upper()
    assert auteur.email not in str(fil.meta)


def test_coordonnees_affichees_l_adresse_part(annonce_discrete):
    s, annonce, auteur, lecteur = annonce_discrete
    annonce.contact_visible = True
    s.add(annonce)
    s.commit()
    assert _enrich(annonce, lecteur, s)["auteur_email"] == auteur.email
