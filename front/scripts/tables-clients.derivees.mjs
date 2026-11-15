/**
 * **Les tables DÉRIVÉES de `tables-clients.json`** — calculées depuis d'autres tables
 * publiées, jamais lues dans une source (#2754).
 *
 * ## Pourquoi
 *
 * Les deux apps (coprofirst-ios, coprofirst-android) tiraient leurs couleurs de
 * `jetonsCharte`, `jetonsCharteSombre`, `palettesClaires` et `palettesSombres`, et
 * refaisaient CHACUNE la même résolution : la cascade du site, puis les `var(--…)` et
 * le `color-mix`. Une vingtaine de lignes en double entre deux dépôts, qui divergent
 * au premier jeton ajouté. La résolution vit ici, une fois ; les apps lisent le
 * résultat (`palettesResolues`).
 *
 * ## La cascade — celle d'`app.css`
 *
 * `socle.css` (`:root`), puis `palettes.css` (`[data-palette]`), puis
 * `palette-sombre.css` (`[data-theme='dark']`) : à spécificité égale, la dernière
 * feuille l'emporte. Au clair, la palette sur la charte ; au sombre, la charte sombre
 * par-dessus la palette claire, puis la palette sombre. « seine » est la palette sans
 * règle propre : la charte seule.
 *
 * Une valeur que la résolution ne sait pas réduire à `#rrggbb` ou `rgba(…)` est
 * REFUSÉE (la CI échoue en la nommant) : jamais publiée telle quelle, jamais omise.
 */
import { Refus } from './tables-clients.lecture.mjs';

/** Les familles publiées : celles que les apps peignent. */
export const FAMILLES_RESOLUES = /^--(color|fil|kanban|serie|palier)-/;
/** La palette sans règle propre dans `palettes.css` : la charte seule. */
export const PALETTE_PAR_DEFAUT = 'seine';

const HEX = /^#([0-9a-f]{3}|[0-9a-f]{6}|[0-9a-f]{8})$/i;
const RGBA = /^rgba?\(\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)\s*(?:,\s*([\d.]+)\s*)?\)$/i;
const VAR = /var\(\s*(--[a-z0-9-]+)\s*(?:,\s*([^()]*))?\)/i;
const MIX = /^color-mix\(\s*in srgb\s*,\s*(.+?)\s+([\d.]+)%\s*,\s*(.+?)\s*\)$/i;
const NOMMEES = { black: [0, 0, 0, 1], white: [255, 255, 255, 1], transparent: [0, 0, 0, 0] };

/** Une couleur littérale → [r, g, b, a], ou `null`. PURE. */
export function canaux(valeur) {
	const v = valeur.trim().toLowerCase();
	if (NOMMEES[v]) return NOMMEES[v];
	if (HEX.test(v)) {
		let h = v.slice(1);
		if (h.length === 3) h = [...h].map((c) => c + c).join('');
		const n = (i) => parseInt(h.slice(i, i + 2), 16);
		return [n(0), n(2), n(4), h.length === 8 ? n(6) / 255 : 1];
	}
	const m = v.match(RGBA);
	return m ? [+m[1], +m[2], +m[3], m[4] === undefined ? 1 : +m[4]] : null;
}

/** [r, g, b, a] → `#rrggbb` (opaque) ou `rgba(r, g, b, a)`. PURE. */
export function ecrire([r, g, b, a]) {
	const x = (n) => Math.round(n).toString(16).padStart(2, '0');
	if (a === 1) return `#${x(r)}${x(g)}${x(b)}`;
	return `rgba(${Math.round(r)}, ${Math.round(g)}, ${Math.round(b)}, ${+a.toFixed(3)})`;
}

/** `color-mix(in srgb, A p%, B)` sur deux couleurs (alpha prémultiplié, CSS Color 5). PURE. */
function melanger(a, p, b) {
	const alpha = a[3] * p + b[3] * (1 - p);
	if (alpha === 0) return [0, 0, 0, 0];
	const c = (i) => (a[i] * a[3] * p + b[i] * b[3] * (1 - p)) / alpha;
	return [c(0), c(1), c(2), alpha];
}

/** La valeur de `nom` dans `jetons`, réduite à ses canaux. PURE. */
export function resoudre(nom, jetons, pile = []) {
	if (pile.includes(nom)) throw new Refus(`palettesResolues : ${[...pile, nom].join(' → ')} se cite lui-même`);
	const brut = jetons[nom];
	if (brut === undefined) throw new Refus(`palettesResolues : ${nom} n'est déclaré nulle part (${pile.join(' → ')})`);
	return reduire(String(brut), jetons, [...pile, nom]);
}

