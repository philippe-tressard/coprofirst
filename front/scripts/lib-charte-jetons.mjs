/**
 *  Les JETONS de la charte, lus dans `styles/socle.css` — et ce qu'on en déduit :
 *  les valeurs qui leur sont égales, le contraste du texte d'un badge.
 *
 *  Extrait de `check-charte-valeurs.mjs` le 10/10/2026 (#1571) : le contrôle
 *  dépassait 500 lignes en recevant `egalesAUnJeton`. Les deux familles lisent
 *  le même fichier de jetons ; elles vivent ensemble ici, le contrôle les appelle.
 */

/**
 *  ## Une valeur ÉGALE à un jeton s'écrit par le jeton (#1571, 10/10/2026)
 *
 *  Le 27/09, toutes avaient été converties ; le 10/10, il y en avait de nouveau
 *  85 — le plafond comptait les valeurs en dur sans distinguer celle qui A un
 *  nom. Les jetons sont LUS dans `socle.css` (une liste recopiée divergerait au
 *  premier ajout) : `--color-*` à valeur hexadécimale, `--fs-*` en `rem`. Une
 *  valeur qui en nomme deux (`--color-bg` et `--color-text-inverse`) les
 *  propose toutes deux : le choix dépend de la propriété.
 *  Les couleurs à transparence (`#rrggbbaa`) ne sont pas des jetons.
 */
export function jetonsDe(socle) {
	const couleurs = {};
	const tailles = {};
	for (const [, nom, brut] of socle.matchAll(/^\s*(--[a-z0-9-]+)\s*:\s*([^;]+);/gm)) {
		const v = brut.trim().toLowerCase();
		if (nom.startsWith('--color-') && /^#[0-9a-f]{6}$/.test(v)) (couleurs[v] ??= []).push(nom);
		if (nom.startsWith('--fs-') && /^[0-9]*\.?[0-9]+rem$/.test(v)) tailles[parseFloat(v)] = nom;
	}
	return { couleurs, tailles };
}

/** `#abc` → `#aabbcc`, en minuscules. */
const hex6 = (h) =>
	h.length === 4 ? '#' + [...h.slice(1).toLowerCase()].map((c) => c + c).join('') : h.toLowerCase();

/** Les valeurs d'un CSS (commentaires déjà retirés) égales à un jeton. */
export function egalesAUnJeton(css, { couleurs, tailles }) {
	const trouves = [];
	for (const m of css.matchAll(/font-size\s*:\s*([0-9]*\.?[0-9]+)rem/g)) {
		const jeton = tailles[parseFloat(m[1])];
		if (jeton) trouves.push([`${m[1]}rem`, `var(${jeton})`]);
	}
	for (const m of css.matchAll(/#(?:[0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b/g)) {
		const noms = couleurs[hex6(m[0])];
		if (noms) trouves.push([m[0], noms.map((n) => `var(${n})`).join(' ou ')]);
	}
	return trouves;
}

/**
 *  ## Un repli sur un jeton DÉFINI est mort (#1571, 21/10/2026)
 *
 *  `var(--color-border, #e5e7eb)` : la charte définit `--color-border`, le repli
 *  ne sert jamais — c'est une valeur en dur que le plafond comptait pour rien, et
 *  que la lecture prenait pour la vraie couleur de l'élément. Onze l'étaient,
 *  chacune avec une teinte différente de la charte. On écrit le jeton seul.
 *
 *  Ne cible QUE les noms définis dans `socle.css` : un repli sur une propriété
 *  propre à un composant (`--avatar-size`) est une API, pas un reste.
 */
export function repliMortsDe(css, socle) {
	const definis = new Set([...socle.matchAll(/^\s*(--[a-z0-9-]+)\s*:/gm)].map((m) => m[1]));
	const trouves = [];
	for (const m of css.matchAll(/var\(\s*(--[a-z0-9-]+)\s*,\s*([^)]+)\)/g)) {
		if (definis.has(m[1])) trouves.push([m[0], `var(${m[1]})`]);
	}
	return trouves;
}

/**
 *  ## Le texte d'un badge se LIT (#1410, 27/09/2026)
 *
 *  Chaque `.badge-<teinte>` de `styles/composants.css` pose un texte de
 *  0,75 rem sur un fond : il lui faut 4,5:1 (standards/11 §2). Le vert de la
 *  charte faisait 4,44 sur son propre fond — un écart que personne ne voit à
 *  l'œil, et que la règle « un état prend son jeton » a répandu partout.
 *  Le contrôle résout les `var(--…)` dans `socle.css` et MESURE le rapport ;
 *  une valeur qu'il ne sait pas résoudre le fait échouer (INCONNU, jamais OK).
 */
export function contraste(a, b) {
	//  Un texte TRANSLUCIDE (`#rrggbbaa`) se mesure posé sur son fond ; un fond
	//  translucide n'a pas de couleur à lui seul — NaN, que l'appelant lit INCONNU.
	if (b.length === 9) return NaN;
	if (a.length === 9) a = melanger(a.slice(0, 7), b, parseInt(a.slice(7), 16) / 255);
	const lum = (h) => {
		const c = [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16) / 255);
		const [r, g, v] = c.map((x) => (x <= 0.03928 ? x / 12.92 : ((x + 0.055) / 1.055) ** 2.4));
		return 0.2126 * r + 0.7152 * g + 0.0722 * v;
	};
	const [x, y] = [lum(a), lum(b)].sort((p, q) => q - p);
	return (x + 0.05) / (y + 0.05);
}

