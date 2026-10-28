#!/usr/bin/env node
/**
 *  La teinte d'un badge venue d'une TABLE se rend par `Badge` (#1571, 15/10/2026).
 *
 *  🔴 `class="badge {expr}"` était écrit vingt-six fois, dans vingt-quatre fichiers.
 *  Devant une classe interpolée, le compilateur Svelte cesse de déclarer les
 *  sélecteurs inutilisés POUR TOUT LE FICHIER : chacune de ces lignes rendait son
 *  écran aveugle à `lint:css-orphelin` (25 fichiers « non mesurables » sur la
 *  carte #1571, dont 24 par un badge). `BadgeVerdict` et `BadgeEtatService`
 *  posaient déjà la teinte par `class:` — c'est cette règle qui se généralise,
 *  écrite une fois dans `Badge.svelte`, qui n'a pas de `<style>`.
 *
 *  Ce contrôle tient trois choses :
 *  1. aucune classe `badge` interpolée hors de `Badge` ;
 *  2. les teintes que `Badge` sait poser sont EXACTEMENT les `.badge-*` des
 *     feuilles — une teinte ajoutée à la charte et oubliée dans le composant
 *     rendrait un badge sans couleur, sans un mot ;
 *  3. une teinte écrite dans le code (`'badge-xxx'`) existe dans les feuilles, ou
 *     se déclare dans `SANS_REGLE` avec son ticket — c'est ainsi qu'est apparue
 *     `badge-teal`, sans règle depuis la v1.0.0 : teintée le 16/10/2026 (#1986),
 *     la liste est vide et le reste.
 *
 *  Lancer : node scripts/check-badge.mjs [--selftest]
 */
import { existsSync, readFileSync } from 'node:fs';
import { controler, fichiersSources, lignesPortant } from './lib-source-unique.mjs';
import { neutraliserCommentaires } from './lib-commentaires.mjs';

const BADGE = 'src/lib/components/Badge.svelte';

/**  Les `.badge-*` qui ne sont pas des teintes de table : rendues par leur
 *   composant propre, jamais par `Badge`. */
const HORS_BADGE = {
	'badge-perimetre': 'rendue par `BadgePerimetre` seul (§2 de `ux-patterns`)',
};

/**  Teintes écrites dans le code sans règle CSS — chacune avec son ticket. Une
 *   entrée qui ne sert plus fait échouer le contrôle. */
const SANS_REGLE = {};

