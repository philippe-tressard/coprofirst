#!/usr/bin/env node
/**
 *  Un texte posé sur un APLAT se dit par son jeton, et l'aplat par le sien
 *  (mode sombre, #2174 — lot S0, 27/10/2026).
 *
 *  Un jeton de la charte sert deux fois : de texte ou de filet (`--color-primary`
 *  d'un lien), et d'aplat sous un texte clair (le fond d'un bouton). Au sombre le
 *  premier s'éclaircit et le second reste assez foncé pour porter du blanc : ils
 *  ne peuvent plus être le même jeton. `socle.css` porte les paires —
 *  `--color-<état>-plein` pour l'aplat, `--color-sur-plein` pour le texte dessus,
 *  `--color-sur-voile` sur un voile noir translucide, qui ne change jamais.
 *
 *  Ce qu'il refuse :
 *  1. `color` à `var(--color-surface)`, `#fff` ou `white` : un texte clair écrit
 *     avec la valeur d'un FOND (la surface devient sombre au sombre, et son texte
 *     avec elle) — dire `--color-sur-plein` ou `--color-sur-voile` ;
 *  2. une règle dont le texte est `--color-sur-plein` et le fond un jeton NU
 *     (`background: var(--color-primary)`) : dire `--color-primary-plein`.
 *
 *  Lancer : node scripts/check-aplats.mjs [--selftest]
 */
import { controler } from './lib-source-unique.mjs';
import { neutraliserCommentaires } from './lib-commentaires.mjs';

const TEXTE_CLAIR = /(?<![-\w])color\s*:\s*(var\(--color-surface\)|#fff(?:fff)?\b|white\b)/i;
const SUR_PLEIN = /(?<![-\w])color\s*:\s*var\(--color-sur-plein\)/;
const APLAT_NU = /background(?:-color)?\s*:\s*var\(--color-(?:primary|danger|success|accent)\)/;

/** Les numéros de ligne fautifs d'un texte. PURE. */
function fautes(texte) {
	const t = neutraliserCommentaires(texte);
	const ligneDe = (i) => t.slice(0, i).split('\n').length;
	const lignes = new Set();
	t.split('\n').forEach((l, i) => {
		if (TEXTE_CLAIR.test(l)) lignes.add(i + 1);
	});
	for (const m of t.matchAll(/\{[^{}]*\}/g)) {
		if (SUR_PLEIN.test(m[0]) && APLAT_NU.test(m[0])) lignes.add(ligneDe(m.index));
	}
	return [...lignes].sort((a, b) => a - b);
}

process.exitCode = controler({
	extensions: ['.svelte', '.css'],
	fautes,
	cas: [
		['.a { color: var(--color-surface); }', 1],
		['.a { color:#fff; }', 1],
		['.a { color: #FFFFFF; }', 1],
		['.a { color: white; }', 1],
		['.a { color: var(--color-sur-plein); background: var(--color-primary-plein); }', 0],
		['.a { color: var(--color-sur-plein); background: var(--color-primary); }', 1],
		['.a { background: var(--color-danger);\n color: var(--color-sur-plein); }', 1],
		['.a { color: var(--color-sur-voile); background: rgba(0, 0, 0, 0.5); }', 0],
		['.a { background: var(--color-primary); color: var(--color-text); }', 0],
		['.a { background: var(--color-surface); }', 0],
		['.a { --color-sur-plein: #ffffff; }', 0],
		['/* color: var(--color-surface); */', 0],
	],
	ok: 'Aplats : aucun texte clair écrit avec la valeur d’un fond',
	ko: 'texte(s) clair(s) posé(s) sur un aplat sans le jeton qui convient',
	conseil:
		'Texte : `--color-sur-plein` (ou `--color-sur-voile` sur un voile noir) ; aplat : `--color-<état>-plein`.',
});
