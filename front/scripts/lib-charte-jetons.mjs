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
	const lum = (h) => {
		const c = [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16) / 255);
		const [r, g, v] = c.map((x) => (x <= 0.03928 ? x / 12.92 : ((x + 0.055) / 1.055) ** 2.4));
		return 0.2126 * r + 0.7152 * g + 0.0722 * v;
	};
	const [x, y] = [lum(a), lum(b)].sort((p, q) => q - p);
	return (x + 0.05) / (y + 0.05);
}

/** `var(--x)` → la valeur hexadécimale de `--x` dans les jetons, ou null. */
export function resoudre(valeur, jetons, profondeur = 0) {
	const v = valeur.trim().toLowerCase();
	if (/^#[0-9a-f]{6}$/.test(v)) return v;
	const m = v.match(/^var\(\s*(--[a-z0-9-]+)\s*\)$/);
	if (!m || profondeur > 5 || !(m[1] in jetons)) return null;
	return resoudre(jetons[m[1]], jetons, profondeur + 1);
}

/** Les badges et leur rapport de contraste ; `null` quand une valeur échappe. */
export function contrastesBadges(composants, socle) {
	const jetons = Object.fromEntries(
		[...socle.matchAll(/^\s*(--[a-z0-9-]+)\s*:\s*([^;]+);/gm)].map((m) => [m[1], m[2]]),
	);
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
