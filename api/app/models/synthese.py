"""La **synthèse d'une affaire close** et l'historique de ses productions (#1643).

## Ce que la table porte

Quand une affaire qui contribue au carnet d'entretien passe en `résolu` ou
`annulé`, une demande entre en file (`statut = a_produire`) ; la tâche
permanente la produit trente minutes plus tard, dépose le texte dans une Suite
de l'affaire et le soumet au conseil, qui le valide. Les règles vivent dans
`utils/synthese_affaire/` ; ce module ne porte que la forme.

| `statut` | ce qu'il dit |
|---|---|
| `a_produire` | la demande attend sa production — le délai de grâce court |
| `brouillon` | produite ; le conseil et l'administration la lisent seuls |
| `validee` | lue par qui lit l'affaire (`ticket_visible`), et au carnet |
| `annulee` | remplacée par une production plus récente, ou demande périmée ; gardée, plus affichée |

## 🔴 Les métriques sont FIGÉES

`metriques_json` est écrit au moment de la production, jamais recalculé à la
lecture : une Suite ajoutée après la validation, ou la moyenne de l'exercice
qui bouge, ne doit pas faire mentir un texte que le conseil a relu et validé
sur d'autres chiffres.

## `cloture_le` — la clôture que la synthèse couvre

La date de clôture de l'affaire AU MOMENT de la demande. C'est elle qui
distingue « déjà produite pour cette clôture » d'« affaire rouverte puis close
à nouveau », qui appelle une nouvelle production (arbitré : elle remplace la
précédente, même validée). Ce champ n'est pas dans la liste du ticket ; il est
ce qui rend la règle de remplacement écrivable sans deviner.

Colonnes simples pour `evolution_id`, `ticket_id` restant une vraie clé
étrangère : les deux tables sont nées avec elle.
"""

from __future__ import annotations

from typing import Optional

from pydantic import NaiveDatetime
from sqlmodel import Field, SQLModel

from app.utils import horloge

#: Les quatre états d'une synthèse — et il n'y en a pas d'autre.
A_PRODUIRE = "a_produire"
BROUILLON = "brouillon"
VALIDEE = "validee"
ANNULEE = "annulee"
STATUTS_SYNTHESE = (A_PRODUIRE, BROUILLON, VALIDEE, ANNULEE)
#: Une synthèse « vivante » : ni remplacée, ni périmée.
STATUTS_VIVANTS = (A_PRODUIRE, BROUILLON, VALIDEE)


class SyntheseAffaire(SQLModel, table=True):
    __tablename__ = "synthese_affaire"

    id: Optional[int] = Field(default=None, primary_key=True)
    ticket_id: int = Field(foreign_key="ticket.id", index=True)
    #: La Suite porteuse (`TicketEvolution.type == "synthese"`), créée à la production.
    evolution_id: Optional[int] = Field(default=None, index=True)
    statut: str = Field(default=A_PRODUIRE, index=True)
    cloture_le: Optional[NaiveDatetime] = None
    metriques_json: Optional[str] = None
    synthese: Optional[str] = None
    difficultes: Optional[str] = None
    amelioration: Optional[str] = None
    #: La consigne ajoutée par « Relancer » ; « Recommencer » l'efface.
    prompt_complement: Optional[str] = None
    #: Rédigée avec l'assistant — faux si elle a été créée vide (IA coupée…).
    assiste_ia: bool = False
    #: Pourquoi la Suite est vide : « l'assistant est désactivé », « plafond
    #: atteint »… Un motif de configuration, jamais une donnée de l'affaire.
    motif_vide: Optional[str] = None
    produite_le: Optional[NaiveDatetime] = None
    validee_le: Optional[NaiveDatetime] = None
    validee_par_id: Optional[int] = Field(default=None, foreign_key="utilisateur.id")
    #: Le courriel « Synthèse à valider » est parti — UN envoi par production.
    mail_envoye_le: Optional[NaiveDatetime] = None
    cree_le: NaiveDatetime = Field(default_factory=horloge.maintenant)
    mis_a_jour_le: NaiveDatetime = Field(default_factory=horloge.maintenant)


class TentativeSynthese(SQLModel, table=True):
    """Une production — automatique, « Produire », « Relancer » ou « Recommencer ».

    L'historique reste quand « Recommencer » efface le complément : c'est ce qui
    permet de relire ce qu'une consigne avait donné. Le coût est celui que
    `llm_journal` chiffre, au tarif saisi pour l'usage ; les compteurs du mois,
    eux, restent dans `appel_ia`.
    """

    __tablename__ = "tentative_synthese"

    id: Optional[int] = Field(default=None, primary_key=True)
    synthese_id: int = Field(foreign_key="synthese_affaire.id", index=True)
    #: Qui l'a demandée — `None` pour la production automatique.
    auteur_id: Optional[int] = Field(default=None, foreign_key="utilisateur.id")
    #: `succes` · `erreur` · `indisponible` (assistant coupé, plafond atteint).
    statut: str = "succes"
    prompt_complement: Optional[str] = None
    synthese: Optional[str] = None
    difficultes: Optional[str] = None
    amelioration: Optional[str] = None
    jetons_entree: Optional[int] = None
    jetons_sortie: Optional[int] = None
    #: En dollars, texte décimal à quatre décimales — `None` sans tarif saisi.
    cout_usd: Optional[str] = None
    cree_le: NaiveDatetime = Field(default_factory=horloge.maintenant)
