/**
 * Les tracés du DÉCOR DES JOURS DE FÊTE (#2312), partagés par le dessin
 * (`DecorFeteDessin`) et par l'élément qui le parcourt (`DecorFeteMouvement`), et le reflet du
 * message (`DecorFeteMessage`).
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
 * La couleur du REFLET qui traverse le message de fête (`DecorFeteMessage`), par
 * fête — des jetons de la charte, qui ont leur valeur au thème sombre. Plusieurs
 * couleurs se suivent dans l'éclat (le 14 juillet). Le gris, et non le blanc, du
 * drapeau : le blanc ne se verrait pas en thème clair (arbitré le 30/10/2026).
 */
export const REFLETS: Record<CodeFete, readonly string[]> = {
	'nouvel-an': ['var(--color-accent)'],
	'saint-valentin': ['var(--fil-rose)'],
	'premier-avril': ['var(--color-primary)'],
	paques: ['var(--fil-vert)'],
	'fete-musique': ['var(--fil-violet)'],
	'quatorze-juillet': ['var(--color-primary)', 'var(--color-border-champ)', 'var(--fil-rouge)'],
	halloween: ['var(--teinte-5)'],
	noel: ['var(--color-accent)'],
};

/**
 * PURE. Le dégradé appliqué au texte du message : sa couleur, puis l'éclat au
 * milieu, puis sa couleur. La feuille l'élargit et n'anime que sa position.
 */
export function degradeReflet(fete: CodeFete): string {
	const couleurs = REFLETS[fete];
	const pas = 10 / Math.max(couleurs.length - 1, 1);
	const eclat = couleurs.map((c, i) => `${c} ${couleurs.length > 1 ? 45 + i * pas : 50}%`);
	return `linear-gradient(100deg, var(--color-primary) 41%, ${eclat.join(', ')}, var(--color-primary) 59%)`;
}
