#!/usr/bin/env node
/**
 * Garde-fou : un export de `#lib` que **plus rien ne référence** est refusé
 * (#1577, 02/10/2026).
 *
 * ## Pourquoi il existe
 *
 * Dix exports sans aucun appelant ont été trouvés le 02/10/2026 — et un audit
 * précédent (#550) en avait déjà fermé soixante-quatorze. Le défaut revient
 * parce que rien ne le voit : `tsc` ne signale pas un export inutilisé, et
 * ESLint a `no-unused-vars` éteint (« la version TypeScript la remplace »).
 * `lint:client-appele` fait déjà ce travail pour les méthodes du client d'API ;
 * celui-ci fait le même relevé pour tout le reste de `src/lib`.
 *
 * 🔴 Un export mort n'est pas inoffensif : il **affirme** un garde-fou ou un
 * usage qui n'existe plus. `STATUTS_TESTES` disait être lue par `lint:statuts`
 * (elle ne l'était plus), `BALISES_DEPLIABLES` par le contrôle de concordance
 * des balises (qui lit le texte du fichier, pas la constante), `htmlPreview` était
 * enseignée par une skill — et trois autres, dont `apercuAvecRepli`, n'avaient
 * plus d'appelant depuis la disparition de la page qui les employait (#1092).
 *
 * ## Ce que « référencé » veut dire
 *
 * Le nom apparaît, comme mot entier, ailleurs que sur sa propre déclaration :
 *
 * - dans `src/` — commentaires **blanchis** (`lib-commentaires`) : un en-tête qui
 *   cite le nom ne le fait pas vivre ;
 * - dans `e2e/`, `scripts/` (hors ce fichier) et `../api/tests/` — **texte brut** :
 *   un contrôle qui lit une constante, ou un test qui cherche `export const X`
 *   dans un source, EST un appelant.
 *
 * Un usage dans son propre fichier compte (un type d'argument, un appel interne) :
 * c'est un export superflu, pas un export mort — autre question, autre ticket.
 *
 * ⚠️ **La résolution est par NOM, pas par module.** Deux symboles homonymes dans
 * deux modules se couvrent l'un l'autre : le contrôle peut manquer un mort, il ne
 * peut pas en accuser un vivant. C'est le bon sens du compromis — un contrôle qui
 * crie sur du légitime finit désarmé (leçon de C16). Les noms réexportés par un
 * barillet (`export { x } from`) comptent aussi comme référencés.
 *
 * ## Exceptions
 *
 * Un symbole gardé exprès sans appelant se déclare dans `EXCEPTIONS`, avec sa
 * raison et la date (`JJ/MM/AAAA`) ; une exception qui cesse de servir (le
 * symbole a un appelant, ou n'existe plus) fait échouer — la liste ne couvre pas
 * ce qui est redevenu vivant. **Il n'y en a aucune** : les onze morts
 * du 02/10/2026 ont été supprimés, pas déclarés (et `STATUTS_TESTES`, qui devait être lue
 * par `lint:statuts`, l'est de nouveau).
 *
 * ## Cas zéro
 *
 * Aucun export lu, ou un corpus trop mince, rend INCONNU (code 2) — jamais ✓.
 *
 * Usage : node scripts/check-exports-morts.mjs [--selftest]
 *         node scripts/check-exports-morts.mjs --racine <dossier front>   (relevé d'un autre arbre)
 */
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join, relative, resolve, sep } from 'node:path';
import { fileURLToPath } from 'node:url';
import { neutraliserCommentaires } from './lib-commentaires.mjs';

/** Symbole → { depuis, raison }. Vide : voir l'en-tête. */
const EXCEPTIONS = {};

const DECLARATION =
	/^export (?:declare )?(?:async )?(?:const|let|function\*?|class|enum|interface|type|abstract class) ([\w$]+)/gm;

/** Les noms exportés par déclaration dans un source TypeScript. PURE. */
export function exportsDeclares(source) {
	return [...neutraliserCommentaires(source).matchAll(DECLARATION)].map((m) => m[1]);
}

/** Le nombre d'occurrences de chaque mot entier d'un texte. PURE. */
export function compterMots(texte, compteur = new Map()) {
	for (const [mot] of texte.matchAll(/[\w$]+/g)) compteur.set(mot, (compteur.get(mot) ?? 0) + 1);
	return compteur;
}

