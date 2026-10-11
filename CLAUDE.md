# CLAUDE.md — 5Hostachy

Règles de développement à appliquer dans toutes les sessions sur ce projet.

## Principe fondamental

Avant toute implémentation : **grep le pattern existant**. Si le pattern existe ≥ 2 fois → l'appliquer à l'identique. Si une demande contredit un pattern établi → signaler le conflit et demander confirmation.

Les références canoniques sont dans `.claude/skills/` (voir le tableau ci-dessous).

---

## Stack

- **Backend** : FastAPI + SQLModel + Alembic (`api/`) — **PostgreSQL 17 en production depuis le 10/10/2026** (DI-7, répliqué vers le standby) ; SQLite WAL pour une installation simple, les tests et le retour arrière de 7 jours (`retour-sqlite.sh`)
- **Documents imprimables** : HTML/CSS → PDF via WeasyPrint (libs système dans `api/Dockerfile`)
- **Frontend** : SvelteKit v2 + TypeScript strict + Vite + PWA (`front/`)
- **Infra** : Docker Compose + Caddy + Raspberry Pi 5
- **Langue** : français exclusif (interface + nommage des champs)

---

## Consignes chargées à la demande

Ce fichier ne porte que ce qui doit être vrai **en permanence**. Le détail vit dans
`.claude/skills/`, découvert automatiquement par Claude Code et chargé **seulement
quand la tâche le demande** — ouvrir la skill *avant* d'agir, jamais après.

| Tâche | Skill à charger |
|---|---|
| MEP, déploiement, pré-check, post-check, rollback | `.claude/skills/mep-precheck` |
| Infra, bascule, RPi, base, WhatsApp, monitoring, incident | `.claude/skills/infra-rpi` |
| Écran, composant, libellé, pattern d'interface | `.claude/skills/ux-patterns` |
| Page ou composant SvelteKit, store, appel API côté front | `.claude/skills/svelte-patterns` |
| Nouveau modèle, schéma, router, migration | `.claude/skills/api-scaffold` |
| Auth, droits, secrets, exposition publique | `.claude/skills/security-audit` |
| Documentation utilisateur — manuel **et** `README.md` | `.claude/skills/user-manual` |

Les bonnes pratiques **génériques** — valables pour un autre projet — sont dans le
socle `~/.claude/standards/`. Ce fichier-ci ne contient que leur **instanciation
5Hostachy** : chemins, seuils, commandes.

> 📖 **Routage du socle : `~/.claude/CLAUDE.md` §1** (source unique, déjà en contexte
> — quel standard charger avant quelle tâche). Mode d'emploi, règle de placement et
> entretien : `standards/INDEX.md`. Une règle générique ne se recopie **jamais** ici :
> elle s'écrit dans le socle et bénéficie alors aux quatre projets.

---

## 🚨 Règle d'or anti-corruption DB — ne dépend d'aucun chargement à la demande

**Ne JAMAIS ouvrir `app.db` depuis un process tiers tant que l'API tourne — même en
lecture seule.** `docker exec … PRAGMA` et `sqlite3` hôte sont **interdits** : le
process tiers se croit dernière connexion, `unlink` le WAL sous le pool SQLAlchemy,
et l'API écrit ensuite dans des inodes orphelins → `disk I/O error`, 503, puis
**perte des données** au prochain arrêt. À chaud, passer par les endpoints
in-process : `POST /admin/db/checkpoint`, `GET /admin/db/integrite`. VACUUM, copie ou
swap de fichier → **stopper l'API d'abord** (0 writer).

Signature de diagnostic, conduite à tenir et historique des trois incidents :
`.claude/skills/infra-rpi`.

### …et sous PostgreSQL (DI-7b, #1781) — la règle change de forme, pas de rang

La règle ci-dessus vaut tant que `.env` désigne SQLite. Sous PostgreSQL, lire la
base depuis un autre processus redevient permis : le serveur sert ses lecteurs
(`docker exec hostachy_postgres psql`, C37, la sauvegarde). Les gestes qui
détruisent sont **autres**, et ils sont interdits au même rang :

- **Jamais deux primaires.** Un ancien primaire ne se relance JAMAIS tel quel après
  une promotion : il s'isole, puis se reconstruit en réplique
  (`sudo bash scripts/exploitation/reconstruire-replique.sh --oui`, sur le standby, en root).
- **Jamais une base absente démarrée sur un nœud qui prend la main** : l'image
  l'initialiserait en primaire VIDE. Un `docker compose up -d` complet sur un standby
  sans réplique fait exactement cela — passer par `lib-promotion.sh`
  (`decider_prise_de_main`), comme la bascule, le failover et la garde au démarrage.
- **Jamais `docker compose stop` sans liste sur le standby** : il arrêterait la
  réplique. `docker compose stop $SERVICES_APPLICATIFS` (`lib-applicatifs.sh`).
- **Jamais `docker volume rm 5hostachy_pg_data`**, ni une écriture sur la réplique.

🔒 C37 (`lib-replication.sh`) et le point 22 du pré-check disent deux primaires, une
réplique absente, déconnectée ou en retard. Conduite à tenir : `.claude/skills/infra-rpi`.

**Exporter la base pendant que l'API tourne** (#1749) : par l'administration —
`POST /admin/export-copropriete` (archive complète) et `…/verifier` (réimport dans une
base jetable) —, qui lisent dans le processus de l'API, en une transaction. Jamais par
`python -m app.utils.export_copropriete` dans le conteneur : cette commande ne sert qu'à
**importer** une archive dans une base CIBLE neuve (DI-7).

> 📖 `standards/06-donnees-et-integrite.md` §1 — le principe généralisé à **tout état
> multi-fichiers qu'un processus tient ouvert**, pas seulement une base : il s'est
> reproduit à l'identique sur l'état d'authentification WhatsApp (24/07/2026).

---

## Front — les quatre règles qui ne se négocient pas

Le détail des patterns est dans `.claude/skills/ux-patterns` et
`.claude/skills/svelte-patterns` — les charger avant d'écrire un écran.

> 📖 `standards/11-interface-et-ux.md` (un pattern par notion, accessibilité,
> formulaires, archiver ≠ supprimer) · `standards/03-securite.md` §4 (assainissement)
> · `standards/02-factorisation.md` §2 (pourquoi dates et montants sont les deux
> récidivistes de la duplication).

