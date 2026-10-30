"""Les aides des tests du règlement de copropriété — Ma résidence › Règlement.

Sorties de `test_question_reglement.py` le 11/10/2026 : le fichier passait les
500 lignes avec les tests de la provenance, qui vivent à côté
(`test_question_reglement_provenance.py`). Un fichier de tests ne s'importe pas
depuis un autre (`test_aides_de_tests_source_unique.py`) : ce qu'ils partagent
vit ici.

`moteur` et `assistant` sont des fixtures : un fichier de tests les IMPORTE pour
que pytest les trouve (même forme qu'`aides_sondage.base`).
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from sqlmodel import Session, select

from app.models.core import CategorieDocument, ProfilAccesDocument, RoleUtilisateur
from app.utils import llm
from app.utils.question_reglement.texte import CODE_CATEGORIE
from tests.aides_http import base_http, client_http

#: Un règlement FICTIF — le dépôt est public, aucun acte réel n'y entre.
TEXTE = (
    '---\ntitle: "Règlement fictif de la résidence"\n---\n\n'
    "# LIVRE I — Règlement de copropriété (1 janvier 1990)\n\n"
    "**⟦ RCP 1990 — PDF p. 12 — folio 11 ⟧**\n\n"
    "## DESTINATION DE L'IMMEUBLE\n\n"
    "L'immeuble est destiné à l'usage d'habitation bourgeoise. L'exercice de professions "
    "libérales est toutefois toléré dans les appartements à condition de ne pas nuire à "
    "la tranquillité de l'immeuble.\n\n"
    "**⟦ RCP 1990 — PDF p. 13 — folio 12 ⟧**\n\n"
    "Aucun animal bruyant ne pourra être détenu dans les parties privatives. "
    + "Clause de remplissage sans portée particulière. "
    * 25
    + "\n\n# LIVRE II — Modificatif (2 février 1995)\n\n"
    "**⟦ MOD 1995 — PDF p. 3 ⟧**\n\n"
    "Les balcons pourront être fermés par des vérandas après autorisation de l'assemblée.\n"
)

CITATION_VRAIE = (
    "L’exercice de professions libérales est toutefois toléré dans les appartements "
    "à condition de ne pas nuire à la tranquillité de l’immeuble"
)


@pytest.fixture(name="moteur")
def moteur_fixture(disque_jetable):
    """La base, la catégorie des fichiers du règlement, et un disque jetable."""
    with base_http() as moteur:
        categorie_reglement(moteur, CODE_CATEGORIE, ["syndic"])
        yield moteur


def categorie_reglement(moteur, code: str, roles: list[str]) -> int:
    """La catégorie `code` (créée si absente), d'un profil lisible des `roles`."""
    with Session(moteur) as s:
        cat = s.exec(select(CategorieDocument).where(CategorieDocument.code == code)).first()
        if cat is None:
            profil = ProfilAccesDocument(
                code=f"p-{code}", libelle=code, roles_autorises=json.dumps(roles)
            )
            s.add(profil)
            s.commit()
            cat = CategorieDocument(code=code, libelle=code, profil_acces_id=profil.id)
            s.add(cat)
            s.commit()
        return cat.id


@pytest.fixture()
def assistant(monkeypatch):
    """Un assistant prêt ; `assistant.messages` garde ce qu'il a reçu, et
    `assistant.ouvert` ouvre l'usage aux copropriétaires (fermé par défaut).

    `assistant.consignes` garde les consignes, `assistant.usages` les usages
    appelés ; `assistant.reponses`, par usage, remplace la réponse rendue (un
    texte), et `assistant.pret` éteint l'assistant (29/10/2026)."""
    messages: list[str] = []
    etat = SimpleNamespace(
        messages=messages, ouvert=False, consignes=[], usages=[], reponses={}, pret=True
    )

    def config(session, usage=None):
        return SimpleNamespace(
            pret=etat.pret,
            prompt="PROMPT",
            modele="modele-test",
            ouvert_coproprietaires=etat.ouvert,
        )

    async def demander(session, *, usage, message, consigne=None, **_):
        messages.append(message)
        etat.consignes.append(consigne)
        etat.usages.append(usage)
        texte = etat.reponses.get(usage) or json.dumps(
            {
                "verdict": "sous_conditions",
                "reponse": "<p>Oui, sans nuire à la tranquillité.</p>",
                "extraits": [
                    {
                        "citation": CITATION_VRAIE,
                        "reference": "Livre I, p. 12",
                        "apport": "Tolérance",
                    },
                    {"citation": "Les professions libérales sont autorisées sans aucune condition"},
                ],
                "reserves": "",
            }
        )
        return SimpleNamespace(texte=texte, jetons_entree=60_000, jetons_sortie=900, jetons_cache=0)

    monkeypatch.setattr(llm, "config_llm", config)
    monkeypatch.setattr(llm, "demander", demander)
    return etat


def client_cs(moteur):
    return client_http(moteur, RoleUtilisateur.conseil_syndical)[0]


def client_admin(moteur):
    """Seule l'administration charge le texte : les tests qui en ont besoin passent par elle."""
    return client_http(moteur, RoleUtilisateur.admin)[0]


def joindre(http, moteur, contenu: str = TEXTE, nom: str = "rcp.md"):
    """Joint un fichier du règlement par la route STANDARD des documents."""
    return http.post(
        "/documents",
        data={"titre": nom, "categorie_id": str(categorie_reglement(moteur, CODE_CATEGORIE, []))},
        files={"file": (nom, contenu.encode("utf-8"), "text/markdown")},
    )