/** `p` de `a` et `1 - p` de `b`, en sRGB — le `color-mix(in srgb, …)` du navigateur. */
export function melanger(a, b, p) {
	const c = (h, i) => parseInt(h.slice(i, i + 2), 16);
	return (
		'#' +
		[1, 3, 5]
			.map((i) => Math.round(c(a, i) * p + c(b, i) * (1 - p)))
			.map((x) => x.toString(16).padStart(2, '0'))
			.join('')
	);
}

const NOMMEES = { white: '#ffffff', black: '#000000' };

/**
 *  Une valeur de couleur → `#rrggbb`, `#rrggbbaa` si elle est translucide, ou
 *  null si elle échappe (INCONNU, jamais OK). Lit `#rgb`, `#rrggbb`, `white`,
 *  `black`, `rgb()`/`rgba()`, `var(--x)` dans les jetons, et — depuis le mode
 *  sombre (#2174, S3) — `color-mix(in srgb, A p%, B)` de deux couleurs opaques.
 */
export function resoudre(valeur, jetons, profondeur = 0) {
	const v = valeur.trim().toLowerCase();
	if (profondeur > 8) return null;
	if (/^#[0-9a-f]{6}$/.test(v)) return v;
	if (/^#[0-9a-f]{3}$/.test(v)) return hex6(v);
	if (v in NOMMEES) return NOMMEES[v];
	const rgb = v.match(/^rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*(?:,\s*([\d.]+)\s*)?\)$/);
	if (rgb) {
		const a = rgb[4] === undefined ? 1 : parseFloat(rgb[4]);
		const hex =
			'#' +
			rgb
				.slice(1, 4)
				.map((x) => (+x).toString(16).padStart(2, '0'))
				.join('');
		return a >= 1
			? hex
			: hex +
					Math.round(a * 255)
						.toString(16)
						.padStart(2, '0');
	}
	const mix = v.match(/^color-mix\(\s*in srgb\s*,\s*(.+?)\s+([\d.]+)%\s*,\s*(.+?)\s*\)$/);
	if (mix) {
		const [a, b] = [
			resoudre(mix[1], jetons, profondeur + 1),
			resoudre(mix[3], jetons, profondeur + 1),
		];
		if (!a || !b || a.length === 9 || b.length === 9) return null;
		return melanger(a, b, parseFloat(mix[2]) / 100);
	}
	const m = v.match(/^var\(\s*(--[a-z0-9-]+)\s*\)$/);
	if (!m || !(m[1] in jetons)) return null;
	return resoudre(jetons[m[1]], jetons, profondeur + 1);
}

/** Les déclarations `--nom: valeur;` d'un CSS, une par ligne, en objet. */
export function declarationsDe(css) {
	return Object.fromEntries(
		[...css.matchAll(/^\s*(--[a-z0-9-]+)\s*:\s*([^;]+);/gm)].map((m) => [m[1], m[2].trim()]),
	);
}

/** Les badges et leur rapport de contraste ; `null` quand une valeur échappe. */
export function contrastesBadges(composants, socle) {
	const jetons = declarationsDe(socle);
	return [...composants.matchAll(/^\.badge-([a-z]+)\s*\{([^}]*)\}/gm)]
		.map(([, nom, corps]) => {
			const fond = corps.match(/background\s*:\s*([^;]+);/);
			const texte = corps.match(/(?:^|[\s;])color\s*:\s*([^;]+);/);
			if (!fond || !texte) return null;
			const f = resoudre(fond[1], jetons);
			const t = resoudre(texte[1], jetons);
			return { nom, rapport: f && t ? contraste(t, f) : null };
		})
		.filter(Boolean);
}