/**
 * Les exports sans la moindre référence en dehors de leur déclaration. PURE.
 *
 * @param {Record<string, string>} lib      chemin → source des modules de `#lib`
 * @param {Map<string, number>} mots        occurrences de chaque mot du corpus
 *        (les modules de `lib` en font partie : chaque déclaration y compte une fois)
 */
export function exportsMorts(lib, mots) {
	const declarations = new Map();
	for (const [chemin, source] of Object.entries(lib)) {
		for (const nom of exportsDeclares(source)) {
			declarations.set(nom, [...(declarations.get(nom) ?? []), chemin]);
		}
	}
	const morts = [];
	for (const [nom, chemins] of declarations) {
		if ((mots.get(nom) ?? 0) - chemins.length <= 0) morts.push({ nom, chemins });
	}
	return { total: declarations.size, morts };
}

/** Les exceptions qui ne servent plus : le symbole est vivant, ou a disparu. PURE. */
export function exceptionsPerimees(exceptions, morts, declares) {
	const mortsNoms = new Set(morts.map((m) => m.nom));
	return Object.keys(exceptions).filter((nom) => !mortsNoms.has(nom) || !declares.has(nom));
}

function fichiers(dossier, extensions, acc = []) {
	for (const e of readdirSync(dossier)) {
		if (e === 'node_modules' || e === '.svelte-kit') continue;
		const chemin = join(dossier, e);
		if (statSync(chemin).isDirectory()) fichiers(chemin, extensions, acc);
		else if (extensions.some((x) => e.endsWith(x))) acc.push(chemin);
	}
	return acc;
}

function selftest() {
	let ko = 0;
	const verifier = (nom, obtenu, attendu) => {
		const ok = JSON.stringify(obtenu) === JSON.stringify(attendu);
		if (!ok) ko++;
		console.log(
			`${ok ? 'PASS' : 'ÉCHEC'}  ${nom} → ${JSON.stringify(obtenu)} (attendu ${JSON.stringify(attendu)})`,
		);
	};
	/** Un arbre fictif : `lib` = modules de `#lib` ; `autres` = le reste du corpus. */
	const releve = (lib, autres = []) => {
		const mots = new Map();
		for (const s of Object.values(lib)) compterMots(neutraliserCommentaires(s), mots);
		for (const s of autres) compterMots(s, mots);
		return exportsMorts(lib, mots).morts.map((m) => m.nom);
	};

	//  🔴 LE CAS FAUTIF : l'export que personne n'appelle.
	verifier('export sans appelant : refusé', releve({ 'a.ts': 'export const ETATS = [1];' }), [
		'ETATS',
	]);
	verifier(
		'appelé par un autre module : accepté',
		releve({ 'a.ts': 'export const X = 1;', 'b.ts': "import { X } from './a'; X;" }),
		[],
	);
	verifier(
		'appelé par un écran, hors lib : accepté',
		releve({ 'a.ts': 'export function f() {}' }, [
			'<script>import { f } from "#lib/a"; f();</script>',
		]),
		[],
	);
	verifier(
		'cité seulement dans un commentaire : refusé',
		releve({ 'a.ts': 'export const X = 1;', 'b.ts': '// voir X, la source\nexport const Y = 2;' }),
		['X', 'Y'],
	);
	verifier(
		'chaîne X lu par Y, Y lu par un écran : tous deux vivants',
		releve({ 'a.ts': 'export const X = 1;', 'b.ts': 'export const Y = X;' }, ['Y']),
		[],
	);
	verifier(
		'usage dans son propre fichier : export superflu, pas mort',
		releve({ 'a.ts': 'export function f() {}\nf();' }),
		[],
	);
	verifier(
		'un nom plus long ne couvre pas le plus court (mot entier)',
		releve({ 'a.ts': 'export function fmtDatetime2d() {}' }, ['fmtDatetime2dx fmtDatetime']),
		['fmtDatetime2d'],
	);
	verifier(
		'texte brut des contrôles et des tests : un appelant',
		releve({ 'a.ts': 'export const STATUTS_TESTES = [];' }, [
			'const m = /export const STATUTS_TESTES/',
		]),
		[],
	);
	verifier(
		'type + valeur de même nom : deux déclarations, aucun appelant',
		releve({ 'a.ts': 'export type T = 1;\nexport const T = 1;' }),
		['T'],
	);
	verifier(
		'formes de déclaration : async, class, enum, interface',
		releve({
			'a.ts':
				'export async function a() {}\nexport class B {}\nexport enum C {}\nexport interface D {}\nexport type E = 1;\nexport let F = 1;',
		}),
		['a', 'B', 'C', 'D', 'E', 'F'],
	);
	verifier(
		'un export par défaut n’est pas relevé',
		exportsDeclares('export default function () {}'),
		[],
	);
	verifier('cas zéro : aucun module', releve({}), []);
	verifier(
		'exception qui ne sert plus : relevée',
		exceptionsPerimees({ X: { raison: 'r' } }, [], new Set(['X'])),
		['X'],
	);
	verifier(
		'exception qui sert : conservée',
		exceptionsPerimees({ X: { raison: 'r' } }, [{ nom: 'X', chemins: ['a.ts'] }], new Set(['X'])),
		[],
	);
	console.log(ko ? `== ${ko} ÉCHEC(S) ==` : '== TOUS OK ==');
	return ko ? 1 : 0;
}

