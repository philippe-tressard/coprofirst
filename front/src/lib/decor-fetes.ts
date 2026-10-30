/**
 * Les tracés du DÉCOR DES JOURS DE FÊTE (#2312), partagés par le dessin
 * (`DecorFeteDessin`) et par l'élément qui le parcourt (`DecorFeteMouvement`), et l'arrêt où se pose le message (`DecorFeteMessage`).
 */
import type { CodeFete } from '#lib/fetes.ts';

//  Les tracés partagés par le décor et par l'élément qui le parcourt : une seule
//  écriture chacun, sinon l'étoile quitterait son serpentin au premier retouché.
export const SERPENTIN = 'M130 0C108 22 120 44 96 56S84 92 62 98';
export const ONDE = 'M66 0A64 64 0 0 0 130 64';
export const ETOILE = 'M12 2l2.9 6 6.6.8-4.9 4.5 1.3 6.5L12 16.6l-5.9 3.2 1.3-6.5L2.5 8.8 9.1 8Z';
export const NOTE = 'M7 19V3l7-2v4l-7 2';
/** Les cinq lignes de la portée, en arcs autour du coin ; deux notes en suivent une. */
export const PORTEE = [44, 52, 60, 68, 76].map((r) => `M${130 - r} 0A${r} ${r} 0 0 0 130 ${r}`);
/** Le fil de la toile, de son centre vers le contenu, que l'araignée parcourt. */
export const TOILE = 'M120 10L64 66';
/** Un tracé du décor, devenu le chemin que suit l'élément qui bouge. */
export const chemin = (d: string) => `path('${d}')`;
/** Les fanions du 14 juillet : position sur la guirlande, et teinte. */
export const FANIONS: readonly (readonly [number, number, string])[] = [
	[38.9, 21, 'bleu'],
	[54.6, 32.7, 'blanc'],
	[70.5, 41, 'rouge'],
	[86.4, 45.9, 'bleu'],
	[102.5, 47.4, 'blanc'],
];

/**
 * Où le message de fête se pose : l'élément qui bouge déjà (`cible`, dans le
 * décor) et l'instant de SON animation où il s'arrête (`phase`, de 0 à 1 d'un
 * tour). Le message apparaît là, le temps que l'élément reste immobile.
 */
export const PAUSES: Record<CodeFete, { cible: string; phase: number }> = {
	//  L'étoile, au bout du serpentin (elle y reste de 50 à 62 % du tour).
	'nouvel-an': { cible: '.glisse', phase: 0.56 },
	//  Le cœur du milieu, au bout de son balancement.
	'saint-valentin': { cible: '.balance', phase: 0.5 },
	//  La première bulle, là où elle éclate.
	'premier-avril': { cible: '.bulle:not(.seconde)', phase: 0.9 },
	paques: { cible: '.balance', phase: 0.5 },
	//  La première note, au bout de la portée, encore visible.
	'fete-musique': { cible: '.parcourt:not(.seconde)', phase: 0.84 },
	//  L'étincelle, à son dernier éclat.
	'quatorze-juillet': { cible: '.scintille', phase: 0.5 },
	//  L'araignée, en bas de son fil.
	halloween: { cible: '.glisse', phase: 0.56 },
	//  Le flocon, posé avant d'avoir fondu.
	noel: { cible: '.flocon', phase: 0.55 },
};
