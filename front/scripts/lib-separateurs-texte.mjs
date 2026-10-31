/**
 *  **Les séparateurs du texte courant** — « {a} · {b} » (#2362, forme 1).
 *
 *  Entre deux espaces SÉCABLES, le navigateur coupe à la dernière occasion qui
 *  tient — souvent APRÈS le séparateur, qui finit alors sa ligne. La règle du site
 *  (`#lib/separateurs`) : sécable avant, insécable après, écrite par
 *  `{SEPARATEUR.point|tiret|fleche}`.
 *
 *  Ce module ne connaît que le SOURCE d'un composant : il rend la position de
 *  chaque séparateur du texte affiché qui est entouré d'espaces sécables et suivi
 *  d'un mot (du texte, une expression, une balise en ligne, un composant). Il
 *  est lu par `check-espace-blocs.mjs`, qui le refuse, et il a servi une fois à
 *  la conversion des 254 occurrences du dépôt (31/10/2026).
 *
 *  Ce qui n'est pas du texte affiché est blanchi, longueurs gardées : les
 *  commentaires, `<script>` et `<style>`, le contenu de `<option>`, `<textarea>`,
 *  `<pre>`, `<code>` et `<title>` (qui ne passe jamais à la ligne), les attributs
 *  (la balise entière), et les expressions.
 *
 *  Ce qu'il laisse, parce qu'une autre règle de `check-espace-blocs` le tient : le
 *  séparateur en tête de branche (`{#if x} · y`, `{:else} — y`) et en tête
 *  d'élément en ligne (`<span>· y</span>`).
 *
 *  Test : node scripts/check-espace-blocs.mjs --selftest
 */
import { neutraliserCommentaires } from './lib-commentaires.mjs';

/** Les balises qui se lisent DANS une phrase — une après le séparateur est un mot. */
export const EN_LIGNE = 'span|strong|a|em|small|b|i|code|abbr|time|mark|sup|sub';
const EST_EN_LIGNE = new RegExp(`^(?:${EN_LIGNE})$`);

/** Le nom de la constante, par séparateur (`#lib/separateurs`). */
export const NOM_DU_SEPARATEUR = { '·': 'point', '—': 'tiret', '→': 'fleche' };

//  Les marques du texte blanchi : un MOT (la suite d'une phrase), une FRONTIÈRE
//  (un bloc, une balise de bloc : la phrase s'arrête).
const MOT = 'x';
const FRONTIERE = '\ue002';
const OUVRANT = '\ue001'; // `{#if}`, `{:else}`, `{/if}`, `{@…}` (zone privée : jamais dans un source)

/** Remplace un fragment par `marque`, sauts de ligne gardés. PURE. */
const masquer = (bloc, marque) => bloc.replace(/[^\n]/g, marque);

/** Les expressions `{…}`, accolades équilibrées, blanchies. PURE. */
function masquerExpressions(texte) {
	let sortie = '';
	let i = 0;
	while (i < texte.length) {
		if (texte[i] !== '{') {
			sortie += texte[i++];
			continue;
		}
		let profondeur = 0;
		let j = i;
		for (; j < texte.length; j++) {
			if (texte[j] === '{') profondeur++;
			else if (texte[j] === '}' && --profondeur === 0) break;
		}
		const bloc = texte.slice(i, j + 1);
		sortie += masquer(bloc, /^\{[#:/@]/.test(bloc) ? OUVRANT : MOT);
		i = j + 1;
	}
	return sortie;
}

/** Le source, où seul le texte affiché reste lisible. PURE. */
export function texteAffiche(source) {
	let t = neutraliserCommentaires(source).replace(
		/(<(script|style)\b[^>]*>)([\s\S]*?)(<\/\2>)/g,
		(_, a, _b, corps, z) => a + masquer(corps, ' ') + z,
	);
	t = masquerExpressions(t);
	//  `<code>` se lit dans la phrase : un MOT ; les autres ne passent pas à la ligne.
	t = t.replace(/<(option|textarea|pre|code|title)\b[\s\S]*?<\/\1>/g, (m, nom) =>
		masquer(m, nom === 'code' ? MOT : FRONTIERE),
	);
	return t.replace(/<\/?([A-Za-z][\w.:-]*)\b[^>]*>/g, (m, nom) =>
		masquer(m, EST_EN_LIGNE.test(nom) || /^[A-Z]/.test(nom) ? MOT : FRONTIERE),
	);
}

//  Un mot ou une balise fermée avant (jamais l'ouverture d'une branche : la règle
//  de tête de branche la tient), des espaces sécables, le séparateur, des espaces,
//  puis un mot.
const MOTIF = /(?<=[^\s\ue001])\s+([·—→])\s+(?=[^\s\ue001\ue002])/g;

/**
 *  Les séparateurs du texte courant : `{ debut, fin, separateur }`, où
 *  `source.slice(debut, fin)` est l'espace, le séparateur et l'espace à remplacer
 *  par `{SEPARATEUR.<nom>}`. PURE.
 */
export function separateursDuTexte(source) {
	return [...texteAffiche(source).matchAll(MOTIF)].map((m) => ({
		debut: m.index,
		fin: m.index + m[0].length,
		separateur: m[1],
	}));
}