if (process.argv.includes('--selftest')) process.exit(selftest());

const MOI = fileURLToPath(import.meta.url);
const i = process.argv.indexOf('--racine');
const FRONT = resolve(i > 0 ? process.argv[i + 1] : fileURLToPath(new URL('..', import.meta.url)));

const modulesLib = fichiers(join(FRONT, 'src', 'lib'), ['.ts']);
const lib = Object.fromEntries(
	modulesLib.map((f) => [relative(FRONT, f).split(sep).join('/'), readFileSync(f, 'utf8')]),
);

const mots = new Map();
let lus = 0;
//  `src/` : commentaires blanchis. Tout le reste : texte brut.
for (const f of fichiers(join(FRONT, 'src'), ['.ts', '.svelte', '.js'])) {
	compterMots(neutraliserCommentaires(readFileSync(f, 'utf8')), mots);
	lus++;
}
for (const [dossier, ext] of [
	[join(FRONT, 'e2e'), ['.ts']],
	[join(FRONT, 'scripts'), ['.mjs']],
	[join(FRONT, '..', 'api', 'tests'), ['.py']],
]) {
	for (const f of fichiers(dossier, ext)) {
		if (resolve(f) === MOI) continue;
		compterMots(readFileSync(f, 'utf8'), mots);
		lus++;
	}
}

const { total, morts } = exportsMorts(lib, mots);

//  🔴 CAS ZÉRO — un relevé qui ne lit rien rend « aucun mort ».
if (total < 300 || lus < 400) {
	console.error(
		`\n⚠️  INCONNU — ${total} export(s) relevé(s), ${lus} fichier(s) lu(s) : le relevé n'a rien lu.\n`,
	);
	process.exit(2);
}

const declares = new Set(exportsDeclares(Object.values(lib).join('\n')));
const mortsHorsExceptions = morts.filter((m) => !(m.nom in EXCEPTIONS));
const perimees = exceptionsPerimees(EXCEPTIONS, morts, declares);
let echec = false;

if (perimees.length) {
	echec = true;
	console.error(
		'\n✗ lint:client-appele (exports morts) — ces exceptions ne servent plus :\n\n  ' +
			perimees.join('\n  ') +
			'\n\n  Le symbole a un appelant, ou n’existe plus : retirer l’entrée de EXCEPTIONS.\n',
	);
}
if (mortsHorsExceptions.length) {
	echec = true;
	console.error(
		`\n✗ lint:client-appele (exports morts) — ${mortsHorsExceptions.length} export(s) de #lib que plus rien ne référence (#1577) :\n\n  ` +
			mortsHorsExceptions.map((m) => `${m.nom}  (${m.chemins.join(', ')})`).join('\n  ') +
			'\n\n  Supprimer l’export — et sa déclaration si elle devient morte. Un export mort\n' +
			'  AFFIRME un usage ou un garde-fou qui n’existe plus. Gardé exprès : le déclarer\n' +
			'  dans EXCEPTIONS (scripts/check-exports-morts.mjs) avec sa raison et sa date.\n',
	);
}
if (echec) process.exit(1);

console.log(
	`✓ Exports de #lib : ${total} déclaré(s), tous référencés ailleurs que sur leur déclaration ` +
		`(${lus} fichiers lus, ${Object.keys(EXCEPTIONS).length} exception(s)).`,
);
