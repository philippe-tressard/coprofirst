#!/usr/bin/env node
/**
 *  Une variable CSS employée est une variable DÉFINIE (#1571, 22/10/2026).
 *
 *  ## Pourquoi
 *
 *  `var(--color-bg-subtle)` : aucune feuille ne définit `--color-bg-subtle`. Le
 *  navigateur ne le dit pas — la déclaration devient « invalide au calcul » et la
 *  propriété retombe à sa valeur initiale. Le bandeau de réorganisation de la FAQ
 *  et sa zone de dépôt n'avaient donc AUCUN fond, et la frise des renouvellements
 *  de contrats perdait le sien (`color-mix` sur `--color-bg-card`, inexistante).
 *  Avec un repli (`var(--color-bg-alt, #f5f5f5)`), c'est l'inverse : le repli
 *  s'applique TOUJOURS, et c'est une couleur en dur déguisée en jeton — huit
 *  l'étaient, sous six noms que personne n'a jamais définis.
 *
 *  `lint:charte-valeurs` ne voyait ni l'un ni l'autre : il compte les valeurs, pas
 *  les noms. Le repli sur un jeton DÉFINI est l'affaire de `repliMortsDe` (même
 *  contrôle de la charte) ; celui-ci répond à la question inverse.
 *
 *  ## Ce qu'il lit
 *
 *  Tout `src/` (`.svelte`, `.css`, `.ts`, `.js`), commentaires retirés. Une
 *  variable est DÉFINIE par `--nom:` (feuille, `<style>`, attribut `style="…"`),
 *  par la directive `style:--nom`, ou par le nom écrit en chaîne
 *  (`setProperty('--nom', …)`, objet de style) ; elle est EMPLOYÉE par `var(--nom`.
 *
 *  Lancer : node scripts/check-variables-css.mjs [--selftest]
 */
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { dirname, join, relative, sep } from 'node:path';
import { fileURLToPath } from 'node:url';

const RACINE = join(dirname(fileURLToPath(import.meta.url)), '..', 'src');
const EXTENSIONS = ['.svelte', '.css', '.ts', '.js'];

/**
 *  Les exceptions : aucune. Une entrée s'écrit `'--nom': 'raison'`, et le
 *  contrôle échoue si elle ne sert plus.
 */
const EXCEPTIONS = {};

/** Un commentaire blanchi garde ses sauts de ligne : les numéros restent justes. */
const blanchir = (bloc) => bloc.replace(/[^\n]/g, ' ');

