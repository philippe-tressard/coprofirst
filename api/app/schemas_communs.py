"""Le socle des schémas — ce dont tous les autres ont besoin, et qui ne dépend de rien.

Extrait de `schemas.py` le 19/08/2026 : le fichier venait de franchir les 500
lignes et le garde-fou de modularité (rang 1, `standards/02` §6) a refusé qu'il
grossisse pour recevoir le périmètre d'une évolution (#497).

⚠️ **Ce module n'importe RIEN du projet, et c'est sa raison d'être.** C'est ce
qui permet à `schemas_tickets.py` de s'en servir sans dépendre de `schemas.py`,
qui l'importe lui-même — un cycle rendrait l'ordre de chargement décisif pour le
démarrage de l'application.
"""

import json
from datetime import datetime
from typing import Annotated, List, Literal, Optional

from pydantic import BaseModel, BeforeValidator


def liste_depuis_json(v):
    """Colonne texte contenant un tableau JSON → liste d'URLs.

    Quatre schémas portaient ce même validateur recopié (`photos_urls`,
    `fichiers_urls` × 3). C'est la contrepartie côté pydantic de
    `app/utils/photos.parse_photos`, que les routeurs utilisent pour lire les
    mêmes colonnes : deux points d'entrée, une seule règle.

    Ne lève jamais : une valeur illisible en base ne doit pas faire échouer la
    lecture de l'élément qui la porte. Le pire cas est une liste vide.

    Publique (et non `_privée`) depuis le 16/08/2026 : le détail d'un sondage
    construit sa réponse à la main, sans `response_model`, et devait donc appeler
    la règle plutôt que la réécrire.
    """
    if v is None:
        return []
    if isinstance(v, str):
        try:
            charge = json.loads(v)
        except Exception:
            return []
        return [str(u) for u in charge] if isinstance(charge, list) else []
    return v


#: Champ exposé en liste, stocké en colonne texte. `Optional[ListeJson]` reste
#: possible là où l'absence et la liste vide doivent se distinguer.
#:
#: ⚠️ Ce type s'appelait `ListeJson` — un nom qui décrivait ses trois premiers
#: usages (photos, fichiers) et non ce qu'il fait. Le ciblage des sondages avait
#: exactement le même besoin pour des CODES de périmètre : soit on importait un
#: type nommé « URLs » pour des périmètres, soit on en écrivait un second,
#: identique. Renommé pour ce qu'il est — une liste sérialisée en JSON.
ListeJson = Annotated[List[str], BeforeValidator(liste_depuis_json)]


def nom_en_majuscules(v: Optional[str]) -> Optional[str]:
    """Un NOM se range en capitales, sans espaces autour — « Dupont » → « DUPONT ».

    Écrit deux fois (inscription, profil) jusqu'au 24/09/2026, et oublié par la
    correction d'un compte en administration (#1155) : un nom corrigé par
    l'administrateur restait en minuscules à côté de tous les autres.
    """
    return v.strip().upper() if v else v


#: Un nom saisi — pour le schéma qui n'a pas d'autre validateur à porter.
NomMajuscules = Annotated[Optional[str], BeforeValidator(nom_en_majuscules)]


class AffaireLieeLue(BaseModel):
    """Une affaire liée, telle qu'un lecteur la voit (#1342) : de quoi la
    reconnaître — numéro, titre, statut (le « suivi » de l'écran) et date de
    création (#2173). Rendue seulement si le lecteur peut la lire
    (`utils/affaires_liees`)."""

    id: int
    numero: str
    titre: str
    statut: str
    cree_le: datetime
    #: 🔀 Absorbée par une autre affaire (#2186) : son état est celui qu'elle a
    #: hérité, et l'écran ne la propose plus à la fusion.
    fusionnee: bool = False


class ChoixConciliation(BaseModel):
    """Ce que le conseil a décidé pour UNE affaire dont la fusion était refusée
    pour fuite de lecture (`utils/fusion_conciliation`).

    `confirmes` : les identifiants des personnes que l'écran a NOMMÉES — celles
    qui liront ce qu'elles ne lisaient pas. Le serveur recalcule la liste et
    exige la même : la confirmation est nominative, elle ne se donne pas en bloc.
    « Inverser » n'est pas ici : c'est la principale qui change (`principale_id`).
    """

    affaire_id: int
    option: Literal["restreindre", "elargir"]
    confirmes: List[int] = []


