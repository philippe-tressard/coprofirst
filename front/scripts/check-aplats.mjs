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
 *  1. un AVANT-PLAN à `var(--color-surface)`, `#fff` ou `white` — le texte
 *     (`color`), un trait (`border*`, `outline*`, `stroke`, `fill`) ou une couleur
 *     transmise à un composant (`--avatar-color`…) : un blanc écrit avec la valeur
 *     d'un FOND (la surface devient sombre au sombre, et ce qu'on posait dessus
 *     avec elle) — dire `--color-sur-plein` ou `--color-sur-voile`. Une valeur
 *     MÊLÉE (`color-mix`, dégradé) n'en est pas un. Étendu au trait par S4b
 *     (#2174) : les pointillés d'une pastille privative retenue et le quart blanc
 *     d'un indicateur passaient sombre sur sombre — la règle, qui ne lisait que
 *     `color`, ne les voyait pas. Un avant-plan posé sur un DÉGRADÉ se mesure à
 *     l'écran : s'il tient l'AA avec la surface, il se déclare en exception ;
 *  2. une règle dont le texte est `--color-sur-plein` et le fond un jeton NU
 *     (`background: var(--color-primary)`) : dire `--color-primary-plein` ;
 *  3. une règle qui pose l'OR en aplat (`background` ou `--avatar-bg`) sans dire
 *     son texte par `--color-sur-accent` : le blanc n'y fait que 2,61:1 (#2174, S3).
 *
 *  Lancer : node scripts/check-aplats.mjs [--selftest]
 */
import { controler } from './lib-source-unique.mjs';
import { neutraliserCommentaires } from './lib-commentaires.mjs';

/** Une déclaration `propriété: valeur` d'une ligne. */
const DECLARATION = /(?<![-\w])(--[\w-]+|[a-z-]+)\s*:\s*([^;{}]+)/gi;
/** Ce qui se pose DEVANT : le texte, un trait, une couleur transmise à un composant. */
const AVANT_PLAN =
	/^(?:color|border(?:-(?:top|right|bottom|left))?(?:-color)?|outline(?:-color)?|stroke|fill|--[\w-]+-colou?r)$/i;
const BLANC_DE_FOND = /var\(--color-surface\)|#fff(?:fff)?\b|\bwhite\b/i;
/** Une valeur mêlée n'est pas un blanc : mélanges et dégradés sont retirés avant de lire. */
const MELANGES = /(?:color-mix|[a-z-]*gradient)\((?:[^()]|\([^()]*\))*\)/gi;

/** La ligne pose-t-elle un avant-plan blanc écrit avec la valeur d'un fond ? PURE. */
const avantPlanClair = (ligne) =>
	[...ligne.matchAll(DECLARATION)].some(
		([, prop, val]) => AVANT_PLAN.test(prop) && BLANC_DE_FOND.test(val.replace(MELANGES, '')),
	);
const SUR_PLEIN = /(?<![-\w])color\s*:\s*var\(--color-sur-plein\)/;
const APLAT_NU = /background(?:-color)?\s*:\s*var\(--color-(?:primary|danger|success|accent)\)/;
const APLAT_OR = /(?:background(?:-color)?|--avatar-bg)\s*:\s*var\(--color-accent(?:-plein)?\)/;
const SUR_ACCENT = /(?<![-\w])(?:color|--avatar-color)\s*:\s*var\(--color-sur-accent\)/;

/** Les numéros de ligne fautifs d'un texte. PURE. */
function fautes(texte) {
	const t = neutraliserCommentaires(texte);
	const ligneDe = (i) => t.slice(0, i).split('\n').length;
	const lignes = new Set();
	t.split('\n').forEach((l, i) => {
		if (avantPlanClair(l)) lignes.add(i + 1);
	});
	for (const m of t.matchAll(/\{[^{}]*\}/g)) {
		if (SUR_PLEIN.test(m[0]) && APLAT_NU.test(m[0])) lignes.add(ligneDe(m.index));
		if (APLAT_OR.test(m[0]) && !SUR_ACCENT.test(m[0])) lignes.add(ligneDe(m.index));
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
		['.a { background: var(--color-accent-plein); color: var(--color-sur-plein); }', 1],
		['.a { --avatar-bg: var(--color-accent); }', 1],
		['.a { background: var(--color-accent-plein); color: var(--color-sur-accent); }', 0],
		['.a { --avatar-bg: var(--color-accent-plein); --avatar-color: var(--color-sur-accent); }', 0],
		['.a { color: var(--color-sur-plein); background: var(--color-primary); }', 1],
		['.a { background: var(--color-danger);\n color: var(--color-sur-plein); }', 1],
		['.a { color: var(--color-sur-voile); background: rgba(0, 0, 0, 0.5); }', 0],
		['.a { background: var(--color-primary); color: var(--color-text); }', 0],
		['.a { background: var(--color-surface); }', 0],
		['.a { --color-sur-plein: #ffffff; }', 0],
		['/* color: var(--color-surface); */', 0],
		//  Un TRAIT clair aussi (#2174, S4b) : la bordure d'une pastille retenue, le
		//  quart blanc d'un indicateur, les initiales d'un avatar.
		['.a { border-color: var(--color-surface); }', 1],
		['.a { border-top-color: var(--color-surface); }', 1],
		['.a { border: 2px dashed var(--color-surface); }', 1],
		['.a { outline: 2px solid white; }', 1],
		['.a { --avatar-color: var(--color-surface); }', 1],
		['.a { stroke: #fff; }', 1],
		['.a { border-color: var(--color-sur-plein); }', 0],
		['.a { border-top-color: var(--color-sur-voile); }', 0],
		[
			'.a { border: 1px solid color-mix(in srgb, var(--color-accent) 45%, var(--color-surface)); }',
			0,
		],
		['.a { --avatar-bg: var(--color-surface); }', 0],
		['.a { background-color: var(--color-surface); }', 0],
	],
	exceptions: {
		'src/lib/components/EnteteAccueil.svelte':
			'initiales de l’avatar sur un voile posé sur le DÉGRADÉ du héros : la surface y fait 6,1:1 au sombre, le blanc 2,6:1 (mesuré à l’écran, S4a) — l’écart est au clair (2,8:1), #2296',
	},
	ok: 'Aplats : aucun texte ni trait clair écrit avec la valeur d’un fond',
	ko: 'texte(s) ou trait(s) clair(s) posé(s) sur un aplat sans le jeton qui convient',
	conseil:
		'Texte : `--color-sur-plein` (ou `--color-sur-voile` sur un voile noir, `--color-sur-accent` sur l’or) ; aplat : `--color-<état>-plein`.',
});
