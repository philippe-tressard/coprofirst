#!/usr/bin/env node
// SPDX-FileCopyrightText: 2026 Philippe Tressard
// SPDX-License-Identifier: AGPL-3.0-or-later
/**
 * Un écran DEMANDE un droit, il ne le recompose pas.
 *
 * ## Pourquoi ce contrôle (#1041, audit du 19/09/2026)
 *
 * `#lib/droits.ts` et `#lib/stores/auth.ts` sont la source déclarée de « qui peut
 * quoi » côté écran. Les écrans la recomposaient quand même — **vingt-deux fois**,
 * de quatre façons :
 *
 * | Forme | Ce qu'elle dit |
 * |---|---|
 * | `$isCS \|\| $isAdmin` | une **tautologie** : `isCS` inclut déjà `admin` (`auth.ts`). Celui qui l'écrit ne connaît pas la définition de ce qu'il appelle |
 * | `['propriétaire','conseil_syndical','admin'].includes(r)` | la cascade littérale, écrite deux fois à l'identique |
 * | `objet.auteur_id === userId` | `peutEditer` réécrite à la main, sans le « saisi pour » ni l'admin |
 * | `userRoles(u).includes('admin')` | `aRole(u, 'admin')` existe et prend un `User` |
 *
 * 🔴 **Aucune n'était fausse au moment où elle a été écrite.** C'est le motif :
 * elles deviennent fausses le jour où la règle centrale apprend quelque chose, et
 * ce jour-là rien ne les signale. La plus dangereuse est la troisième — une
 * comparaison d'`auteur_id` oublie le champ « saisi pour », donc elle fait
 * disparaître le crayon d'un résident pour qui le conseil a déposé un ticket.
 *
 * ⚠️ **Le front n'est jamais le gardien d'un droit** : le serveur tranche, et
 * `test_autorisation.py` le vérifie. Mais l'écran doit dire **la même chose** que
 * lui, ni plus (un bouton qui finit en 403), ni moins (une capacité introuvable).
 * C'est écrit en toutes lettres dans `droits.ts`, et c'est ce que ce contrôle tient.
 *
 * ## Ce qu'il ne regarde PAS
 *
 * Les trois fichiers qui DÉFINISSENT ces règles — `stores/auth.ts`, `droits.ts`,
 * `roles.ts`. Ils ont le droit d'écrire la cascade : c'est leur travail, et c'est
 * même tout leur contenu.
 */
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join, sep } from 'node:path';
import { globSync } from 'node:fs';
import { neutraliserCommentaires } from './lib-commentaires.mjs';

const ICI = dirname(fileURLToPath(import.meta.url));
const SRC = join(ICI, '..', 'src');

/** Les fichiers qui DÉFINISSENT les droits — la cascade y est chez elle. */
const SOURCES = ['lib/stores/auth.ts', 'lib/droits.ts', 'lib/roles.ts'];

/**
 * Chaque forme interdite, avec ce qu'il faut appeler à la place.
 *
 * ⚠️ Le motif décrit la NOTION, pas l'écriture déjà rencontrée (`standards/04`
 * §40) : les deux ordres de l'alternative, et n'importe quel nom de variable.
 */
const FORMES = [
	{
		nom: 'tautologie « CS ou admin »',
		//  Les DEUX écritures de la même chose : l'alternative, et sa négation par
		//  De Morgan (`!isCS && !isAdmin`). Ne chercher que la première aurait laissé
		//  passer la moitié des cas — un motif décrit la NOTION, pas la forme sous
		//  laquelle on l'a rencontrée d'abord (`standards/04` §40).
		motif:
			/\$?\bisCS\b\s*\|\|\s*\$?\bisAdmin\b|\$?\bisAdmin\b\s*\|\|\s*\$?\bisCS\b|!\s*\$?\bisCS\b\s*&&\s*!\s*\$?\bisAdmin\b|!\s*\$?\bisAdmin\b\s*&&\s*!\s*\$?\bisCS\b/,
		remede:
			"`isCS` inclut déjà `admin` (stores/auth.ts) — écrire `$isCS` seul. L'alternative " +
			"révèle que la définition du store n'est pas connue de l'écran.",
	},
	{
		nom: 'cascade de rôles écrite en clair',
		motif: /\[[^\]]*'(?:propriétaire|conseil_syndical|résident)'[^\]]*\]\s*\.includes/,
		remede:
			'appeler un store dérivé (`$isProprioOuCS`, `$isCS`…) ou `aRole(user, …)` de ' +
			'`stores/auth.ts`. Une liste de rôles recopiée dérive de sa jumelle.',
	},
	{
		nom: 'appartenance recomposée sur `auteur_id`',
		motif: /\.auteur_id\s*===/,
		remede:
			'appeler `peutEditer` / `peutCommenter` de `#lib/droits`. Une comparaison ' +
			'directe oublie le champ « saisi pour » : le crayon disparaît pour le résident ' +
			'au nom de qui le conseil a déposé la demande.',
	},
	{
		nom: '`userRoles(...).includes(...)`',
		motif: /userRoles\([^)]*\)\s*\.includes/,
		remede: '`aRole(utilisateur, …)` prend un `User` et fait exactement cela.',
	},
];

