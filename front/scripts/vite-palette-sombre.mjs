/**
 *  Le mode AUTO du thème sombre, GÉNÉRÉ au build (#2174, lot S3, 29/10/2026).
 *
 *  `styles/palette-sombre.css` écrit la palette sombre UNE fois, sous
 *  `@media screen { :root[data-theme='dark'] { … } }`. Ce greffon PostCSS
 *  (`vite.config.ts`, `css.postcss`) en ajoute la copie qui suit le système :
 *
 *      @media screen and (prefers-color-scheme: dark) {
 *        :root[data-theme='auto'] { …les mêmes jetons… }
 *      }
 *
 *  Pourquoi une copie GÉNÉRÉE plutôt qu'écrite : un sélecteur ne peut pas
 *  porter une requête média, et deux blocs écrits à la main divergeraient au
 *  premier réglage — l'un des deux thèmes « sombres » aurait tort sans un mot.
 *  Les raisons d'écarter `light-dark()` et un script de démarrage sont dans
 *  l'en-tête de la feuille.
 *
 *  `data-theme="auto"` est le défaut depuis le lot S5 (`lib/theme.ts`).
 *  🔒 `e2e/palette-sombre.spec.ts` prouve sur la feuille SERVIE qu'elle existe et qu'elle s'allume (Auto + système sombre), et que rien d'autre ne
 *  l'allume. Le greffon échoue au build si la règle n'a plus la forme attendue,
 *  plutôt que de laisser passer une feuille sans mode Auto.
 */

export const SELECTEUR_FORCE = ":root[data-theme='dark']";
export const SELECTEUR_AUTO = ":root[data-theme='auto']";
export const MEDIA_FORCE = 'screen';
export const MEDIA_AUTO = 'screen and (prefers-color-scheme: dark)';
const ATTRIBUT_FORCE = "[data-theme='dark']";
const ATTRIBUT_AUTO = "[data-theme='auto']";
/** La règle sombre de la charte, et celle de chaque palette de la copropriété
 *  (`styles/palettes.css`, #2379) : `:root[data-palette='…'][data-theme='dark']`. */
const FORCE = /^:root(?:\[data-palette='[a-z]+'\])?\[data-theme='dark'\]$/;

/** @returns {import('postcss').Plugin} */
export function paletteSombreAuto() {
	return {
		postcssPlugin: 'palette-sombre-auto',
		OnceExit(racine) {
			/** @type {import('postcss').Rule[]} */
			const regles = [];
			racine.walkRules((regle) => {
				if (FORCE.test(regle.selector)) regles.push(regle);
			});
			for (const regle of regles) {
				const media = /** @type {import('postcss').AtRule | undefined} */ (regle.parent);
				if (
					media?.type !== 'atrule' ||
					media.name !== 'media' ||
					media.params !== MEDIA_FORCE ||
					media.nodes?.length !== 1
				)
					throw new Error(
						`palette-sombre-auto : ${SELECTEUR_FORCE} doit être SEUL sous ` +
							`@media ${MEDIA_FORCE} (styles/palette-sombre.css).`,
					);
				const copie = media.clone({ params: MEDIA_AUTO });
				const regleCopie = /** @type {import('postcss').Rule} */ (copie.first);
				regleCopie.selector = regleCopie.selector.replace(ATTRIBUT_FORCE, ATTRIBUT_AUTO);
				media.after(copie);
			}
		},
	};
}
paletteSombreAuto.postcss = true;
