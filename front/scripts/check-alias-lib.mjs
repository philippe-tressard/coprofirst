#!/usr/bin/env node
/**
 *  `#lib/…` est le SEUL chemin d'import vers `src/lib` (#2278, 28/10/2026).
 *
 *  ## Pourquoi
 *
 *  SvelteKit 3 ne génère plus l'alias historique de `src/lib`, que l'option
 *  `alias` de `sveltekit({…})` maintenait en attendant, et qu'il avertit de
 *  retirer à chaque build (`config_option_deprecated_alias`). Le front s'importe
 *  désormais par les imports de sous-chemin de Node, déclarés dans le champ
 *  `imports` de `package.json` : `#lib/outil.ts`, **extension obligatoire**.
 *  Vite, TypeScript, esbuild (`scripts/lib/charger-module.mjs`) et Node les
 *  lisent tous au même endroit — l'alias, lui, se répétait dans chaque outil.
 *
 *  ## Ce que ce contrôle refuse
 *
 *  Le retour de l'ancien alias, **commentaires compris** : un en-tête qui cite
 *  l'ancien chemin apprend à l'écrire, et c'est ainsi qu'il revient. Il lit `src/`,
 *  `e2e/`, `scripts/` et les fichiers de configuration. Le jeton est assemblé
 *  ici pour ne pas se refuser lui-même.
 *
 *  Et le champ `imports` de `package.json` doit déclarer `#lib` et `#lib/*` :
 *  sans lui, chaque import du front est irrésoluble — le cas zéro de ce contrôle.
 *
 *  Lancer : node scripts/check-alias-lib.mjs [--selftest]
 */
import { readFileSync } from 'node:fs';
import { controler } from './lib-source-unique.mjs';

const ANCIEN = `$${'lib'}`;
//  `$libelle` est un store qui s'appelle `libelle` : seul le jeton ENTIER est refusé.
const MOTIF = new RegExp(String.raw`[$]lib(?![\w$])`);

/** Les numéros des lignes qui portent l'ancien alias, commentaires compris. PURE. */
const fautes = (texte) => texte.split('\n').flatMap((l, i) => (MOTIF.test(l) ? [i + 1] : []));

/** Le champ `imports` déclare-t-il les deux entrées ? PURE : rend les clés absentes. */
export function importsManquants(packageJson) {
	const declares = JSON.parse(packageJson).imports ?? {};
	return ['#lib', '#lib/*'].filter((cle) => typeof declares[cle] !== 'string');
}

const cas = [
	[`import { x } from '${ANCIEN}/utils';`, 1],
	[`import('${ANCIEN}/components/X.svelte')`, 1],
	[`// voir ${ANCIEN}/date.ts`, 1],
	[`/* ${ANCIEN} */`, 1],
	[`import { x } from '#lib/utils.ts';`, 0],
	//  Un store nommé `libelle` : `$libelle` n'est pas l'alias.
	[`const v = ${ANCIEN}elle + 1;`, 0],
];

function absentsDuPackage() {
	const manquants = importsManquants(readFileSync('package.json', 'utf8'));
	if (manquants.length) {
		console.error(
			`✗ package.json : champ « imports » sans ${manquants.join(' ni ')} — tout import du front est irrésoluble.`,
		);
		return 1;
	}
	return 0;
}

//  Cas zéro du témoin : le contrôle de `package.json` voit un champ absent.
function selftestPackage() {
	const ok =
		importsManquants('{}').length === 2 &&
		importsManquants('{"imports":{"#lib":"./a"}}').join() === '#lib/*' &&
		importsManquants('{"imports":{"#lib":"./a","#lib/*":"./b/*"}}').length === 0;
	console.log(`${ok ? 'PASS' : 'FAIL'}  le champ imports se juge (absent, partiel, complet)`);
	return ok ? 0 : 1;
}

const selftest = process.argv.includes('--selftest');
const code = controler({
	racines: ['src', 'e2e', 'scripts'],
	fichiers: ['vite.config.ts', 'eslint.config.js', 'playwright.config.ts'],
	extensions: ['.svelte', '.ts', '.js', '.mjs', '.css', '.json'],
	fautes,
	cas,
	ok: "Aucun import par l'ancien alias : `#lib/…` est le seul chemin",
	ko: "occurrence(s) de l'ancien alias de `src/lib`",
	conseil:
		'Écrire `#lib/<fichier>.<extension>` (extension obligatoire ; un dossier : `#lib/<dossier>/index.ts`).',
});
process.exit(code || (selftest ? selftestPackage() : absentsDuPackage()));
