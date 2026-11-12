---
name: api-scaffold
description: "Scaffold a complete FastAPI endpoint for 5Hostachy: SQLModel model + Alembic migration + router CRUD + Pydantic schemas + frontend API client module. Use when: creating a new feature, adding a new entity, adding a new API resource, or writing any code under api/app (model, schema, router, utils, migration) or api/tests — §8 holds the backend conventions (the single entry points), §9 what the pytest suite enforces."
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

#  Préfixe au pluriel, tag en minuscules à tirets (§8, « Nommage, contrat »).
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
`Formulaire*`, `#lib/table-statuts`, `#lib/types-acces`) sont routées dans
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
- [ ] ⚠️ Dans un paquet, les routes à segment **fixe** s'incluent AVANT celles à paramètre
      (`/admin/imports/{id}` avant `/admin/{type}/{id}`) : FastAPI retient la première qui
      correspond (#1151, 🔒 `test_routes_masquees.py` pour `acces`) ; un routeur que personne
      ne monte est refusé par `test_routeurs_montes.py`
- [ ] Le client **rend le type** de ce que le serveur renvoie, déclaré à côté de lui — jamais
      `any` qu'un écran retype (`npm run lint:types-locaux`, ESLint `no-explicit-any` en
      erreur sur tout le front) ; un champ dont le nom est une donnée se lit par `champDe`
      (`#lib/utils`) ; une **adresse** (téléchargement, `src` d'image) vient aussi du client
      (`documents.downloadUrl`), aucune chaîne `/api` dans un écran (`npm run lint:client-api`)
- [ ] `cd api && ruff format .` (Ruff épinglé dans `ci.yml`, largeur 100, migrations exclues
      par `api/ruff.toml`). Une ligne coupée emporte son `# noqa` : rejouer le contrôle tel que
      la CI le passe — `bash scripts/poste/rejouer-ci.sh lint-backend` —, jamais un `ruff check`
      nu (#1603). Une comparaison SQLAlchemy (`Model.actif == True`) garde `# noqa: E712` —
      jamais `is True`, qui vide le filtre sans un mot
- [ ] `cd api && pytest tests/<fichiers du lot> -q`, puis `bash scripts/poste/rejouer-ci.sh`

---

## 8. Conventions du backend — le détail (`CLAUDE.md` en garde la liste courte)

Venu de `CLAUDE.md` (#2709). Chaque règle nomme sa porte et le test qui la tient.

### Modèles
- Un module neuf de `app/models/` s'importe dans `models/__init__.py` : c'est ce qui
  enregistre la table (oublié, elle manque à `create_all` sans un mot). `core.py`
  **ré-exporte** les modèles extraits (imports `# noqa: E402`) : `alembic/env.py`
  n'importe que `core`, et c'est par eux qu'Alembic voit la moitié des tables — pas un
  doublon à nettoyer (#1157). 🔒 `test_modeles_enregistres.py`, `test_core_sans_modele_neuf.py`
  (sa liste — l'utilisateur et ce qui lui est attaché — est close depuis #2316).
- Déplacer une classe change l'ordre des `DELETE` d'un même flush entre deux tables sans
  `Relationship` (SQLAlchemy trie par nom qualifié, #2316) : supprimer l'enfant, `flush()`,
  puis le parent.
- `__tablename__` en snake_case français ; champs français (`statut_validation`) ;
  FK `{modele}_id = Field(default=None, foreign_key="table.id")` ; enums
  `class MonEnum(str, Enum)` à slugs français en minuscules.
- Horodatage : suffixe `_le`, valeur `horloge.maintenant()` (UTC **naïf**), annoté
  `NaiveDatetime` — jamais `datetime` (sqlmodel ≥ 0.0.45 en fait une colonne consciente du
  fuseau qui refuse la date naïve, #1412), jamais `datetime.utcnow()` (Ruff `DTZ003`).
- Le **jour** du résident : `horloge.aujourd_hui()` (jour de Paris) ; celui d'un instant de la
  base : `horloge.jour_civil(x)`, son heure murale `horloge.a_paris(x)`, le fuseau
  `horloge.TZ_PARIS`. Jamais `date.today()`, `datetime.now()` sans fuseau ni
  `maintenant.date()` (faux d'un jour entre 0 h et 2 h, #1565). 🔒 `test_horloge.py`
  (`default_factory` compris), Ruff `DTZ005/011`.
- **Archiver, pas une colonne `actif`** : les objets qui quittent les listes se déclarent dans
  `utils/archivage.REGLES`. 🔒 `test_archivage_colonnes_booleennes.py` (toute colonne
  `actif`/`active`/`archivee` couverte par `REGLES` ou déclarée référentiel, #1568).
- Deux tables qui portent le même objet (Vigik/Télécommande et leurs stagings) : une classe de
  base non-table (`models/acces._ObjetAcces`). Un import xlsx déclare son `_traiter_rows` et
  nomme ses importeurs par `import_xlsx.importeurs`.

### Une copropriété (`app/contexte.py`, #1744)
`contexte.nouvelle_session()` hors requête (une route prend `get_session`),
`contexte.moteur()`, `contexte.courante()` (`url_base`, `racine_fichiers`, `secret`,
`expediteur`, `nom_expediteur`) — jamais `engine`, `SessionLocal` ni
`settings.database_url|secret_key|uploads_dir|mail_from`. Un cache ou un quota en mémoire :
`contexte.etat("nom")`, jamais une variable de module. La copropriété d'une requête se
résout à son entrée (`contexte.ResolutionCopropriete`) ; une tâche hors requête la reçoit de
`contexte.dans(copro)`. Une installation commune déclare ses copropriétés dans
`COPROPRIETES_FICHIER`, lu par `installation_commune/declaration` seul (#1894) ; hors
requête elle n'a pas de copropriété courante (`contexte.HorsCopropriete`) : une commande
`python -m app…` la nomme par `utils/commande` (`--copropriete`), le dossier des sauvegardes
se demande à `contexte.dossier_des_sauvegardes()` (#2053).
🔒 `test_commandes_nomment_leur_copropriete.py`, `test_contexte_source_unique.py`,
`test_etat_module_par_copropriete.py` (`A_INDEXER` vide), `test_etancheite_coproprietes.py`
(deux bases aux identifiants identiques, aucune réponse de l'une ne porte les données de
l'autre, #1746).

### Lots (#2212, spec `specs/architecture/lots-et-perimetres.md`)
Nature : `utils/designation_lot` (`nature_du_lot`, `est_annexe`), jamais `lot.nature` (vide
tant que l'état descriptif n'est pas importé). Périmètres (*situé dans*, *desservi par*)
dérivés par `utils/perimetres/lots`, rangés dans `lot_perimetre`. Une annexe (cave, place)
n'apporte pas son bâtiment à « mes bâtiments » : ce qui la concerne passe par
`mes_batiments.perimetres_desservis` (`perimetre_visible`, #2214).
🔒 `test_nature_lot_source_unique.py`, `test_annexes_hors_mes_batiments.py`, `test_mes_perimetres.py`.

### Lire, refuser, rendre
- `utils/recuperer.ou_404(session, Modele, id, "libellé")` — jamais `session.get` puis
  `raise HTTPException(404)` ni un alias. Les 404 écrits à la main se déclarent un par un dans
  `EXCEPTIONS` de `test_recuperer_source_unique.py` (#1571). Un objet qui doit porter son
  parent : `sous={"bail_id": …}`. Même module : `fichier_ou_404(chemin, "PDF")`,
  `premier_ou_404(session, Modele, "…non configurée")` (ligne unique d'une table de réglage),
  `connu_ou_404(TABLE, cle, "Section inconnue")` (clé d'un registre du code, jamais une liste
  blanche d'accès), `present_ou_404(valeur, "…")`.
- Lire puis refuser en 403 si le prédicat de l'entité dit non :
  `auth/appartenance.exiger_objet_autorise` (#1564).
- Valeur d'une énumération : `utils/valeurs.valeur(x)`, jamais `str(x)` ni
  `getattr(x, "value", x)` (🔒 `test_valeur_source_unique`). Écrite POUR UNE PERSONNE (titre de
  notification, `context=` d'un courriel) : son libellé, jamais `x.type` ni
  `valeur(x.statut)` (`libelle_statut`,
  `libelle_categorie`, `libelle_priorite`, `libelle_type_acces`, `libelle_type_lot`).
  🔒 `test_enumerations_en_clair.py`.
- Rendre un objet : `Schema.model_validate(objet)`, ou `utils/lecture.lire_objet(Schema,
  objet, **dérivés)` — jamais une recopie colonne par colonne (#1563).
  🔒 `test_lecture_colonne_par_colonne`, `test_lectures_rendent_le_modele`.

### Schémas Pydantic
Trois formes par entité exposée : `EntiteCreate` (sans id ni horodatage), `EntiteRead`
(`class Config: from_attributes = True`), `EntiteUpdate` (tout `Optional`). Ils vivent dans
le `schemas_<domaine>.py` de l'entité, que `schemas.py` ré-exporte ; un schéma propre à un
routeur vit à côté de lui. `schemas_communs.py` n'importe RIEN du projet (cycle `schemas` ⇄
`schemas_tickets`).

### Nommage, contrat, tables publiées
- Français, tables, routes et tags compris. Les noms anglais existants sont **figés
  définitivement** (`TABLES_FIGEES`, `ROUTES_FIGEES` de `test_nommage_francais.py`, décision du
  30/10/2026, #2314) ; un nom figé renommé sort de la liste. Tag OpenAPI en minuscules à
  tirets (`carnet-entretien`), préfixe de routeur au pluriel (#1056).
- **Le contrat de l'API ne recule pas sans annonce** (#2456) : l'app iOS génère son client
  depuis `openapi.json`, joint à chaque release (`scripts/ci/lib-contrat-version.sh`), jamais
  servi par le site. `api/app/contrat/reference.json` est GÉNÉRÉE par `python
  scripts/ci/exporter_openapi.py --ecrire-reference` (elle calcule `version_contrat`, servie
  par `GET /config`). Retirer une route ou un champ : `deprecated` + une entrée dans
  `app/contrat/retraits.RETRAITS` (version V), puis le retrait dans une version ultérieure.
  L'`operationId` vient du chemin (`contrat.identifiant_operation`). 🔒 `test_contrat_api.py`.
- **Tables du site que l'app iOS lit** (#2634) : `front/tables-clients.json`, GÉNÉRÉE par
  `node front/scripts/tables-clients.mjs --ecrire` depuis `tables-clients.registre.mjs`
  (constantes LITTÉRALES de `#lib`, lues dans l'arbre syntaxique), jointe à la release. Une
  table que l'app lit vit dans `#lib` en constante NOMMÉE (`parAttribut(ATTRIBUTS_ROLE)`), et
  le code qui la sert la LIT (`aRole($u, ...ROLES_DU_DROIT.cs)`) ; jetons de la charte et
  palettes se publient par leur règle CSS (`<feuille>.css@<sélecteur>`). Retirer ou changer de
  forme s'annonce dans `RETRAITS`. 🔒 `npm run lint:tables-clients`.
- **Une règle d'affichage que le site ET l'app montrent se calcule dans l'API** (#2501,
  `standards/09` §8) : dans `app/utils/` (ou un prédicat d'`auth/`), servie en champ que le
  front LIT. Chacune se déclare dans `front/scripts/check-regles-partagees.regles.mjs` ; celles
  que le front calcule encore y portent leur ticket de migration OUVERT. 🔒 `npm run
  lint:regles-partagees`, point 25 du pré-check (#2633).

### Documents imprimables (PDF)
Thème commun `app/utils/pdf_theme.py` (logo, palette, data-URI, `html_to_pdf()`) — jamais une
palette, un logo ou un moteur ailleurs. HTML autonome (CSS dans `<style>`, images en
data-URI) ; le moteur n'ouvre que le data-URI — une image `http(s)` ou `file://` est refusée, jamais
récupérée par le serveur (`pdf_rendu.PROTOCOLES_ADMIS`, #1908, 🔒
`test_pdf_hors_reseau.py`). `@page { size: A4|A5 }` ; pas d'emoji dans les affiches.
Documents : `fiche_arrivant.py`, `annonce_hall.py`, `manuel_pdf.py`. Le rendu s'exécute
**hors du process de l'API** (`app/utils/pdf_rendu.py`), dans un enfant `spawn` — jamais
`fork`, qui hériterait des connexions à la base ; coût assumé +1,5 à 2 s.
🔒 `test_weasyprint_appel_unique.py` (aucun appel au moteur ailleurs — c'est aussi la porte de
la dérogation GHSA-jf6q-chmf-3h3v), `test_pdf_hors_process.py`. La mécanique de l'enfant :
`app/utils/process_isole.py`, partagée avec les images (#2396).

### Destinataires (`app/utils/destinataires.py`, source unique)

| Ce qu'on vise | Fonction | Employée par |
|---|---|---|
| le CS **concerné par un périmètre** | `membres_cs_notifiables(session, batiment_ids)` (+ `batiments_du_perimetre()`) | nouvel arrivant, annonces de hall |
| le CS **par le rôle**, sans périmètre | `membres_cs_avec_email(session)` | publications, sondages, calendrier, tickets |
| le **syndic principal** | `syndic_principal(session)` | ci-dessous, fiche copropriété, arrivants |
| le **gestionnaire du site** — un administrateur, ou personne (#1505) | `site_manager_user_id(session)` | ce qui renvoie à `/admin` : comptes, alertes, bogues |
| « cette personne gère-t-elle le site ? » — le désigné, sinon tout administrateur | `est_gestionnaire_du_site(session, user)` | répondre aux avis, les retenir et les exporter (#2075) |
| **syndic puis CS, dédoublonnés** | `destinataires_syndic_cs(session, syndic=…, cs=…)` | les quatre entités qui cochent « envoyer au syndic / au CS » |
| **gestionnaire du site puis CS, dédoublonnés** | `gestionnaire_puis_cs(session)` | la synthèse d'une affaire close à valider (#1643) |

🔒 `test_destinataires_source_unique.py`. Il laisse passer les notifications in-app, qui
visent « CS ou admin » et rendent des `Utilisateur` — autre destinataire.

### Diffuser, couper un service
- Prévenir le groupe de la résidence : `utils/diffusion` — `config_diffusion(session)` (`None`
  si le canal est éteint) puis `diffuser(background_tasks, config, titre, contenu, …)`. Le
  registre `CANAUX` n'a qu'un canal (WhatsApp, dont le bridge est l'adaptateur) ; les clés
  `whatsapp_*` et `whatsapp_log` gardent leur nom jusqu'au second (#1060).
  🔒 `test_diffusion_canal.py`.
- « Ce service est-il activé ? » : `utils/services` — `service_actif(cfg, SERVICE_…)`,
  `cle_actif(SERVICE_…)` —, jamais une lecture de `llm_actif`, `whatsapp_enabled` ou
  `imap_enabled` (#1718). Le registre `SERVICES` est la seule liste ; l'onglet Admin ›
  Services s'en déduit (`GET /config/services`). Les courriels de sécurité ne sont pas un
  service (`COURRIELS_DE_SECURITE`). Un modèle d'e-mail `desactivable=False`
  (`seed.emails.NON_DESACTIVABLES`) part même décoché, et le `PATCH` refuse de le décocher
  (#2054). 🔒 `test_services_registre.py`, `test_courriels_securite_hors_service.py`,
  `test_modeles_non_desactivables.py`.

### Tâches planifiées de l'API
Elles tournent dans le process et se déclarent dans `app/utils/taches.TACHES_PERMANENTES`,
avec ce qu'on perd si elle cesse. Chacune s'enregistre par copropriété :
`scheduler.add_job(contexte.pour_chaque_copropriete(tache, "id"), …, id="id")` ; une tâche de
la plateforme se déclare dans `TACHES_DE_LA_PLATEFORME` avec sa raison (#1745). Le démarrage
journalise tout écart en `WARNING` ; 🔒 `test_taches_planifiees_declarees.py` le vérifie en
CI, dans les deux sens.

## 9. Tests de l'API — ce que la suite tient

> 📖 `standards/05-tests-et-garde-fous.md`. Lancer : `cd api && pytest tests/ -q -n 8`, ou
> toute la suite comme la CI : `bash ../scripts/ci/mesure-postgresql.sh`.

- **Gabarits de courriel** : `test_email_templates.py` verrouille les variables Jinja2
  (`EXPECTED_VARS`, dans `tests/aides_contrats_email.py`). Changer les variables d'un gabarit
  (`seed.EMAIL_TEMPLATES`) = mettre à jour `EXPECTED_VARS` ET vérifier que le
  `send_email(code=...)` les fournit — sinon échec silencieux à l'envoi.
- **Migrations** : `test_migrations.py` (head unique, base unique, révisions uniques).
- **Licences tierces** (#1542, #1543) : `scripts/ci/licences_tierces.py` juge chaque
  dépendance de `front/`, `whatsapp-bridge/` et `api/` contre une liste blanche. Une licence
  hors liste = une exception NOMMÉE avec son motif dans `scripts/ci/licences_politique.py`
  (une exception qui ne sert plus fait échouer) ; `--ecrire` régénère
  `docs/licences-tierces.md`. Un contenu repris d'un tiers se déclare dans `CONTENUS_TIERS` et
  `REUSE.toml` (`contenus_tiers.py`). Ce que pip ne voit pas (paquet Debian d'une image, roue
  qui embarque un binaire interdit — `pillow-heif` porte x265, GPLv2, #2389) :
  `BIBLIOTHEQUES_SYSTEME`, `INTERDITS_DANS_LES_IMAGES`, `ROUES_A_COMPILER`, confrontés aux
  Dockerfile par `licences_image.py` ; l'image construite : `api/scripts/verifier_heif.py`.
- **Le code de test ne se recopie pas** (#1495) : les aides et ce qu'elles remplacent dans
  `MOTIFS` de `test_aides_de_tests_source_unique.py`. Une aide partagée vit dans un
  `tests/aides_*.py`, jamais dans un fichier de tests ; seuls `test_*.py`, `aides_*.py` et
  `conftest` vivent dans `tests/` (`test_nommage_modules_de_tests.py`). Une
  `Session(moteur_de_test())` jamais fermée, un patrimoine vidé à la main sont refusés.
- **Aucun état mutable de module de plus** (#1743) : `test_etat_module_par_copropriete.py`
  (conteneur modifié depuis une fonction, `global`, `@lru_cache`) ; un état neuf va en base,
  ou dans `DU_PROCESSUS` avec sa raison ; un état de copropriété passe par `contexte.etat(nom)`,
  la seule porte (`PAR_COPROPRIETE`).
- **La suite passe sur PostgreSQL** (#1747, check requis) : un schéma neuf par test sur le
  PostgreSQL de `TESTS_BASE_URL` (`tests/aides_base`). En parallèle et dans un ordre tiré au
  sort (#2223) : `pytest -n` (`--dist loadfile`, workers `PYTEST_WORKERS` sinon
  `workers_suite`) et pytest-randomly, dont la graine se rejoue (`PYTEST_GRAINE=<n>`). Chaque
  worker pose son schéma (`tests/aides_processus`), chaque fichier le trouve neuf
  (`aides_purge.remettre_a_neuf`). Les schémas jetables portent heure et créateur ; la suite
  retire ceux d'un créateur mort ou de plus de 6 h (`dialecte.schemas_jetables_a_retirer`,
  #2399). Base injoignable : `SERVEUR_INJOIGNABLE`.
- **Verrous** (#2279) : aucune transaction de la suite ne tient plus de verrous qu'un worker
  n'en a. Pose des tables en AUTOCOMMIT (`aides_base.creer_les_tables`), retrait par lots de
  `dialecte.TABLES_PAR_LOT` (`instructions_de_retrait`) — jamais `create_all` sur un schéma
  jetable ni `DROP SCHEMA` en direct. 🔒 `test_verrous_par_transaction.py`.
- **La langue du moteur vit dans `app/dialecte.py`** (intégrité, compactage, `dialecte.jour`,
  `dialecte.mois`, base jetable). Une base neuve reçoit le schéma courant d'un coup, marqué à
  la tête (`utils/schema_initial`, appelé par `start.sh`).
- `test_routeurs_nommes_par_un_test.py` : un routeur qu'aucun test ne nomme est refusé (#1569).
- **Un module s'importe seul** (#2241) : `test_imports_sans_cycle.py` ; un cycle se coupe par
  un import dans la fonction qui s'en sert.
- **Clones Python** (#1564) : `scripts/ci/clones_python.py` (jscpd épinglé) échoue dans les
  deux sens — un clone ajouté, ou un retiré sans baisser `PLAFOND_CLONES`.
- Un contrôle front « une notion, une source » s'écrit sur `front/scripts/lib-source-unique.mjs`
  (cas zéro, témoin, exceptions déclarées) (#779).
- Un test sauté sur le poste (`@besoin_weasyprint`) est NOMMÉ par le rejeu (#1734) : seule la
  CI de la PR le joue.
