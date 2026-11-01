/**
 * Garde-fou : un écran d'administration doit être atteignable par l'interface.
 *
 * POURQUOI. Le 11/08/2026, trois routes sous `admin/` compilaient, étaient
 * protégées par le layout, avaient leurs endpoints et leur client TypeScript —
 * et **aucun écran n'y menait** (#307). Parmi elles, la configuration des
 * sauvegardes : fréquence, heure et nombre de versions conservées n'étaient
 * réglables par aucun chemin de l'interface. Il fallait connaître l'URL et la
 * taper à la main.
 *
 * Un écran inaccessible est pire qu'un écran absent : son code, ses tests et ses
 * endpoints sont maintenus, la capacité est réputée livrée, et personne ne peut
 * s'en servir. Rien ne pouvait le voir — ni la compilation, ni les tests, ni le
 * contrôle des endpoints orphelins, qui vérifie l'autre bout de la chaîne.
 *
 * 🔴 LE DÉFAUT A CHANGÉ DE FORME LE 19/08/2026, ET LE CONTRÔLE AVEC LUI.
 *
 * Les sept écrans qui vivaient sur leur propre route sont devenus des ONGLETS
 * de `admin/+page.svelte` (arbitré à l'écran : « fiche copropriété et Périmètre
 * sont des pages autonomes alors que les autres sont intégrées au menu
 * Paramétrage »). Il ne reste plus une seule route sous `admin/` — et ce
 * contrôle a fait exactement ce qu'il devait : son CAS ZÉRO a échoué, « 0 route
 * trouvée, ce contrôle ne mesure plus rien ». Il ne s'est pas tu.
 *
 * Mais « un écran que rien ne permet d'atteindre » n'a pas disparu : un onglet
 * rendu sans bouton pour l'ouvrir est le même défaut, à l'identique. Le contrôle
 * couvre donc désormais LES DEUX formes.
 *
 * LA RÈGLE, EN DEUX VOLETS :
 *   A. toute route sous `routes/(app)/admin/` est citée par un `href=` ou un
 *      `goto(`, ailleurs que dans la route elle-même ;
 *   B. les onglets que la table des pages déclare pour `admin` (`pages-roles.ts`)
 *      et les blocs `{#if}` / `{:else if onglet === …}` de `admin/+page.svelte`
 *      concordent EXACTEMENT ; la page rend sa rangée par `BarreOnglets` et lit
 *      sa liste dans la table (01/10/2026 — elle tenait jusque-là sa propre
 *      liste `ONGLETS` et ses boutons écrits à la main).
 *
 * Un onglet déclaré et non rendu affiche une page vide ; rendu sans bouton, il
 * est inatteignable ; bouton sans rendu, il ne montre rien. Les trois sont
 * silencieux, et aucun ne fait échouer la compilation.
 *
 * Une exception se déclare dans `TOLEREES`, avec sa raison. Si la raison ne tient
 * pas en une ligne, c'est probablement que la route doit être supprimée ou reliée.
 * Les deux sens sont vérifiés : une tolérance qui a retrouvé un lien fait échouer
 * le contrôle, sinon la liste se remplit et ne protège plus rien.
 *
 * Le contrôle s'auto-contrôle : s'il n'analyse aucun fichier ou ne trouve aucune
 * route, il ÉCHOUE au lieu de conclure au vert
 * (`standards/04-fiabilite-des-controles.md` §2, cas zéro).
 */
import { readFileSync, readdirSync, statSync, existsSync } from 'node:fs';
import { join } from 'node:path';
import { blocsDePages } from './lib-pages.mjs';

const RACINE = new URL('../src', import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, '$1');
const ADMIN = join(RACINE, 'routes', '(app)', 'admin');

/**
 * Routes admin légitimement sans lien, avec la raison.
 *
 * ⚠️ Une entrée ici est une décision consciente, pas un contournement.
 */
/**
 * Routes admin légitimement sans lien, avec la raison.
 *
 * ⚠️ Une entrée ici est une décision consciente, pas un contournement.
 *
 * VIDE depuis le 19/08/2026 : la seule entrée était `templates-email`, doublon
 * partiel de l’onglet « Modèles e-mail ». Il est devenu l’onglet « Designs
 * e-mail » — donc atteignable, donc plus rien à tolérer. La question du doublon,
 * elle, reste entière et appartient à #307 : les deux écrans montrent la même
 * donnée sous deux angles, et les fusionner est une décision fonctionnelle.
 */
