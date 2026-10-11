"""Les consignes de la fiche arrivant : lues en base, rendues échappées (#1727).

## Pourquoi

Jusqu'au 07/10/2026, `utils/fiche_arrivant.py` les écrivait en dur — jours de
collecte des encombrants par rue, nom du syndic. Une autre copropriété aurait
imprimé ces consignes sur la fiche de ses arrivants. Elles vivent désormais dans
`ConfigSite` (clé `CLE`), éditables par le conseil syndical ; le seed n'en porte
qu'un gabarit générique (`seed/consignes_arrivant.GABARIT`).

## 🔴 Du TEXTE, jamais du HTML

La fiche est une page HTML servie à **tout utilisateur connecté**
(`GET /admin/fiche-arrivant`), et l'API n'a pas d'assainisseur HTML. Un HTML
libre saisi ici y serait injecté tel quel. Les consignes sont donc du texte,
**échappé** au rendu ; deux conventions seulement :

- `**gras**` → `<strong>` (l'emphase que portait le texte d'origine) ;
- `{syndic}` → le nom du syndic, lu dans le contrat (`utils/syndic.nom_du_syndic`)
  au moment du rendu — jamais écrit dans le texte, où il périmerait au premier
  changement de syndic.

Les retours à la ligne sont gardés par la feuille de la fiche (`white-space: pre-wrap`).
"""

from __future__ import annotations

import json
import re
from html import escape

from pydantic import BaseModel, Field
from sqlmodel import Session

from app.models.core import ConfigSite
from app.seed.consignes_arrivant import GABARIT
from app.utils.config_site import ecrire_cle

#: La clé de `ConfigSite` qui porte les consignes de CETTE résidence.
CLE = "consignes_arrivant"

#: Le marqueur remplacé au rendu par le nom du syndic.
MARQUEUR_SYNDIC = "{syndic}"

_GRAS = re.compile(r"\*\*(.+?)\*\*", re.S)


class Consigne(BaseModel):
    """Une rubrique de la fiche : son titre, puis son texte."""

    titre: str = Field(min_length=1, max_length=120)
    contenu: str = Field(min_length=1, max_length=4000)


class Consignes(BaseModel):
    """Ce que lit et écrit l'écran : les rubriques, et si elles sont propres à la résidence."""

    consignes: list[Consigne] = Field(min_length=1, max_length=12)
    #: Faux tant que la résidence n'a rien saisi : ce sont alors celles du gabarit.
    personnalisees: bool = False


def lire_consignes(session: Session) -> Consignes:
    """Les consignes de la résidence, ou le gabarit si rien n'est saisi (ou illisible)."""
    ligne = session.get(ConfigSite, CLE)
    if ligne and ligne.valeur:
        try:
            return Consignes(consignes=json.loads(ligne.valeur), personnalisees=True)
        except ValueError:
            #  Une valeur illisible ne doit pas priver l'arrivant de sa fiche : le
            #  gabarit la remplace, et l'écran la montre « non personnalisée ».
            pass
    return Consignes(consignes=[Consigne(**c) for c in GABARIT])


def enregistrer_consignes(session: Session, consignes: list[Consigne]) -> Consignes:
    """Écrit les consignes de la résidence (le schéma a déjà borné leur forme)."""
    valeur = json.dumps([c.model_dump() for c in consignes], ensure_ascii=False)
    ecrire_cle(session, CLE, valeur)
    session.commit()
    return Consignes(consignes=consignes, personnalisees=True)


def texte_en_html(texte: str, nom_syndic: str) -> str:
    """Le texte d'une consigne, échappé, avec son gras et le nom du syndic."""
    html = _GRAS.sub(r"<strong>\1</strong>", escape(texte, quote=False))
    #  Le nom du syndic est une DONNÉE : échappé lui aussi.
    return html.replace(MARQUEUR_SYNDIC, escape(nom_syndic or "de la copropriété", quote=False))


def consignes_en_html(consignes: Consignes, nom_syndic: str) -> list[tuple[str, str]]:
    """Les rubriques prêtes pour la fiche : (titre échappé, contenu rendu)."""
    return [
        (escape(c.titre, quote=False), texte_en_html(c.contenu, nom_syndic))
        for c in consignes.consignes
    ]
