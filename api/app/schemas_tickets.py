"""Les schémas d'un TICKET et de son fil de suivi.

Extraits de `schemas.py` le 19/08/2026, au fil de l'eau : le fichier venait de
franchir les 500 lignes et le garde-fou de modularité (rang 1) a refusé qu'il
grossisse pour recevoir `perimetre_cible` sur une évolution (#497). La règle est
« on découpe le fichier QUAND on y touche » — et c'est bien aux évolutions de
ticket qu'on touchait.

Même geste que `models/tickets.py` (17/08) et `models/evenement.py` : les noms
restent **ré-exportés par `schemas.py`**, donc aucun des routeurs appelants n'a
une ligne à changer.

⚠️ N'importe que `schemas_communs` et `models.core` — jamais `schemas`, qui
l'importe. Un cycle ferait dépendre le démarrage de l'ordre des imports.
"""

from datetime import datetime
from typing import List, Optional

from app.models.core import StatutTicket
from app.schemas_communs import ChampsIntervenant, ChoixConciliation, EvolutionLue, ListeJson
from app.utils.assiste_ia import AssisteIACorrection, AssisteIAEntree


class ChampsSuiteAffaire(ChampsIntervenant):
    """Ce qu'une Suite pose sur l'AFFAIRE — à l'ajout comme à la correction.

    Partagés par `TicketEvolutionCreate` et `TicketEvolutionUpdate` depuis le
    01/10/2026 : l'édition d'une Suite rouvre toutes ses sections, et deux
    listes de champs auraient divergé au premier ajout. Les règles vivent dans
    `routers/tickets/suite_sections.py`.
    """

    #  Une Suite AJOUTE des affaires liées, elle n'en retire aucune (#1342).
    affaires_liees: Optional[list[int]] = None
    #  Ce que le CONSEIL pose dans une Suite (#1207, 24/09/2026) : « Quand », et
    #  par `ChampsIntervenant` l'intervenant et l'équipement. Ignorés pour tout
    #  autre auteur ; mêmes règles que la correction.
    debut: Optional[datetime] = None
    fin: Optional[datetime] = None
    #  🔴 LES OPTIONS DE PUBLICATION SE CORRIGENT DEPUIS UNE SUITE (05/09/2026) :
    #  le formulaire montre le DERNIER état, et ce qu'on enregistre DEVIENT
    #  l'état. `None` veut dire « cette entrée ne dit rien de cette option » —
    #  le ticket garde la sienne, exactement comme `perimetre_cible`.
    epingle: Optional[bool] = None
    confidentiel: Optional[bool] = None
    #  🚨 « Marquer urgente » ne crée PAS de colonne : elle pilote `priorite`,
    #  que la catégorie « Urgence » met déjà à `haute`. Arbitré le 05/09/2026 —
    #  deux notions d'urgence sur le même écran finiraient par se contredire.
    urgente: Optional[bool] = None
    #  À qui l'on parle (`[]` = défaut) et l'Accès « visible du seul périmètre »
    #  — une actualité (#1091) comme une affaire suivie (#1343). Du conseil seul.
    public_cible: Optional[List[str]] = None
    reserve_perimetre: Optional[bool] = None


class TicketEvolutionCreate(AssisteIAEntree, ChampsSuiteAffaire):
    type: str  # commentaire | etat
    contenu: Optional[str] = None
    #  Même type que `TicketUpdate.statut`, donc **même verdict** : les deux
    #  chemins de changement d'état d'un ticket valident désormais la même
    #  chose, au même endroit. `_STATUTS_ADMIS` — la liste écrite à la main qui
    #  refusait `annulé` depuis toujours — a disparu du routeur (#415).
    nouveau_statut: Optional[StatutTicket] = None
    #  🔀 Les affaires liées à ABSORBER, quand cette Suite clôt l'affaire (#1704) :
    #  conseil seul, règles dans `utils/fusion_affaires`. Ignoré hors clôture.
    fusionner: Optional[List[int]] = None
    #  Les fusions refusées pour fuite de lecture que le conseil a conciliées.
    conciliations: Optional[List[ChoixConciliation]] = None
    partager_whatsapp: Optional[bool] = None
    envoyer_syndic: Optional[bool] = None
    envoyer_cs: Optional[bool] = None
    #  « M'envoyer une copie » — la 4e case de la Diffusion (31/08/2026).
    #  Jamais persistée : c'est une décision propre à CET envoi, pas un réglage
    #  de l'objet. La recharger cochée reviendrait à l'imposer.
    envoyer_auteur: Optional[bool] = None
    #  🔕 Faux : n'avertir PERSONNE, pas même l'auteur (#1092, 23/09/2026). C'est
    #  le glissement d'une carte au kanban d'Affaires — arbitré « une Suite sans
    #  texte, sans aucun courriel », comme le kanban des événements le faisait.
    #  Vrai par défaut : une Suite écrite prévient l'auteur selon son profil.
    notifier: bool = True
    fichiers_urls: List[str] = []
    email_externe: Optional[str] = None  # adresse libre, CS/Admin uniquement
    #  Le périmètre que cette entrée déclare — facultatif. `None` veut dire « cette
    #  évolution ne dit rien du périmètre », et le ticket garde le sien. Quand il
    #  est fourni, il devient le périmètre COURANT du ticket (#497).
    perimetre_cible: Optional[List[str]] = None


class TicketEvolutionUpdate(AssisteIACorrection, ChampsSuiteAffaire):
    contenu: Optional[str] = None
    #  🔄 LE SUIVI SE CORRIGE (01/10/2026, arbitré à l'écran) : absent, la Suite
    #  garde le sien ; envoyé, il est corrigé SUR la Suite — même date, même
    #  auteur —, et l'affaire ne le suit que si c'est sa dernière transition
    #  (`app/utils/suivi_fil.py`). `etat` vers l'état d'avant = un commentaire.
    type: Optional[str] = None
    nouveau_statut: Optional[StatutTicket] = None
    fichiers_urls: Optional[List[str]] = None
    #  🔴 LE PÉRIMÈTRE SE CORRIGE (01/09/2026). Ce champ était refusé ici, au
    #  motif qu'« un périmètre déclaré est un fait daté ». Le raisonnement vaut
    #  pour un RESSERREMENT — « finalement, c'est le hall du bâtiment 3 » — et
    #  pas pour une FAUTE DE CLIC, qui s'écrit exactement pareil et qui coûte
    #  cher : le périmètre d'une entrée écrase celui du ticket, donc une erreur
    #  d'affectation reclasse tout le ticket.
    #
    #  ⚠️ La propagation à l'objet obéit à une règle : voir
    #  `app/utils/perimetre_fil.py`. Corriger une entrée ancienne ne doit pas
    #  défaire une précision récente.
    perimetre_cible: Optional[List[str]] = None


class TicketEvolutionRead(EvolutionLue):
    #  Les neuf champs communs viennent d'`EvolutionLue` — seule la clé du
    #  porteur distingue les trois historiques.
    ticket_id: int
    #  `None` quand l'entrée ne parle pas du périmètre — à distinguer d'une liste
    #  vide, qui voudrait dire « plus aucun périmètre ».
    perimetre_cible: Optional[ListeJson] = None
    #  L'état en vigueur JUSTE AVANT cette entrée — calculé par le serveur sur
    #  tout le fil (`suivi_fil.statuts_avant`) : c'est la pastille qui, choisie
    #  en correction, ramène la Suite à un commentaire. L'écran n'en a pas de copie.
    statut_avant: Optional[str] = None

    class Config:
        from_attributes = True
