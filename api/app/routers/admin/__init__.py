"""Router admin — assemblage des sous-domaines.

`admin.py` faisait **2057 lignes** et 45 routes, soit quatre fois le plafond de
500 lignes du rang 1. Découpé le 06/08/2026, au fil de l'eau : c'est le fichier
d'API le plus modifié du dépôt (10 commits en 30 jours), donc celui où la taille
coûtait réellement quelque chose.

## La règle de découpage : par domaine, pas par type

Reprise de `app/seed/` — un module par domaine, **chacun ayant sa propre raison de
changer** — et non un découpage par nature technique (« les schémas ici, les routes
là »), qui aurait obligé à ouvrir trois fichiers pour suivre un seul endpoint. Les
modèles Pydantic et les helpers privés vivent donc auprès des routes qu'ils servent.

| Module | Ce qui y change |
|---|---|
| `comptes` | validation des comptes en attente, appariement des accès |
| `utilisateurs` | rôles, modification, suppression, bannissement d'un compte existant |
| `profils` | workflow des demandes de modification de profil |
| `arrivants` | accueil d'un arrivant, baux locatifs, fiche d'arrivée |
| `annuaire` | annuaire public, composition du CS et du syndic |
| `exploitation` | sauvegardes, maintenance planifiée, opérations sûres sur la base |
| `rapports_scripts` | canal machine-à-machine des scripts cron (clé partagée, sans session) |
| `communications` | historique et modèles d'e-mail, notifications, télémétrie |
| `acces` | commandes vigik/télécommande, audit des liens utilisateur-lot |

## Ce qui n'a PAS changé, volontairement

Le préfixe `/admin` reste porté **ici**, et les sous-routers n'en ont aucun : les
45 chemins sont donc identiques au caractère près, ce qui a été vérifié par
comparaison d'inventaire avant/après. `main.py` continue d'écrire
`app.include_router(admin.router)` sans savoir que ce module est devenu un paquet.

Aucune logique n'a été touchée : les corps ont été déplacés verbatim. La seule
suppression est celle de `_get_site_manager_user_id`, un alias de cinq lignes dont
la docstring disait elle-même « la règle vit dans app.utils.destinataires » — le
garder aurait imposé un module partagé pour une simple redirection. Ses quatre
appels vont désormais droit à `site_manager_user_id`.

## Les ré-exports ci-dessous ne sont pas décoratifs

`app/utils/health_monitor.py` et trois fichiers de tests importent des constantes de
périodicité et deux helpers **depuis `app.routers.admin`**. Les ré-exporter garde ces
imports valides et borne le découpage à ce paquet, au lieu de le faire déborder sur
du code de production qui n'a rien demandé.

Cela dit, ces constantes n'ont rien à faire dans un router : ce sont des métadonnées
de tâches planifiées, que `health_monitor` consomme légitimement. Leur place est un
module dédié — non fait ici pour ne pas mélanger un déplacement mécanique et un
changement de conception, et noté comme suite à donner.
"""

from fastapi import APIRouter

from . import (
    acces,
    annuaire,
    arrivants,
    communications,
    comptes,
    exploitation,
    export_copropriete,
    inscription,
    installation,
    profils,
    rapports_scripts,
    utilisateurs,
)

#  Le préfixe et le tag vivent ICI : les sous-routers déclarent des chemins nus,
#  donc identiques à ceux d'avant le découpage.
router = APIRouter(prefix="/admin", tags=["admin"])

for _sous_router in (
    comptes.router,
    utilisateurs.router,
    profils.router,
    arrivants.router,
    annuaire.router,
    exploitation.router,
    installation.router,
    inscription.router,
    export_copropriete.router,
    rapports_scripts.router,
    communications.router,
    acces.router,
):
    router.include_router(_sous_router)

#  Surface publique conservée pour les importateurs externes (cf. docstring).
#
#  ⚠️ Les seuils et les fonctions de décision ne viennent plus du routeur mais de
#  `app/utils/sante_taches.py` (#542). La surface publique, elle, ne bouge pas :
#  `health_monitor` et deux tests importent toujours `from app.routers.admin`.
#  Une extraction qui casse ses importateurs n'est pas une extraction, c'est un
#  déménagement à leurs frais.
from app.utils.sante_taches import (  # noqa: E402
    _PERIODICITE_ATTENDUE_H,
    _PERIODICITE_SAUVEGARDE_H,
    _PERIODICITE_TELEMETRIE_H,
    _TOLERANCE_H,
    _etat_tache_a_table_propre,
)
from .exploitation import (  # noqa: E402  (après le montage du router, pour la lisibilité)
    _RAPPORTS_CONSERVES,
    _purger_anciens_rapports,
)

#  Le canal des scripts vit dans son propre module depuis le 11/08/2026 ;
#  la surface publique, elle, ne bouge pas.
from .rapports_scripts import maintenance_rapport  # noqa: E402

__all__ = [
    "router",
    "_PERIODICITE_ATTENDUE_H",
    "_PERIODICITE_SAUVEGARDE_H",
    "_PERIODICITE_TELEMETRIE_H",
    "_RAPPORTS_CONSERVES",
    "_TOLERANCE_H",
    "_etat_tache_a_table_propre",
    "_purger_anciens_rapports",
    "maintenance_rapport",
]