const TOLEREES = {};

function fichiers(dir) {
	const sortie = [];
	for (const nom of readdirSync(dir)) {
		const chemin = join(dir, nom);
		if (statSync(chemin).isDirectory()) sortie.push(...fichiers(chemin));
		else if (/\.(svelte|ts|js)$/.test(nom)) sortie.push(chemin);
	}
	return sortie;
}

if (!existsSync(ADMIN)) {
	console.error(`✗ Routes admin introuvables (${ADMIN}) — contrôle inopérant.`);
	process.exit(1);
}

//  Sous-répertoires de `admin/` portant une page : ce sont les routes à atteindre.
const routes = readdirSync(ADMIN).filter(
	(nom) => statSync(join(ADMIN, nom)).isDirectory() && existsSync(join(ADMIN, nom, '+page.svelte')),
);

const tous = fichiers(RACINE);
if (tous.length === 0) {
	console.error("✗ Cas zéro : aucun fichier analysé — l'arborescence a changé.");
	process.exit(1);
}

//  ⚠️ `routes.length === 0` n'est PLUS un cas zéro : c'est l'état attendu depuis
//  que les sept écrans sont devenus des onglets. Le cas zéro a déménagé avec le
//  défaut — il porte maintenant sur le nombre d'ONGLETS (voir plus bas).

const orphelines = [];
const tolereesLiees = [];

for (const route of routes) {
	//  On cherche le lien PARTOUT sauf dans la route elle-même : une page qui
	//  se cite (un onglet interne, un retour) ne la rend pas atteignable.
	const dossier = join(ADMIN, route) + '/';
	const motif = new RegExp(
		`(href=["'\`][^"'\`]*|goto\\(\\s*["'\`][^"'\`]*)/admin/${route}(?![\\w-])`,
	);
	const lie = tous.some((f) => !f.startsWith(dossier) && motif.test(readFileSync(f, 'utf8')));

	if (!lie && !(route in TOLEREES)) orphelines.push(route);
	if (lie && route in TOLEREES) tolereesLiees.push(route);
}

let echec = false;

if (orphelines.length > 0) {
	echec = true;
	console.error("✗ Écran(s) d'administration qu'aucun lien ne permet d'atteindre :");
	for (const r of orphelines) console.error(`    /admin/${r}`);
	console.error(
		"\n  Ajouter un lien (`href`) depuis l'écran qui les porte, supprimer la route si\n" +
			'  elle fait doublon, ou la déclarer dans TOLEREES avec sa raison.',
	);
}

const tolereesFantomes = Object.keys(TOLEREES).filter((r) => !routes.includes(r));
if (tolereesFantomes.length > 0) {
	echec = true;
	console.error('\n✗ Tolérance(s) désignant une route qui n’existe plus :');
	for (const r of tolereesFantomes) console.error(`    /admin/${r} — retirer l'entrée de TOLEREES`);
	console.error('  Une dérogation pour un écran disparu ne protège rien et masque la suivante.');
}

if (tolereesLiees.length > 0) {
	echec = true;
	console.error('\n✗ Tolérance(s) devenue(s) inutile(s) — un lien existe désormais :');
	for (const r of tolereesLiees) console.error(`    /admin/${r} — retirer l'entrée de TOLEREES`);
}

// ── Volet B : les onglets de `admin/+page.svelte` ───────────────────────────
//  Trois listes doivent concorder. Elles sont lues À LA SOURCE, jamais recopiées
//  ici : une quatrième liste dans le contrôle divergerait au premier ajout, et
//  c'est exactement le défaut que `lint:consignes` garde ailleurs (#482).
const ONGLETS_MINIMAUX = 15;
const PAGE_ADMIN = join(ADMIN, '+page.svelte');
if (!existsSync(PAGE_ADMIN)) {
	console.error(`✗ INCONNU : ${PAGE_ADMIN} est introuvable — ce contrôle ne conclut pas.`);
	process.exit(1);
}
const srcAdmin = readFileSync(PAGE_ADMIN, 'utf8');

