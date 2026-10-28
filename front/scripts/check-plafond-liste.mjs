#!/usr/bin/env node
// SPDX-FileCopyrightText: 2026 Philippe Tressard
// SPDX-License-Identifier: AGPL-3.0-or-later
/**
 * Un plafond d'affichage se déclare une fois, il ne s'écrit pas deux.
 *
 * ## Le motif exact (#1076, 20/09/2026)
 *
 * Le kanban de l'accueil coupait ses colonnes à cinq cartes, et l'annonçait par
 * un compteur « +N » :
 *
 * ```js
 * items: items.slice(0, 5)
 * col.total > 5 ? `+${col.total - 5} / ${col.total}` : col.total
 * ```
 *
 * **Le même nombre, trois fois, dans deux expressions différentes.** Changer le
 * plafond demande de les corriger toutes : en oublier une donne un compteur qui
 * ment — « +2 » sur une colonne qui en cache trois — sans qu'aucun test ne le
 * voie, parce que les deux écritures restent valides séparément.
 *
 * C'est la duplication la plus discrète qui soit : elle tient dans deux lignes
 * voisines, et elle a l'air d'un détail jusqu'au jour où l'on change la valeur.
 * Ce jour-là est arrivé — l'utilisateur a demandé de passer de cinq à trois.
 *
 * ## Ce que ce contrôle refuse
 *
 * Dans un écran ou un composant, un **même littéral numérique** employé à la fois
 * pour couper une liste (`slice(0, N)`) et dans une comparaison (`> N`, `>= N`).
 * Cette conjonction est la signature du couple « je coupe à N » / « j'affiche le
 * reste » : le nombre est alors un **seuil**, et un seuil se nomme.
 *
 * ⚠️ Il ne refuse PAS un `slice(0, N)` isolé : `toISOString().slice(0, 10)` est
 * une troncature de chaîne, pas un plafond de liste, et il y en a huit dans le
 * dépôt. Un contrôle qui les signalerait serait désarmé la semaine suivante
 * (`standards/04` §36) — c'est la conjonction qui porte le sens, pas l'appel.
 */
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join, sep } from 'node:path';
import { globSync } from 'node:fs';
import { neutraliserCommentaires } from './lib-commentaires.mjs';

const ICI = dirname(fileURLToPath(import.meta.url));
const SRC = join(ICI, '..', 'src');

const fautes = [];
let examines = 0;

for (const relatif of globSync('**/*.svelte', { cwd: SRC }).map((p) => p.split(sep).join('/'))) {
	const source = neutraliserCommentaires(readFileSync(join(SRC, relatif), 'utf8'));
	const coupes = [...source.matchAll(/\.slice\(\s*0\s*,\s*(\d+)\s*\)/g)].map((m) => m[1]);
	if (coupes.length === 0) continue;
	examines++;

	for (const n of new Set(coupes)) {
		//  Le même nombre sert-il aussi de seuil de comparaison ?
		if (!new RegExp(`>=?\\s*${n}\\b`).test(source)) continue;
		fautes.push({ relatif, n });
	}
}

//  Cas zéro : plus aucun `slice(0, N)` dans les écrans, c'est que le motif est
//  périmé — pas que le dépôt est devenu parfait (`standards/04` §1 et §27).
if (examines === 0) {
	console.error('✗ Cas zéro : aucun `slice(0, N)` trouvé dans les écrans.');
	console.error("Le motif ne lit plus rien — ce n'est pas un vert.");
	process.exit(2);
}
console.log(`✓ Cas zéro : ${examines} écran(s) coupent une liste, le motif mesure encore.`);

if (fautes.length > 0) {
	console.error(`\n✗ ${fautes.length} plafond(s) écrit(s) deux fois dans un écran :\n`);
	for (const f of fautes) {
		console.error(`  src/${f.relatif} — le nombre ${f.n} coupe la liste ET sert de seuil`);
	}
	console.error(
		'\n  Un nombre employé pour couper ET pour comparer est un SEUIL : le changer\n' +
			'  demande de corriger les deux, et en oublier un donne un compteur qui ment\n' +
			'  sans qu’aucun test ne le voie.\n' +
			'  → le déclarer dans un module (`#lib/kanban`, `#lib/pages`…) et l’importer.\n',
	);
	process.exit(1);
}

console.log('✓ Aucun plafond de liste écrit en clair dans un écran.');
