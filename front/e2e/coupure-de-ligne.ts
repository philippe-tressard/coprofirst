/*
 *  **Un séparateur ne finit jamais une ligne** — la mesure sur le rendu (#2360).
 *
 *  La règle (`#lib/separateurs`) : espace sécable AVANT le séparateur, insécable
 *  APRÈS. Ce qui se vérifie ici n'est pas le source mais la COUPURE que trace le
 *  navigateur : pour chaque séparateur (— · →), le caractère visible suivant
 *  est-il sur la même ligne ?
 *
 *  Une seule largeur prouverait peu — la ligne se coupe ailleurs, ou pas du
 *  tout. Le bloc est donc rétréci pas à pas (`max-width`, un témoin posé dans la
 *  page) de sa largeur rendue jusqu'à `plancher`, et chaque coupure est jugée.
 *  Le cas zéro est rendu avec : le nombre de largeurs où le texte a bien passé à
 *  la ligne — zéro, et l'absence de fautif ne prouverait rien.
 */
import type { Locator } from '@playwright/test';

export type MesureCoupures = {
	/** les séparateurs lus dans le bloc : sans eux, il n'y a rien à juger */
	separateurs: number;
	/** les largeurs essayées où le texte tenait sur plus d'une ligne */
	largeursCoupees: number;
	/** « largeur px : …contexte· » pour chaque séparateur laissé en bout de ligne */
	fautifs: string[];
};

/** Mesure les coupures du bloc `cible` de sa largeur rendue jusqu'à `plancher` px. */
export async function separateursEnFinDeLigne(
	cible: Locator,
	{ plancher = 120, pas = 6 }: { plancher?: number; pas?: number } = {},
): Promise<MesureCoupures> {
	return cible.evaluate(
		(bloc, { plancher, pas }) => {
			const el = bloc as HTMLElement;
			const SEP = /[—·→]/;
			const caracteres = () => {
				const car: { c: string; haut: number }[] = [];
				const parcours = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
				for (let n = parcours.nextNode(); n; n = parcours.nextNode()) {
					const texte = n.textContent ?? '';
					for (let i = 0; i < texte.length; i++) {
						if (/\s/.test(texte[i])) continue;
						const r = document.createRange();
						r.setStart(n, i);
						r.setEnd(n, i + 1);
						const rect = r.getBoundingClientRect();
						if (!rect.width && !rect.height) continue;
						car.push({ c: texte[i], haut: rect.top + rect.height / 2 });
					}
				}
				return car;
			};
			const avant = el.style.maxWidth;
			const depart = Math.floor(el.getBoundingClientRect().width);
			const fautifs: string[] = [];
			let largeursCoupees = 0;
			for (let w = depart; w >= plancher; w -= pas) {
				el.style.maxWidth = `${w}px`;
				const car = caracteres();
				if (new Set(car.map((x) => Math.round(x.haut))).size > 1) largeursCoupees++;
				car.forEach((x, i) => {
					//  Un séparateur dont le voisin est plus bas que lui finit sa ligne.
					if (SEP.test(x.c) && i + 1 < car.length && car[i + 1].haut - x.haut > 4) {
						const contexte = car
							.slice(Math.max(0, i - 8), i + 1)
							.map((y) => y.c)
							.join('');
						fautifs.push(`${w} px : …${contexte}`);
					}
				});
			}
			el.style.maxWidth = avant;
			const separateurs = caracteres().filter((x) => SEP.test(x.c)).length;
			return { separateurs, largeursCoupees, fautifs };
		},
		{ plancher, pas },
	);
}