function reduire(valeur, jetons, pile) {
	const v = valeur.trim();
	const seule = v.match(new RegExp(`^${VAR.source}$`, 'i'));
	if (seule) {
		if (seule[1] in jetons) return resoudre(seule[1], jetons, pile);
		if (seule[2] !== undefined) return reduire(seule[2], jetons, pile);
		return resoudre(seule[1], jetons, pile); // lève en le nommant
	}
	const mix = v.match(MIX);
	if (mix) return melanger(reduire(mix[1], jetons, pile), +mix[2] / 100, reduire(mix[3], jetons, pile));
	const c = canaux(v);
	if (c) return c;
	throw new Refus(`palettesResolues : ${pile.at(-1)} vaut « ${v} », que la résolution ne réduit pas`);
}

/**
 * Les jetons résolus, par palette et par thème. PURE.
 * → `{ <code>: { clair: { --jeton: couleur }, sombre: { … } } }`, codes dans l'ordre
 *   (« seine » d'abord, puis ceux de `palettesClaires`), jetons triés.
 */
export function palettesResolues({ jetonsCharte, jetonsCharteSombre, palettesClaires, palettesSombres }) {
	const codes = [PALETTE_PAR_DEFAUT, ...Object.keys(palettesClaires).filter((c) => c !== PALETTE_PAR_DEFAUT)];
	const publier = (jetons) =>
		Object.fromEntries(
			Object.keys(jetons)
				.filter((n) => FAMILLES_RESOLUES.test(n))
				.sort()
				.map((n) => [n, ecrire(resoudre(n, jetons))]),
		);
	return Object.fromEntries(
		codes.map((code) => {
			const claire = palettesClaires[code] ?? {};
			return [
				code,
				{
					clair: publier({ ...jetonsCharte, ...claire }),
					sombre: publier({ ...jetonsCharte, ...claire, ...jetonsCharteSombre, ...(palettesSombres[code] ?? {}) }),
				},
			];
		}),
	);
}

/** Les dérivations, par nom publié : les tables lues, et le calcul. */
export const DERIVATIONS = {
	palettesResolues: {
		depuis: ['jetonsCharte', 'jetonsCharteSombre', 'palettesClaires', 'palettesSombres'],
		calcul: palettesResolues,
	},
};

/** Le contrat des décisions ci-dessus, faute injectée et cas zéro compris. */
export function selftestDerivees(ok, leve) {
	ok('hexadécimal court déplié', ecrire(canaux('#AbC')) === '#aabbcc');
	ok('rgba gardé', ecrire(canaux('rgba(0, 0, 0, 0.45)')) === 'rgba(0, 0, 0, 0.45)');
	ok('var() suivi en chaîne', ecrire(resoudre('--color-a', { '--color-a': 'var(--b)', '--b': 'var(--c)', '--c': '#102030' })) === '#102030');
	ok('var() et son repli', ecrire(resoudre('--color-a', { '--color-a': 'var(--absent, #fff)' })) === '#ffffff');
	ok('color-mix calculé', ecrire(resoudre('--color-a', { '--color-a': 'color-mix(in srgb, var(--b) 85%, black)', '--b': '#ffffff' })) === '#d9d9d9');
	ok('jeton absent refusé', leve(() => resoudre('--color-a', { '--color-a': 'var(--absent)' })));
	ok('cycle refusé', leve(() => resoudre('--color-a', { '--color-a': 'var(--b)', '--b': 'var(--color-a)' })));
	ok('forme inconnue refusée', leve(() => resoudre('--color-a', { '--color-a': 'hsl(10 20% 30%)' })));
	const p = palettesResolues({
		jetonsCharte: { '--color-fond': '#ffffff', '--color-primaire': 'var(--teinte)', '--teinte': '#000080', '--autre': '#123456' },
		jetonsCharteSombre: { '--color-fond': '#000000' },
		palettesClaires: { roi: { '--teinte': '#002060' } },
		palettesSombres: { roi: { '--teinte': '#4060c0' } },
	});
	ok('seine d’abord, puis les palettes', Object.keys(p).join() === 'seine,roi');
	ok('famille filtrée', !('--autre' in p.seine.clair) && !('--teinte' in p.seine.clair));
	ok('palette claire sur la charte', p.roi.clair['--color-primaire'] === '#002060');
	ok('charte sombre par-dessus', p.roi.sombre['--color-fond'] === '#000000');
	ok('palette sombre en dernier', p.roi.sombre['--color-primaire'] === '#4060c0');
	ok('seine au sombre : la charte sombre seule', p.seine.sombre['--color-primaire'] === '#000080');
}