function fichiersAnalyses() {
	return globSync('**/*.{svelte,ts}', { cwd: SRC })
		.map((p) => p.split(sep).join('/'))
		.filter((p) => !SOURCES.includes(p));
}

//  Auto-test : chaque forme doit reconnaître son cas fautif ET laisser passer le
//  cas sain. Un motif qui n'attrape plus rien passerait au vert en silence.
const CAS = [
	['{#if $isCS || $isAdmin}', 'tautologie « CS ou admin »'],
	['{#if $isAdmin || $isCS}', 'tautologie « CS ou admin »'],
	['if (!$isCS && !$isAdmin) return;', 'tautologie « CS ou admin »'],
	['if (!$isAdmin && !$isCS) return;', 'tautologie « CS ou admin »'],
	[
		"roles.some((r) => ['propriétaire', 'conseil_syndical', 'admin'].includes(r))",
		'cascade de rôles écrite en clair',
	],
	['{#if idee.auteur_id === currentUserId}', 'appartenance recomposée sur `auteur_id`'],
	["userRoles(u).includes('admin')", '`userRoles(...).includes(...)`'],
];
const SAINS = [
	'{#if $isCS}',
	'peutEditer(ticket, $currentUser?.id, $isAdmin)',
	"aRole(u, 'admin')",
];

let autotestOk = true;
for (const [source, attendu] of CAS) {
	const vue = FORMES.find((f) => f.motif.test(source));
	if (vue?.nom !== attendu) {
		console.error(`✗ Auto-test : « ${source} » devrait être vu comme « ${attendu} ».`);
		autotestOk = false;
	}
}
for (const source of SAINS) {
	const vue = FORMES.find((f) => f.motif.test(source));
	if (vue) {
		console.error(`✗ Auto-test : « ${source} » est SAIN, refusé à tort par « ${vue.nom} ».`);
		autotestOk = false;
	}
}
if (!autotestOk) process.exit(2);
console.log(
	`✓ Auto-test : les ${FORMES.length} formes reconnaissent leur cas et épargnent le cas sain.`,
);

const fautes = [];
for (const chemin of fichiersAnalyses()) {
	const source = neutraliserCommentaires(readFileSync(join(SRC, chemin), 'utf8'));
	source.split('\n').forEach((ligne, i) => {
		for (const forme of FORMES) {
			if (forme.motif.test(ligne)) {
				fautes.push({ chemin, ligne: i + 1, texte: ligne.trim().slice(0, 88), forme });
			}
		}
	});
}

if (fautes.length > 0) {
	console.error(`\n✗ ${fautes.length} droit(s) recomposé(s) dans un écran :\n`);
	for (const f of fautes) {
		console.error(`  src/${f.chemin}:${f.ligne}  [${f.forme.nom}]`);
		console.error(`      ${f.texte}`);
	}
	console.error("\nCe qu'il faut appeler à la place :");
	for (const forme of new Set(fautes.map((f) => f.forme))) {
		console.error(`  • ${forme.nom} → ${forme.remede}`);
	}
	console.error(
		"\n⚠️ Le front n'est jamais le gardien d'un droit — mais il doit dire la MÊME\n" +
			'   chose que le serveur. Plus large, il tend un bouton qui finira en 403 ;\n' +
			'   plus étroit, il rend une capacité introuvable.\n',
	);
	process.exit(1);
}

console.log(`✓ Aucun droit recomposé dans les ${fichiersAnalyses().length} écrans et composants.`);
