/**
 *  **Un séparateur se rattache au mot qui le SUIT** (#2360, 30/10/2026).
 *
 *  « résident · Conseil syndical » se coupait en « résident · » puis « Conseil
 *  syndical » : la forme du dépôt, `{#if x}&nbsp;· {x}{/if}`, collait le
 *  séparateur au mot d'AVANT et ne laissait couper qu'après lui — il finissait
 *  donc la ligne. Philippe ne veut pas qu'un séparateur termine une ligne.
 *
 *  La règle : espace SÉCABLE avant, INSÉCABLE après. La ligne se coupe devant le
 *  séparateur, qui ouvre la suivante avec son mot.
 *
 *  Pourquoi une constante et pas une écriture dans le balisage : Svelte 5 retire
 *  l'espace en tête d'une branche `{#if}` (même `&#32;`), si bien que l'espace
 *  sécable ne peut s'y écrire qu'AVANT le bloc — où elle reste quand la branche
 *  est fausse (« Vient du syndic . »). Le texte d'une expression, lui, n'est
 *  jamais retouché : l'espace part avec sa branche.
 *
 *  ```svelte
 *  {nom}{#if fonction}{SEPARATEUR.tiret}{fonction}{/if}
 *  ```
 *
 *  🔒 `npm run lint:espace-blocs` refuse les formes qui laissent le séparateur en
 *  bout de ligne ; `e2e/separateurs-fin-de-ligne.spec.ts` le mesure sur le rendu.
 */
export const SEPARATEUR = {
	/** sépare deux éléments d'une même ligne : « 3/5 · PDF » */
	point: ' ·\u00a0',
	/** introduit un complément : « 📞 01 02 — la gérante » */
	tiret: ' —\u00a0',
	/** borne un intervalle : « 18:00 → 20:00 » */
	fleche: ' →\u00a0',
} as const;
