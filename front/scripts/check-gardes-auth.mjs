#!/usr/bin/env node
// SPDX-FileCopyrightText: 2026 Philippe Tressard
// SPDX-License-Identifier: AGPL-3.0-or-later
/**
 * Un garde de route refuse sur un « non » avéré, jamais sur un « pas encore ».
 *
 * ## Le défaut, et sa récidive (#1083, audit du 19/09/2026)
 *
 * `stores/auth.ts` porte la distinction, écrite noir sur blanc :
 *
 * > `isAuthenticated` vaut faux dans **deux** cas très différents : « pas
 * > connecté » et « on ne sait pas encore ». `authResolue` les sépare.
 *
 * Elle existe parce qu'un garde l'avait confondue : `admin/+layout.svelte`
 * testait `$isAdmin` dans son `onMount`, pendant que `(app)/+layout.svelte`
 * chargeait encore l'utilisateur. Il décidait donc toujours sur une valeur vide,
 * et **toute adresse `/admin/**` ouverte directement — lien partagé, favori, F5 —
 * renvoyait au tableau de bord, y compris pour un administrateur.** En navigation
 * interne l'utilisateur est déjà chargé : le défaut était invisible.
 *
 * 🔴 **Corrigé le 12/08/2026 sur `/admin`, et reproduit à l'identique sur
 * `/espace-cs`** — même `onMount`, même store de rôle, même conséquence pour un
 * membre du conseil syndical. Un an de commentaires explicatifs dans `auth.ts`
 * n'a pas empêché la deuxième occurrence : c'est le motif exact que les
 * garde-fous existent pour couvrir (`standards/05` §1).
 *
 * ## Ce que ce contrôle refuse
 *
 * Une redirection qui dépend d'un store de rôle **sans** consulter `authResolue`,
 * quel que soit l'endroit où elle est écrite — `onMount`, bloc réactif, fonction.
 * C'est la conjonction qui compte : rediriger est légitime, tester un rôle aussi ;
 * faire les deux sans savoir si la réponse est connue ne l'est pas.
 *
 * ⚠️ Ce qu'il ne regarde PAS : les redirections qui ne dépendent d'aucun rôle
 * (retour après une action, lien profond). Elles n'ont rien à attendre.
 */
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join, sep } from 'node:path';
import { globSync } from 'node:fs';
import { neutraliserCommentaires } from './lib-commentaires.mjs';

const ICI = dirname(fileURLToPath(import.meta.url));
const SRC = join(ICI, '..', 'src');

/**
 * Les stores qui disent un RÔLE — ceux dont la valeur est vide avant résolution.
 *
 * 🔴 LUS dans `stores/auth.ts` : l'utilisateur, et toute dérivée de lui. La liste
 * était recopiée ici et en avait perdu six, dont `isGestionnaire` — celui de la
 * garde de `sondages/[id]`, qui décidait avant de savoir sans que ce contrôle le
 * voie (#1486, 30/09/2026).
 */