const INTERPOLEE = /class="badge\b[^"]*\{/;

/** Les teintes `.badge-*` déclarées par les feuilles communes. PURE. */
export function teintesDesFeuilles(css) {
	return [...new Set([...css.matchAll(/^\.(badge-[a-z]+)\s*[{,]/gm)].map((m) => m[1]))].sort();
}

/** Les teintes que `Badge` sait poser (`class:badge-x=`). PURE. */
export function teintesDuComposant(source) {
	return [...new Set([...source.matchAll(/class:(badge-[a-z]+)=/g)].map((m) => m[1]))].sort();
}

/** Les teintes écrites en littéral (`'badge-x'`), hors commentaires. PURE. */
export function teintesEcrites(source) {
	return [...neutraliserCommentaires(source).matchAll(/'(badge-[a-z]+)'/g)].map((m) => m[1]);
}

/** Les écarts entre feuilles, composant et code. PURE. */
export function ecartsTeintes(feuilles, composant, ecrites, sansRegle = SANS_REGLE) {
	const attendues = feuilles.filter((t) => !(t in HORS_BADGE));
	const ecarts = [];
	for (const t of attendues)
		if (!composant.includes(t)) ecarts.push(`${t} : teinte des feuilles que \`Badge\` ne pose pas`);
	for (const t of composant)
		if (!attendues.includes(t))
			ecarts.push(`${t} : posée par \`Badge\` sans règle dans les feuilles`);
	const connues = new Set([...feuilles, ...Object.keys(sansRegle)]);
	for (const t of new Set(ecrites))
		if (!connues.has(t)) ecarts.push(`${t} : écrite dans le code, définie nulle part`);
	for (const t of Object.keys(sansRegle)) {
		if (feuilles.includes(t))
			ecarts.push(
				`${t} : déclarée sans règle, mais les feuilles la définissent — retirer l'exception`,
			);
		else if (!ecrites.includes(t)) ecarts.push(`${t} : exception qui ne sert plus — la retirer`);
	}
	return ecarts;
}

function concordance() {
	const feuilles = teintesDesFeuilles(
		fichiersSources('src/styles', ['.css'])
			.map((f) => readFileSync(f, 'utf8'))
			.join('\n'),
	);
	if (!feuilles.length) return ['aucune teinte `.badge-*` lue sous src/styles : contrôle INCONNU'];
	if (!existsSync(BADGE)) return [`${BADGE} absent : la source unique manque`];
	const composant = teintesDuComposant(readFileSync(BADGE, 'utf8'));
	const ecrites = fichiersSources('src', ['.svelte', '.ts']).flatMap((f) =>
		teintesEcrites(readFileSync(f, 'utf8')),
	);
	return ecartsTeintes(feuilles, composant, ecrites);
}

function selftestConcordance() {
	const F = ['badge-blue', 'badge-gray', 'badge-perimetre'];
	//  Une exception témoin : la liste réelle est vide, le mécanisme doit servir.
	const E = { 'badge-teal': '#témoin' };
	const ecarts = (f, c, e, x = E) => ecartsTeintes(f, c, e, x);
	const cas = [
		[
			'tout concorde',
			ecarts(F, ['badge-blue', 'badge-gray'], ['badge-blue', 'badge-teal']).length,
			0,
		],
		['teinte oubliée par le composant', ecarts(F, ['badge-blue'], ['badge-teal']).length, 1],
		[
			'teinte du composant sans règle',
			ecarts(F, ['badge-blue', 'badge-gray', 'badge-rose'], ['badge-teal']).length,
			1,
		],
		[
			'teinte écrite, définie nulle part',
			ecarts(F, ['badge-blue', 'badge-gray'], ['badge-rose', 'badge-teal']).length,
			1,
		],
		['exception qui ne sert plus', ecarts(F, ['badge-blue', 'badge-gray'], []).length, 1],
		[
			'lecture des feuilles',
			teintesDesFeuilles('.badge {\n}\n.badge-blue {\n}\n.badge-red,\n.x {}').join(),
			'badge-blue,badge-red',
		],
		[
			'un commentaire ne compte pas',
			teintesEcrites("// 'badge-rose'\nconst t = 'badge-blue';").join(),
			'badge-blue',
		],
	];
	let ko = 0;
	for (const [quoi, obtenu, attendu] of cas) {
		const ok = obtenu === attendu;
		console.log(`${ok ? 'PASS' : 'FAIL'}  ${quoi}`);
		if (!ok) ko = 1;
	}
	return ko;
}

let code = controler({
	extensions: ['.svelte'],
	sources: [BADGE],
	fautes: lignesPortant(INTERPOLEE),
	cas: [
		['<span class="badge {statutBadge(x)}">{label}</span>', 1],
		['<span class="badge {t} pastille-xs">', 1],
		['\t\tclass="badge {cond\n', 1],
		//  La forme voulue, jamais signalée.
		['<Badge teinte={statutBadge(x)}>{label}</Badge>', 0],
		['<span class="badge badge-gray">fixe</span>', 0],
		['<span class="badge" class:badge-green={ok}>', 0],
		['<!-- on écrivait class="badge {x}" ici -->', 0],
	],
	ok: 'Badges : aucune teinte interpolée hors de `Badge`',
	ko: 'classe(s) `badge` interpolée(s) — l’écran devient aveugle à `lint:css-orphelin`',
	conseil:
		'Employer `<Badge teinte={…}>` (`#lib/components/Badge.svelte`) ; `petit` pour le cran `--fs-2xs`.',
});
if (process.argv.includes('--selftest')) {
	code = selftestConcordance() || code;
} else {
	const ecarts = concordance();
	if (ecarts.length) {
		console.error(`\n✗ Teintes de badge : ${ecarts.length} écart(s)`);
		for (const e of ecarts) console.error(`   ${e}`);
		code = 1;
	} else {
		console.log('✓ Teintes de badge : feuilles, composant et code concordent.');
	}
}
process.exit(code);
