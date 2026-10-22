"""Le fil d'actualité ne sert que ce que la rubrique servirait (22/10/2026, #2141).

## Le défaut

`GET /flux` servait TOUTES les petites annonces et idées, Destinataires
ignorés : titre, résumé, photos et auteur d'une annonce ciblée « propriétaires »
arrivaient chez un locataire. Les routes de la rubrique filtraient par
`annonce_visible` / `idee_visible` ; le fil, à côté, relisait la table sans
filtre. Seul le sondage était filtré.

## Ce qu'on regarde

1. Ce que la route du fil rend à un lecteur que la cible écarte.
2. Sur l'AST, chaque fonction de `routers/flux/` qui lit un modèle ciblé appelle
   le prédicat de visibilité de CE modèle — jamais une réécriture de la règle.
   Un modèle lu sans prédicat se déclare, avec sa raison : un modèle neuf fait
   échouer le contrôle tant que personne n'a décidé qui le lit.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest
from sqlmodel import Session

from app.database import engine
from app.models.core import Idee, PetiteAnnonce, RoleUtilisateur
from app.routers.flux.commun import ContexteFlux
from app.routers.flux.communaute import collecter
from app.utils import horloge
from tests.aides_base import compte

FLUX = Path(__file__).resolve().parents[1] / "app" / "routers" / "flux"

#: Modèle ciblé → le prédicat qui dit qui le lit (`utils/visibility`, `auth/deps`).
PREDICATS = {
    "Sondage": "sondage_accessible",
    "PetiteAnnonce": "annonce_visible",
    "Idee": "idee_visible",
    "Ticket": "ticket_visible",
    "Document": "document_visible",
    "QuestionReglement": "question_reglement_visible",
    "Evenement": "evenement_visible",
}

#: Modèles lus sans prédicat d'objet, et pourquoi.
SANS_PREDICAT = {
    "FaqItem": "la FAQ est lue de tout compte (`GET /faq`, `get_current_user`)",
    "DiagnosticRapport": "les diagnostics de l'immeuble sont lus de tout compte",
    "MembreCS": "l'annuaire du conseil est public dans la copropriété",
    "MembreSyndic": "l'annuaire du syndic est public dans la copropriété",
    "Copropriete": "la fiche de la résidence",
    "FluxMasque": "les masques du fil, une table technique",
    "ContratEntretien": "le contrat ne sort que par son rythme, lu de tous (#1445)",
    "Prestataire": "réservé au conseil par `est_moderateur` en tête du collecteur",
    "PointConseil": "réservé par `lit_les_points_conseil` en tête du collecteur",
    "TicketEvolution": "une suite se lit avec son affaire, jointe et jugée (`Ticket`)",
}

#: Fonctions qui RENDENT des lignes à un appelant qui, lui, les juge.
AIDES = {
    ("tickets.py", "_evolutions"): ("collecter", "ticket_visible"),
}


def _appels(fonction: ast.AST) -> set[str]:
    return {
        getattr(n.func, "id", None) or getattr(n.func, "attr", None)
        for n in ast.walk(fonction)
        if isinstance(n, ast.Call)
    }


def lectures(arbre: ast.AST) -> list[tuple[str, str, set[str]]]:
    """(fonction, modèle lu par `select(...)`, noms appelés dans la fonction)."""
    trouvees = []
    for fonction in ast.walk(arbre):
        if not isinstance(fonction, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        appeles = _appels(fonction)
        for n in ast.walk(fonction):
            if isinstance(n, ast.Call) and getattr(n.func, "id", None) == "select":
                for arg in n.args:
                    if isinstance(arg, ast.Name):
                        trouvees.append((fonction.name, arg.id, appeles))
    return trouvees


def _appelant_juge(arbre: ast.AST, aide: str, appelant: str, predicat: str) -> bool:
    """L'appelant déclaré d'une aide l'appelle ET appelle le prédicat."""
    return any(
        isinstance(f, ast.FunctionDef) and f.name == appelant and {aide, predicat} <= _appels(f)
        for f in ast.walk(arbre)
    )


def ecarts(dossier: Path) -> list[str]:
    fautes = []
    for chemin in sorted(dossier.glob("*.py")):
        arbre = ast.parse(chemin.read_text(encoding="utf-8"))
        for fonction, modele, appeles in lectures(arbre):
            if modele in SANS_PREDICAT:
                continue
            if modele not in PREDICATS:
                fautes.append(f"{chemin.name}:{fonction} lit {modele}, ni ciblé ni déclaré")
                continue
            predicat = PREDICATS[modele]
            if predicat in appeles:
                continue
            aide = AIDES.get((chemin.name, fonction))
            if aide and _appelant_juge(arbre, fonction, aide[0], aide[1]):
                continue
            fautes.append(f"{chemin.name}:{fonction} lit {modele} sans {predicat}")
    return fautes


def test_chaque_collecteur_appelle_le_predicat_de_son_modele():
    assert not ecarts(FLUX), ecarts(FLUX)


def test_le_controle_attrape_un_collecteur_sans_predicat(tmp_path):
    """Le cas zéro : l'état du 22/10/2026 — une annonce lue sans `annonce_visible`."""
    (tmp_path / "fuite.py").write_text(
        "def _collecter_annonces(ctx):\n"
        "    return ctx.session.exec(select(PetiteAnnonce)).all()\n"
        "def _collecter_neuf(ctx):\n"
        "    return ctx.session.exec(select(Inconnu)).all()\n",
        encoding="utf-8",
    )
    assert ecarts(tmp_path) == [
        "fuite.py:_collecter_annonces lit PetiteAnnonce sans annonce_visible",
        "fuite.py:_collecter_neuf lit Inconnu, ni ciblé ni déclaré",
    ]


# ── Ce que le fil rend ──────────────────────────────────────────────────────


@pytest.fixture()
def lecteurs():
    with Session(engine) as s:
        auteur = compte(s, prefixe="auteur", roles_json=RoleUtilisateur.propriétaire.value)
        locataire = compte(
            s,
            prefixe="locataire",
            roles_json=RoleUtilisateur.résident.value,
            statut="locataire",
        )
        cible = json.dumps(["copropriétaires_occupants", "bailleurs"])
        s.add(
            PetiteAnnonce(
                titre="Annonce aux propriétaires",
                description="Réservée.",
                type_annonce="don",
                auteur_id=auteur.id,
                public_cible=cible,
            )
        )
        s.add(
            Idee(
                titre="Idée aux propriétaires",
                description="Réservée.",
                auteur_id=auteur.id,
                public_cible=cible,
            )
        )
        s.commit()
        yield s, locataire


def test_un_locataire_ne_recoit_pas_une_annonce_ni_une_idee_ciblees(lecteurs):
    s, locataire = lecteurs
    maintenant = horloge.maintenant()
    ctx = ContexteFlux(
        session=s,
        user=locataire,
        since=maintenant.replace(year=maintenant.year - 1),
        now=maintenant,
    )
    titres = {c.titre for c in collecter(ctx)}
    assert "Annonce aux propriétaires" not in titres
    assert "Idée aux propriétaires" not in titres