1. **XSS** : jamais `{@html contenu}`, toujours `{@html <assainisseur>(contenu)}`.
   Ils sont **trois**, tous exportés par `$lib/sanitize.ts` et tous adossés à
   DOMPurify : `safeHtml` (HTML riche), `safeRichContent` (riche ou texte, **sans**
   enveloppe — appelé à l'intérieur d'un `<p>`), `safeDescription` (idem, **avec**
   enveloppe `<p>`). Cette règle ne nommait que le premier alors que les trois
   étaient en service : c'est ce qui a fait croire à 19 écarts qui n'en étaient pas
   (#429).

   🔒 **Garde-fou : `npm run lint:html`** (`front/scripts/check-html.mjs`), en CI
   depuis le 18/08/2026. Il lit la liste des assainisseurs **dans `sanitize.ts`** —
   une liste recopiée diverge au premier ajout — et exige que le nom vienne de
   l'**import**, pas de la portée du fichier : une fonction locale homonyme qui ne
   ferait rien passerait sinon. C'est ainsi qu'a été trouvée `renderContent`
   (`tickets/[id]`), copie littérale de `safeDescription`, correcte par chance.

   **Deux** exceptions, et deux seulement — relevées par l'audit du 18/08/2026,
   qui en a trouvé une non déclarée ; elles sont **déclarées dans le contrôle**
   (`EXCEPTIONS`), qui échoue si l'une d'elles cesse de servir :
   - `Icon.svelte` — SVG codé en dur côté serveur ;
   - `QRCode.svelte` — SVG produit **localement** par `qrcode-generator` à partir
     d'une donnée encodée en modules, jamais interpolée dans le balisage.

   ⚠️ Une exception non écrite n'est pas une exception, c'est un oubli qui
   ressemble à une décision. Toute nouvelle exception s'ajoute **ici** avec sa
   raison, sinon la règle devient « sauf quand on a jugé que ça allait ».
2. **Dates et montants** : ne jamais réimplémenter un format dans une page.
   `$lib/date.ts` (`fmtDate`, `fmtDatetime`, `fmtMonthYear`…), `$lib/utils.ts`
   (`fmtMontant`, `fmtOctets`, `fmtNombre`, `perimetreLabel`), et côté API `app/utils/dates_fr.py`. Deux
   garde-fous échouent en CI : `api/tests/test_dates_fr.py` et `npm run lint:dates`.
3. **Accessibilité** : tout élément cliquable non-`<button>` porte `role="button"`,
   `tabindex="0"` et `on:keydown` (Enter/Space) ; `aria-label` sur les boutons
   icône-seule ; `role="dialog"` + `aria-modal="true"` sur les modales
   (`standards/11-interface-et-ux.md` §2, seule source générique ; les skills y renvoient).
4. **Icônes de contexte** : 📍 = lieu physique, 🔹 = périmètre logique — **jamais
   mélangés**, et le périmètre par défaut ne s'affiche pas — la question se pose à
   `estPerimetreParDefaut` (`$lib/perimetres`), jamais par un `=== 'résidence'` :
   le code n'en contient plus un seul, et le nom du périmètre racine est
   **administrable**.

   🔒 **Garde-fou : `npm run lint:pictogrammes`** (#1045, 24/09/2026). Le badge 🔹
   ne se rend que par `BadgePerimetre` ; une phrase qui nomme un périmètre et
   chaque vrai lieu 📍 se **déclarent** dans le contrôle, avec leur nombre
   d'occurrences. Il a trouvé « 📍 Concerne votre bâtiment » et « 📍 Dépannage ».

   **Côté API, la même règle** vit dans `app/utils/perimetres/arbre.py` :
   `est_perimetre_par_defaut(codes)` pose la question, `perimetre_cible_json(codes)`
   écrit une sélection (vide → le défaut ; sans argument, c'est le
   `default_factory` des colonnes `perimetre_cible`), `perimetre_defaut_liste()`
   la donne en liste — toutes lisent la racine dans l'arbre (`code_par_defaut`).
   Le code « résidence » n'est écrit que par le **seed** qui pose le nœud ; il
   l'était 23 fois avant #1567. 🔒 `test_perimetre_racine_source_unique.py`
   (exceptions déclarées : la granularité documentaire `Document.perimetre`,
   autre axe — *qui lit* un fichier, pas *où* se passe un contenu).

---

## Conventions Backend (Python / FastAPI)

> 📖 `standards/06-donnees-et-integrite.md` §3 (migrations : chaîne linéaire, jamais
> de f-string SQL, le code et le schéma voyagent ensemble) et §4–5 (suppression
> logique, montants en entiers) · `standards/03-securite.md` §1–5 (autorisation
> centralisée, liste blanche, entrées/sorties, session et transport).

### Modèle SQLModel
- Un modèle vit dans le module de **son domaine** sous `app/models/` (`acces`,
  `communaute`, `prestataires`, `gouvernance`…) — **jamais dans `core.py`**.
  Repassé sous 500 lignes le 28/09/2026 (#779), le contrôle de modularité ne
  l'empêche que d'en ressortir : 🔒 `test_core_sans_modele_neuf.py` y refuse une
  classe de plus, et sa liste ne fait que baisser.
  Un module neuf s'**importe dans `models/__init__.py`** : c'est ce qui enregistre
  la table auprès de SQLModel — oublié, elle manque à `create_all` sans un mot.
- `core.py` **ré-exporte** les modèles extraits (imports `# noqa: E402` en milieu
  de fichier). Ils laissent `from app.models.core import X` valable après chaque
  extraction — **et ils enregistrent** : `alembic/env.py` n'importe que `core`, et
  c'est par eux qu'Alembic voit la moitié des tables. Pas un doublon à nettoyer
  en passant (#1157). 🔒 `test_modeles_enregistres.py` : chaque module de
  `app/models/` doit être chargé par `import app.models.core`.
- `__tablename__` = snake_case français
- Champs en français snake_case : `statut_validation`, `date_debut`
- Timestamps : suffixe `_le` → `cree_le`, `mis_a_jour_le` ; la valeur par
  `horloge.maintenant()` (UTC **naïf**, comme la base), jamais `datetime.utcnow()`
  — déprécié en 3.12, refusé par Ruff `DTZ003` (#1047). Le champ s'annote
  **`NaiveDatetime`** (pydantic), jamais `datetime` : depuis sqlmodel 0.0.45 ce
  dernier devient une colonne consciente du fuseau qui refuse la date naïve à
  l'écriture (#1412). 🔒 `test_horloge.py`
- Le **jour** du résident (calendrier, échéance, date affichée, `default_factory`
  d'un champ `date`) : `horloge.aujourd_hui()` — le jour de **Paris**, quel que
  soit le fuseau du conteneur ; celui d'un instant de la base :
  `horloge.jour_civil(x)`, son heure murale `horloge.a_paris(x)`, le fuseau
  `horloge.TZ_PARIS`. Jamais `date.today()`, `datetime.now()` sans fuseau ni
  `maintenant.date()` — le jour UTC, faux d'un jour entre 0 h et 2 h (#1565).
  🔒 `test_horloge.py` (forme `default_factory` comprise) et Ruff `DTZ005/011`
- FK : `{modele}_id = Field(default=None, foreign_key="table.id")`
- Enums : `class MonEnum(str, Enum)` → slugs français lowercase
- **Archiver, pas une colonne `actif` par réflexe.** Les objets qui quittent les
  listes se déclarent dans `utils/archivage.REGLES` — la règle unique, avec son
  test de concordance. La plupart des tables n'ont ni `actif` ni `archivee`, et
  c'est voulu : un booléen ajouté à côté ferait une seconde façon de disparaître.
  🔒 `test_archivage_colonnes_booleennes.py` : toute colonne `actif`/`active`/`archivee`
  est couverte par `REGLES` ou déclarée référentiel avec son sens (#1568).
- **Les ressources d'UNE copropriété se demandent à `app/contexte.py`** (#1744,
  chantier multi-copropriétés) : `contexte.nouvelle_session()` hors requête (une
  route prend `get_session`), `contexte.moteur()`, et `contexte.courante()` —
  `url_base`, `racine_fichiers`, `secret`, `expediteur`, `nom_expediteur`. Jamais
  `engine`, `SessionLocal` ni `settings.database_url|secret_key|uploads_dir|mail_from`.
  Un cache ou un quota tenu en mémoire se range dans `contexte.etat("nom")`, jamais
  dans une variable de module : l'utilisateur n° 12 d'une copropriété n'est pas
  celui d'une autre. La copropriété d'une requête se résout à son ENTRÉE
  (`contexte.ResolutionCopropriete`, le plus extérieur des intergiciels) ; une
  tâche hors requête la reçoit de `contexte.dans(copro)`. 🔒 `test_contexte_source_unique.py`,
  `test_etat_module_par_copropriete.py` (`A_INDEXER` vide, plafond zéro), et
  `test_etancheite_coproprietes.py` : deux bases aux identifiants identiques, aucune
  réponse servie pour l'une ne porte les données de l'autre (#1746).
- Lire un objet ou rendre 404 : `utils/recuperer.ou_404(session, Modele, id,
  "libellé")` — jamais `session.get` suivi d'un `raise HTTPException(404)`. Les
  404 bruts qui restent sont un **plafond décroissant**, `PLAFOND_404_BRUTS` dans
  `api/tests/test_recuperer_source_unique.py` — la valeur se lit là, et la carte
  des plafonds est #1571 (#1047, qui le citait, est fermé). Le 404 d'un objet
  qui doit porter son parent (`sous={"bail_id": …}`) passe aussi par lui.
  Les autres questions du même module : le **fichier absent du disque** —
  `fichier_ou_404(chemin, "PDF")` —, la **ligne unique** d'une table de réglage —
  `premier_ou_404(session, Modele, "…non configurée")` —, la **clé d'un registre**
  du code — `connu_ou_404(TABLE, cle, "Section inconnue")`, jamais pour une liste
  blanche d'accès — et le **résultat déjà calculé** qui vaut `None` —
  `present_ou_404(valeur, "…")` (#1571).
- Lire un objet, puis refuser en **403** si le prédicat de l'entité dit non
  (`ticket_visible`, `sondage_accessible`…) : `auth/appartenance.exiger_objet_autorise`
  — jamais `ou_404` suivi d'un `if not visible: raise HTTPException(403)`, qui
  était écrit à l'identique dans six routeurs (#1564).
- Deux tables qui portent le même objet (Vigik/Télécommande et leurs deux
  stagings d'import) : une **classe de base non-table** (`models/acces.py`,
  `_ObjetAcces`), jamais deux déclarations de colonnes. Un import xlsx déclare
  son `_traiter_rows` et nomme ses deux importeurs par `import_xlsx.importeurs`.
- La valeur d'une énumération (`categorie`, `statut`…) : `utils/valeurs.valeur(x)`,
  jamais `str(x)` — qui rend « CategorieTicket.etude_travaux » — ni un
  `getattr(x, "value", x)` recopié (il l'était neuf fois ; 🔒 `test_valeur_source_unique`).
- Lire un objet pour le RENDRE : `Schema.model_validate(objet)`, ou
  `utils/lecture.lire_objet(Schema, objet, **dérivés)` quand des champs se
  calculent — jamais une recopie colonne par colonne, où tout oubli part à sa
  valeur par défaut sans un mot : l'historique d'une affaire a ainsi perdu
  `assiste_ia` et `contenu_origine` (#1563). 🔒 `test_lecture_colonne_par_colonne`
  refuse la recopie pour TOUT schéma de l'application (il ne gardait que
  `TicketRead`, #1092) ; `test_lectures_rendent_le_modele` relit les sorties.

> 🔴 Cette section décrivait jusqu'au 23/09/2026 un backend disparu : « modèle
> dans `models/core.py` », « trois schémas dans `schemas.py` », « soft delete par
> `actif` ». Suivre la consigne violait la modularité (rang 1), et ce fichier est
> relu à chaque session (#1046).

- **Nommage : français, tables, routes et tags compris.** Les noms anglais
  existants — tables et routes — sont **figés** dans `api/tests/test_nommage_francais.py`
  (`TABLES_FIGEES`, `ROUTES_FIGEES` : le compte se lit là, pas ici), qui refuse le suivant : ils se renomment **au fil de l'eau**, quand un lot touche
  déjà la table ou la route — jamais en bloc (migration + client front) —, et on retire
  alors l'entrée, la liste ne fait que décroître. Un **tag** OpenAPI s'écrit en
  minuscules à tirets (`carnet-entretien`), un **préfixe** de routeur au pluriel (#1056).

### Schémas Pydantic
- Trois formes par entité exposée : `EntiteCreate` (entrée, sans id ni
  horodatage), `EntiteRead` (sortie, `class Config: from_attributes = True` —
  la forme de tout le dépôt), `EntiteUpdate` (tout `Optional`, PATCH partiel).
- Ils vivent dans le `schemas_<domaine>.py` de l'entité (`schemas_tickets`
  — actualités comprises —, `schemas_evenement`…), que `schemas.py` ré-exporte.
- Un schéma **propre à un seul routeur** — le corps d'un geste, la réponse d'un
  écran — vit à côté de lui (dans le routeur ou son `_schemas.py`). Le mettre
  dans un fichier partagé créerait un couplage que personne n'a demandé.
- `schemas_communs.py` n'importe RIEN du projet : c'est ce qui évite le cycle
  `schemas` ⇄ `schemas_tickets`. Ne pas lui en ajouter.

### Migrations Alembic
- ID séquentiel 4 chiffres : `0087`, `0088`…
- **Jamais** modifier une migration existante — créer une nouvelle
- **Jamais** de f-string dans `op.execute()` pour une **valeur** →
  `text(...).bindparams(...)`. Un **identifiant** (nom de table ou de colonne)
  ne peut pas se lier en SQLite : il s'interpole depuis une constante du fichier,
  et on l'écrit en commentaire. Cette nuance manquait, et la règle en « jamais »
  était donc fausse treize fois sur quarante — une consigne qu'on ne peut pas
  suivre à la lettre est une consigne qu'on cesse de lire.
  🔒 `test_migrations.py` refuse la **28ᵉ** f-string non liée ; les 27 existantes
  sont **figées** dans le test — une migration appliquée ne se modifie jamais,
  donc c'est de l'historique et non un retard à résorber. Ruff `S608` couvre le
  code vivant (`api/app/`), pas `alembic/`, pour la même raison.
- SQLite : pas de `ALTER TYPE`, pas de `CREATE TYPE`, et **pas de `ForeignKey`
  dans un `add_column`** — SQLite refuse d'altérer les contraintes d'une table
  existante, la migration crashe *après* avoir ajouté la colonne, et `start.sh`
  (`set -e`) arrête le conteneur. C'est arrivé **deux fois** (0117 le 25/07/2026,
  0165 le 01/09) sans que personne le voie : le redémarrage suivant passe grâce à
  la garde d'idempotence. Poser une colonne simple, et ne pas déclarer
  `foreign_key` dans le modèle non plus — sinon base neuve et base migrée
  divergent. `api/tests/test_migrations.py` le refuse.
- `start.sh` a `set -e` : une migration qui crash = conteneur bloqué
- 🔴 **Une migration reste compatible avec la version précédente du code** (#1757,
  08/10/2026) : revenir en arrière doit n'être qu'un changement d'image, sans
  restaurer la base. **Ajouter, puis retirer — jamais dans la même version** : une
  colonne neuve est nullable ou porte un `server_default` ; retirer une table ou
  une colonne, renommer, passer à `nullable=False` est un **second temps**, annoncé
  dans `CONTRACTIONS` par le lot où le code cesse d'en dépendre, et fait dans une
  version ultérieure. Pas de SQL brut qui retire ou renomme. 🔒
  `test_migrations_compatibles.py` (l'historique, jusqu'à 0271, n'est pas jugé ; il
  vérifie aussi qu'aucun modèle ne déclare plus ce qui est retiré).

### Dépendances d'auth
| Dependency | Usage |
|-----------|-------|
| `get_current_user` | Tout utilisateur connecté |
| `require_cs_or_admin` | Création/modification de contenu |
| `require_admin` | Suppression définitive, config système |
| `require_proprietaire` | Fonctions propriétaires |

Ces quatre-là **refusent** (elles lèvent un 401 ou un 403). La délégation n'en
a pas : elle est en **lecture seule** depuis le 02/10/2026 (#1534) — l'aidant
lit ce que lit la personne aidée, par `utils/delegations_actives`.
`get_acting_user`, qui figurait ici (« Délégation, header `X-Acting-As` »),
n'avait **jamais** été prise par une route : l'aidant écrivait sous sa propre
identité pendant que l'écran disait « Vous agissez pour ».
🔒 `test_autorisation.py` refuse une dépendance qu'aucune route ne prend ;
`npm run lint:en-tetes-lus`, un en-tête posé par le front qu'aucune route ne lit. À côté vivent les **prédicats**,
qui *disent* sans refuser — et qui s'appellent, jamais ne se redérivent :

| Prédicat | La question |
|---|---|
| `est_moderateur(user)` | conseil syndical **ou** admin — « qui modère » |
| `est_rattache_au_lot(user, lot_id, comme=…)` | « ce lot est le mien » (lien **actif** exigé) ; `comme` en restreint la nature — donner à bail exige un lien copropriétaire (#1535) |
| `peut_commenter` / `peut_editer` | l'auteur, le « saisi pour », l'admin (+ le CS pour commenter) ; une **actualité** : le CS et son auteur — l'arrivant corrige son annonce, sans décider qui la lit (#1091) |

Et les règles d'**appartenance** — « cet objet est-il le mien ? » — vivent dans
`auth/appartenance.py`, **jamais chez un routeur** : elles ne sont pas des
`Depends`, donc `test_autorisation.py` ne les voyait pas (#1028).

⚠️ Elles ne sont **pas** fondues en une fonction, et c'est mesuré : le bail d'un
bailleur refuse en **403** et admet le CS ; l'accès d'un porteur refuse en **404**
et ne l'admet pas ; l'aidant d'une délégation refuse en 403 sans l'admettre non
plus. Trois combinaisons pour trois règles — les réunir demanderait quatre
paramètres de variation. Ce qu'elles gagnent est un **lieu** : côte à côte, on
voit ce qui diverge et pourquoi. 🔒 `test_appartenance_source_unique.py`.

🔴 **Une route qui reçoit un `lot_id` (chemin, requête, formulaire ou corps) pose
la question** — `est_rattache_au_lot` ou `exiger_lot_du_bailleur` —, ou se réserve
au CS/admin, ou se déclare dans `ROUTES_SANS_QUESTION` avec sa raison. Un écran
qui ne propose que « mes lots » n'est pas un refus : `creer-multi` laissait tout
propriétaire poser un bail sur le lot d'un voisin, et en porter les badges
(#1535). 🔒 `test_appartenance_lot_source_unique.py`.

🔒 Écrire `has_role(conseil_syndical, admin)` en ligne est refusé par
`api/tests/test_moderateur_source_unique.py`. Il l'était **vingt-six fois** avant le
20/09/2026 — dont trois dans `deps.py` lui-même —, parce que le prédicat existait
sous le nom `peut_commander` : un nom qui décrivait **un geste** (fixer les champs de
commandement d'un ticket) n'est appelé que par ce geste, et les vingt-cinq autres
points d'usage n'ont jamais vu qu'ils posaient la même question (#1028).

🔴 **Une liste qui FILTRE appelle le prédicat du geste qui REFUSE** — jamais sa
copie. Une règle qui rend `False` (visibilité) ou fait `continue` (une liste) ne
lève rien, et les contrôles qui reconnaissaient une règle à sa **levée** ou à son
**nom** ne la voyaient pas : la liste des transferts recopiait
`exiger_auteur_du_versement` (→ `peut_defaire_le_versement`), celle des
catégories de documents le profil d'accès de `document_visible`
(→ `visibility.profil_admet`), et `document_visible` jugeait `ul.actif` à côté
d'`est_rattache_au_lot` (#1551). Les trois contrôles lisent désormais le
**contenu** sur l'AST : `roles_autorises` lu hors de `profil_admet`
(`test_autorisation.py`), un élément de `user_lots` jugé sur `actif` hors
d'`est_rattache_au_lot` (`test_appartenance_lot_source_unique.py`), un champ que
`auth/appartenance.py` compare à un utilisateur recomparé ailleurs
(`test_appartenance_source_unique.py` — les champs sont **lus** dans le module,
une règle neuve étend le contrôle d'elle-même).

### Documents imprimables (PDF)
- Thème commun : `app/utils/pdf_theme.py` — logo, palette de la charte, data-URI (image/QR), `html_to_pdf()`.
  **Ne jamais** redéfinir une palette, un logo ou un moteur PDF ailleurs.
- Le HTML doit être **autonome** : CSS dans `<style>`, images en data-URI (rendu hors requête HTTP).
- Format de page via `@page { size: A4|A5 }`. Pas d'emoji dans les affiches — logo SVG et aplats de couleur.
- Documents existants : fiche arrivant (`fiche_arrivant.py`), annonce de hall (`annonce_hall.py`),
  manuel utilisateur (`manuel_pdf.py`).
- 🔴 **Le rendu s'exécute hors du process de l'API** (`app/utils/pdf_rendu.py`, 16/09/2026),
  dans un enfant `spawn` — **jamais `fork`**, qui hériterait des descripteurs de `app.db`
  et ramènerait la règle d'or ci-dessus. Un WeasyPrint qui plante ou épuise la mémoire
  du RPi n'emporte donc plus l'API. Coût assumé : +1,5 à 2 s par document.
  `api/tests/test_weasyprint_appel_unique.py` refuse tout appel au moteur ailleurs que
  dans ce module — c'est ce qui empêche le rendu de retomber dans le process, en silence.
  Il gardait déjà cette porte pour une **autre** raison (la dérogation de sécurité
  GHSA-jf6q-chmf-3h3v) : ne pas en écrire un second, c'est la même porte.
  `api/tests/test_pdf_hors_process.py` vérifie, lui, que l'enfant est bien `spawn`.

### Destinataires CS

`app/utils/destinataires.py` est la source unique, et elle porte **deux règles
distinctes** — les confondre envoie le bon message aux mauvaises personnes :

| Ce qu'on vise | Fonction | Employée par |
|---|---|---|
| le CS **concerné par un périmètre** | `membres_cs_notifiables(session, batiment_ids)` (+ `batiments_du_perimetre()`) | nouvel arrivant, annonces de hall |
| le CS **par le rôle**, sans périmètre | `membres_cs_avec_email(session)` | publications, sondages, calendrier, tickets |
| le **syndic principal** | `syndic_principal(session)` | ci-dessous, fiche copropriété, arrivants |
| le **gestionnaire du site** — un administrateur, ou personne (#1505) | `site_manager_user_id(session)` | ce qui renvoie à `/admin` : comptes, alertes, bogues |
| **syndic puis CS, dédoublonnés** — qui reçoit un e-mail interne | `destinataires_syndic_cs(session, syndic=…, cs=…)` | les quatre entités qui cochent « envoyer au syndic / au CS » |
| **gestionnaire du site puis CS, dédoublonnés** | `gestionnaire_puis_cs(session)` | la synthèse d'une affaire close à valider (#1643) |

🔴 La dernière ligne a existé en **quatre exemplaires identiques** (tickets,
calendrier, publications, sondages) jusqu'au 31/08/2026 — et celui des tickets
affirmait, en toutes lettres, être *« le seul endroit où cette règle s'écrit »*.
Les trois autres n'avaient aucun commentaire : le seul fichier qui parlait du
sujet disait que le problème n'existait pas.

🔒 `api/tests/test_destinataires_source_unique.py` refuse une cinquième copie. Il
laisse passer les notifications **in-app**, qui visent « CS **ou** admin » et
rendent des `Utilisateur` — autre décision, autre destinataire.

### Prévenir le groupe de la résidence

On **diffuse sur le canal de la résidence**, on n'« envoie pas un WhatsApp » :
`utils/diffusion` — `config_diffusion(session)` (la configuration du canal, ou
`None` s'il est éteint) puis `diffuser(background_tasks, config, titre, contenu,
…)`. Le registre `CANAUX` n'a qu'un canal, WhatsApp, dont le bridge est
l'adaptateur ; les clés `whatsapp_*` et la table `whatsapp_log` gardent leur nom
jusqu'au second (#1060). 🔒 `test_diffusion_canal.py` refuse qu'un appelant
importe les gestes du transport.

### Couper ou rétablir un service

« Ce service est-il activé ? » se demande à `utils/services` —
`service_actif(cfg, SERVICE_…)`, et `cle_actif(SERVICE_…)` pour nommer la clé —,
jamais par une lecture de `llm_actif`, `whatsapp_enabled` ou `imap_enabled` :
elles avaient trois règles, dont une plus large (#1718). Le registre `SERVICES`
est la seule liste ; l'onglet **Admin › Services** s'en déduit
(`GET /config/services`). Un service neuf s'y déclare, avec ce qu'on perd en le
coupant. 🔴 **Les courriels de sécurité ne sont pas un service**
(`COURRIELS_DE_SECURITE`) : le SMTP y est une infrastructure, sans interrupteur.
🔒 `test_services_registre.py`, `test_courriels_securite_hors_service.py`.

### Sécurité
- JWT HS256 en cookies `httponly=True`, `secure=settings.cookie_secure`, `samesite="strict"`
- CORS : allowlist explicite, jamais `["*"]` avec `credentials=True`
- Rate limiting slowapi sur `/auth/*`
- **Un jeton se stocke par son empreinte, jamais en clair** — rafraîchissement,
  mot de passe oublié, vérification d'adresse : `auth/empreinte_jeton.empreinte`
  (HMAC avec `SECRET_KEY`) à l'écriture ET à la recherche ; le brut ne vit que
  dans le cookie ou le lien. Une copie de la base donnait des jetons
  utilisables (#1389). Changer `SECRET_KEY` ferme donc toutes les sessions et
  invalide les liens en attente — voulu. 🔒 `test_jetons_empreinte.py`.
- **« Le compte de cette adresse » : une seule porte.** `auth/adresse_compte` —
  `compte_par_adresse` (insensible à la casse et aux espaces, des deux côtés) et
  `normaliser_adresse`, la forme sous laquelle une adresse s'écrit ET se cherche.
  Deux écritures divergeaient sur la casse : un compte à majuscule se connectait
  mais ne recevait ni lien de vérification ni mot de passe oublié (#1550).
  🔒 `test_adresse_compte_source_unique.py` refuse une comparaison sur
  `Utilisateur.email` ou une normalisation d'adresse recopiée.
- **Changer l'adresse d'un compte est une DEMANDE, jamais une écriture** —
  `utils/verification_adresse.demander_changement_adresse`, pour le profil comme
  pour l'administrateur : mot de passe de **qui agit**, lien à la nouvelle
  adresse (le jeton de l'inscription, qui porte alors `nouvelle_adresse`), avis
  à l'ancienne, qui reste celle du compte jusqu'au clic, journal. Une session
  volée suffisait à détourner un compte (#1549). 🔒 `test_changement_adresse.py`
  refuse aussi `x.email = …` hors de la confirmation du lien.
- **Journal de sécurité : une seule porte.** Un geste sensible — connexion
  refusée, mot de passe changé ou réinitialisé, rôle ajouté ou retiré,
  bannissement, jeton de rafraîchissement rejoué, changement d'adresse demandé
  ou confirmé ; la liste fait foi dans `GESTES_SENSIBLES` — appelle `utils/journal_securite.journaliser_securite`, et
  **aucun** n'écrit dans un `logger` local. Rien n'était journalisé avant le
  20/09/2026 : un compte compromis ou une élévation de rôle ne laissait aucune
  trace exploitable (#1040). Depuis #1548, le **cycle de vie d'un compte** aussi :
  validé ou refusé, désactivé ou réactivé, supprimé, et une délégation créée,
  acceptée ou révoquée. Le geste suivant n'attend pas un audit : 🔒 `test_journal_securite.py`
  confronte `GESTES_SENSIBLES` à ce que les routeurs **écrivent** (décision sur
  un compte, rôles, effacement, délégation) et refuse un code absent de `_NIVEAUX`.
  🔴 **Jamais de donnée personnelle dans une ligne de journal** — un identifiant,
  jamais une adresse, un mot de passe ou un jeton, même tronqué. Le défaut
  inverse existe dans ce dépôt (#777, adresses journalisées en clair), et
  `test_journal_securite.py` le refuse **chez la fonction et chez ses appelants**.
  ⚠️ `WARNING`, jamais `ERROR` : le point 6 du pré-check compte les
  `ERROR`/`CRITICAL` (motif `MOTIF_ERREURS_API`), et une faute de frappe sur un
  mot de passe bloquerait alors la MEP. Cette ligne nommait aussi
  `check-reliability.sh`, qui ne compte rien de tel (23/09/2026).
- **Téléversement : une seule porte.** Un fichier reçu s'écrit sur disque par
  `utils/fichiers.enregistrer_fichier_recu` **et nulle part ailleurs** ; les
  règles — liste blanche de types, plafond de taille, cohérence de la signature —
  vivent dans `FAMILLES` (image · document · document_prive · tableur). Un
  routeur **nomme une famille**, il ne redéfinit pas ce qu'il accepte.
  🔒 `test_televersement_source_unique.py` refuse une écriture ailleurs (le PDF
  d'affiche, qui est **produit** et non reçu, y est déclaré), une liste MIME ou
  un plafond redéclaré dans un routeur, et une famille qui oublierait l'une des
  trois règles. `test_signature_fichiers.py` vérifie que **chaque** point de
  réception appelle la règle — les trois imports de tableur y ont été ajoutés,
  ils n'avaient aucun contrôle.
  Le nom stocké passe par `nom_stocke` : préfixe UUID, radical assaini, et
  **extension dérivée du type**, jamais du nom fourni — `/uploads/*` est servi
  en statique et Caddy pose le `Content-Type` d'après l'extension sur disque.
- La **racine du volume** se lit dans `Settings.uploads_dir`, seule lecture de
  la variable d'environnement. Elle était écrite six fois : un fichier posé hors
  du volume n'est ni répliqué par `bascule.sh`, ni sauvegardé par `backup.py`.
- **Le dépôt est PUBLIC : aucun nom de personne réelle** — ni dans un test, un
  commentaire, un message de commit, ni dans un ticket. Un nom inventé de même
  forme (#1493). 🔒 `test_identites_fictives.py` (liste blanche) lit le code,
  les tests, les **migrations** et les **documents** — ces deux-là depuis
  #1544, une docstring de migration nommait deux employées du syndic ; ce qu'il
  ne voit pas : `.claude/skills/security-audit` §8.
  **Exception assumée** (arbitrage du 06/10/2026, #1581) : l'identifiant SSH
  d'exploitation et les IP du LAN restent dans les scripts, crontabs et documents —
  jamais dans l'application ; 🔒 `test_hygiene_depot.py` l'enferme. Même skill, §8.

---

## Checklist avant commit

### Frontend
- [ ] Pattern existant réutilisé (pas de variante ad hoc) — *non mesurable : aucun
      garde-fou ne le tient, c'est la relecture qui le porte*
- [ ] Méta toujours visible en mode collapsé — tenue par `EnteteCarte`, qui porte
      les tags sur la carte repliée (`npm run lint:entete-carte` exige qu'une
      carte passe par lui)
- [ ] Corps déplié d'une carte : `class="carte-corps …"` — c'est ce qui le fait
      entrer (fondu 200 ms) ; sans elle il apparaît sec, sans un mot. 🔒 `npm run
      lint:entete-carte` l'exige de tout fichier qui rend `.carte-liste` (#1579). Un survol
      qui ne sert qu'à la souris vit sous `@media (hover: hover) and (pointer:
      fine)` — au doigt, `:hover` reste collé (`ux-patterns` §17)
- [ ] Dernière ligne d'une carte d'affaire, d'actualité ou du fil : `PastillesAffaire`,
      l'auteur par `AuteurCarte` (« ✍️ Nom ») — jamais recomposée ; ordre et
      exceptions dans `ux-patterns` §3 (`npm run lint:pastilles`)
- [ ] `.clamp-3` sur l'aperçu d'une carte (`.clamp-5` seulement hors carte) ;
      aucune troncature écrite hors de `normes.css` (`npm run lint:clamp`)
- [ ] un assainisseur de `$lib/sanitize` sur tout `{@html}` — jamais un helper
      local, même correct (`npm run lint:html` le refuse)
- [ ] Accessibilité : `role`, `tabindex`, `aria-label`, `on:keydown`
- [ ] Droits : jamais recomposés dans un écran — `$isCS` (il **inclut** admin),
      `$isProprioOuCS`, `aRole(u, …)`, `peutEditer`/`peutCommenter`. Ils l'étaient
      **22 fois** avant #1041 (`npm run lint:droits` le refuse)
- [ ] Onglet réservé à un rôle : `reserve:` **sur l'onglet** dans `pages.ts`, jamais
      un masquage écrit dans la page — `BarreOnglets` masque ET refuse la route
      directe (`npm run lint:onglets-reserves`)
- [ ] Nom affiché d'un objet « Saisi pour » : `nomProprietaire` (`$lib/saisi-pour`),
      **jamais** `objet.auteur_nom` — c'est le rédacteur, et le « Saisi pour » s'y
      substitue (12/09). La case de copie, elle, dit `nomCopie` : deux questions.
      Il y en avait **13** avant #1104 (`npm run lint:nom-proprietaire` le refuse)
- [ ] Section d'un formulaire : elle est déclarée dans `$lib/entites/<entité>`,
      dans l'ordre de `SECTIONS_ORDRE` (`$lib/entites/types.ts`) — la liste ET
      son compte se lisent là, jamais ici : « treize » y est resté écrit six
      jours pour quatorze (#1541, `npm run lint:consignes`) — et son **pliage** suit la
      règle *obligatoire → déplié · facultatif → plié*, ou porte son
      `exceptionPliage` (`npm run lint:etats` refuse dans les deux sens). Un
      composant qui **porte** une section au lieu de l'écrire dans la page la
      **transmet** : sans prop `pliable`, la table a beau dire `pliee`, la
      section s'ouvre — il y en avait **trois** (`npm run lint:pliage-transmis`).
      Et l'**appelant** la passe, lue par `pliageDe` : jamais absente ni `pliable`
      nu — la Suite d'une affaire ouvrait ce que l'Édition pliait (#1329)
- [ ] Libellé qui NOMME un objet — bouton, titre de boîte, toast, confirmation :
      le mot vient de `$lib/entites/<entité>` (`libelle`, `libelleNouveau`,
      `libelleModifier`), **jamais** réécrit dans un écran. « Ticket » est un
      nom de modèle (« Publication » l'était, jusqu'à sa suppression le
      30/09/2026, #1177) ; l'écran dit « Affaire » et « Actualité ». Il y en avait **20** avant #1107 (`npm run lint:vocabulaire-ecran`)
- [ ] Périmètre : masqué s'il est celui par défaut — le badge passe par
      `BadgePerimetre`, qui le tait (`npm run lint:pictogrammes`)
- [ ] Archiver (pas supprimer) sur la vue principale — 📦, jamais un 🗑️ intitulé
      « Archiver » ; la corbeille ne s'offre qu'aux Archives, et ce qu'on range a
      son écran (`api/tests/test_suppression_aux_archives.py` : affaires,
      actualités, prestataires, contrats — une carte qui archive s'y ajoute) ;
      le titre des archives vient d'une constante (`lint:archives`)
- [ ] Champs requis : `<EtoileRequis vide={!champ} />` — jamais une astérisque
      tapée. Elle est **collée** au libellé et **rouge tant que le champ est
      vide** : c'est son état, pas une décoration (#1121, 22/09/2026). Une
      **valeur par défaut active** le remplit — « Tous », « aucune
      restriction » : étoile noire (27/09/2026, `e2e/etoile-valeur-defaut`) — un
      GROUPE de champs aussi : `<LibelleGroupe titre="…" requis vide={…}>`,
      jamais `titre="… *"` (#1329, 27/09/2026). Les
      libellés de champ sont en MAJUSCULES par le style (`champs.css`), comme
      les intitulés de section — jamais tapées (`npm run lint:champs`)
- [ ] Libellés et nommage en français — 🔒 les mots d'interface anglais sont refusés par
      `npm run lint:vocabulaire-ecran` (`lib-mots-anglais.mjs`, #1579) ; *le reste de la langue
      reste non mesurable : `lint:texte` et `lint:champs` ne la jugent pas*
- [ ] Couleur et taille de texte : `var(--color-…)`, `var(--fs-…)` (`socle.css`),
      jamais une valeur en dur — `npm run lint:charte-valeurs`, plafond qui ne
      fait que baisser (#1055). Arbitré sur maquette le 27/09/2026 : une taille
      hors échelle se range au cran **supérieur**, un état (danger, succès,
      avertissement) prend son jeton et ses dérivés `-fond`, `-bordure`, et
      `--color-warning` ne sert jamais au texte (`--color-warning-texte`). Ces
      valeurs-là sont **refusées**, sans plafond (`ux-patterns` §18) — comme une
      valeur **égale** à un jeton (`#fff`, `0.8rem`) : 85 étaient revenues (#1571)
- [ ] Un style s'écrit dans le `<style>` du composant ou dans `src/styles/`, jamais
      en attribut `style="…"` — sauf une valeur tirée des données (`width:{pct}%`).
      `npm run lint:styles-en-ligne` le refuse : plafond à **zéro** depuis le
      08/10/2026 (#1571, 524 au départ). Une classe pèse moins qu'un attribut :
      si une règle globale plus forte vise l'élément, qualifier le sélecteur
- [ ] Bloc pliable (carte, section, année, `<details>`…) : **un seul déplié à la
      fois**, par `$lib/accordeon` — jamais un `Set` d'ouverture. Exceptions
      arbitrées : section modifiée, carte en correction (`npm run lint:accordeon`,
      30/09/2026)
- [ ] Rangée de pastilles qui FILTRE une liste : `compte={<liste affichée>.length}` —
      le nombre se montre sur la pastille **retenue** seulement, jamais un par
      entrée (maquette J, 10/10/2026 ; `ux-patterns` §5). `npm run lint:compte-filtres`
- [ ] Attente d'un écran : `<EtatListe chargement />`, jamais un « Chargement… »
      écrit à la main — il y en avait **23** avant #1045 (`npm run lint:chargement`)
- [ ] En-tête de page : `<EntetePage>`, jamais `<div class="page-header">`
      (`ux-patterns` §13)
- [ ] Icône vérifiée dans `$lib/icones-svg.json` — un nom inconnu échoue en silence
      (`npm run lint:icones` le refuse ; un relais d'icône s'appelle `icone`)
- [ ] Tout champ libellé dans un `.field` — jamais une nomenclature locale
      (`npm run lint:champs` ; il y en avait **six** avant #413) — **y compris**
      le champ dont l'intitulé de section est le libellé, et une étoile dans un
      `label.field` enveloppant se tient dans un `<span>` avec son texte (#1230)

### Backend (nouveau endpoint)
- [ ] Modèle dans le module de **son domaine** (`app/models/<domaine>.py`), importé
      par `models/__init__.py` — jamais dans `core.py`
- [ ] Schémas dans `schemas_<domaine>.py` s'ils sont partagés, à côté du routeur sinon
- [ ] Migration `NNNN_slug.py`, numéro suivant le dernier de `alembic/versions/`
- [ ] Routeur inclus dans `main.py` ou dans le `__init__.py` de son paquet —
      `test_routeurs_montes.py` refuse un routeur que personne ne monte : ses URL
      rendraient 404, et rien d'autre ne le dirait
- [ ] ⚠️ Dans un paquet, les routes à segment **fixe** s'incluent AVANT celles à
      paramètre (`/admin/imports/{id}` avant `/admin/{type}/{id}`) : FastAPI retient
      la première qui correspond. Deux écrans d'import sont morts ainsi (#1151) ;
      `test_routes_masquees.py` le tient pour `acces`
- [ ] Lecture d'un objet par `ou_404`, pas `session.get` + 404
- [ ] Client TypeScript ajouté dans le paquet `front/src/lib/api/` — dans le module de son domaine (`acces`, `patrimoine`, `communaute`…), jamais dans un `api.ts` ressuscité à la racine
- [ ] …**y compris pour une adresse** — lien de téléchargement, `src` d'image : le
      client la rend (`documents.downloadUrl`, `manuel.pdfUrl`), et aucune chaîne
      `/api` ne s'écrit dans un écran (`npm run lint:client-api` ; il en manquait
      cinq, qu'il ne voyait pas, avant #1578)
- [ ] …et il **rend le type** de ce que le serveur renvoie, déclaré à côté de lui —
      jamais `any` qu'un écran retype. Un type d'entité (champ `id`) déclaré dans un
      écran est refusé (`npm run lint:types-locaux`, #1044 — dette soldée le 06/10/2026,
      seuls les `id` qui ne sont pas des entités se déclarent, avec leur raison), et
      **aucun `any` nulle part** : ESLint `no-explicit-any` en erreur sur tout le
      front (`eslint.config.js` — le client à zéro en v2.105.0, #1572, le reste
      le 08/10/2026, #1571). Typer sur les types du client, lire un champ dont le
      nom est une donnée par `champDe` (`$lib/utils`)
- [ ] `cd api && ruff format .` — la CI refuse un fichier non formaté depuis le
      24/09/2026 (#1048 ; Ruff **épinglé** dans `ci.yml`, largeur 100, migrations
      exclues par `api/ruff.toml`). ⚠️ Une ligne coupée emporte son `# noqa` sur
      une autre ligne : rejouer le contrôle **tel que la CI le passe** —
      `bash scripts/poste/rejouer-ci.sh lint-backend` —, jamais un `ruff check`
      nu, qui juge autre chose que la CI (fixtures pytest et ré-exports de `core.py`
      écartés exprès par `ci.yml`, #1603). Une comparaison SQLAlchemy
      (`Model.actif == True`) garde `# noqa: E712` — jamais `is True`, qui vide
      le filtre sans un mot

### Documentation utilisateur — **deux** documents de même rang
- [ ] `docs/manuel-utilisateur.html` — **comment on s'en sert** : mis à jour dans le
      même commit dès qu'un écran, un libellé, un geste ou un parcours change
- [ ] Synchronisé : `Copy-Item docs/manuel-utilisateur.html front/static/manuel-utilisateur.html`
- [ ] `README.md` — **ce que le produit est** : mis à jour dès qu'un module, un écran
      de premier niveau ou une capacité est **ajouté, retiré ou renommé**, que la pile
      change, ou qu'un document du tableau `docs/` bouge
- [ ] Un lot qui ne touche qu'un seul des deux, c'est possible — mais on **dit** lequel
      et pourquoi, on ne l'omet pas en silence

> ⚠️ Le manuel ne se modifie **jamais** avec `sed -i` : il est versionné en CRLF, que
> `sed` réécrit en LF (les dégâts mesurés : `standards/10-encodage-et-fichiers.md` §2). L'écrire en OCTETS, et
> vérifier `git diff --stat`.
>
> Le README était vérifié par personne alors que le point **0e** du pré-check le nomme
> depuis toujours au même rang que le manuel : cette checklist-ci ne citait que le
> manuel, et c'est la liste la plus courte qui a été suivie (11/08/2026, signalé par
> l'utilisateur). Détail et déclencheurs : `.claude/skills/user-manual`.

### Tests préventifs (CI : `api/tests/`, lancés à chaque PR)

> 📖 `standards/05-tests-et-garde-fous.md` — pourquoi un défaut corrigé sans garde-fou
> revient (trois récidives en deux mois ici), les quatre familles de garde-fous qui
> marchent, et l'analyse statique quand le couplage entre deux fichiers est implicite.

Garde-fous contre les classes d'erreurs récurrentes de l'historique GitHub :
- **`test_email_templates.py`** — verrouille les variables Jinja2 de chaque template
  (`EXPECTED_VARS`, déclaré dans `tests/aides_contrats_email.py`). Complète le **point 9** (réactif) côté template.
  ⚠️ Si tu modifies les variables d'un template (`seed.EMAIL_TEMPLATES`), **mets à jour
  `EXPECTED_VARS`** ET vérifie que le `send_email(code=...)` correspondant fournit ces
  variables — sinon échec silencieux à l'envoi (cf. bug `'destinataire' is undefined`).
- **`test_migrations.py`** — chaîne Alembic : head unique, base unique, révisions uniques
  (attrape un `down_revision` erroné qui bloquerait `alembic upgrade head` au démarrage).
- **Licences tierces** (#1542, #1543) — `scripts/ci/licences_tierces.py` (job
  `test-backend`) juge chaque dépendance de `front/`, `whatsapp-bridge/` et `api/`
  contre une liste blanche. Une licence hors liste s'ajoute en **exception nommée**
  avec son motif dans `scripts/ci/licences_politique.py` — jamais en élargissant la
  liste ; une exception qui ne sert plus fait échouer. Un paquet qui entre ou
  change de licence : relire, puis `--ecrire` régénère `docs/licences-tierces.md`,
  jamais tenu à la main. Un fichier ou un tracé **repris** d'un projet tiers se
  déclare dans `CONTENUS_TIERS` et dans `REUSE.toml` — `contenus_tiers.py` (job
  `lint-backend`) le vérifie : `reuse lint` dit qu'une licence est déclarée, pas
  qu'elle est vraie.
- **Le code de test ne se recopie pas non plus** (#1495) : la liste des aides et
  de ce qu'elles remplacent se lit dans `MOTIFS` de
  🔒 `test_aides_de_tests_source_unique.py` — balayage de `app/`, base en mémoire
  (la fixture `session` vient du conftest), comptes, migrations, horloge, scripts
  shell. Seuls `test_*.py`, `aides_*.py` et `conftest` vivent dans `tests/`
  (`test_nommage_modules_de_tests.py`, `api/pytest.ini`). Une aide partagée vit dans un `tests/aides_*.py`, **jamais** dans un
  fichier de tests qu'un autre importerait. Il y en avait 162 copies.
- **Un contrôle front « une notion, une source »** — la forme d'une copie refusée
  hors du fichier qui porte la notion — s'écrit sur `front/scripts/lib-source-unique.mjs`
  (cas zéro, témoin qui doit servir, exceptions déclarées, commentaires blanchis) :
  six contrôles en recopiaient le squelette, et l'un n'avait pas de cas zéro (#779).
- 🔒 **Aucun état mutable de module de plus** (#1743, chantier multi-copropriétés) :
  un conteneur de module modifié depuis une fonction, un `global`, un `@lru_cache`
  fuiraient d'une copropriété à l'autre dans un même processus (spec §4.5).
  `test_etat_module_par_copropriete.py` les relève sur l'AST ; un état neuf se range
  en base, ou se déclare dans `DU_PROCESSUS` avec sa raison s'il ne porte aucune
  donnée de copropriété. Un état de copropriété passe par `contexte.etat(nom)`,
  la seule porte (`PAR_COPROPRIETE`) ; `A_INDEXER` est soldée depuis #1744.
- 🐘 **La suite passe sur PostgreSQL, et c'est un check REQUIS** (#1747, D4) :
  `tests/aides_base.moteur_memoire` bascule sur PostgreSQL quand `TESTS_BASE_URL`
  est posé — un schéma neuf par test, retiré à sa fin, clés désactivées sauf
  `cles_etrangeres=True` comme en mémoire —, et le workflow `postgresql.yml` rejoue
  toute la suite (`scripts/ci/mesure-postgresql.sh`, en tranches). Une comparaison
  qui ne tient que sous SQLite — un horodatage contre du texte, un booléen contre
  `1` — y échoue. Ce qui ne vaut QUE pour SQLite se déclare
  `@pytest.mark.sqlite_seulement("pourquoi")` ; les migrations historiques (≤
  `DERNIERE_HISTORIQUE`, `tests/aides_migrations.py`) n'y sont pas rejouées, une
  base PostgreSQL naissant du schéma initial. En local : `TESTS_BASE_URL=postgresql+psycopg://…`.
- 🔒 **Ce qui ne vaut que pour SQLite vit dans `app/dialecte.py`** (#1747) : `PRAGMA`,
  URL de base-fichier, journal WAL, intégrité, compactage, clés étrangères, format
  SQL d'une date (`dialecte.jour`, `dialecte.mois`). `test_adherence_sqlite.py` le
  refuse partout ailleurs dans `app/`, sur l'AST. Une base NEUVE reçoit le schéma
  courant d'un coup, marqué à la tête (`utils/schema_initial`, appelé par `start.sh`).
- 🔒 `test_routeurs_nommes_par_un_test.py` : un routeur de `app/routers/` que
  **aucun** fichier de `tests/` ne nomme est refusé (#1569).
- 🔒 **Clones Python** (#1564) : `scripts/ci/clones_python.py` (job `lint-backend`,
  jscpd épinglé) mesure les duplications exactes de `api/app` et échoue **dans les
  deux sens** — un clone ajouté, ou un retiré sans baisser `PLAFOND_CLONES`. Les
  six qui restent sont des déclarations que le langage force à répéter (blocs
  d'imports, signatures), nommées dans l'en-tête du script.
- 🔒 **La CI se rejoue à l'identique** (#1584) : tout `pip install` s'épingle
  (`test_ci_installations_epinglees.py`) et chaque `uses:` s'écrit par **SHA** avec
  sa version en commentaire (`test_ci_actions_epinglees.py` — Dependabot suit les
  deux). Un workflow se mesure comme du code (500 lignes) ; `ci.yml` seul est admis
  au-dessus, par une **exception nominative** de `scripts-ci-modularite.sh`
  (`EXCEPTIONS_PLAFOND`, #1547) qui échoue quand elle ne sert plus.
  L'image de Caddy porte une **mineure explicite** (`FROM caddy:2.11`,
  `test_image_caddy_epinglee.py`, #1602) : Dependabot propose alors ses montées. Python et
  Node restent flottants, par choix de `dependabot.yml`.
- Lancer en local (deps requises) : `cd api && pytest tests/ -q`.

### Scripts d'infra — job CI `test-scripts` (depuis le 30/07/2026)
Les scripts qui décident d'arrêter la prod (`bascule.sh`, `health-watch.sh`,
`boot-role-guard.sh`, `check-reliability.sh`…) n'étaient couverts par **aucun**
test : ni Python ni Svelte, donc hors de portée des trois autres jobs. Le job
`test-scripts` vérifie à chaque PR la syntaxe (`bash -n`) de tous les `.sh`
versionnés, les modes git (0b), et exécute les **self-tests**.

**Règle pour toute nouvelle logique de décision d'infra** : l'isoler en fonction
**pure** (aucun SSH, docker, écriture ni `sudo`), exposer `--selftest`, et
l'ajouter au job. C'est le seul moyen de tester une décision de bascule sans les
deux RPi — pattern inauguré par `boot-role-guard.sh --selftest` (15/07/2026),
étendu à `health-watch.sh` et `check-reliability.sh` (30/07/2026).
Lancer en local : `bash <script>.sh --selftest`.

### Navigateur — job CI `e2e-frontend` (depuis le 08/09/2026)
`front/e2e/` porte les tests Playwright — squelette, lien d'évitement, absence de
défilement horizontal, cibles tactiles — sur les profils **bureau ET mobile**.

🔴 **Ils existaient depuis le 06/09 et ne tournaient dans aucun job** : le dépôt
contenait les tests, `npm run e2e` les passait sur le poste de qui y pensait, et
les checks requis restaient verts si l'un d'eux cassait. C'est la même famille que
#409, #410 et #411 — des contrôles qui existent et ne s'exécutent pas. Écrire un
test et le **brancher** sont deux gestes, et le second ne manque à personne.

Un écran **authentifié** se rend avec l'**API simulée** (compte témoin, listes
nécessaires) — `e2e/depot-fichier.spec.ts`, `e2e/ligne-pastilles.spec.ts`. ⚠️ Le
motif d'interception vise le chemin `/api/` du serveur seulement : sinon il attrape
les modules source `/src/lib/api/…` et la page tombe en 500 (`standards/05` §13).
Cette ligne disait jusqu'au 27/09/2026 que ces tests « s'arrêtent aux écrans
publics » : c'était vrai, et ce n'est plus une limite.

🔒 **Une position ou une taille lue juste après l'ouverture d'une boîte** se mesure par
`boiteStable` (`e2e/aides.ts`), jamais par `boundingBox()` seul : la boîte entre en 200 ms
à 96 % de sa taille, et la mesure faussée faisait échouer un test sur trente (#1625).

🔒 **Un spec prend `test` et `expect` dans `./aides`**, jamais dans
`@playwright/test` (`npm run lint:e2e-test`) : ce `test`-là fait échouer toute
**exception de la page**. Une réponse simulée qui ne se devine pas au chemin se
déclare dans `REPONSES_PAR_DEFAUT` (`e2e/aides.ts`), avec le type qu'elle imite.
Pourquoi — un titre figé par une exception que personne n'écoutait, et quatre
specs verts qui en cachaient une : `standards/05` §13, #1475.

🔒 **Le serveur des tests écoute sur `127.0.0.1`, et les tests le visent là**
(#1732, 08/10/2026). Avec `localhost`, Vite n'écoutait que sur `::1` et le
navigateur tentait aussi `127.0.0.1` : `ERR_CONNECTION_REFUSED`, ou « Failed to
fetch dynamically imported module …/app.js », un spec différent à chaque passage
— une suite complète sur deux échouait sur le poste. `npm run lint:e2e-serveur`
refuse `localhost` dans `playwright.config.ts`.

Lancer en local : `cd front && npm run e2e`.
Un délai d'hydratation dépassé se lit avec le bilan **⏱ hydratation** en fin de
sortie (et `test-results/hydratation.json`) : la durée du test fautif comparée à
celle des tests verts du même passage (#1475).

🔒 **Aucun rechargement de Vite pendant les tests** (#1421, 28/09/2026). Une
dépendance chargée par un `import()` dynamique (`dompurify`, l'éditeur `@tiptap`)
n'est optimisée qu'au premier écran qui l'appelle, et Vite recharge alors toutes
les pages ouvertes : des e2e tombaient au hasard, quatre rejeux complets sur six.
Elle se déclare dans `optimizeDeps.include` (`vite.config.ts`) ; l'étape de CI
échoue en la nommant si une nouvelle venue recharge une page.

### Rejouer la CI en local — `bash scripts/poste/rejouer-ci.sh` (depuis le 13/08/2026)
Les **cinq** jobs ci-dessus se rejouent en une à deux minutes sur le poste, sans rien
recopier : le script **extrait** les commandes de `.github/workflows/ci.yml`. Une
liste tenue à la main divergerait au premier job ajouté — et c'est justement le job
ajouté, ou celui qu'on ne pense pas à lancer, qui échoue (#319 : Ruff, le 12/08).
Sa trace (`.git/rejeu-ci.ok`) est lue par le **point 16** du pré-check.
Un seul job : `bash scripts/poste/rejouer-ci.sh build-frontend` — mais alors aucune trace n'est
écrite, et le point 16 reste INCONNU.

🔒 **Depuis le 28/09/2026 (#1417), deux choses le rendent INCONNU au lieu d'un faux
vert** : un poste dont les dépendances installées ne sont pas celles que le lot
épingle — la ligne `ENV … dépendances` donne l'écart et la commande qui aligne
(`scripts/poste/verifier-dependances-poste.py`) —, et un second rejeu lancé
pendant qu'un autre tourne : un verrou dans le répertoire git commun le refuse,
worktrees compris. Le rejeu de #1415 avait rendu « pytest OK » sur sqlmodel
0.0.39 pour un lot qui posait 0.0.44.

Sur un poste déjà chargé par d'autres sessions, le rejeu passe les e2e à **un
seul worker** (`E2E_WORKERS`, seuil et mesure dans `rejouer-ci.sh`, règle
`ci_workers_e2e`) : les workers s'y disputaient la machine et quatre specs
tombaient en délai d'hydratation (#1665). La CI GitHub garde le défaut.

🔒 Un worktree dont `front/node_modules` est une **jonction** vers le clone
principal en partage le cache de Vite : les e2e y tombent au hasard dès qu'une
autre session lance Vite. Le rejeu les rend alors **INCONNU** et donne la
commande qui répare — `rmdir` de la jonction (le lien seul) puis `npm ci` dans
le worktree (#1722, `ci_node_modules_etat`).

🔒 **Un test sauté sur le poste se NOMME** (#1734). Les tests de rendu PDF
(`@besoin_weasyprint`) ne tournent pas ici — WeasyPrint ne s'installe pas sous
Windows — et le rejeu rendait « pytest OK » sur un lot qui les cassait : la CI
de la PR les a vus. L'étape reste OK, mais sa ligne compte et nomme ses sauts par
raison, et le point 16 du pré-check les reprend (`SAUTS=` dans la trace). Un
saut annoncé n'est pas une mesure : ces tests-là, **seule la CI de la PR** les
joue. Mécanisme : le crochet de `api/tests/conftest.py` (`tests/aides_rejeu.py`)
et `ci_resumer_sauts`.

🔒 **Un e2e tombé sur « Failed to fetch dynamically imported module » est relancé
une fois, et cela se dit** (#1809). Quatre rejeux le 10/10/2026 sont tombés sur un
seul test, un autre à chaque passage, que la CI GitHub n'a jamais vu. Le rejeu
relance alors les seuls tests tombés : vert, l'étape reste OK et sa ligne les
nomme, le point 16 les reprend (`RELANCES=`) et chaque relance s'inscrit dans
`rejeu-e2e-relances.log` (répertoire git commun, avec la charge) — la mesure qui
manque pour trouver la cause. Conditions et plafond : `ci_relance_e2e`
(`lib-ci-e2e.sh`) ; un rechargement de Vite (#1421) n'y ouvre jamais droit.

Le **verrou** du rejeu ne se retire que par son propriétaire, et un orphelin se
reprend seul au lancement suivant : ne jamais l'effacer à la main (#1808).

---

## Infrastructure — l'essentiel

Production **HA sur 2 Raspberry Pi** : rpi1 `192.168.1.222` (PhT-RB5), rpi2
`192.168.1.223` (PhT-RB5i2). Les conteneurs ne tournent que sur le **RPi actif**
(`cat /opt/5hostachy/.active`) ; des conteneurs sur les deux = **split-brain**, à
traiter avant toute autre chose. Site HS : SSH sur l'actif →
`cd /opt/5hostachy && . scripts/lib/lib-env-role.sh && env_role_appliquer .env actif && docker compose up -d`.

⚠️ **Le `env_role_appliquer` n'est pas décoratif** : deux réglages du `.env`
dépendent du rôle — `ORIGIN` (nom public pour l'actif, IP locale pour le standby)
et `COOKIE_SECURE` (**absent** chez l'actif, donc `true` par défaut ; `false` chez
le standby). Démarrer la stack sur un nœud dont le `.env` est resté en rôle
standby sert le public avec une origine locale et un cookie de session sans
drapeau `Secure`. C'est le « gap .env du 15/07/2026 ». La règle vit dans
`scripts/lib/lib-env-role.sh` et nulle part ailleurs (#1077).

> 📇 **Les points d'entrée sont versionnés depuis le 15/08/2026** :
> `infra/points-entree/` porte les crons et l'unité systemd attendus, et le
> **point 17** du pré-check compare l'installé au dépôt. C18 ne compare que les
> nœuds entre eux, donc pas la dérive commune.

**Quand** chacun tourne — jour, heure, minutes — se lit dans
`infra/points-entree/cron-root.crontab` (et `cron-ptressard.crontab`), jamais ici :
les minutes y sont **décalées** exprès, et une cadence recopiée dans cette table
écrivait `*/5` là où le dépôt écrit autre chose (#1562).

| Cron root (identique sur les 2 nœuds) | Rôle |
|---|---|
| `bascule.sh` (quotidien, de nuit) | bascule active/standby, puis le nouveau standby pose sa **révision** de noyau et redémarre (`noyau-standby.sh`, #1395) — une nouvelle **série** reste manuelle, C30 la signale avec la commande |
| `maintenance.sh` (hebdomadaire) | purges **demandées à l'API** (`POST /admin/maintenance/purges` — jamais `docker exec … python`, #1232), VACUUM API arrêtée ; sur les **deux** nœuds, images de base re-tirées (#1379) et rotation des logs |
| `health-watch.sh` (toutes les quelques minutes) | failover automatique si le site est HS — et une ligne datée à **chaque** sonde, site OK compris : son battement, que **C31** mesure sur les deux nœuds (#1586). Il se taisait quand tout allait bien, donc rien ne distinguait ce calme d'un failover mort |
| `check-reliability.sh` (quart d'heure) | contrôles de fiabilité numérotés (C8 retiré le 17/07/2026 : il causait les pertes qu'il devait prévenir) + alerte e-mail sur `FAIL`, digest quotidien sur `WARN` — chaque fait envoyé **une fois**, par le nœud qu'il concerne (#1402) —, et constats en cours dans **Admin › Maintenance** (rapport sur changement, **battement à chaque passage** qui dit « dernier contrôle » et rafraîchit les chiffres des constats (#1805), et chaque constat affiché **une fois** — sous le nœud qu'il nomme, ou sous « Les deux nœuds » par l'actif, #1396). ⚠️ La moitié vit dans les modules de `scripts/lib/`, et greper « C25 » dans le script ne le trouve pas. **Où vit chacun** : `grep -rn "── C[0-9]" scripts/` — cette ligne en tenait la liste, et elle plaçait C27 dans le mauvais module (23/09/2026) |

**Les tâches de l'API**, elles, tournent **dans le process** et se déclarent dans
`app/utils/taches.TACHES_PERMANENTES` — avec, pour chacune, **ce qu'on perd** si
elle cesse de tourner. Chacune s'enregistre **par copropriété** :
`scheduler.add_job(contexte.pour_chaque_copropriete(tache, "id"), …, id="id")`, qui la
joue dans le contexte de chacune et isole l'échec de l'une ; une tâche de la
plateforme se déclare dans `TACHES_DE_LA_PLATEFORME` avec sa raison (#1745). Le démarrage compare les tâches réellement enregistrées à
cette table et journalise tout écart en `WARNING` ; `test_taches_planifiees_declarees.py`
le vérifie aussi en CI, dans les deux sens. Aucun des deux ne suffit seul : le test
lit le code, le contrôle au démarrage lit le scheduler (#1047).

⚠️ « Identique sur les 2 nœuds » **est un invariant, pas un constat** : il était faux
jusqu'au 06/08/2026, rpi2 portant en plus un `check-stack.sh` en échec permanent (récit et
chiffres : `mep-precheck/HISTORIQUE.md`, à « check-stack »). Le vérifier fait partie du point 8 du pré-check. `auto-deploy.sh` est
à part : c'est le seul cron **utilisateur** (`ptressard`), et c'est ce qui fait
l'objet du point 11.

**Réflexe avant de suspecter un nœud** : depuis l'autre RPi, `curl
http://<actif>/api/health`. S'il répond 200, la panne est sur le **chemin** public
(box, DNS, Cloudflare) et non sur le nœud — ne pas basculer, ne pas redémarrer la
stack.

Toute intervention infra — bascule, base, WhatsApp, incident, coupure de courant,
panne réseau — commence par charger `.claude/skills/infra-rpi` : protections DB,
conduite à tenir en cas de corruption, panne de chemin ≠ panne de nœud, monitoring
APScheduler, bridge WhatsApp, sync DB manuelle et risques connus.

> 📖 `standards/04-fiabilite-des-controles.md` §10 — le réflexe ci-dessus généralisé :
> **deux sondes indépendantes avant toute décision destructive**, pour distinguer la
> panne d'un composant de celle d'une dépendance partagée · `standards/07-observabilite-et-alertes.md`
> §6–8 (rotation par motif, maintenance sur **tous** les nœuds, hygiène surveillée).

---

## Git & MEP — l'essentiel

**Premier réflexe de toute session, avant le moindre commit.** `origin/dev` et
`origin/main` avancent côté GitHub (PR fusionnées, merges `main → dev`) et ne
redescendent **jamais** seules : sans fetch explicite, le clone local dérive
d'exactement le nombre de PR fusionnées depuis le dernier pull manuel.

```bash
git fetch origin && git merge --ff-only origin/dev
```

Garde-fou mécanique : `.githooks/pre-commit` refuse un commit dont la branche est en
retard sur son upstream. Il est versionné mais doit être armé **une fois par clone** :
`git config core.hooksPath .githooks && git config pull.ff only` — et
`git config blame.ignoreRevsFile .git-blame-ignore-revs`, pour que `blame` saute
les reformatages déclarés (règle d'entrée : `mep-precheck`, piège 4). Contournement
d'urgence : `ALLOW_STALE=1 git commit …`.

> 📖 `standards/08-git-et-versioning.md` §2–3 — un hook versionné **n'est pas** un
> hook actif (il a déjà été committé en `100644`, donc inerte), et Windows avale
> `chmod +x` en silence. Voir aussi la skill globale `avant-commit` : les six
> contrôles de deux minutes, dont `git diff --stat` et l'encodage.
>
> ⚠️ `standards/13-outillage-claude-code.md` §10 — avant de réécrire un fichier
> partagé, regarder `git worktree list` puis `git -C <autre> status` : rien ne
> signale le travail **non committé** d'une session voisine (vécu le 02/08/2026).

- `main` = production **réellement protégée depuis le 09/08/2026** : les jobs de la
  CI et la suite sur PostgreSQL (#1747) sont des *checks requis* — leur liste se lit
  dans la protection (`gh api repos/philippe-tressard/coprofirst/branches/main/protection/required_status_checks`),
  jamais un compte recopié ici —, `enforce_admins` est actif, le push direct et le
  `--force` sont refusés. Toute modification passe par une PR depuis `dev`.
  ⚠️ Cette ligne affirmait « production protégé » alors que GitHub répondait
  « Branch not protected » : rien n'empêchait de fusionner une CI rouge — ce qui
  est arrivé trois fois le 08/08. Une consigne fausse est pire qu'absente.
- Préfixes de commit : `feat:` `fix:` `docs:` `refactor:` `test:` `chore:` `perf:`
- 🔴 **Claude crée ET fusionne la PR `dev → main`, et conduit la MEP** (28/08/2026).
  Cette ligne disait le contraire jusque-là — « Claude s'arrête au push sur `dev` » —
  et c'était l'exemple même de la consigne fausse que le point ci-dessus dénonce.
  La contrepartie demandée n'est pas une validation *avant*, c'est un **compte rendu
  après** : à chaque MEP, **la version et les fonctionnalités apportées**.
  Le pré-check ne s'allège pas pour autant : c'est lui qui remplace la relecture.
  `gh pr create` → attendre **tous les checks requis** → `gh pr merge --squash
  --delete-branch` → **réaligner `dev` sur `origin/main`** (la fusion est un squash
  et supprime la branche distante).
  ⚠️ `gh pr merge --delete-branch` supprime aussi la branche **locale** et bascule
  sur `main` : committer sans regarder `git branch --show-current` met le lot suivant
  sur `main`, où le push est refusé.
- MEP : elle n'est **pas** la fusion. `auto-deploy.sh` (cron utilisateur, toutes les quelques minutes) fait le `git pull`
  **puis** le build : entre les deux, les points 12 et 18 du pré-check échouent
  légitimement — le code est à jour, l'image ne l'est pas. Attendre la ligne
  `Déployé: <sha>` dans `/var/log/hostachy-deploy.log` **sur l'actif**, puis
  post-check. Ne jamais conclure sur le seul `git log` du nœud.
  Reprise en main : `scripts/exploitation/MaJ-Hostachy.sh` sur le **RPi actif**
  uniquement (le script bloque sur le standby)
- **Session cloud** (claude.ai/code) : aucun SSH vers les RPi, et le site public
  est hors de la politique réseau de la session. 🔴 **La MEP s'y enchaîne SANS
  validation intermédiaire** (arbitré le 25/09/2026) : PR du lot vers `dev` →
  fusion dès les checks requis verts → bump de version en **dernier commit** du lot →
  PR `dev → main` → fusion dès ses checks requis verts → **recréer `dev` depuis `main`**
  (la fusion la supprime ; par l'API GitHub, le hook `pre-push` refusant un push
  sans trace de pré-check). Une seule demande de l'utilisateur couvre toute la
  chaîne, et le compte rendu arrive **après** — version et fonctionnalités, comme
  au poste.
  Ce qui ne s'improvise pas : le **pré-check** est INCONNU et la PR le dit ; le
  **post-check** P1–P9 reste au poste (SSH), et le compte rendu le demande. Les
  tickets du lot se ferment à la fusion dans `main`, avec un commentaire qui dit
  que l'observation en production reste à faire (P7, P11).
  ⚠️ Cette ligne disait « le lot s'arrête à une PR vers `dev` » — relayée par la
  bannière de démarrage (`.claude/env-report.sh`) et par `.claude/cloud/LISEZMOI.md`.
  Le 25/09/2026, l'utilisateur a donc dû valider **une à une** la fusion vers
  `dev`, la PR `dev → main`, sa fusion puis la clôture de chaque ticket, deux MEP
  de suite. Les deux relais renvoient désormais ici au lieu de recopier la règle.
  Environnement, setup et ce qui y manque : `.claude/cloud/LISEZMOI.md`.
- `.env` non versionné · `SECRET_KEY` ≥ 32 caractères · `ENABLE_API_DOCS=false` en prod
- Bascule manuelle (test) : `sudo bash /opt/5hostachy/scripts/exploitation/bascule.sh` depuis le RPi actif
  (chemin de **relais** ; le script vit dans `scripts/exploitation/` — cf. #337)

**Aucune MEP sans avoir chargé `.claude/skills/mep-precheck`.** Cette skill porte les
étapes 0 et 0 bis (poste de développement, exigences sans exception), le **pré-check**
(`scripts/poste/precheck-mep.sh`), le **post-check P1–P11**, le rollback, la rétrospective du 26/07/2026 et
l'état de la surveillance continue. Elle porte surtout les trois règles qui priment
sur la liste des contrôles :

1. **Un contrôle qui ne peut pas s'exécuter renvoie INCONNU, jamais OK.**
2. **Ce qui est critique en continu ne doit pas être vérifié seulement en MEP.**
3. **Vérifier le fait, pas le symptôme attendu** — et le comportement, jamais l'artefact.

> 📖 Ces trois règles sont nées ici le 26/07/2026 ; le socle en porte **d'autres**,
> toutes issues d'incidents : `standards/04-fiabilite-des-controles.md`. Elles valent
> aussi pour ce projet — notamment le **cas zéro** (§2), le **battement manquant** (§4), le
> **contrôle sans destinataire** (§7) et **observer la chose, pas son enregistrement**
> (§14), qui ont tous produit un faux vert ici.
> Principes de livraison, pré-check générique et post-check :
> `standards/09-livraison-et-mep.md`.

---

## Versioning (`front/package.json`)

> 📖 `standards/08-git-et-versioning.md` §6 — la règle patch/minor/major, le commit
> dédié, et le bump **d'office** dès qu'une MEP est demandée, sans rappel.

Instanciation 5Hostachy :
- Le fichier est **`front/package.json`** ; la version s'affiche dans le **pied de
  page** du site — c'est ce que contrôle **P3** du post-check.
- …et la version **du projet** dans `front/package-lock.json`, en tête et à la
  racine (`packages[""]`) : deux lignes, jamais une dépendance. `npm run lint:lock`
  refuse l'écart en CI — cette ligne ne nommait que `package.json`, et un bump
  l'a suivie à la lettre le 30/09/2026 (rattrapé au rejeu, pas avant).
- Bump **avant** le push final sur `dev`, commit dédié `chore(version): bump vX.Y.Z`.
- **Chaque commit de `main` publie ses images, le bump y ajoute le tag** (#1753) :
  le workflow `images.yml` publie les images signées des quatre services sur
  `ghcr.io/philippe-tressard/coprofirst-*` (amd64 et arm64, publiques d'office :
  liées au dépôt public), étiquetées `sha-<commit>` ; une version bumpée reçoit en
  plus le tag git `vX.Y.Z` (par `scripts/ci/tag-version.sh`, jamais à la main) et
  l'étiquette d'image `X.Y.Z`. 🔒 `test_images_publiees.py` : la matrice publie
  exactement ce que `docker-compose.yml` construit.
- **Le maître TIRE ces images, il ne les construit plus** (#1758) : `auto-deploy.sh`
  et la bascule passent par `obtenir_images` (`scripts/lib/lib-images-ci.sh`), qui
  tire `sha-<commit>` et les ré-étiquette sous les noms de Compose ; tant qu'elles
  ne sont pas publiées, le journal dit « en attente des images de la CI », et au-delà
  de 30 min le nœud construit en **secours** et alerte (arbitrage du 08/10/2026).
  ⚠️ La fusion n'est donc plus le build : `Déployé:` arrive après la CI « Images »,
  une quinzaine de minutes.
- **Les répliques suivent `replica`, et une version y passe par PROMOTION** (#1754) :
  le workflow « Promotion », lancé à la main par l'auteur (`gh workflow run
  promotion.yml -f version=X.Y.Z`), avance `replica` en avance rapide vers le tag
  et publie les notes de version (release GitHub). `replica` n'a **aucun commit
  propre** — un correctif passe par `main` puis se promeut. Ce qui est VERROUILLÉ
  par les règles du dépôt : `replica` ni supprimée ni réécrite de force, un tag
  `v*` ni déplacé ni supprimé. Ce qui ne l'est PAS — un dépôt personnel ne peut
  pas exempter GitHub Actions (`standards/08` §5 bis) : qui avance `replica` et qui
  pose un tag ; c'est une consigne. Je ne promeus **jamais** de moi-même : c'est la
  décision de l'auteur, après rodage sur le maître (spec §9, question 8).
- **Une réplique s'installe par `deploiement/standard/`** (#1755) : la surcouche
  `compose.images.yml` (`build: !reset`, image publiée à `COPROFIRST_VERSION`)
  se pose sur le `docker-compose.yml` de la racine, qui reste la **seule**
  description des services ; le mode d'emploi est son `LISEZMOI.md`, et l'archive
  de la version est jointe aux notes de version. Les scripts des RPi ne s'y
  déplacent pas (arbitrage du 08/10/2026 : ils ne partent déjà pas avec une
  installation). Le contenu de `front/static/` part tel quel chez toutes : il ne
  nomme jamais la résidence (`npm run lint:nom-residence`, le manuel dit CoproFirst).
- **Une réplique se met à jour seule chaque nuit** (#1756) :
  `deploiement/standard/mise-a-jour.sh` — sauvegarde vérifiée AVANT tout geste,
  retour à l'image précédente puis à la sauvegarde si la santé reste KO, rapport
  `mise_a_jour` (courriel de 06:00 en cas d'échec, `utils/sante_mise_a_jour`).
  Ce retour arrière tient parce que `start.sh` **saute les migrations d'une base
  en avance sur le code** (`utils/revision_base`) : sans lui, l'ancienne image
  s'arrêtait en boucle sur une révision inconnue.
- **Le rôle de l'installation** (#1761) : `ROLE_INSTALLATION` (`maitre` sur les deux RPi,
  `replique` posé d'office par `compose.images.yml`) se lit dans `utils/installation` et
  nulle part ailleurs ; absent → « Inconnu », jamais « Maître ». Le bloc *Installation*
  d'Admin › Maintenance le montre, avec l'écart au dépôt si le service *Vérification de
  la version* est activé (coupé par défaut : rien ne sort sans accord).
- ⚠️ Un onglet PWA resté ouvert peut servir une version en cache : le bandeau de mise
  à jour (v2.24.0) existe pour ça, et `api/tests/test_pwa_maj.py` le verrouille.