class ContratDeLAffaire(BaseModel):
    """Le contrat sous lequel intervient le prestataire d'une affaire (#1445).

    DÉRIVÉ à la lecture (`routers/tickets/commun.contrat_de_l_affaire`). Le
    rythme se lit par tous — il était déjà affiché sur l'affaire ; le libellé et
    le numéro par le conseil seul, comme la liste des contrats
    (`GET /prestataires/contrats`, réservée au conseil).
    """

    id: int
    libelle: Optional[str] = None
    numero_contrat: Optional[str] = None
    frequence_type: Optional[str] = None
    frequence_valeur: Optional[int] = None


class ChampsIntervenant(BaseModel):
    """Intervenant, récurrence et équipement d'une affaire — conseil seul.

    Les trois formes du ticket (création, lecture, correction) portaient chacune
    les trois premiers champs, recopiés ; l'équipement (#1097) aurait fait la
    quatrième ligne de chaque copie. Les règles vivent dans `utils/intervenant`.
    """

    prestataire_id: Optional[int] = None
    contrat_id: Optional[int] = None  # sous contrat ; `None` hors contrat (#1445)
    frequence_type: Optional[str] = None
    frequence_valeur: Optional[int] = None
    equipement: Optional[str] = None


class EvolutionLue(BaseModel):
    """**Une entrée de fil, telle qu'un écran la reçoit** — les neuf champs
    communs aux trois historiques (ticket, actualité, événement).

    ## 🔴 Pourquoi ici (15/09/2026)

    Les trois schémas les déclaraient à l'identique… à un détail près, et ce
    détail est un défaut :

    | schéma | `fichiers_urls` |
    |---|---|
    | `TicketEvolutionRead` | `ListeJson` |
    | `PublicationEvolutionRead` | `ListeJson` |
    | `EvolutionEvenementRead` | `list[str]` — et un `parse_photos` **à la main** |

    La colonne stocke un tableau JSON. `ListeJson` le désérialise ; `list[str]`
    ne le fait pas, et le calendrier compensait en convertissant avant de
    valider. Les deux marchent — tant que personne n'ajoute un second chemin de
    lecture sans se rappeler de la conversion. Alors Pydantic reçoit une chaîne
    là où il attend une liste, et rejette l'entrée entière.

    ⚠️ C'est le motif que le dépôt connaît : deux copies qui divergent sur le
    cas limite, et celle qui compense est la plus fragile — elle marche par
    l'attention de qui la lit, pas par construction.

    ## Ce qu'il ne porte pas

    La clé du porteur (`ticket_id`, `publication_id`, `evenement_id`) et les
    champs propres à une entité (`perimetre_cible`, sur les tickets seuls).
    C'est exactement ce qui les distingue.
    """

    id: int
    #: `commentaire` ou `etat` — jamais un troisième. Une correction est un
    #: commentaire préfixé (`utils/corrections`).
    type: str
    contenu: Optional[str] = None
    ancien_statut: Optional[str] = None
    nouveau_statut: Optional[str] = None
    auteur_id: Optional[int] = None  # #1688
    #: Composé par le serveur : l'écran ne rapproche pas un identifiant d'un nom.
    auteur_nom: Optional[str] = None
    cree_le: datetime
    fichiers_urls: ListeJson = []
    #: Le texte reçu, quand l'assistant a mis en forme une réponse par courriel
    #: (#1322) — l'écran l'offre sous « Message d'origine ».
    contenu_origine: Optional[str] = None
    #: « Rédigé avec l'assistant IA » (#985). Déclaré ici et non par le mixin
    #: `AssisteIASortie` : ce module n'importe RIEN du projet, c'est sa raison
    #: d'être (voir l'en-tête).
    assiste_ia: bool = False

    class Config:
        from_attributes = True
