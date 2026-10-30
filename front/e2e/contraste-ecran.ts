/*
 *  **Ce qu'un écran rendu au SOMBRE donne à lire** (mode sombre, #2174 — lot S4).
 *
 *  `lint:palette-sombre` mesure des PAIRES déclarées de jetons ; il ne voit pas
 *  l'écran. Un composant qui lit le mauvais jeton — un texte écrit avec la valeur
 *  d'un fond, une surface restée blanche — passe ce contrôle et se voit à l'écran.
 *  Ce relevé lit l'écran : pour chaque élément visible, la couleur CALCULÉE de son
 *  texte sur le fond qu'il a réellement (fonds translucides composés, opacité des
 *  ancêtres comprise), et la clarté de son propre fond.
 *
 *  Ce qu'il ne mesure pas, et le dit : un texte posé sur un DÉGRADÉ ou une image
 *  (le fond n'est pas une couleur) est compté dans `nonMesures`, jamais lu comme
 *  conforme. Un contrôle désactivé est hors de l'AA (WCAG 1.4.3, « composants
 *  inactifs ») et n'est pas mesuré, ni un texte qui n'est qu'émoji : la police
 *  le peint en couleur, il ne suit pas `color`.
 *
 *  Écrit une fois pour les quatre zones de S4 : chaque spec `@sombre` l'appelle.
 */
import type { Page } from '@playwright/test';
import { expect } from './aides';

/** Le thème de la page : `sombre` pose `data-theme="dark"`, `clair` retire l'attribut. */
export async function forcerTheme(page: Page, theme: 'clair' | 'sombre'): Promise<void> {
	await page.evaluate((t) => {
		const racine = document.documentElement;
		if (t === 'clair') racine.removeAttribute('data-theme');
		else racine.setAttribute('data-theme', 'dark');
	}, theme);
	//  Bordures et fonds ont une transition (`--duree-geste`) : on attend qu'elle se pose.
	await page.waitForTimeout(350);
}

/**
 * **Attendre que les fondus de la page soient POSÉS** (#2334) — toute animation
 * finie du document, transitions comprises (celles qui bouclent sont laissées).
 * L'accueil entre en fondu échelonné (`.section-reveal`, gardé en mouvement
 * réduit) : sous charge, le relevé lisait des cartes à demi opaques — un blanc
 * à ~55 % sur `--color-bg` rendait « DIAG. » à 4,42 sur rgb(249, 248, 245).
 */
export async function attendreFinDesAnimations(page: Page): Promise<void> {
	await page.evaluate(() =>
		Promise.all(
			document
				.getAnimations()
				.filter((a) => a.effect?.getComputedTiming().iterations !== Infinity)
				.map((a) => a.finished.catch(() => undefined)),
		),
	);
}

/**
 * **Attendre qu'une portion de l'écran se lise au thème posé** : rien sous l'AA,
 * rien de clair au sombre, et du texte LU. Une modale ou un toast entre en
 * fondu : au premier instant son texte est à opacité nulle, donc ni fautif ni
 * mesuré — sans `texteLu`, le relevé passait à vide.
 */
export async function attendreLisible(
	page: Page,
	portee = 'body',
	options: OptionsReleve = {},
): Promise<void> {
	await expect
		.poll(
			async () => {
				const { contrastes, surfacesClaires, marques, mesures } = await releverContrastes(
					page,
					portee,
					options,
				);
				return { contrastes, surfacesClaires, marques, texteLu: mesures > 0 };
			},
			{ message: `relevé de contraste : ${portee}` },
		)
		.toEqual({ contrastes: [], surfacesClaires: [], marques: [], texteLu: true });
}

export type OptionsReleve = {
	/**
	 * Le sélecteur des MARQUES de données (barre, tranche, segment d'un
	 * graphique) : claires exprès au sombre, elles ne sont pas des surfaces.
	 * Chacune se mesure à 3:1 contre le fond de son parent (WCAG 1.4.11).
	 */
	marques?: string;
};

export type Releve = {
	/** Un texte sous son seuil : 4,5, ou 3 pour un grand texte. */
	contrastes: string[];
	/** Une surface claire (luminance > 0,4) au thème sombre. */
	surfacesClaires: string[];
	/** Une marque de données (`options.marques`) sous 3:1 contre le fond de son parent. */
	marques: string[];
	/** Les textes mesurés — zéro est un échec, pas un succès. */
	mesures: number;
	/** Les textes posés sur un dégradé ou une image : non mesurés. */
	nonMesures: number;
};

/**
 * Relève les textes sous l'AA et les surfaces claires d'une portion de la page.
 * `portee` : le sélecteur de la racine relevée (une modale, un menu ouvert…).
 */
