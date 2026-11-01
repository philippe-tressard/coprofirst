/*
 *  **La page ne défile pas en largeur, même quand le texte s'élargit** (#2437).
 *
 *  Le tableau d'Admin › Lots ne débordait qu'avec les polices de macOS, plus
 *  larges que celles du Linux de la CI : son `<span class="sr-only">`, en position
 *  absolue, sortait du conteneur qui défile — lequel n'était pas son bloc
 *  conteneur — et élargissait la page entière (523 px pour 393). Un iPhone a les
 *  mêmes polices. Un contrôle qui ne mesure qu'avec la police du poste ne voit que
 *  ce poste : `elargirLeTexte` impose un texte plus large que toute police de
 *  système, et le débordement se voit alors partout, CI comprise.
 */
import type { Page } from '@playwright/test';
import { expect } from './aides';

/** Un approche de lettres qui dépasse l'écart entre les polices de Linux et de macOS. */
export async function elargirLeTexte(page: Page): Promise<void> {
	await page.addStyleTag({ content: '* { letter-spacing: 0.15em !important; }' });
}

/**
 *  La page n'a rien à faire défiler en largeur — attendu, jamais lu une seule fois.
 *  C'est la seule mesure de la page entière : `npm run lint:defilement` refuse
 *  qu'un spec la recopie. `ou` dit où l'on regarde, pour le message d'échec.
 */
export async function attendreSansDefilementHorizontal(page: Page, ou?: string): Promise<void> {
	await expect
		.poll(
			() =>
				page.evaluate(
					() => document.documentElement.scrollWidth - document.documentElement.clientWidth,
				),
			{ message: `la page défile en largeur${ou ? ` — ${ou}` : ''} (px de trop)` },
		)
		.toBeLessThanOrEqual(0);
}
