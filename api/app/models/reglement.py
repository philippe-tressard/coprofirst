"""Le **texte du règlement de copropriété** et les **questions** qu'on lui pose (03/10/2026).

## Ce que les deux tables portent

| Table | Ce qu'elle garde |
|---|---|
| `texte_reglement` | une VERSION du texte de travail (Markdown) chargée par le conseil — la plus récente est celle qu'on interroge |
| `question_reglement` | une question posée à l'assistant, sa réponse, ses extraits, et la version du texte lue |

Les règles vivent dans `utils/question_reglement/` ; ce module ne porte que la forme.

## 🔴 Le texte vit en BASE, jamais dans le dépôt

Un règlement de copropriété nomme des personnes réelles (notaires, vendeurs,
propriétaires d'origine) et le dépôt est public. Le texte entre par l'écran du
conseil syndical, et nulle part ailleurs.

## Une version ne s'écrase pas

Charger un texte corrigé crée une ligne : chaque question garde `texte_id`, la
version qu'elle a lue. Une réponse ancienne se relit donc contre le texte qui
l'a fondée, pas contre celui d'aujourd'hui.

## Ni `actif`, et la suppression est à l'administration seule

Rien ne quitte les listes d'elle-même : l'historique des questions est ce qui
évite de repayer une question déjà posée. Seul l'administrateur efface une
question (`DELETE /reglement/questions/{id}`) — une réponse fausse, une question
qui n'aurait pas dû être posée —, et l'entrée de FAQ qu'elle a pu produire reste.
"""

from __future__ import annotations

from typing import Optional

from pydantic import NaiveDatetime
from sqlmodel import Field, SQLModel

from app.utils import horloge


class TexteReglement(SQLModel, table=True):
    __tablename__ = "texte_reglement"

    id: Optional[int] = Field(default=None, primary_key=True)
    #: Le titre lu dans l'en-tête du fichier (`title:`), sinon son nom.
    titre: str
    nom_fichier: str
    #: Le Markdown tel que chargé, BOM retiré et fins de ligne normalisées.
    contenu: str
    #: SHA-256 du contenu — recharger le même fichier ne crée pas de version.
    empreinte: str = Field(index=True)
    charge_par_id: Optional[int] = Field(default=None, foreign_key="utilisateur.id")
    cree_le: NaiveDatetime = Field(default_factory=horloge.maintenant, index=True)


class QuestionReglement(SQLModel, table=True):
    __tablename__ = "question_reglement"

    id: Optional[int] = Field(default=None, primary_key=True)
    question: str
    #: `oui` · `non` · `sous_conditions` · `non_prevu` · `incertain`
    #: (`utils/question_reglement/format.VERDICTS`).
    verdict: str
    #: HTML simple — rendu par un assainisseur de `#lib/sanitize`.
    reponse: str
    #: Les réserves du juriste : ce que la loi impose par-dessus le règlement,
    #: une majorité d'assemblée, un passage illisible. HTML simple, ou vide.
    reserves: Optional[str] = None
    #: Les extraits justificatifs, en JSON : citation, repère, vérifiée ou non
    #: (`format.Extrait`) — la vérification est faite par le CODE, à la réponse.
    extraits_json: str = "[]"
    texte_id: int = Field(foreign_key="texte_reglement.id", index=True)
    auteur_id: Optional[int] = Field(default=None, foreign_key="utilisateur.id")
    #: Le modèle qui a répondu — une réponse vieillit avec lui.
    modele: Optional[str] = None
    #: La provenance du texte au moment de la question (« la numérisation du
    #: RCP… ») — `utils/question_reglement/provenance`.
    provenance: Optional[str] = None
    jetons_entree: Optional[int] = None
    jetons_sortie: Optional[int] = None
    #: En dollars, texte décimal — `None` sans tarif saisi (`llm_journal.cout_appel`).
    cout_usd: Optional[str] = None
    #: L'entrée de FAQ née de cette réponse, une fois relue et publiée.
    faq_item_id: Optional[int] = Field(default=None, foreign_key="faq_item.id")
    cree_le: NaiveDatetime = Field(default_factory=horloge.maintenant, index=True)
