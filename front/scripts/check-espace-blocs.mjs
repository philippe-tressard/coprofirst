#!/usr/bin/env node
/**
 *  **L'espace qu'un bloc `{#if}` mange** (#2356, 30/10/2026).
 *
 *  ## Le défaut
 *
 *  Svelte 5 retire l'espace en TÊTE et en FIN de chaque branche d'un bloc (et en
 *  tête et en fin de chaque balise). Écrit ainsi :
 *
 *  ```svelte
 *  {prenom}{#if lot}
 *  	<span>— {lot}</span>{/if}
 *  ```
 *
 *  le retour à la ligne qui sépare `{#if lot}` du `<span>` disparaît, et l'écran
 *  lit « Philippe— Bât. 4 ». Le salut de l'accueil le faisait (« Prénom— Bât. …
 *  2ème· Copropriétaire »), trouvé à l'œil pendant un contrôle de la charte ; le
 *  relevé en a trouvé une quinzaine d'autres — un téléphone collé à un nom, une
 *  date collée à une flèche, « Fixe.Relues le ».
 *
 *  ⚠️ La forme est celle que Prettier écrit : pour lui, comme en HTML, un retour
 *  à la ligne vaut une espace. Pour Svelte 5, non. Ce qu'il coupe en deux lignes
 *  là où il y avait une espace est précisément ce qui la perd.
 *
 *  ## Ce que ce contrôle refuse
 *
 *  - **à l'ouverture** : `{#if}`, `{#each}` ou `{#key}` COLLÉ à ce qui le précède
 *    (un caractère, une expression, une balise fermée), dont la branche commence
 *    par un retour à la ligne suivi de texte, d'une expression ou d'une balise
 *    en ligne ;
 *  - **à la fermeture** : un `{/if}` ou `{/key}` précédé d'un retour à la ligne
 *    et COLLÉ au texte, à l'expression ou au bloc qui le suit.
 *
 *  Une espace en tête de branche est retirée, même écrite `&#32;` ; seule
 *  `&nbsp;`, insécable, y survit — et `{' '}` est refusé par ESLint
 *  (`svelte/no-useless-mustaches`). L'espace sécable se pose donc AVANT le
 *  bloc, où Svelte la garde entre deux nœuds : `{prenom} {#if lot}{lot}{/if}`.
 *  Devant un séparateur, c'est la constante de `#lib/separateurs` (ci-dessous).
 *  Un collage voulu (l'astérisque d'un libellé requis) s'écrit sur la ligne du bloc.
 *
 *  Ce qu'il laisse : un bloc précédé d'une espace (elle subsiste, entre deux
 *  nœuds), un bloc en tête d'élément (`<td>{#if …}` : rien avant), une branche
 *  qui commence par un élément de bloc, et `{:else}`, qu'on ne juge qu'avec son
 *  `{#if}` — limite connue : une branche `{:else}` d'un `{#if}` collé n'est pas
 *  vue. Les commentaires, `<script>` et `<style>` sont blanchis.
 *
 *  ## Le séparateur qui finit une ligne (#2360, 30/10/2026)
 *
 *  Même cause, autre symptôme : `{#if x}&nbsp;· {x}{/if}` — l'espace d'avant le
 *  séparateur ne pouvait s'écrire qu'insécable — ne laisse couper qu'APRÈS lui,
 *  et la ligne finit sur « · ». La règle du site : espace sécable avant,
 *  insécable après, écrites par `{SEPARATEUR.point|tiret|fleche}`
 *  (`#lib/separateurs`), dont l'espace part avec sa branche. Le contrôle refuse :
 *
 *  - **collé avant** : `&nbsp;` juste devant un séparateur suivi d'une espace
 *    sécable (`&nbsp;· x`, et `&nbsp;·&nbsp;` suivi d'un retour à la ligne) ;
 *  - **en tête de branche** : `{#if x}· x`, `{:else}— x` — Svelte retire
 *    l'espace d'avant, le séparateur colle au mot qui précède ;
 *  - **recopié** : `·&nbsp;` écrit à la main — la forme juste, mais une seconde
 *    écriture de la constante.
 *
 *  Ce qu'il laisse : `&nbsp;·&nbsp;` collé des deux côtés (la ligne ne s'y coupe
 *  pas), et — limite connue, mesurée à l'écran plutôt que convertie en bloc —
 *  le séparateur entre deux espaces sécables du texte courant (` · `), et celui
 *  qui ouvre un élément en ligne (`<span>· x</span>`) — #2362.
 *
 *  Lancer : node scripts/check-espace-blocs.mjs [--selftest]
 */
