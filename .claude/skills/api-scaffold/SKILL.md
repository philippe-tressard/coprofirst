---
name: api-scaffold
description: "Scaffold a complete FastAPI endpoint for 5Hostachy: SQLModel model + Alembic migration + router CRUD + Pydantic schemas + frontend API client module. Use when: creating a new feature, adding a new entity, adding a new API resource."
argument-hint: "Describe the entity to create (e.g. 'Fournisseur with nom, siret, email')"
---

# API Scaffold — 5Hostachy

Génère un endpoint complet (backend + frontend client) en respectant toutes les conventions du projet.

## Procédure

> 🔴 **Réécrite le 23/09/2026 (#1046).** Cette skill enseignait un backend disparu :
> modèle dans `core.py`, trois schémas dans `schemas.py`, colonne `actif` sur toute
> table, `session.get` + 404, `body.dict()`, client ajouté à `api.ts`. La suivre
> violait la modularité (rang 1) — et une skill se relit exactement au moment où
> l'on crée quelque chose, c'est-à-dire là où elle fait le plus de dégâts.
>
> Règle d'écriture : elle dit **où la vérité se lit**, elle ne la recopie pas. Les
> chiffres (nombre de modules, dernier numéro de migration) se mesurent dans le
> dépôt au moment du geste.

### 1. Modèle SQLModel — `api/app/models/<domaine>.py`

Le modèle va dans le module de **son domaine** (`acces`, `communaute`,
`prestataires`, `gouvernance`, `tickets`…). Un domaine neuf reçoit son propre
module. **Jamais `core.py`** : `test_core_sans_modele_neuf.py` y refuse toute
classe de plus (#779 l'a ramené sous 500 lignes ; le contrôle de modularité ne
juge que sa longueur, pas ce qu'on y range).

```python
from typing import Optional

from pydantic import NaiveDatetime
from sqlmodel import Field, SQLModel

from app.utils import horloge


class NouvelleEntite(SQLModel, table=True):
    __tablename__ = "nouvelle_entite"
    id: Optional[int] = Field(default=None, primary_key=True)
    nom: str                                           # français, snake_case
    batiment_id: Optional[int] = Field(default=None, foreign_key="batiment.id")
    cree_le: NaiveDatetime = Field(default_factory=horloge.maintenant)
    mis_a_jour_le: Optional[NaiveDatetime] = None
```

⚠️ **Une date de modèle s'annote `NaiveDatetime`** (`from pydantic import
NaiveDatetime`), jamais `datetime` : depuis sqlmodel 0.0.45, `datetime` donne
une colonne consciente du fuseau qui REFUSE à l'écriture la date naïve de
`horloge.maintenant()` (#1412). 🔒 `test_horloge.py` refuse une telle colonne.
Un schéma pydantic (`EntiteRead`) garde `datetime` : il n'écrit rien en base.

⚠️ **L'heure s'écrit `horloge.maintenant()`** (`from app.utils import horloge`),
jamais `datetime.utcnow()` : déprécié depuis Python 3.12, et refusé par Ruff
`DTZ003` sur `api/app/` (#1047). Elle rend de l'**UTC naïf**, la forme de
toutes les dates en base — `now(timezone.utc)` rendrait une date consciente,
qui lève à la première comparaison avec une date lue en base. Et **par son
module**, jamais importée seule : des variables locales s'appellent déjà `maintenant`.
Un champ `date` (jour civil) : `Field(default_factory=horloge.aujourd_hui)`,
le jour de Paris — jamais `date.today` (#1565, règle dans `CLAUDE.md`).

Puis **l'enregistrer** dans `app/models/__init__.py` — c'est cet import qui
déclare la table à SQLModel. Oublié, elle manque à `create_all` sans un mot.

⚠️ `core.py` **ré-exporte** les modèles extraits — et ces imports enregistrent :
`alembic/env.py` n'importe que `core`. Pour un modèle NEUF, importer depuis son
module de domaine, et le déclarer dans `models/__init__.py` (#1157).
🔒 `test_modeles_enregistres.py` refuse un module que `import app.models.core`
ne charge pas.

**Règles modèle :**
- `__tablename__` = snake_case français ; champs en français snake_case
- Timestamps : suffixe `_le` → `cree_le`, `mis_a_jour_le`
- FK : `{modele}_id = Field(default=None, foreign_key="table.id")`
- Enums : `class MonEnum(str, Enum)` → slugs français lowercase
- JSON stocké en `str` → parsé par `@field_validator` dans le schéma Read
- 🔴 **Pas de colonne `actif` par réflexe.** Un objet qui doit quitter les listes
  se déclare dans `utils/archivage.REGLES` — la règle unique, testée contre les
  modèles réels. Un booléen de plus ferait une seconde façon de disparaître.
- Une relation (`Relationship`) empêche plus tard de DÉPLACER le modèle sans
  cycle d'import : `Publication` a été le dernier modèle retenu dans `core.py`
  pour cette raison, jusqu'à sa suppression (#1177, 30/09/2026). Ne l'ajouter
  que si un `select` explicite ne suffit pas.

### 2. Schémas Pydantic — là où ils servent

Trois formes par entité exposée :

```python
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class EntiteCreate(BaseModel):      # entrée : ni id, ni horodatage
    nom: str

class EntiteRead(BaseModel):        # sortie
    id: int
    nom: str
    cree_le: datetime

    class Config:                   # `from_attributes` s'écrit ainsi dans le dépôt
        from_attributes = True

class EntiteUpdate(BaseModel):      # PATCH partiel : tout Optional
    nom: Optional[str] = None
```

`model_config = ConfigDict(extra="forbid")` n'existe que là où un schéma d'entrée
doit **refuser** les champs inconnus (`routers/tickets/lot.py`) : c'est une autre
décision que `from_attributes`, pas une seconde manière de l'écrire.

**Où les mettre :**
- partagés par plusieurs routeurs → `app/schemas_<domaine>.py`, ré-exporté par
  `schemas.py` ;
- propres à UN routeur (le corps d'un geste, la réponse d'un écran) → à côté de
  lui, dans le routeur ou son `_schemas.py`.
- ⚠️ `schemas_communs.py` n'importe RIEN du projet : c'est ce qui évite le cycle
  `schemas` ⇄ `schemas_tickets`. Ne pas lui en ajouter.

### 3. Migration Alembic — `api/alembic/versions/NNNN_slug.py`

Le numéro suit le plus élevé présent dans `alembic/versions/` (le lire, ne pas le
deviner) ; le fichier porte un **slug** qui dit ce qu'il fait.

```python
"""Ce que la migration fait, et pourquoi — en français."""
import sqlalchemy as sa
from alembic import op

revision = "NNNN"
down_revision = "NNNN-1"
branch_labels = None
depends_on = None

TABLE = "nouvelle_entite"   # un IDENTIFIANT s'interpole depuis une constante


def upgrade():
    op.create_table(
        TABLE,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("nom", sa.String, nullable=False),
        sa.Column("batiment_id", sa.Integer, sa.ForeignKey("batiment.id"), nullable=True),
        sa.Column("cree_le", sa.DateTime, nullable=False),
        sa.Column("mis_a_jour_le", sa.DateTime, nullable=True),
    )


def downgrade():
    op.drop_table(TABLE)
```

**Règles migration :** `CLAUDE.md` → « Migrations Alembic » (liaison des
valeurs, identifiants depuis une constante, ajouter puis retirer) et
`standards/06-donnees-et-integrite.md` §3 pour le générique — seules copies
(claude-config#122). Ce qui n'est écrit que là :
- tester l'existence d'une colonne avant `add_column` par
  `sa.inspect(conn).get_columns(TABLE)`, jamais par une requête en f-string.
- **Jamais** modifier une migration existante : en créer une nouvelle.
- Une colonne ajoutée est **nullable ou porte un `server_default`** : l'image
  précédente doit pouvoir insérer sans la connaître. Retirer ou renommer se fait
  en deux versions (`CLAUDE.md` → « Migrations Alembic », #1757).
- Corriger un texte **livré** en base (FAQ, modèle d'e-mail) : `utils/textes_livres.remplacer_si_intact` — il ne touche que les lignes intactes. Recopié quinze fois avant le 24/09/2026 ; `test_textes_livres.py` refuse la seizième copie.

### 4. Routeur FastAPI — `api/app/routers/`

```python
"""Ce que ce routeur sert, à qui, et pourquoi il est à part."""
from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from app.auth.deps import get_current_user, require_cs_or_admin
from app.database import get_session
from app.models.<domaine> import NouvelleEntite
from app.models.core import Utilisateur
from app.schemas_<domaine> import EntiteCreate, EntiteRead, EntiteUpdate
from app.utils import horloge
from app.utils.recuperer import ou_404

#  Préfixe au pluriel, tag en minuscules à tirets (`CLAUDE.md`, « Nommage »).
router = APIRouter(prefix="/nouvelles-entites", tags=["nouvelles-entites"])


@router.get("", response_model=list[EntiteRead])
def lister(session: Session = Depends(get_session), _: Utilisateur = Depends(get_current_user)):
    return session.exec(select(NouvelleEntite).order_by(NouvelleEntite.cree_le.desc())).all()


@router.get("/{entite_id}", response_model=EntiteRead)
def lire(entite_id: int, session: Session = Depends(get_session),
         _: Utilisateur = Depends(get_current_user)):
    return ou_404(session, NouvelleEntite, entite_id, "entité")


@router.post("", response_model=EntiteRead, status_code=201)
def creer(body: EntiteCreate, session: Session = Depends(get_session),
          _: Utilisateur = Depends(require_cs_or_admin)):
    obj = NouvelleEntite(**body.model_dump())
    session.add(obj)
    session.commit()
    session.refresh(obj)
    return obj


@router.patch("/{entite_id}", response_model=EntiteRead)
def modifier(entite_id: int, body: EntiteUpdate, session: Session = Depends(get_session),
             _: Utilisateur = Depends(require_cs_or_admin)):
    obj = ou_404(session, NouvelleEntite, entite_id, "entité")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(obj, k, v)
    obj.mis_a_jour_le = horloge.maintenant()
    session.add(obj)
    session.commit()
    session.refresh(obj)
    return obj
```

- **`ou_404(session, Modele, id, "libellé")`**, jamais `session.get` + `raise
  HTTPException(404)` : le 404 nomme ce qui manque, et c'est écrit une fois.
- **`model_dump()`**, pas `.dict()` (déprécié).
- **Rendre un objet** : `return obj` ou `EntiteRead.model_validate(obj)` ; s'il
  y a des champs CALCULÉS, `lire_objet(EntiteRead, obj, champ_calcule=…)`
  (`app/utils/lecture.py`) — jamais `EntiteRead(id=obj.id, nom=obj.nom, …)`,
  où un champ oublié part à son défaut sans un mot.
  🔒 `test_lecture_colonne_par_colonne.py` (#1563).
- **Une LISTE ne lit pas une table par élément** (#1838) : ce que chaque ligne
  lit autour d'elle (auteur, bâtiment, compte, repli) se lit UNE fois pour la
  liste — `recuperer.precharger(session, Modele, ids)` pour les `session.get` /
  `ou_rien` (garder la liste rendue : la session ne retient ses lignes que
  faiblement), une requête groupée (`group_by`, `in_`) pour le reste. Modèle :
  `routers/tickets/lecture_groupee.py`, où l'objet seul passe par le même
  chemin avec une liste d'un élément. 🔒 `test_requetes_listes_affaires.py` : le
  compte de requêtes de `/tickets` et `/flux` est le même pour 5 et 40 affaires.
- **Suppression** : physique réservée à `require_admin`. Ce que le résident voit
  disparaître s'**archive** (`utils/archivage`), il ne se supprime pas.
- Une règle d'appartenance (« cet objet est-il le mien ? ») va dans
  `auth/appartenance.py`, jamais dans le routeur (#1028).

**Monter le routeur** : `app.include_router(<module>.router)` dans `main.py`, ou
dans le `__init__.py` de son paquet s'il en a un.
🔒 `api/tests/test_routeurs_montes.py` refuse un routeur que personne ne monte —
ses URL rendraient 404, et rien d'autre ne le dirait.

⚠️ **Dans un paquet, l'ORDRE d'inclusion décide.** FastAPI retient la première
route qui correspond : un `/admin/{type}/{id}` inclus avant `/admin/imports/{id}`
l'avale. C'est ce qui a tué les deux écrans d'import le 22/09/2026 (#1151).
Inclure le plus spécifique d'abord ; `test_routes_masquees.py` le tient pour
`acces`.

⚠️ Un fichier de routeur qui dépasse 500 lignes se découpe par NOTION, pas par
intervalle de lignes, avec le même préfixe : les URL publiques ne bougent pas
(`copropriete_patrimoine`, `prestataires_archivage`, `auth_profil`).

**Dépendances d'auth :** le tableau fait foi dans `CLAUDE.md` (« Dépendances
d'auth ») — avec les **prédicats** (`est_moderateur`, `peut_editer`…), qui
s'appellent et ne se redérivent jamais.

### 5. Client API frontend — `front/src/lib/api/<domaine>.ts`

Le client s'ajoute dans le **module de son domaine** du paquet
`front/src/lib/api/` (`acces`, `patrimoine`, `communaute`…) — **jamais** dans un
`api.ts` ressuscité à la racine, et jamais recopié dans un écran (38 routes
l'étaient avant le 06/09).

```typescript
export const nouvelleEntite = {
    list: () => api.get<NouvelleEntite[]>('/nouvelles-entites'),
    get: (id: number) => api.get<NouvelleEntite>(`/nouvelles-entites/${id}`),
    create: (body: Partial<NouvelleEntite>) => api.post<NouvelleEntite>('/nouvelles-entites', body),
    update: (id: number, body: Partial<NouvelleEntite>) =>
        api.patch<NouvelleEntite>(`/nouvelles-entites/${id}`, body),
};
```

Le type va dans `front/src/lib/api/types.ts`.

### 6. Dates affichées — `app/utils/dates_fr.py`, jamais un `strftime` local

Toute date **destinée à être lue** (email, PDF, réponse affichée telle quelle) passe
par les helpers partagés :

```python
date_longue(d)            # 25 juillet 2026
date_courte(d)            # 25/07/2026
datetime_longue(dt)       # 25 juillet 2026 à 09:05
datetime_longue_paris(dt) # horodatage naïf UTC de la base → heure de Paris
```

`api/tests/test_dates_fr.py` **échoue en CI** si `%B` `%b` `%A` `%a` apparaissent
dans `api/app/` : ces motifs traduisent le mois ou le jour selon `LC_TIME`, ce qui a
produit des mois en anglais sur la fiche arrivant (26/07/2026).

⚠️ Les `strftime("%Y-%m-%d")` / `("%Y-%m")` restants sont des **clés machine**
(requêtes SQL, agrégats de télémétrie, noms de sauvegarde) : **ne pas les
« factoriser »**, ce ne sont pas des formats d'affichage.

### 6 bis. Avant d'écrire un utilitaire : celui-là existe peut-être (#1561)

Les modules de `api/app/utils/` les plus importés n'étaient enseignés par aucune
consigne — « grep le pattern existant » était la seule. **Une ligne de routage
par notion** ; le nombre d'importeurs se compte par `grep`, il ne s'écrit pas ici.
Chacun porte, en tête de fichier, le pourquoi et la règle arbitrée :

| Ce qu'on veut faire | Le module |
|---|---|
| prévenir quelqu'un **dans l'application** (la cloche) | `utils/cloche` (`sonner`, `sonner_systeme`) — la porte unique, qui obéit au profil ; jamais une ligne écrite dans la table à la main |
| savoir **ce qu'est** une affaire (actualité, affaire suivie, catégorie réservée, statut de départ) | `utils/nature_affaire` — dérivé, jamais saisi ; `utils/categories_ticket.libelle_categorie` pour le libellé français d'une catégorie |
| marquer un texte « Rédigé avec l'assistant IA » | `utils/assiste_ia` (`marquer`) ; les usages de l'assistant (modèle, prompt, plafond) se déclarent dans `utils/llm_usages` |
| décrire un **badge d'accès** (Vigik, télécommande) | `utils/types_acces` ; ses porteurs se LISENT par `utils/porteurs_acces`, la ligne d'import se rattache par `utils/resolution_acces` — rien n'enregistre un porteur |
| savoir si un **service** est activé (IA, diffusion, réponses par courriel) | `utils/services` (`service_actif`, `cle_actif`) — jamais la clé lue à la main ; un service neuf s'y déclare, et l'écran Admin › Services le montre seul |
| lire la **configuration du site** | `utils/config_site` (`config_site`, `contexte_site`) — pas un `select` sur la table dans un routeur |
| savoir **à qui part « une copie à moi »** | `utils/copie_auteur` — l'auteur de l'objet, pas celui du message |
| lier des affaires entre elles | `utils/affaires_liees` — un lien ne révèle rien qu'on ne puisse lire |
| fusionner des affaires à la clôture | `utils/fusion_affaires` (le geste) ; ce que le carnet et les moyennes en lisent : `utils/affaire_absorbee` (`pas_absorbee`, `ouverture_effective`) |
| relever une **réponse par courriel** | `utils/courriel_entrant` (le jeton) ; du MIME au texte : `utils/courriel_decodage` |
| lire un **classeur Excel d'import** | `utils/import_xlsx` — écrit une fois pour les trois imports |
| comparer deux **noms de personnes** | `utils/rapprochement_noms` |
| dire qui a **lancé une tâche planifiée** | `utils/declenchement` — un vocabulaire, un geste |
| le **libellé d'un étage** | `utils/etages` (et non `dates_fr`, qui ne parle que de dates) |
| la **nature d'un lot** (logement, cave, parking…), « est-ce une annexe ? » | `utils/designation_lot` — jamais `lot.nature` lu en direct (#2212) |
| les **périmètres d'un lot** (situé dans, desservi par) | `utils/perimetres/lots` (`deriver`, `rederiver`) ; leur lecture groupée : `utils/lecture_lots` |

Côté front, les familles équivalentes (composants `Section*`, `Onglet*`,
`Formulaire*`, `$lib/table-statuts`, `$lib/types-acces`) sont routées dans
`svelte-patterns`.

### 7. Checklist finale

- [ ] Modèle dans `app/models/<domaine>.py`, importé par `models/__init__.py` — jamais `core.py`
- [ ] Pas de colonne `actif` : l'archivage se déclare dans `utils/archivage.REGLES`
- [ ] Schémas dans `schemas_<domaine>.py` s'ils sont partagés, à côté du routeur sinon
- [ ] Migration `NNNN_slug.py` au bon numéro ; colonne neuve nullable ou avec `server_default`
- [ ] Routeur monté (`main.py` ou `__init__.py` du paquet), routes fixes avant routes à paramètre
- [ ] `ou_404` et `model_dump()` — ni `session.get` + 404, ni `.dict()`
- [ ] Client dans le module de domaine de `front/src/lib/api/`, type dans `types.ts`
- [ ] Dates affichées via `dates_fr.py` (pas de `%B`/`%A` dans `api/app/`)
- [ ] `cd api && pytest tests/ -q`, puis `bash scripts/poste/rejouer-ci.sh`
