---
name: svelte-patterns
description: "Create SvelteKit pages and components following 5Hostachy conventions: page structure, data loading, stores, API client, CSS variables, accessibility. Use when: creating a new page, creating a new component, refactoring a Svelte page, adding a frontend feature."
argument-hint: "Describe the page or component to create (e.g. 'page fournisseurs with list + detail modal')"
---

# Svelte Patterns — 5Hostachy

Conventions et patterns pour créer des pages et composants SvelteKit dans le projet.

## Structure d'une page standard

### Imports obligatoires

```svelte
<script lang="ts">
	import Icon from '$lib/components/Icon.svelte';
	import { onMount } from 'svelte';
	import { isCS, isAdmin, currentUser } from '$lib/stores/auth';
	import { entity as entityApi, ApiError, type Entity } from '$lib/api';
	import { getPageConfig, configStore, siteNomStore } from '$lib/stores/pageConfig';
	import { safeHtml } from '$lib/sanitize';
	import { toast } from '$lib/components/Toast.svelte';
	import { fmtDate, fmtDatetime } from '$lib/date';
	import { fmtMontant, perimetreLabel } from '$lib/utils';
</script>
```

### Page Config (titre dynamique via admin)

Les valeurs par défaut vivent dans `$lib/pages.ts` et **nulle part ailleurs** :
`defautsDePage('page-id')`, jamais un objet recopié dans l'écran (#420). Titre,
icône et descriptif passent par `EntetePage` — jamais un `<h1>` ni un
`page-subtitle` écrits à la main (`npm run lint:entetes`, #1369).

```svelte
<script lang="ts">
	import EntetePage from '$lib/components/EntetePage.svelte';
	import { configStore, getPageConfig, defautsDePage, siteNomStore } from '$lib/stores/pageConfig';

	$: _pc = getPageConfig($configStore, 'page-id', defautsDePage('page-id'));
	$: _siteNom = $siteNomStore;
</script>

<svelte:head>
	<title>{_pc.titre} — {_siteNom}</title>
</svelte:head>

<EntetePage titre={_pc.titre} descriptif={_pc.descriptif} icone={_pc.icone || 'nom-icone'} />
```

Le descriptif d'**onglet** est rendu par `BarreOnglets`, sous la rangée ; il se
tait quand il répète mot pour mot celui de la page (`ux-patterns` §13).

### Chargement des données

```svelte
<script lang="ts">
	import EtatListe from '$lib/components/EtatListe.svelte';

	let items: Entity[] = [];
	let chargement = true;
	let erreur = '';

	onMount(async () => {
		try {
			items = await entityApi.list();
		} catch (e) {
			erreur = messageErreur(e);
		} finally {
			chargement = false;
		}
	});
</script>

<EtatListe {chargement} {erreur} vide={items.length === 0}>
	{#each items as item (item.id)}
		<!-- contenu -->
	{/each}
</EtatListe>
```

🔴 **Cet exemple portait le motif à deux branches** — `{#if loading}` puis
`{:else if items.length === 0}` — que `npm run lint:etat-liste` refuse. Il
laissait toujours un état de côté, et c'était l'**erreur** : un appel en échec
s'affichait comme une liste vide, donc comme « il n'y a rien » au lieu de « je
n'ai pas pu regarder ».

C'est le **cas zéro** de `standards/04` appliqué à un écran : une absence
d'information ne se rend pas comme une information d'absence. `EtatListe`
porte les trois états, et `messageErreur` (`$lib/erreurs.ts`) porte le texte.

#### Ce qui dépend du rôle : `quandAuthResolue`, jamais `onMount`

🔴 Svelte monte la **page avant le layout** : l'`onMount` d'un écran précède
celui de `(app)/+layout.svelte`, qui charge l'utilisateur. Sur un chargement
direct ou un rechargement, `$isCS`, `$isLocataire`, `$currentUser`… y valent
encore `false` / `null` — seule une navigation interne rend l'écran juste, et
c'est la seule qu'on essaie à la main (#1486 : huit écrans, dont un bailleur qui
voyait tous ses lots « Vacant »).

Un chargement qui lit un rôle — même par une fonction locale qu'il appelle —
passe par `quandAuthResolue(action)` (`$lib/stores/auth`), qui l'exécute une
fois, quand l'utilisateur est connu. L'`onMount` reste pour ce qui ne dépend de
personne. 🔒 `npm run lint:gardes-auth` refuse un rôle lu dans un `onMount`, et
son e2e type est `e2e/role-au-chargement-direct.spec.ts`.

### Un nombre saisi : `nombreOuNull`, jamais une conversion à la main

🔴 Un `<input type="number" bind:value>` **vidé rend `null`**, pas `''`. Une
conversion `v === '' ? null : Number(v)` l'envoie donc à **0** — un relevé de
consommation enregistré à 0 m³, un nombre de lots à 0 (#1516, #779) ; et
`v ? Number(v) : null` efface un 0 réellement saisi. La règle vit dans
`nombreOuNull` (`$lib/utils`) ; 🔒 `npm run lint:nombre-saisi` refuse la forme
recopiée, et `e2e/nombre-saisi` tient le comportement.

### Gestion d'erreurs API

Un message d'erreur ne se rédige pas dans un écran : il vient de
**`$lib/erreurs.ts`** (`messageErreur`), que tous les écrans emploient. Deux écrans qui
formulent le même échec autrement apprennent deux choses différentes à
l'utilisateur pour un seul fait.

🔒 `npm run lint:message-erreur` refuse la formulation locale, et
`npm run lint:catch-vide` refuse un échec rendu comme une absence : le repli
`.catch(() => [])`, et le `catch` muet d'un `try` qui affecte une variable
après son `await` (#1459) — l'écran lirait sa valeur initiale comme une réponse.
Un silence légitime se déclare dans `MUETS_DECLARES`, avec sa raison.

⚠️ **L'API de `toast` est `toast('error', message)`**, jamais `toast.error(…)` :
cette section enseignait la seconde forme, qui n'existe nulle part
(`Toast.svelte`). Une consigne qui décrit une API absente fait écrire du code qui
ne compile pas — et, pire, fait douter du composant plutôt que de la consigne.

### Chargement et listes vides

**`EtatListe`** porte les trois états d'une liste : en cours, vide,
en erreur. Une page ne compose plus ces états elle-même.

🔒 `npm run lint:etat-liste` refuse le motif à deux branches
(`{#if chargement}…{:else if !items.length}…`) qui laissait toujours un état de
côté — le plus souvent l'erreur, affichée comme une liste vide. La troncature de
l'aperçu d'une carte (3 lignes) est tenue par `npm run lint:clamp` ; `lint:apercu`,
lui, ne regarde que l'aperçu de **diffusion** (`ApercuDiffusion`, #498).

🔴 **L'attente s'écrit `<EtatListe chargement />`** — ou `messageChargement="…"`
pour un message propre à l'écran —, jamais un paragraphe. Cette section affirmait
que `<p>Chargement…</p>` écrit à la main « n'existait plus nulle part » : il y en
avait **vingt-trois** le 24/09/2026, sous cinq allures, dont une copie de la
classe `.etat-chargement` d'`EtatListe` avec son style (#1045). 🔒
`npm run lint:chargement` refuse le suivant ; un bouton qui attend
(`{envoi ? 'Chargement…' : label}`) n'est pas concerné.
`$lib/chargement.ts` porte `essayer` et `messagePartiel` (elle ne porte pas de
libellés, contrairement à ce que disait cette ligne), et `ChargementPartiel` le
cas d'un bloc qui se recharge seul.

## Pattern: Onglets (Tabs) — un onglet est une ADRESSE

🔴 Depuis le 05/09/2026, un onglet n'est plus un état local : c'est une **route**.
On ne l'affecte pas, on y navigue. Le détail (forme des URL, redirection des
anciennes, masquage vs redirection) est dans `ux-patterns` §4.

```svelte
<!-- src/routes/(app)/tickets/+page.ts — la page ne bouge pas -->
import { resoudreOnglet } from '$lib/deepLink';

export const load = ({ url }) => resoudreOnglet('mes-demandes', url);
```

`/tickets/kanban` arrive sur cette même route : `reroute` (`src/hooks.ts`) l'y
envoie, et `url` reste l'adresse demandée.

```svelte
<!-- src/routes/(app)/tickets/+page.svelte -->
<script lang="ts">
	import BarreOnglets from '$lib/components/BarreOnglets.svelte';

	export let data: { onglet: string; sous: string | null };
	$: onglet = data.onglet;
</script>

<BarreOnglets pageId="mes-demandes" actif={onglet} />

{#if onglet === 'liste'}
	<!-- contenu liste -->
{:else if onglet === 'archives'}
	<!-- contenu archives -->
{/if}
```

⚠️ **Ne pas écrire la rangée à la main** : `BarreOnglets` lit la liste, l'ordre, les
libellés (configurables en administration) et les routes dans `$lib/pages.ts`, et
rend chaque onglet en `<a>`. Un `<div class="tabs">` local rouvre les cinq
divergences que ce composant vient de fermer.

## Pattern: Carte de liste — **trois composants, aucun balisage à écrire**

🔴 Cette section décrivait un motif écrit à la main — conteneur
`role="button"`, `.ev-expand`, `expandedItems = new Set()`, `.clamp-5`. **Il n'en
reste aucune occurrence**, et trois linters refusent de le voir revenir.

| Ce qu'il faut | Composant / module | Contrôle |
|---|---|---|
| l'en-tête d'une carte (titre, icônes, chevron) | `EnteteCarte` | `lint:entete-carte` — **exceptions vides** |
| l'aperçu du contenu, coupé à 3 lignes | `ApercuCarte` | `lint:clamp` |
| l'ouverture / fermeture d'un élément de liste | `$lib/listeDepliable.ts` | `lint:liste-depliable` |
| les pastilles d'état | `Pastille` | `lint:statuts`, `lint:etats` |
| le périmètre affiché | `BadgePerimetre` | `lint:libelle-perimetre`, `lint:teinte` |

⚠️ **`role="presentation"`, pas `role="button"`** sur le conteneur : le geste
d'ouverture appartient au chevron d'`EnteteCarte`, qui porte déjà son nom
accessible et son `keydown`. Un conteneur cliquable annonçait « bouton » un bloc
qui contient lui-même des boutons.

La **densité** d'une carte (ce qui va sur quelle ligne, et ce qui est masqué en
collapsé) est arbitrée dans `ux-patterns` §13 bis — elle a été validée à l'écran,
elle ne se redécide pas ici.

## Pattern: Où s'ouvre un formulaire — **c'est arbitré, pas au choix**

🔴 Cette section enseignait un `<div class="modal-overlay">` écrit à la main,
avec `showModal` et `.modal-actions`. **`npm run lint:modales` le refuse**, et
`.modal-actions` n'existe pas.

Le **cadre du geste** est tranché (`ux-patterns` §14 à §14 ter, validé à l'écran
après quatre positions essayées) :

| Geste | Où |
|---|---|
| **créer** | en place, dans la page (`FormulaireCreation`, via `CadreFormulaire`) — **jamais** une modale |
| **modifier** | **dans la carte**, à la place de son corps (`ux-patterns` §14 ter) — `<Modale edition>` est **refusée** par `lint:geste-edition`, ses écarts sont déclarés ; `Modale` reste pour les confirmations, aperçus et gestes courts |
| **faire évoluer** | `EvolForm`, qui reçoit son `entite: EntiteDeclaree` |

🔒 `npm run lint:cadre-geste` et `npm run lint:geste-edition` tiennent cette
règle ; `lint:pied-formulaire` impose `PiedFormulaire` pour les
boutons, `lint:ordre-sections` l'ordre des sections, `lint:champs` le libellé
d'un champ, et `lint:section-formulaire` leur découpe.

Un formulaire ne compose donc plus ni son enveloppe, ni son pied, ni l'ordre de
ses sections : il déclare son contenu.

## Avant d'écrire un composant : la famille existe peut-être déjà (#1561)

« Grep le pattern existant » est la seule consigne qui couvrait ces familles, et
elles sont les plus réutilisées de `$lib/components/`. **Une ligne de routage par
famille** — l'usage se compte en cherchant l'import du composant sous `front/src`, il ne
s'écrit pas ici :

| Ce qu'on écrit | Ce qui existe | Où lire pourquoi |
|---|---|---|
| une **section** de formulaire | l'enveloppe est `SectionFormulaire` (intitulé, filet, pliage) ; le contenu partagé entre écrans est un `Section<Nom>` : `SectionQuand`, `SectionPerimetre`, `SectionEquipement`, `SectionDiffusion`, `SectionDestinataires`, `SectionAffairesLiees`, `SectionOptionsPublication`, `SectionDescription`…, et `SectionsSuiteConseil` pour ce que le conseil pose dans une Suite. Elle se **déclare** dans `$lib/entites/<entité>` (`CLAUDE.md`, checklist front) | l'en-tête du composant |
| un **onglet d'administration** | un composant `Onglet<Nom>` (`OngletSmtp`, `OngletWhatsApp`, `OngletConsommations`, `OngletPerimetres`, `OngletAcces`…) : l'état et les appels réseau vivent **dedans**, la page ne garde que le choix de l'onglet — c'est ce qui la garde sous le plafond de modularité. `Onglet.svelte` est, lui, le **bouton** d'une rangée | `OngletSmtp.svelte` (même forme que `OngletWhatsApp`) |
| un onglet **qui n'est pas celui par défaut**, ou un formulaire qui ne s'ouvre qu'au geste (✏️, « Répondre », « Nouvelle… ») | `ChargementDiffere` : la page passe l'`import()`, le composant revient typé par le snippet `contenu`. Importé en tête de page, il entre dans l'**ouverture** de l'écran — `/admin` téléchargeait ses seize onglets pour en afficher un (298 → 94 Ko compressés, 11/10/2026). 🔒 `npm run lint:poids-ouverture` (après le build) refuse qu'un composant ainsi confié soit chargé d'emblée par un écran | `ChargementDiffere.svelte` |
| un **formulaire d'entité** | un `Formulaire<Entité>` qui sert la création **et** la correction (`FormulaireBail`, `FormulaireAnnonce`, `FormulaireSondage`, `FormulaireAnnonceHall`…) ; ses seules différences se passent par props (`avecLots`, `avecDateEntree`). Ne pas le réécrire dans un écran | `FormulaireBail.svelte` |
| « **qui est prévenu ?** » | `CanauxNotification` (WhatsApp, syndic, conseil), puis `ApercuDiffusion` pour voir ce qui partira avant de confirmer | `CanauxNotification.svelte` |
| le **fil d'une affaire**, liste et fiche | `HistoriqueTicket` — un seul câblage pour les deux rendus | `HistoriqueTicket.svelte` |
| un bandeau « 📁 Historique (n) ▼ » | `SectionRepliee` | `SectionRepliee.svelte` |
| une case 🔒 « visible du seul périmètre sélectionné » | `CaseReservePerimetre` | `CaseReservePerimetre.svelte` |
| un mot de passe | `ChampMotDePasse` (bascule, jauge, « Verr. Maj. ») | idem |
| les actions d'une carte d'actualité | `ActionsActualite` | idem |
| le tableau des tâches planifiées | `TachesPlanifiees` (prévu **et** arrivé, ensemble) | idem |
| un **état** (libellé, classe de pastille, aide) qui se décline par clé | `$lib/table-statuts.ts` — une table, ses colonnes s'en déduisent | l'en-tête du module |
| le **type d'un accès** (Vigik, télécommande) | `$lib/types-acces.ts` | idem |

⚠️ Côté serveur, les familles équivalentes (`utils/cloche`, `utils/nature_affaire`…)
sont routées dans `api-scaffold`.

## Helpers de formatage — **à importer, jamais à réécrire**

Les formats de date et de montant sont **centralisés**. Une page qui redéfinit
`fmtDate` localement casse la cohérence et **échoue en CI**.

```svelte
<script lang="ts">
	// $lib/date.ts — TOUTES les dates affichées (locale fr-FR + TZ Europe/Paris figés)
	import { fmtDate, fmtDateLong, fmtDateShort, fmtDatetime, fmtTime, fmtMonthYear } from '$lib/date';
	// $lib/utils.ts — montants, périmètre, extraits HTML
	import { fmtMontant, perimetreLabel, stripHtml } from '$lib/utils';
</script>
```

| Helper | Entrée → sortie |
|---|---|
| `fmtDate(d)` | `'2026-07-25'` → `25/07/2026` |
| `fmtDatetime(d)` | horodatage → date + heure de Paris |
| `fmtMontant(v)` | `1234` → `1 234 €` · `1234.5` → `1 234,50 €` · `null` → `—` |
| `perimetreLabel(items)` | `['bat:1','parking']` → `Bât. 1 · Parking` |

**Interdits, vérifiés par `npm run lint:dates`** (sur `front/src/` **et**
`vite.config.ts`) : `toLocaleDateString`, `toLocaleTimeString`,
`Intl.DateTimeFormat` et `new Date(…).toLocaleString` **sans `timeZone`**. Restent
autorisés : `toISOString()` seul (sérialisation UTC d'un payload d'API) et
`toLocaleString()` sur un **nombre** — ce n'est pas une date.

Un alias local qui délègue au helper partagé (`const formatDate = fmtDatetimeShort`)
est une indirection inutile : appeler directement le helper.

🔴 **Et il n'y a plus d'exception.** Cette section en déclarait une — le rendu
d'une description mixte texte/HTML, « le seul helper qui reste légitimement
local » — dont le corps était :

```svelte
	function renderDesc(c: string) {          // ⚠️ NE PLUS ÉCRIRE CECI
		const t = c.trimStart();
		return safeHtml(t.startsWith('<') ? c : `<p>${c.replace(/
/g, '<br>')}</p>`);
	}
```

C'est **exactement** `safeDescription`, exportée par `$lib/sanitize.ts` — laquelle
a été créée pour supprimer ce helper, alors écrit en double sous le nom `renderDesc`
dans deux pages. **La consigne a survécu à la factorisation qu'elle décrivait.**

Le résultat était prévisible : `tickets/[id]` en portait une **troisième** copie,
sous le nom `renderContent`, jusqu'au 19/08/2026 (#429). Une skill qui enseigne un
motif supprimé le fait réapparaître — c'est la duplication qui se reproduit par sa
propre documentation.

```svelte
	import { safeDescription } from '$lib/sanitize';
	…
	{@html safeDescription(contenu)}
```

## CSS : où vivent les règles

🔴 **`app.css` ne porte plus aucune règle** depuis le 27/08/2026 (#453) : il n'a
gardé que ses `@import` vers `src/styles/*.css`. Les deux skills l'annonçaient
encore comme « le fichier des règles globales », à onze endroits.

| Fichier | Ce qu'il porte |
|---|---|
| `src/styles/socle.css` | les **variables** (couleurs, rayon, ombre) et la base |
| `src/styles/ecrans.css` | les classes partagées entre écrans |
| les autres `src/styles/*.css` | par domaine — voir les `@import` d'`app.css` |

**La liste des variables n'est pas recopiée ici** : elle se lit dans
`socle.css`, où chacune porte son usage en commentaire. Cette section en listait
douze alors que le fichier en déclarait bien davantage — une liste recopiée est
fausse dès qu'on en ajoute une, et personne ne relit une consigne qu'on n'a pas
touchée.

🔒 `npm run lint:styles`, `lint:classes-nues`, `lint:css-duplique`,
`lint:css-orphelin` et `lint:charte` tiennent l'usage des couleurs et des
classes. `lint:points-rupture` impose les points de rupture de l'échelle
déclarée, et `lint:largeur-saisie` interdit d'écrire une largeur dans un écran —
`--largeur-saisie` est **généralisée** depuis le 18/08/2026, et la constante
`ROUTES_LARGEUR_PLEINE` qui la limitait à une route n'existe plus.

## Sécurité XSS

**OBLIGATOIRE** : tout `{@html}` passe par une fonction de `$lib/sanitize.ts`.
Elles sont **trois**, toutes adossées à DOMPurify — cette section n'en nommait
qu'une alors que les trois étaient en service, ce qui faisait lire 19 usages
conformes comme autant d'écarts (#429) :

| Fonction | Quand |
|---|---|
| `safeHtml` | contenu déjà en HTML riche |
| `safeRichContent` | riche **ou** texte simple, **sans** enveloppe — à l'intérieur d'un `<p>` |
| `safeDescription` | riche **ou** texte simple, **avec** enveloppe `<p>` |

```svelte
<!-- ✗ INTERDIT -->
{@html contenu}

<!-- ✗ INTERDIT AUSSI : une fonction locale, même correcte, même homonyme -->
{@html monRenduLocal(contenu)}

<!-- ✓ CORRECT -->
{@html safeDescription(contenu)}
```

🔒 **`npm run lint:html` le vérifie en CI.** Ce qu'il exige et ses exceptions :
`CLAUDE.md`, règle front n° 1 — la seule copie. Celle-ci en recopiait la date et
la liste, et la date divergeait déjà (claude-config#122).

## Emojis (y compris hors du plan de base, U+10000 et au-delà)

**Un caractère qu'on peut lire s'écrit en clair** — emoji et symboles compris :
`const icon = '🔧';`, `🔹` dans un gabarit. C'est la règle du dépôt, et son
garde-fou est `api/tests/test_echappements_source.py` (périmètre `api`,
`front/src`, `front/scripts`, `scripts`), qui refuse `\uXXXX` et `\UXXXXXXXX`
pour tout caractère imprimable. Seuls restent échappés les caractères qu'on ne
voit pas (espace insécable, sélecteur de variante, contrôles).

Le risque Windows — un emoji qui « survit mal » à un aller-retour — se tient par
l'**encodage du fichier** (UTF-8 sans BOM, `standards/10`), pas par l'échappement :
écrire la forme à accolades ou l'entité numérique rend le source illisible à la
relecture, qui est le seul contrôle d'un libellé. ⚠️ Ces deux formes-là ne sont pas
attrapées par le test (il ne reconnaît ni l'une ni l'autre) et le code en porte
encore ; ne pas en ajouter, et les écrire en clair quand un lot touche la ligne.
Cette section enseignait jusqu'au 02/10/2026 l'inverse (« les encoder »), contre le
test du dépôt (#1557).

## Accessibilité

La règle : `standards/11-interface-et-ux.md` §2 (seule copie) ; son instanciation, `CLAUDE.md` —
« Front », règle 3 ; ce qu'en vérifie la CI : `npm run lint:a11y`.

🔴 Cette section en portait une septième copie, avec une ligne **fausse** depuis
le 22/09/2026 — « Labels : `Titre *` (astérisque pour les champs requis) », là
où la règle est `<EtoileRequis vide={!champ} />` et où `lint:champs` refuse
l'astérisque tapée (claude-config#122, 24/09/2026).

## Archivage vs Suppression

**On archive, on ne supprime pas** : la vue principale masque ce qui est
archivé, et `ListeEtArchives` / `ArchivesParAnnee` en donnent l'accès.
`npm run lint:archives` tient cette règle.

**Deux façons de quitter la liste**, et c'est `ux-patterns` §8 et §16 qui font
foi — cette section n'en recopie que ce qu'un écran doit savoir :

- **le temps** : `archivee` est calculé côté serveur (`utils/archivage.REGLES`) —
  annonces, idées, sondages, affiches, affaires résolues. Jamais recalculé ici ;
- **le geste 📦 du conseil** : affaires, actualités (`archive_manuel`),
  prestataires et contrats (`PATCH …/archivage`, #1538). Le bouton porte
  `aria-label="Archiver"` et l'icône 📦 — **jamais 🗑️**, qui dit « supprimer ».
  Le pendant aux Archives est ↩️ Restaurer. La confirmation passe par `ARCHIVAGE`
  ou `archiverPuis` (`$lib/confirmation`), jamais une phrase écrite dans l'écran.

🔴 Cette section affirmait jusqu'au 02/10/2026 *« il n'y a pas de bouton 📦 »* —
démenti depuis le 24/09 par les affaires (#1555). Une consigne qui nie un geste
existant le fait réécrire en 🗑️ : c'est exactement ce que portaient les cartes
des prestataires et des contrats (#1538).

La **suppression définitive** reste possible pour un administrateur, et c'est le
seul cas : `require_admin` côté API.
