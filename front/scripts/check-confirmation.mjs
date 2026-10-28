#!/usr/bin/env node
/**
 * Garde-fou : AUCUN `confirm()` NATIF (#605, #1043).
 *
 * 🔴 **Interdiction sèche depuis le 25/09/2026.** Les douze derniers ont été
 * convertis (#1043) : le plafond est tombé à zéro, et un plafond à zéro et une
 * interdiction disent la même chose — mais seule la seconde le dit à qui lit le
 * code. C'est le chemin qu'avaient déjà suivi `prompt()` et `alert()`.
 *
 * ## Pourquoi il a d'abord été un plafond
 *
 * Quarante gestes du site demandaient confirmation avec la boîte native du
 * navigateur. Elle bloque le fil d'exécution, ignore la charte, et — le plus
 * grave — donne exactement le même aspect à « archiver » et à « supprimer
 * définitivement », alors que l'un se défait et l'autre non.
 *
 * Les convertir d'un coup toucherait vingt-cinq écrans avant qu'on en ait
 * regardé un seul, ce que **R5** du cadre #430 interdit : *l'enrichissement se
 * propose sur UN écran, se fait constater, puis se généralise.*
 *
 * Le plafond est donc la seule forme honnête : il empêche d'en AJOUTER, et il
 * baisse à chaque écran repris. Une interdiction sèche aurait été désarmée dans
 * la semaine ; un simple avertissement n'aurait rien empêché.
 *
 * Usage : npm run lint:confirmation   (exit 1 au premier `confirm()` natif)
 */
import { readFileSync, readdirSync, statSync } from 'node:fs';

import { neutraliserCommentaires as sansCommentaires } from './lib-commentaires.mjs';
import { dirname, join, relative, sep } from 'node:path';
import { fileURLToPath } from 'node:url';

const RACINE = join(dirname(fileURLToPath(import.meta.url)), '..');
const SOURCE = join(RACINE, 'src');

/**
 * L'historique du compte, gardé parce qu'il dit à quel rythme une dette se
 * solde : 40 → 28 → 18 (12/09/2026, avec le lot `messageErreur` : mêmes écrans,
 * mêmes gestes) → 14 → 12 (24/09, Petites annonces) → **0** (25/09, #1043).
 */

/**
 * Fichiers qui PARLENT de `confirm()` sans en appeler un : le composant de
 * remplacement et son appel impératif, qui le citent dans leur documentation.
 */
const HORS_RELEVE = [
	'lib/components/Confirmation.svelte',
	'lib/confirmation.ts',
	//  Même raison : la modale de SAISIE et son appel impératif citent `prompt()`
	//  — le défaut qu'ils retirent — dans leur documentation.
	'lib/components/Saisie.svelte',
	'lib/saisie.ts',
	'lib/modale-imperative.ts',
];

function fichiers(dir) {
	const sortie = [];
	for (const nom of readdirSync(dir)) {
		const chemin = join(dir, nom);
		if (statSync(chemin).isDirectory()) sortie.push(...fichiers(chemin));
		else if (nom.endsWith('.svelte') || nom.endsWith('.ts')) sortie.push(chemin);
	}
	return sortie;
}

const tous = fichiers(SOURCE);
//  Cas zéro : l'arborescence a changé, le contrôle ne mesure plus rien.
if (tous.length < 50) {
	console.error(
		`✗ Cas zéro : ${tous.length} fichier(s) analysé(s), au moins 50 attendus — ` +
			'le parcours ne correspond plus à `src/`.',
	);
	process.exit(1);
}

/**
 * 🔴 `confirmer()` rend une **promesse**. Sans `await`, l'appel est *truthy* :
 *
 *     if (!confirmer('Supprimer ?')) return;     // ← ne retourne JAMAIS
 *
 * Le geste s'exécute alors **sans que personne ait confirmé**, et rien ne le
 * dit : pas d'erreur, pas de journal, une boîte qui s'affiche puis disparaît
 * pendant que la suppression est déjà partie.
 *
 * C'est le risque que la conversion des quarante `confirm()` natifs introduit à
 * chaque écran repris — la forme native, elle, était synchrone. Le contrôle est
 * donc **préventif** : il n'y a aucun appel fautif aujourd'hui, et c'est
 * précisément le moment de le poser.
 *
 * ⚠️ Motif volontairement étroit : `confirmer(` non précédé de `await`. Une
 * affectation différée (`const p = confirmer(…)`) n'existe nulle part et serait
 * un usage à instruire, pas à tolérer en silence.
 */