/** Le source sans ses commentaires CSS, HTML et JavaScript de ligne. */
export function sansCommentaires(source) {
	return source
		.replace(/<!--[\s\S]*?-->/g, blanchir)
		.replace(/\/\*[\s\S]*?\*\//g, blanchir)
		.replace(/(^|[^:'"])\/\/.*$/gm, '$1');
}

/** Les noms de variables qu'un source DÉFINIT. */
export function definitionsDe(source) {
	const s = sansCommentaires(source);
	const noms = new Set();
	for (const m of s.matchAll(/(--[a-z][a-z0-9-]*)\s*:/g)) noms.add(m[1]);
	for (const m of s.matchAll(/style:(--[a-z][a-z0-9-]*)/g)) noms.add(m[1]);
	for (const m of s.matchAll(/['"`](--[a-z][a-z0-9-]*)['"`]/g)) noms.add(m[1]);
	return noms;
}

/** Les emplois `var(--nom…)` d'un source, avec leur ligne. */
export function emploisDe(source) {
	const lignes = sansCommentaires(source).split('\n');
	const emplois = [];
	lignes.forEach((ligne, i) => {
		for (const m of ligne.matchAll(/var\(\s*(--[a-z][a-z0-9-]*)/g))
			emplois.push({ nom: m[1], ligne: i + 1 });
	});
	return emplois;
}

/** Les emplois dont le nom n'est défini nulle part, déclarés exceptés à part. */
export function fantomes(sources, exceptions = {}) {
	const definis = new Set();
	for (const source of Object.values(sources))
		for (const nom of definitionsDe(source)) definis.add(nom);
	const trouves = [];
	const servies = new Set();
	for (const [chemin, source] of Object.entries(sources))
		for (const { nom, ligne } of emploisDe(source)) {
			if (definis.has(nom)) continue;
			if (nom in exceptions) servies.add(nom);
			else trouves.push(`   ${chemin}:${ligne} : var(${nom}) — définie nulle part`);
		}
	return { trouves, definis: definis.size, servies };
}

if (process.argv.includes('--selftest')) {
	let ko = 0;
	const cas = (libelle, obtenu, attendu) => {
		const ok = JSON.stringify(obtenu) === JSON.stringify(attendu);
		if (!ok) ko = 1;
		console.log(`${ok ? 'PASS' : 'FAIL'}  ${libelle} → ${JSON.stringify(obtenu)}`);
	};
	const r = fantomes({
		'socle.css': ':root {\n\t--color-surface: #fff;\n}',
		'A.svelte':
			'<div style:--largeur="{l}%" style="--pas: 2">x</div>\n<style>\n.a { background: var(--color-bg-alt, #f5f5f5); }\n.b { width: var(--largeur); gap: var(--pas); color: var(--color-surface); }\n</style>',
		'B.ts': "el.style.setProperty('--hauteur', '3px');\nconst s = 'height: var(--hauteur)';",
		'C.css': '/* var(--commentee) */\n.c { margin: var(--marge-absente); }',
	});
	cas(
		'un nom sans définition, avec ou sans repli ; pas un défini par style:, attribut, setProperty ; pas en commentaire',
		r.trouves,
		[
			'   A.svelte:3 : var(--color-bg-alt) — définie nulle part',
			'   C.css:2 : var(--marge-absente) — définie nulle part',
		],
	);
	cas(
		'une exception sert, et se dit servie',
		[...fantomes({ 'x.css': '.x{color:var(--y)}' }, { '--y': 'raison' }).servies],
		['--y'],
	);
	console.log(ko ? '== ÉCHECS ==' : '== TOUS OK ==');
	process.exit(ko);
}

function fichiers(dir, acc = []) {
	for (const nom of readdirSync(dir)) {
		const chemin = join(dir, nom);
		if (statSync(chemin).isDirectory()) fichiers(chemin, acc);
		else if (EXTENSIONS.some((e) => nom.endsWith(e))) acc.push(chemin);
	}
	return acc;
}

const sources = Object.fromEntries(
	fichiers(RACINE).map((chemin) => [
		relative(RACINE, chemin).split(sep).join('/'),
		readFileSync(chemin, 'utf8'),
	]),
);
const { trouves, definis, servies } = fantomes(sources, EXCEPTIONS);
const emplois = Object.values(sources).reduce((n, s) => n + emploisDe(s).length, 0);
if (definis < 20 || emplois < 100) {
	console.error(
		`\n✗ ${definis} variable(s) définie(s), ${emplois} emploi(s) lus : contrôle inopérant (INCONNU).\n`,
	);
	process.exit(2);
}
let echec = 0;
if (trouves.length) {
	echec = 1;
	console.error(
		`\n✗ ${trouves.length} variable(s) CSS employée(s) sans définition — la propriété ` +
			'retombe à sa valeur initiale, ou le repli s’applique toujours. Employer un jeton ' +
			'de styles/socle.css :',
	);
	trouves.forEach((l) => console.error(l));
}
for (const nom of Object.keys(EXCEPTIONS))
	if (!servies.has(nom)) {
		echec = 1;
		console.error(`\n✗ Exception sans objet : ${nom} est définie ou n’est plus employée.`);
	}
if (!echec)
	console.log(
		`✓ Variables CSS : ${emplois} emplois, tous sur l’une des ${definis} variables définies.`,
	);
process.exit(echec);