export function releverContrastes(
	page: Page,
	portee = 'body',
	options: OptionsReleve = {},
): Promise<Releve> {
	return page.evaluate(
		([selecteur, selecteurMarques]) => {
			const toile = document
				.createElement('canvas')
				.getContext('2d', { willReadFrequently: true })!;
			/** Toute couleur CSS (`color(srgb …)` d'un `color-mix` compris) en [r, g, b, a]. */
			const rgba = (c: string): number[] => {
				toile.clearRect(0, 0, 1, 1);
				toile.fillStyle = 'rgba(0, 0, 0, 0)';
				toile.fillStyle = c;
				toile.fillRect(0, 0, 1, 1);
				const d = toile.getImageData(0, 0, 1, 1).data;
				return [d[0], d[1], d[2], d[3] / 255];
			};
			const composer = (dessous: number[], dessus: number[], a: number) =>
				dessous.map((v, i) => v * (1 - a) + dessus[i] * a);
			const luminance = ([r, g, b]: number[]) => {
				const f = (v: number) => {
					const s = v / 255;
					return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
				};
				return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b);
			};
			const SEULEMENT_EMOJI = /^[\p{Extended_Pictographic}\u{FE0F}\u{200D}\s]+$/u;
			const rapport = (a: number[], b: number[]) => {
				const [l1, l2] = [luminance(a), luminance(b)].sort((x, y) => y - x);
				return (l1 + 0.05) / (l2 + 0.05);
			};
			/** Le fond réellement sous un élément, ou `null` s'il est un dégradé ou une image. */
			const fondDe = (el: Element): number[] | null => {
				const couches: number[][] = [];
				for (let e: Element | null = el; e; e = e.parentElement) {
					const s = getComputedStyle(e);
					if (s.backgroundImage !== 'none') return null;
					const c = rgba(s.backgroundColor);
					if (c[3] > 0) {
						couches.push(c);
						if (c[3] >= 1) break;
					}
				}
				let fond = rgba(getComputedStyle(document.documentElement).backgroundColor).slice(0, 3);
				for (const c of couches.reverse()) fond = composer(fond, c.slice(0, 3), c[3]);
				return fond;
			};
			const opaciteDe = (el: Element) => {
				let o = 1;
				for (let e: Element | null = el; e; e = e.parentElement)
					o *= Number(getComputedStyle(e).opacity);
				return o;
			};
			const nom = (e: Element) => {
				const classes = typeof e.className === 'string' ? e.className : '';
				const propres = classes.split(/\s+/).filter((c) => c && !c.startsWith('svelte-'));
				return e.tagName.toLowerCase() + (propres.length ? '.' + propres.join('.') : '');
			};
			const chemin = (e: Element) => {
				const morceaux: string[] = [];
				for (let x: Element | null = e; x && morceaux.length < 3; x = x.parentElement)
					morceaux.unshift(nom(x));
				return morceaux.join(' > ');
			};

			const racine = document.querySelector(selecteur);
			const releve = {
				contrastes: [] as string[],
				surfacesClaires: [] as string[],
				marques: [] as string[],
				mesures: 0,
				nonMesures: 0,
			};
			if (!racine) return releve;
			const sombre = document.documentElement.getAttribute('data-theme') === 'dark';
			for (const el of [racine, ...Array.from(racine.querySelectorAll('*'))]) {
				const boite = el.getBoundingClientRect();
				if (boite.width < 1 || boite.height < 1) continue;
				const s = getComputedStyle(el);
				if (s.visibility !== 'visible' || opaciteDe(el) === 0) continue;
				//  Une surface : au moins 6 px dans les deux sens — un filet ou un point
				//  (les traits du bouton ☰) est un pictogramme, pas un fond.
				const fondPropre = rgba(s.backgroundColor);
				if (selecteurMarques && fondPropre[3] > 0 && el.matches(selecteurMarques)) {
					const dessous = el.parentElement ? fondDe(el.parentElement) : null;
					if (!dessous) releve.nonMesures++;
					else {
						const marque = composer(dessous, fondPropre.slice(0, 3), fondPropre[3]);
						const r = rapport(marque, dessous);
						if (r < 3)
							releve.marques.push(`${chemin(el)} — ${s.backgroundColor} : ${r.toFixed(2)}`);
					}
				} else if (
					sombre &&
					fondPropre[3] > 0.5 &&
					Math.min(boite.width, boite.height) >= 6 &&
					luminance(fondPropre) > 0.4
				)
					releve.surfacesClaires.push(`${chemin(el)} — fond ${s.backgroundColor}`);
				//  Un texte qui n'est QU'émoji (le ✨ de `MarqueIA`) est peint en couleur
				//  par la police et ne suit pas `color` : rien à mesurer.
				const texte = Array.from(el.childNodes).some(
					(n) =>
						n.nodeType === Node.TEXT_NODE &&
						n.textContent!.trim() &&
						!SEULEMENT_EMOJI.test(n.textContent!),
				);
				if (!texte || el.closest(':disabled, [aria-disabled="true"]')) continue;
				const fond = fondDe(el);
				if (!fond) {
					releve.nonMesures++;
					continue;
				}
				//  L'opacité d'un ancêtre (carte archivée à 0,8, fondu d'entrée) atténue le
				//  CALQUE entier, fond compris : texte et fond se composent tous deux sur
				//  le fond de la page — n'atténuer que l'encre noircirait le rapport.
				const encre = rgba(s.color);
				const opacite = opaciteDe(el);
				const page = rgba(getComputedStyle(document.documentElement).backgroundColor).slice(0, 3);
				const vu = composer(page, composer(fond, encre.slice(0, 3), encre[3]), opacite);
				const r = rapport(vu, composer(page, fond, opacite));
				const taille = parseFloat(s.fontSize);
				const grand = taille >= 24 || (taille >= 18.66 && Number(s.fontWeight) >= 700);
				releve.mesures++;
				if (r < (grand ? 3 : 4.5)) {
					const extrait = (el.textContent ?? '').trim().replace(/\s+/g, ' ').slice(0, 32);
					releve.contrastes.push(
						`${chemin(el)} « ${extrait} » ${s.color} sur rgb(${fond.map(Math.round).join(', ')}) : ${r.toFixed(2)}`,
					);
				}
			}
			return releve;
		},
		[portee, options.marques ?? ''] as const,
	);
}