const APPELS_SANS_AWAIT = /(?<!await\s{1,4})\bconfirmer\s*\(/;

/**
 * 🔴 `prompt()` et `alert()` : **interdiction sèche**, pas un plafond.
 *
 * Le plafond était la bonne forme pour `confirm()` — quarante appels, vingt-cinq
 * écrans : une interdiction aurait été désarmée dans la semaine. Ici le compte
 * est **zéro** depuis le 12/09/2026, et c'est exactement le moment de fermer :
 * un plafond à zéro et une interdiction disent la même chose, mais seule la
 * seconde le dit à qui lit le code.
 *
 * Le remplacement est `demander()` (`#lib/saisie`) pour une saisie, et un
 * `toast()` pour un message — `alert()` n'a jamais eu d'usage légitime ici.
 */
const BOITES_NATIVES = [
	['prompt', 'demander() — `#lib/saisie`'],
	['alert', "toast('info' | 'error', …) — `#lib/components/Toast.svelte`"],
];

const releve = [];
const natives = [];
const sansAwait = [];
for (const chemin of tous) {
	const rel = relative(SOURCE, chemin).split(sep).join('/');
	if (HORS_RELEVE.includes(rel)) continue;
	//  🔴 LES COMMENTAIRES SONT NEUTRALISÉS, depuis le 31/08/2026.
	//
	//  Ce contrôle lisait le fichier brut. Deux commentaires écrits ce jour-là —
	//  « L'aperçu de ce qui partira, avant de confirmer (#498) » — ont donc été
	//  comptés comme des appels sans `await`, et la CI a échoué sur du texte.
	//
	//  ⚠️ Un contrôle qui crie sur du légitime finit désarmé (leçon de C16), et
	//  le remède évident aurait été de reformuler la phrase pour lui plaire —
	//  c'est-à-dire de laisser le contrôle dicter la prose. Les autres contrôles
	//  du dépôt neutralisent les commentaires depuis longtemps ; celui-ci ne le
	//  faisait pas, et personne ne l'avait vu parce qu'aucun commentaire n'avait
	//  encore employé le mot.
	//
	//  La neutralisation remplace le texte par des espaces sans changer le nombre
	//  de lignes : les numéros du relevé restent justes.
	const lignes = sansCommentaires(readFileSync(chemin, 'utf8')).split('\n');
	lignes.forEach((ligne, i) => {
		//  `confirmer(` est le remplacement : il ne doit pas compter.
		if (/\bconfirm\s*\(/.test(ligne)) releve.push(`${rel}:${i + 1}`);
		for (const [nom, remplacement] of BOITES_NATIVES) {
			if (new RegExp(String.raw`(?<![.\w])${nom}\s*\(`).test(ligne))
				natives.push(`${rel}:${i + 1} — \`${nom}()\` → ${remplacement}`);
		}
		//  `confirmer(` sans `await` — le geste part sans confirmation.
		if (/\bconfirmer\s*\(/.test(ligne) && APPELS_SANS_AWAIT.test(ligne)) {
			sansAwait.push(`${rel}:${i + 1} — ${ligne.trim().slice(0, 70)}`);
		}
	});
}

if (natives.length) {
	console.error(
		`\n✗ ${natives.length} boîte(s) NATIVE(s) du navigateur :\n\n` +
			natives.map((l) => `   ${l}`).join('\n') +
			'\n\n  🔴 Elles bloquent le navigateur entier, ignorent la charte, et sur' +
			"\n  mobile s'affichent en haut de l'écran, loin du pouce. Le site a son" +
			'\n  équivalent pour chacune, et le compte était à ZÉRO le 12/09/2026.\n',
	);
	process.exit(1);
}

if (sansAwait.length) {
	console.error(
		`\n✗ ${sansAwait.length} appel(s) à \`confirmer()\` SANS \`await\` :\n\n` +
			sansAwait.map((l) => `   ${l}`).join('\n') +
			'\n\n  🔴 `confirmer()` rend une PROMESSE : sans `await`, elle est toujours' +
			'\n  *truthy*, la garde ne retourne jamais, et le geste part SANS que personne' +
			'\n  ait confirmé. Rien ne le signale — ni erreur, ni journal.\n' +
			"\n  La forme : `if (!(await confirmer('…'))) return;`\n",
	);
	process.exit(1);
}

if (releve.length) {
	console.error(
		`\n✗ ${releve.length} appel(s) à \`confirm()\` natif :\n\n` +
			releve.map((l) => `   ${l}`).join('\n') +
			`\n\n  La boîte native bloque le navigateur, ignore la charte, et donne le MÊME` +
			`\n  aspect à « archiver » et à « supprimer définitivement ». Le compte est à` +
			`\n  ZÉRO depuis le 25/09/2026 (#1043).` +
			`\n  → \`if (!(await confirmer('…'))) return;\` — \`#lib/confirmation\`, une ligne,` +
			`\n    et \`SUPPRESSION(…)\` pour ce qui ne se défait pas.\n`,
	);
	process.exit(1);
}

console.log(
	`✓ Confirmation : aucun \`confirm()\`, \`prompt()\` ni \`alert()\` natif ` +
		`(${tous.length} fichiers analysés), et chaque \`confirmer()\` est attendu.`,
);