import { neutraliserCommentaires } from './lib-commentaires.mjs';
import { controler } from './lib-source-unique.mjs';

/** Les balises qui se lisent DANS une phrase : une branche qui s'ouvre sur elles colle. */
const EN_LIGNE = 'span|strong|a|em|small|b|i|code|abbr|time|mark|sup|sub';

//  Ouverture collée : un caractère non blanc juste avant le bloc, puis un retour
//  à la ligne, puis du texte ou une balise en ligne.
const OUVERTURE = new RegExp(
	String.raw`(?<=\S)\{#(?:if|each|key)\b[^}]*\}[ \t]*\r?\n\s*(?=[^\s<{]|\{[^#/:]|<(?:${EN_LIGNE})\b)`,
	'g',
);
//  Fermeture collée : un retour à la ligne avant `{/if}`, puis du texte, une
//  expression ou un autre bloc juste après.
const FERMETURE = /(?<=\S)[ \t]*\r?\n\s*\{\/(?:if|key)\}(?=[^\s<{]|\{[^/:])/g;

/** Les séparateurs d'une phrase (#2360). */
const SEP = '[—·→]';
//  Une espace sécable, puis ce qu'il sépare : du texte, une expression, une balise
//  en ligne. Un tiret seul devant `{:else}` est une valeur absente, pas un séparateur.
const PUIS_UN_MOT = String.raw`(?=\s+(?:[^\s<{]|\{[^#/:]|<(?:${EN_LIGNE})\b))`;
//  Collé avant : `&nbsp;` devant, une espace sécable après (au besoin après `&nbsp;`).
const COLLE_AVANT = new RegExp(String.raw`&nbsp;${SEP}(?:&nbsp;)?${PUIS_UN_MOT}`, 'g');
//  En tête de branche : l'espace d'avant est retirée par Svelte.
const TETE_DE_BRANCHE = new RegExp(
	String.raw`\{(?:#(?:if|each|key)|:else)\b[^}]*\}\s*${SEP}${PUIS_UN_MOT}`,
	'g',
);
//  Recopié : séparateur puis insécable, écrit à la main.
const RECOPIE = new RegExp(String.raw`(?<!&nbsp;)${SEP}&nbsp;`, 'g');

/** Blanchit le contenu de `<script>` et `<style>`, longueurs et lignes conservées. PURE. */
function balisageSeul(texte) {
	return texte.replace(
		/(<(script|style)\b[^>]*>)([\s\S]*?)(<\/\2>)/g,
		(_, a, _b, corps, z) => a + corps.replace(/[^\n]/g, ' ') + z,
	);
}

/**
 *  Le caractère d'avant est-il la fin d'une balise OUVRANTE (`<td>`, `<span …>`) ?
 *  Le bloc est alors en tête d'élément : il n'y a rien à quoi coller. PURE.
 */
function apresBaliseOuvrante(texte, indice) {
	if (texte[indice - 1] !== '>') return false;
	const debut = texte.lastIndexOf('<', indice - 1);
	const balise = texte.slice(debut, indice);
	return debut >= 0 && !balise.startsWith('</') && !balise.endsWith('/>');
}

/** Les numéros des lignes où un bloc mange une espace. PURE. */
export function fautes(source) {
	const texte = balisageSeul(neutraliserCommentaires(source));
	const ligne = (i) => texte.slice(0, i).split('\n').length;
	const acc = [];
	for (const m of texte.matchAll(OUVERTURE)) {
		if (!apresBaliseOuvrante(texte, m.index)) acc.push(ligne(m.index));
	}
	for (const m of texte.matchAll(FERMETURE)) acc.push(ligne(m.index) + 1);
	for (const motif of [COLLE_AVANT, TETE_DE_BRANCHE, RECOPIE]) {
		for (const m of texte.matchAll(motif)) acc.push(ligne(m.index + m[0].length - 1));
	}
	return acc;
}

const cas = [
	//  Le défaut du ticket, tel qu'il était écrit.
	['<h1>{prenom}{#if lot}\n\t<span>— {lot}</span>{/if}</h1>', 1],
	['<h1>{a}{/if}{#if roles}\n\t<span>· {roles}</span>{/if}</h1>', 1],
	['Vient du <strong>{o}</strong>{#if ou}\n\tqui se change dans {ou}{/if}.', 1],
	['v{x}{#if y}\n\tmise à jour{/if}', 1],
	['{titre}{#if requis}\n\t*{/if}', 1],
	['<Icon />{#if n}\n\t({n}){/if}', 1],
	['{#each l as x}{x}{/each}{#each m as y}\n\ttexte{/each}', 1],
	//  La fermeture : la fin de branche est retirée, le texte d'après colle.
	['{#if a}\n\tfoo\n{/if}bar', 1],
	['{#if a}\n\tfoo\n{/if}{b}', 1],
	//  L'annuaire : « Bât. 3 -2e étage », le tiret collé au bloc suivant.
	['{#if a}\n\t-\n{/if}{#if b}2e étage{/if}', 1],
	//  Une expression en tête de branche colle aussi.
	['{a}{#if b}\n\t{c}{/if}', 1],
	//  Le séparateur qui finit une ligne (#2360) : la forme du ticket, telle qu'écrite.
	['v{x}{#if y}&nbsp;· mise à jour{/if}', 1],
	['{n}/{m}{#if t}&nbsp;· {t}{/if}', 1],
	['© {an}\n&nbsp;·&nbsp;\n<a href="/">site</a>', 1],
	['texte\n{#if a}\n\t· b{/if}', 1],
	['{#if a}{x}{:else}— {y}{/if}', 1],
	['{#each l as x}→ {x}{/each}', 1],
	['<h1>{prenom}\n{#if lot}<span>—&nbsp;{lot}</span>{/if}</h1>', 1],
	//  Les formes justes.
	['<h1>{prenom}{#if lot}<span>{SEPARATEUR.tiret}{lot}</span>{/if}</h1>', 0],
	['{n}/{m}{#if t}{SEPARATEUR.point}{t}{/if}', 0],
	['v{x}{#if e}&nbsp;·&nbsp;<a href="/">e</a>{/if}', 0],
	['<a href="/">GitHub&nbsp;→</a>', 0],
	['Fixe. {#if y}Relues le {y}{/if}', 0],
	['{titre}{#if requis}*{/if}', 0],
	['<td>{#if a}\n\tb{/if}</td>', 0],
	['<span class="x">{#if a}\n\tb{/if}</span>', 0],
	['<td>{#if vide}\n\t—\n{:else}{v}{/if}</td>', 0],
	//  Limite connue (#2362) : le texte courant, mesuré à l’écran plutôt que converti.
	['{a} · {b}', 0],
	['{a}{#if b}\n\t<div>bloc</div>{/if}', 0],
	['{a}{#if b}\n\t{#if c}x{/if}{/if}', 0],
	['{#if a}\n\tfoo\n{/if}\nbar', 0],
	['{#if a}\n\tfoo\n{/if}<span>x</span>', 0],
	//  Commentaires, script et style ne comptent pas.
	['<!-- {a}{#if b}\n · c{/if} -->', 0],
	['<script>\nconst s = `x{#if y}\n · z`;\n</script>', 0],
];

process.exit(
	controler({
		racine: 'src',
		extensions: ['.svelte'],
		fautes,
		cas,
		ok: 'Aucun bloc {#if} ne mange l’espace voisine, aucun séparateur ne finit une ligne',
		ko: 'bloc(s) collé(s) au texte voisin, ou séparateur(s) laissé(s) en bout de ligne',
		conseil:
			"Poser l'espace AVANT le bloc (texte {#if x}…) ; un collage voulu s'écrit sur la ligne du bloc. Un séparateur s'écrit {SEPARATEUR.point|tiret|fleche} (#lib/separateurs) : sécable avant, insécable après.",
	}),
);
