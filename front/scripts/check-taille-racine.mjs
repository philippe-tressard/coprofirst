#!/usr/bin/env node
/**
 *  La taille de la RACINE ne s'écrit jamais en pixels (#2165, #2166, 23/10/2026).
 *
 *  Toute l'échelle du texte (`--fs-*`) et la plupart des marges sont en `rem` :
 *  la taille de la racine les décide toutes. Elle était écrite `16px` au bureau,
 *  ce qui écrasait la taille de texte choisie dans le navigateur, et `12px` sous
 *  768 px, ce qui rendait le texte de lecture à 10,8 px sur téléphone (8,6 px
 *  pour le plus petit cran) et faisait zoomer iOS à chaque appui dans un champ.
 *  Arbitré sur maquette le 23/10/2026 : `100 %` au bureau, `87,5 %` (14 px par
 *  défaut) sur téléphone — une PROPORTION de la préférence de la personne.
 *
 *  Ce qu'il refuse : `font-size` en `px` dans un bloc `:root` ou `html`.
 *  Une cible tactile ou un champ de saisie, qui sont des tailles physiques,
 *  restent en `px` ailleurs (`--fs-saisie-tactile`, `min-height: 44px`).
 *
 *  Lancer : node scripts/check-taille-racine.mjs [--selftest]
 */
import { controler } from './lib-source-unique.mjs';
import { neutraliserCommentaires } from './lib-commentaires.mjs';

const RACINE_EN_PX = /(?:^|[\s,}])(?::root|html)\s*\{[^{}]*?font-size\s*:\s*[\d.]+px/g;

/** Les numéros de ligne des `font-size` en px posés sur la racine. PURE. */
export function fautes(texte) {
	const t = neutraliserCommentaires(texte);
	return [...t.matchAll(RACINE_EN_PX)].map(
		(m) => t.slice(0, m.index + m[0].length).split('\n').length,
	);
}

process.exitCode = controler({
	extensions: ['.svelte', '.css'],
	fautes,
	cas: [
		[':root {\n\tfont-size: 16px;\n}', 1],
		['@media (max-width: 767px) {\n\t:root {\n\t\tfont-size: 12px;\n\t}\n}', 1],
		['html { font-size: 14px }', 1],
		[':root {\n\t--fs-base: 0.9rem;\n\tfont-size: 100%;\n}', 0],
		[':root { font-size: 87.5%; }', 0],
		['.champ { font-size: 16px; }', 0],
		[':root {\n\t--fs-saisie-tactile: 16px;\n}', 0],
		['/* :root { font-size: 12px; } */', 0],
	],
	ok: 'Taille de la racine : jamais en pixels',
	ko: 'taille(s) de racine en pixels — elle écrase la préférence de la personne',
	conseil:
		'Écrire la racine en pourcentage (`100%`, `87.5%`) : une proportion de la taille choisie dans le navigateur.',
});