//  🔴 La déclaration a quitté la page le 01/10/2026 : les onglets d'Admin vivent
//  dans la table des pages (`pages-roles.ts`, bloc `admin`), comme ceux des
//  autres pages, et `BarreOnglets` les rend. Le volet « un bouton par onglet »
//  est donc tenu par construction ; restent la déclaration, la LECTURE de la
//  table par la page, et le rendu.
const blocAdmin = blocsDePages().find((b) => /^\t\tid: 'admin',/m.test(b));
if (!blocAdmin) {
	console.error('✗ INCONNU : le bloc de la page `admin` est introuvable dans la table des pages.');
	console.error("  Sans lui, il n'y a plus de liste qui fasse foi, et ce contrôle ne conclut pas.");
	process.exit(1);
}
const declares = [...blocAdmin.matchAll(/^\t\t\t\tid: '([a-z_]+)',/gm)].map((m) => m[1]);
//  La page doit RENDRE la rangée de la table et LIRE sa liste — sans quoi un
//  onglet déclaré n'aurait pas de bouton, ou ne s'ouvrirait pas par l'adresse.
const lienTable = [
	[/<BarreOnglets[^>]*pageId="admin"/, 'rendre sa rangée par <BarreOnglets pageId="admin">'],
	//  Par `ongletsOuverts` depuis #2029 : la table, filtrée par les droits de
	//  qui regarde — l'opérateur qui n'est pas administrateur n'en a que deux.
	[/ongletsOuverts\('admin',/, 'lire ses onglets dans la table (`ongletsOuverts`)'],
];
for (const [motif, attendu] of lienTable) {
	if (!motif.test(srcAdmin)) {
		echec = true;
		console.error(`\n✗ admin/+page.svelte ne sait plus ${attendu}.`);
	}
}
const rendus = new Set(
	[...srcAdmin.matchAll(/\{(?:#if|:else if) onglet === '([a-z_]+)'\}/g)].map((m) => m[1]),
);
//  Les onglets qui ne reçoivent rien de la page passent par UNE branche et une
//  table de chargeurs (#2442) : `{:else if onglet in TABLE}` rend chaque clé de
//  `const TABLE = { cle: () => import(…), … }`. Une table que nulle branche ne lit
//  ne rend rien — ses clés restent alors « sans rendu ».
for (const [, table] of srcAdmin.matchAll(/\{(?:#if|:else if) onglet in (\w+)\}/g)) {
	const debut = srcAdmin.search(new RegExp(`const\\s+${table}\\b[^{]*\\{`));
	const corps = debut < 0 ? '' : srcAdmin.slice(debut, srcAdmin.indexOf('};', debut));
	for (const [, cle] of corps.matchAll(/^\t+([a-z_]+): \(\) => import\(/gm)) rendus.add(cle);
}

if (declares.length < ONGLETS_MINIMAUX) {
	console.error(
		`✗ Cas zéro : ${declares.length} onglet(s) déclaré(s), ${ONGLETS_MINIMAUX} attendus au minimum.`,
	);
	console.error(
		"L'administration en portait 19 le 19/08/2026. Un effondrement du relevé dit que\n" +
			'le contrôle a cessé de voir, pas que le défaut a disparu.',
	);
	process.exit(1);
}

const sansRendu = declares.filter((o) => !rendus.has(o));
const nonDeclares = [...rendus].filter((o) => !declares.includes(o));

if (sansRendu.length) {
	echec = true;
	console.error('\n✗ Onglet(s) déclaré(s) que RIEN ne rend — la page serait vide :');
	for (const o of sansRendu) console.error(`    ${o}`);
	console.error("  → ajouter un bloc {:else if onglet === '…'}, ou retirer l'entrée.");
}
if (nonDeclares.length) {
	echec = true;
	console.error('\n✗ Onglet(s) employé(s) sans figurer dans `ONGLETS` :');
	for (const o of nonDeclares) console.error(`    ${o}`);
	console.error("  → la table fait foi : l'y ajouter, sinon aucun bouton ne l'ouvrira.");
}

if (echec) process.exit(1);

console.log(
	`✓ Écrans d'administration atteignables : ${routes.length} route(s) ` +
		`(${Object.keys(TOLEREES).length} tolérée(s)), et ${declares.length} onglet(s) ` +
		'déclarés, tous munis de leur bouton et de leur rendu.',
);