const SOURCE_AUTH = readFileSync(join(SRC, 'lib', 'stores', 'auth.ts'), 'utf8');
const STORES_DE_ROLE = [
	'currentUser',
	...[...SOURCE_AUTH.matchAll(/export const (\w+) = derived\(\s*currentUser\b/g)].map((m) => m[1]),
];
if (STORES_DE_ROLE.length < 5) {
	console.error(
		`✗ ${STORES_DE_ROLE.length - 1} dérivée(s) de currentUser lue(s) dans stores/auth.ts — ` +
			`la forme a changé, ce contrôle ne mesurerait plus rien.`,
	);
	process.exit(2);
}

/** Ce qui prouve qu'on a attendu de savoir. */
const TEMOIN = 'authResolue';

/**
 * Une seule exception, valable pour les deux volets : le fichier qui CHARGE
 * l'utilisateur. Il lit `$currentUser` pour savoir s'il doit appeler
 * `authApi.me()`, et renvoie vers la mire quand la réponse est « personne » —
 * il ne peut pas attendre `authResolue`, puisque c'est lui qui le pose. Elle est
 * apparue le 30/09/2026 (#1486), quand `currentUser` est entré dans la liste.
 *
 * J'avais d'abord déclaré `lib/stores/auth.ts`, et le contrôle l'a refusée **à
 * sa première exécution** : il ne lit que les `.svelte`, donc elle ne couvrait
 * rien (`standards/04` §40). Toute nouvelle exception s'écrit ici **avec sa
 * raison et sa date**, et le contrôle la refuse dès qu'elle cesse de servir.
 */
const EXCEPTIONS = {
	'routes/(app)/+layout.svelte': 'charge l’utilisateur et pose `authResolue`',
};

/**
 * Ce rôle GOUVERNE-t-il une redirection, ou vit-il ailleurs dans le fichier ?
 *
 * 🔴 « un `goto` quelque part et un rôle quelque part » signalait huit écrans,
 * dont six où les deux n'ont aucun rapport : le calendrier navigue vers un
 * événement et filtre par rôle, sans qu'aucune garde n'existe. Un contrôle qui
 * rougit six fois sur huit à tort est désarmé dans la semaine.
 *
 * Ce qui compte est la **conjonction dans une même instruction** : une condition
 * qui teste le rôle, et un `goto` qu'elle gouverne à moins de 300 caractères.
 */
function gouverneUnGoto(script, role) {
	const motif = new RegExp(`if\\s*\\([^)]*\\$${role}\\b[\\s\\S]{0,300}?goto\\s*\\(`);
	return motif.test(script);
}

const fautes = [];
const exceptionsVues = new Set();

for (const relatif of globSync('**/*.svelte', { cwd: SRC }).map((p) => p.split(sep).join('/'))) {
	const source = neutraliserCommentaires(readFileSync(join(SRC, relatif), 'utf8'));
	//  Le `<script>` seul : une redirection ne s'écrit pas dans le balisage, et
	//  y chercher ajouterait du bruit sans ajouter de cas.
	const script = source.match(/<script[^>]*>([\s\S]*?)<\/script>/)?.[1] ?? '';
	if (!/goto\s*\(/.test(script)) continue;

	const roles = STORES_DE_ROLE.filter((r) => gouverneUnGoto(script, r));
	if (roles.length === 0) continue;

	//  Le fichier attend-il de SAVOIR avant de décider ?
	if (script.includes(TEMOIN)) continue;

	if (EXCEPTIONS[relatif]) {
		exceptionsVues.add(relatif);
		continue;
	}
	fautes.push({ relatif, roles });
}

//  Cas zéro : si plus aucun fichier ne combine `goto` et un store de rôle, ce
//  contrôle ne mesure plus rien — soit les gardes ont changé de forme, soit le
//  motif est périmé (`standards/04` §1 et §27).
const candidats = globSync('**/*.svelte', { cwd: SRC })
	.map((p) => p.split(sep).join('/'))
	.filter((p) => {
		const s = neutraliserCommentaires(readFileSync(join(SRC, p), 'utf8'));
		return STORES_DE_ROLE.some((r) => gouverneUnGoto(s, r));
	});
if (candidats.length === 0) {
	console.error('✗ Cas zéro : aucun écran ne combine `goto()` et un store de rôle.');
	console.error("Les gardes ont changé de forme — ce n'est pas un vert.");
	process.exit(2);
}
console.log(`✓ Cas zéro : ${candidats.length} écran(s) combinent une redirection et un rôle.`);

if (fautes.length > 0) {
	console.error(`\n✗ ${fautes.length} garde(s) qui décident avant de savoir :\n`);
	for (const f of fautes) {
		console.error(`  src/${f.relatif}  — redirige selon ${f.roles.map((r) => `$${r}`).join(', ')}`);
	}
	console.error(
		`\n  Ces stores valent faux tant que \`authApi.me()\` n'a pas répondu : le garde\n` +
			`  refuse alors sur « on ne sait pas encore », et l'adresse ouverte directement\n` +
			`  — lien partagé, favori, F5 — renvoie au tableau de bord y compris l'ayant droit.\n` +
			`\n  → conditionner la redirection à \`$${TEMOIN}\`, comme \`admin/+layout.svelte\`.\n`,
	);
	process.exit(1);
}

// ════════════════════════════════════════════════════════════════════════════
//  AUCUN RÔLE LU DANS UN `onMount` (#1486, 30/09/2026)
// ════════════════════════════════════════════════════════════════════════════
//
//  La même confusion que ci-dessus, mais pour CHARGER au lieu de rediriger.
//  Svelte monte la page avant le layout : l'`onMount` d'un écran précède celui
//  qui charge l'utilisateur, et y lit donc `false` / `null` sur un chargement
//  direct. Deux récidives le même jour, trouvées par des e2e et non par un
//  contrôle : la file de modération jamais demandée (v2.84.5) et un bailleur qui
//  voyait tous ses lots « Vacant » (#779). Le relevé en a trouvé six autres.
//
//  Portée : le corps de l'`onMount` — fonction écrite en ligne ou nommée — et les
//  fonctions LOCALES qu'il appelle, sur un niveau. Au-delà (un module importé),
//  le contrôle ne voit rien, et il ne prétend pas le contraire.

//  L'exception est la même qu'au premier volet (`EXCEPTIONS`) : le chargeur.

/** Le texte entre la parenthèse ouvrante `debut` et sa fermante. */
function jusquaFermante(source, debut) {
	let profondeur = 0;
	for (let i = debut; i < source.length; i++) {
		if (source[i] === '(' || source[i] === '{') profondeur++;
		else if (source[i] === ')' || source[i] === '}') {
			profondeur--;
			if (profondeur === 0) return source.slice(debut, i + 1);
		}
	}
	return source.slice(debut);
}

/** Les fonctions déclarées dans le script, par nom → leur corps. */
function fonctionsLocales(script) {
	const corps = new Map();
	const motif =
		/(?:function\s+(\w+)\s*\(|(?:const|let)\s+(\w+)\s*=\s*(?:async\s*)?\([^)]*\)\s*=>)/g;
	for (const m of script.matchAll(motif)) {
		const accolade = script.indexOf('{', m.index + m[0].length - 1);
		if (accolade >= 0) corps.set(m[1] ?? m[2], jusquaFermante(script, accolade));
	}
	return corps;
}

function rolesLus(texte) {
	return STORES_DE_ROLE.filter((r) => new RegExp(`\\$${r}\\b|get\\(\\s*${r}\\s*\\)`).test(texte));
}

/** Ce que lisent les `onMount` d'un script : leur corps et leurs appels locaux. */
function rolesLusAuMontage(script) {
	const locales = fonctionsLocales(script);
	const lus = new Set();
	for (const m of script.matchAll(/onMount\s*\(/g)) {
		const argument = jusquaFermante(script, m.index + m[0].length - 1);
		const nomme = argument.match(/^\(\s*(\w+)\s*\)$/)?.[1];
		const corps = nomme ? (locales.get(nomme) ?? '') : argument;
		const appels = [...corps.matchAll(/\b(\w+)\s*\(/g)].map((a) => locales.get(a[1]) ?? '');
		for (const texte of [corps, ...appels]) for (const r of rolesLus(texte)) lus.add(r);
	}
	return [...lus];
}

const auMontage = [];
let onMountLus = 0;
for (const relatif of globSync('**/*.svelte', { cwd: SRC }).map((p) => p.split(sep).join('/'))) {
	const source = neutraliserCommentaires(readFileSync(join(SRC, relatif), 'utf8'));
	const script = source.match(/<script[^>]*>([\s\S]*?)<\/script>/)?.[1] ?? '';
	if (!/onMount\s*\(/.test(script)) continue;
	onMountLus++;
	const roles = rolesLusAuMontage(script);
	if (roles.length === 0) continue;
	if (EXCEPTIONS[relatif]) {
		exceptionsVues.add(relatif);
		continue;
	}
	auMontage.push({ relatif, roles });
}

//  Cas zéro : aucun `onMount` lu = le motif de recherche est cassé, pas un vert.
if (onMountLus === 0) {
	console.error('✗ Cas zéro : aucun `onMount` trouvé — ce contrôle ne mesure plus rien.');
	process.exit(2);
}
if (auMontage.length > 0) {
	console.error(
		`\n✗ ${auMontage.length} onMount qui lisent l'utilisateur avant qu'il soit chargé :\n`,
	);
	for (const f of auMontage) {
		console.error(`  src/${f.relatif}  — ${f.roles.map((r) => `$${r}`).join(', ')}`);
	}
	console.error(
		`\n  L'onMount d'un écran précède celui du layout qui charge l'utilisateur : sur un\n` +
			`  chargement direct ou un rechargement, ces stores y valent encore false / null.\n` +
			`\n  → \`quandAuthResolue(() => …)\` (\`#lib/stores/auth\`) à la place de l'onMount.\n`,
	);
	process.exit(1);
}
//  Après les DEUX volets : une exception vue par l'un ou l'autre sert encore.
const perimees = Object.keys(EXCEPTIONS).filter((f) => !exceptionsVues.has(f));
if (perimees.length > 0) {
	console.error(
		`✗ Exception(s) qui ne servent plus : ${perimees.join(', ')} — les retirer, ` +
			`sinon elles couvriront un homonyme réintroduit plus tard.`,
	);
	process.exit(1);
}
console.log(
	`✓ ${onMountLus} fichier(s) à onMount : aucun ne lit l'utilisateur avant de le connaître.`,
);

// ════════════════════════════════════════════════════════════════════════════
//  UNE SEULE PORTE VERS LA MIRE (#1083, point 2)
// ════════════════════════════════════════════════════════════════════════════
//
//  🔴 La garde « non connecté » était écrite à SIX endroits, et trois écrivaient
//  l'adresse en dur. Celles qui passent par `urlDeConnexion()` conservent la
//  page demandée — un lien partagé ramène où l'on allait ; les trois autres la
//  perdent. Un utilisateur non connecté atterrissait donc où il voulait ou sur
//  le tableau de bord, **selon la porte par laquelle il était entré**.
//
//  ⚠️ Les écrans d'authentification eux-mêmes gardent leurs liens en clair :
//  « Retour à la connexion » depuis l'inscription ou l'oubli de mot de passe est
//  une navigation, pas une garde, et il n'a aucune destination à conserver.
const MIRE = '/auth/connexion';
const SOURCE_REDIRECTION = ['lib/redirection.ts'];

/** Un chemin a-t-il le droit d'écrire l'adresse de la mire en clair ? */
function peutEcrireLaMire(relatif) {
	return SOURCE_REDIRECTION.includes(relatif) || relatif.startsWith('routes/auth/');
}

const enDur = [];
for (const chemin of globSync(join(SRC, '**', '*.{svelte,ts}'))) {
	const relatif = chemin
		.slice(SRC.length + 1)
		.split(sep)
		.join('/');
	if (peutEcrireLaMire(relatif)) continue;
	const source = neutraliserCommentaires(readFileSync(chemin, 'utf8'));
	source.split('\n').forEach((ligne, i) => {
		if (ligne.includes(MIRE))
			enDur.push({ relatif, ligne: i + 1, texte: ligne.trim().slice(0, 70) });
	});
}

if (enDur.length > 0) {
	console.error(`\n✗ ${enDur.length} redirection(s) vers la mire écrite(s) en dur :\n`);
	for (const f of enDur) console.error(`  src/${f.relatif}:${f.ligne}  ${f.texte}`);
	console.error(
		`\n  La destination se perd : celui qui ouvre un lien reçu n'y revient pas\n` +
			`  après s'être connecté, alors qu'il y revient par les autres portes.\n` +
			`\n  → \`urlDeConnexion(cible?)\` pour garder la page demandée, ou\n` +
			`    \`CHEMIN_CONNEXION\` quand il n'y a rien à garder (déconnexion,\n` +
			`    racine du site) — les deux dans \`lib/redirection.ts\`.\n`,
	);
	process.exit(1);
}

console.log(
	'✓ Toute garde qui refuse selon un rôle attend que l’authentification soit résolue,\n' +
		`  et les ${enDur.length === 0 ? 'seules' : ''} portes vers la mire passent par \`lib/redirection.ts\`.`,
);
