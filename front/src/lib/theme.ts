/**
 *  Le THÈME choisi — Automatique, Clair ou Sombre (mode sombre, #2174, lot S5,
 *  30/10/2026).
 *
 *  ## Une préférence d'APPAREIL, portée par un cookie
 *
 *  Arbitré le 29/10/2026 : le choix vit dans le cookie `theme`, pas en base. Un
 *  téléphone le soir et un ordinateur de bureau n'ont pas le même besoin, et un
 *  écran de connexion — sans compte — doit déjà le respecter. Le cookie ne porte
 *  qu'un mot de la liste blanche ; tout autre valeur retombe sur Automatique.
 *
 *  ## Le serveur pose l'attribut : aucun éclair, aucun script
 *
 *  `hooks.server.ts` lit le cookie et remplit les repères `%theme.…%` de
 *  `app.html` (`remplirGabarit`) : la page part avec son `data-theme`, son
 *  `color-scheme` et ses couleurs de barre. Le navigateur la peint donc d'emblée
 *  dans le bon thème — un script de démarrage aurait coûté un condensat CSP de
 *  plus et un éclair clair → sombre (en-tête de `styles/palette-sombre.css`).
 *  Le sélecteur du Profil (`ChoixTheme.svelte`) applique ensuite un changement
 *  sur place (`appliquerTheme`) : l'attribut, les balises et le cookie, sans
 *  rechargement.
 *
 *  ## Ce module DÉCIDE du thème
 *
 *  Avec `styles/palette-sombre.css`, c'est le seul fichier de `src/` qui nomme
 *  une préférence de couleurs du système — déclaré dans `LIEUX_DU_THEME`
 *  (`scripts/check-palette-sombre.mjs`, règle 6). Un écran ne pose jamais
 *  l'attribut lui-même.
 *
 *  🔒 `e2e/bascule-theme.spec.ts` : cookie absent, Auto, Clair, Sombre, valeur
 *  inconnue, rechargement, et l'attribut présent dans le HTML SERVI.
 */

export const CHOIX_THEME = ['auto', 'clair', 'sombre'] as const;
export type ChoixTheme = (typeof CHOIX_THEME)[number];

/** Le nom du cookie — nommé dans la politique de confidentialité (🔒 côté API). */
export const COOKIE_THEME = 'theme';
export const THEME_PAR_DEFAUT: ChoixTheme = 'auto';

/** Un an : la préférence survit aux visites espacées (Chrome plafonne à 400 jours). */
const DUREE_COOKIE_S = 365 * 24 * 3600;

/** Les entrées du sélecteur, dans leur ordre d'affichage. */
export const OPTIONS_THEME: readonly { val: ChoixTheme; label: string; desc: string }[] = [
	{ val: 'auto', label: 'Automatique', desc: 'Suit le réglage de l’appareil' },
	{ val: 'clair', label: 'Clair', desc: 'Toujours clair' },
	{ val: 'sombre', label: 'Sombre', desc: 'Toujours sombre' },
];

/** Ce qu'un choix écrit dans la page. */
interface RenduTheme {
	/** `data-theme` de `<html>` — la palette s'allume sur `dark`, ou `auto` + système sombre. */
	attribut: 'auto' | 'light' | 'dark';
	/** `<meta name="color-scheme">` : contrôles natifs, et fond du canevas avant la feuille. */
	schema: string;
	/** `media` des deux `<meta name="theme-color">` (barre du navigateur) : le premier qui
	 *  s'applique l'emporte. */
	barreClair: string;
	barreSombre: string;
}

const SYSTEME_CLAIR = '(prefers-color-scheme: light)';
const SYSTEME_SOMBRE = '(prefers-color-scheme: dark)';
const TOUJOURS = 'all';
const JAMAIS = 'not all';

const RENDUS: Record<ChoixTheme, RenduTheme> = {
	auto: {
		attribut: 'auto',
		schema: 'light dark',
		barreClair: SYSTEME_CLAIR,
		barreSombre: SYSTEME_SOMBRE,
	},
	clair: { attribut: 'light', schema: 'light', barreClair: TOUJOURS, barreSombre: JAMAIS },
	sombre: { attribut: 'dark', schema: 'dark', barreClair: JAMAIS, barreSombre: TOUJOURS },
};

/** Le choix d'un cookie, liste blanche : absent ou inconnu → Automatique. PURE. */
export function lireChoix(valeur: string | null | undefined): ChoixTheme {
	return CHOIX_THEME.find((c) => c === valeur) ?? THEME_PAR_DEFAUT;
}

/** Le choix qu'affiche une page, lu sur l'attribut que le serveur a posé. PURE. */
export function choixDeLAttribut(attribut: string | null | undefined): ChoixTheme {
	return CHOIX_THEME.find((c) => RENDUS[c].attribut === attribut) ?? THEME_PAR_DEFAUT;
}

/** Les repères de `app.html`, et ce qu'ils deviennent pour un choix. */
const REPERES: Record<string, (r: RenduTheme) => string> = {
	'%theme.attribut%': (r) => r.attribut,
	'%theme.schema%': (r) => r.schema,
	'%theme.barre-clair%': (r) => r.barreClair,
	'%theme.barre-sombre%': (r) => r.barreSombre,
};
const REPERE = /%theme\.[a-z-]+%/g;

/** Le gabarit de page rempli pour un choix — appelé par `hooks.server.ts`. PURE.
 *  Un repère inconnu lève : une page partirait sinon avec `%theme.…%` en clair. */
export function remplirGabarit(html: string, choix: ChoixTheme): string {
	const rendu = RENDUS[choix];
	return html.replace(REPERE, (repere) => {
		const valeur = REPERES[repere];
		if (!valeur) throw new Error(`theme : repère inconnu dans app.html — ${repere}`);
		return valeur(rendu);
	});
}

/** Le cookie d'un choix. `Lax` suffit : une préférence d'affichage n'est pas un
 *  secret, et elle doit suivre un lien qui arrive d'ailleurs. PURE. */
export function cookieTheme(choix: ChoixTheme, securise: boolean): string {
	const attributs = [
		`${COOKIE_THEME}=${choix}`,
		'Path=/',
		`Max-Age=${DUREE_COOKIE_S}`,
		'SameSite=Lax',
	];
	if (securise) attributs.push('Secure');
	return attributs.join('; ');
}

/** Applique un choix à la page ouverte et le retient sur l'appareil — ce que le
 *  serveur aurait écrit, pour qu'un changement se voie sans rechargement. */
export function appliquerTheme(choix: ChoixTheme): void {
	const rendu = RENDUS[choix];
	document.documentElement.dataset.theme = rendu.attribut;
	document.querySelector('meta[name="color-scheme"]')?.setAttribute('content', rendu.schema);
	for (const meta of document.querySelectorAll<HTMLMetaElement>('meta[name="theme-color"]'))
		meta.media = meta.dataset.barre === 'sombre' ? rendu.barreSombre : rendu.barreClair;
	document.cookie = cookieTheme(choix, location.protocol === 'https:');
}
