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
    #: Les sections de l'avis (29/10/2026) — d'après le règlement, d'après les
    #: décisions d'AG, et leur synthèse. HTML simple ; vides dans un avis plus ancien,
    #: et les deux dernières sans décision d'AG jointe (`format.SECTIONS`).
    selon_reglement: Optional[str] = None
    selon_ag: Optional[str] = None
    synthese: Optional[str] = None
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


class TranscriptionPV(SQLModel, table=True):
    """La transcription d'un procès-verbal d'AG par l'assistant (29/10/2026).

    Le PV déposé dans la Fiche (catégorie `pv_ag`) est lu par l'assistant, qui en
    rend les RÉSOLUTIONS en Markdown ; la transcription attend la relecture de
    l'administration (`a_relire`) et n'entre dans ce que lisent les questions
    (`texte_decisions_ag`) qu'une fois validée — `utils/question_reglement/transcription`.

    ⚠️ `pv_id` et `document_id` sans `foreign_key` : retirer le PV ou le fichier
    validé de la bibliothèque ne doit pas buter sur cette ligne, qui dit alors
    « PV retiré » — la même raison que `Document.document_parent_id`.
    """

    __tablename__ = "transcription_pv"

    id: Optional[int] = Field(default=None, primary_key=True)
    #: Le PV transcrit — un `Document` de la catégorie `pv_ag`.
    pv_id: int = Field(index=True)
    #: `en_cours` · `a_relire` · `validee` · `echec` (`transcription.STATUTS`).
    statut: str = Field(index=True)
    #: Le Markdown rendu par l'assistant, puis tel que l'administration l'a relu.
    contenu: Optional[str] = None
    #: Pourquoi la transcription a échoué — dit à l'écran tel quel.
    erreur: Optional[str] = None
    #: Le fichier des décisions né de la validation (`texte_decisions_ag`).
    document_id: Optional[int] = None
    #: Qui l'a demandée — `None` : la tâche quotidienne.
    demande_par_id: Optional[int] = Field(default=None, foreign_key="utilisateur.id")
    valide_par_id: Optional[int] = Field(default=None, foreign_key="utilisateur.id")
    modele: Optional[str] = None
    cree_le: NaiveDatetime = Field(default_factory=horloge.maintenant, index=True)
    valide_le: Optional[NaiveDatetime] = None
