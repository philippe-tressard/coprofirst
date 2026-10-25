"""Router accès — badges Vigik, télécommandes, et les imports qui les alimentent.

`acces.py` faisait **981 lignes**. Découpé le 06/09/2026, au fil de l'eau :
enrichir la lecture des badges pour qu'elle dise enfin **qui les porte** (#805)
l'avait fait passer de 962 à 981, et c'est le garde-fou de modularité qui a
refusé le lot.

C'est le deuxième découpage de la journée, après `bailleur/` — et la règle a
fonctionné deux fois de la même façon : on ne découpe pas parce qu'un fichier est
gros, on découpe **quand on y touche**.

## La règle de découpage : un domaine, un module

| Module | Ce qui y change | Lignes |
|---|---|---|
| `resident` | ce qu'un porteur fait de ses badges, plus les deux lectures du CS | 407 |
| `imports_telecommandes` | l'import Excel des télécommandes et son appariement | 384 |
| `imports_vigik` | idem pour les badges Vigik | 276 |
| `commun` | la normalisation des noms, employée par les DEUX imports | 50 |

## 🔴 Ce qu'on a cru ne PAS pouvoir fusionner — et qui a fini par diverger

Cette note affirmait, du 06/09 au 08/09/2026, que fondre les deux modules
d'import « demanderait un paramétrage qui coûterait plus cher que les deux
fichiers », au nom de `standards/02` §4 : *deux morceaux qui se ressemblent par
hasard*.

**C'était faux, et un défaut en production l'a établi** (#847). Deux morceaux qui
se ressemblent par hasard ne divergent pas sur la même ligne : ils n'ont pas la
même ligne. Ceux-ci en avaient une — le report de `chez_locataire` sur l'objet
créé — et seul le côté télécommande la portait. Un badge Vigik remis à un
locataire arrivait donc marqué « chez le propriétaire », et se reproposait au
transfert vers le locataire suivant.

Le cycle des deux imports vit désormais dans `socle_imports`, avec l'objet
`utils/types_acces.TypeAcces`, qui porte les différences réelles. Ce qui reste
séparé est ce qui diffère vraiment :

| Ce qui reste séparé | Pourquoi |
|---|---|
| `utils/import_telecommandes.py`, `utils/import_vigiks.py` | ni les mêmes colonnes ni les mêmes règles de lecture de l'Excel |
| `_etape_lot_par_adresse` (vigik) | le fichier Vigik porte bâtiment + appartement ; celui des télécommandes ne les a pas |
| `refuser-locataire` (télécommande) | asymétrie **déclarée** dans `test_symetrie_imports_acces.py` |

⚠️ La leçon n'est pas « fusionner davantage ». Elle est que **le seul fichier
qui parlait du sujet disait que le problème n'existait pas** — le même motif que
les quatre copies des destinataires CS (`CLAUDE.md`), dont l'une affirmait être
« le seul endroit où cette règle s'écrit ».

## Ordre de montage

`resident` en premier : ses chemins sont les plus courts (`/mes-vigiks`,
`/declarer-badge`) et les plus spécifiques (`/admin/vigiks` avant les
`/admin/imports-vigik/{id}` des autres modules). Les 31 chemins sont identiques
au caractère près à ceux d'avant le découpage — trois routes d'écriture en moins,
supprimées sur arbitrage le même jour (#805).

### 🔴 Pourquoi le LISTAGE reste écrit deux fois (16/09/2026)

`GET /admin/vigiks` et `GET /admin/telecommandes` sont les deux seules routes
du parc qui ne passent pas par `{type_cle}` — un relevé mécanique les signale
comme identiques, et elles le sont au type près.

Les fondre en `GET /admin/{type_cle}` serait une régression : `imports_vigik`
et `imports_telecommandes` exposent `GET /admin/imports-vigik` et
`GET /admin/imports`, **deux chemins à un seul segment** sous `/admin/`.
Un `{type_cle}` les avalerait et rendrait **422 « Type invalide »** à la place
des listes d'import — deux écrans d'administration cassés, sans la moindre
erreur côté serveur.

⚠️ C'est précisément ce qui est arrivé aux **PATCH** le 22/09/2026, dans
l'autre sens : `parc` était monté en premier, et son joker à deux segments
avalait `PATCH /admin/imports/{id}`. L'ordre est désormais inverse, et un test
le tient — voir le commentaire de l'inclusion, plus bas.

⚠️ Ce qui reste dupliqué est le **décorateur**, c'est-à-dire précisément ce
qui distingue les deux routes ; leur corps passe déjà par `_acces_admin_out`.
Une divergence légitime qui ne se déclare pas est indistinguable d'un oubli
(`standards/02` §4).
"""

from fastapi import APIRouter

from . import imports_telecommandes, imports_vigik, parc, portes, resident

router = APIRouter(prefix="/acces", tags=["acces"])

router.include_router(resident.router)
#  🔴 LES IMPORTS AVANT `parc` — l'inverse de ce qui était écrit ici jusqu'au
#  22/09/2026, et l'inverse tuait deux gestes en production.
#
#  L'ancienne note disait : *« `parc` AVANT les imports : ses chemins
#  `/admin/vigiks` et `/admin/{type}` sont plus spécifiques »*. C'était vrai des
#  chemins à UN segment (`/admin/imports`, `/admin/imports-vigik`), qu'un
#  `/admin/{type_cle}` avale bel et bien. C'était **faux** de ceux à deux :
#
#      PATCH /admin/{type_cle}/{objet_id}   (parc)
#      PATCH /admin/imports/{import_id}     (imports_telecommandes)
#
#  Même forme, même méthode. Monté en premier, `parc` prenait la requête avec
#  `type_cle="imports"` et rendait **422 « Type invalide : vigik ou
#  telecommande »** — l'erreur que l'utilisateur a vue à l'écran en liant un
#  locataire. Les deux écrans d'import étaient morts à l'enregistrement.
#
#  ⚠️ Une note qui explique un piège au singulier laisse croire qu'il n'y en a
#  qu'un : sa conclusion a survécu à une prémisse qui ne couvrait que la moitié
#  des routes.
#
#  Dans l'autre sens, rien ne casse : `/admin/vigiks` et `/admin/telecommandes`
#  sont littéraux et à un seul segment — aucun chemin d'import ne leur
#  ressemble. C'est ce que `test_routes_masquees.py` vérifie, dans les deux sens
#  et à chaque PR.
router.include_router(imports_vigik.router)
router.include_router(imports_telecommandes.router)
#  Les lectures de ce qu'un badge ouvre (#2217) : chemins fixes à un segment,
#  montés AVANT le joker `/admin/{type_cle}` du parc.
router.include_router(portes.router)
router.include_router(parc.router)
