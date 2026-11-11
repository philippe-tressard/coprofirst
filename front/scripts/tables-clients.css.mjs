/**
 * **Lire une règle CSS publiée sans l'exécuter** — le lecteur des jetons de la charte
 * pour `tables-clients.mjs` (#2634, lot C).
 *
 * Une table CSS se déclare `src/styles/<feuille>.css@<sélecteur>`, ou dans le `<style>`
 * d'un composant, `src/lib/…/X.svelte@<sélecteur>`. Ce qui se lit : les déclarations de
 * la SEULE règle dont la liste de sélecteurs contient exactement ce sélecteur — dans un
 * `@media` compris —, rendues en `{ propriété: valeur }`. Un `*` en fait une FAMILLE :
 * `:root[data-palette='*']` rend `{ bordeaux: {…}, cuivre: {…} }`, une règle par code.
 *
 * Refusé : aucune règle, deux règles pour un même sélecteur (la table publiée serait
 * l'une d'elles au hasard de l'ordre), un bloc ou une chaîne non fermés. Les
 * commentaires se sautent, chaînes et parenthèses respectées (`url(…;…)`), et une
 * valeur garde son texte, blancs réduits : l'app résout elle-même un `var(--…)`.
 */
import { Refus } from './tables-clients.lecture.mjs';

/** `src/styles/x.css@sel` ou `src/lib/…/X.svelte@sel` : la forme d'une source CSS. */
export const SOURCE_CSS = /^src\/(?:styles\/[\w-]+\.css|lib\/[\w/-]+\.svelte)@\S.*$/;

function finDeChaine(texte, debut) {
	for (let i = debut + 1; i < texte.length; i++) {
		if (texte[i] === '\\') i++;
		else if (texte[i] === texte[debut]) return i;
	}
	throw new Refus('chaîne CSS non fermée');
}

/** Le texte sans ses commentaires, chaînes respectées. PURE. */
function sansCommentaires(texte) {
	let sortie = '';
	for (let i = 0; i < texte.length; i++) {
		const c = texte[i];
		if (c === '"' || c === "'") {
			const fin = finDeChaine(texte, i);
			sortie += texte.slice(i, fin + 1);
			i = fin;
		} else if (c === '/' && texte[i + 1] === '*') {
			const fin = texte.indexOf('*/', i + 2);
			if (fin < 0) throw new Refus('commentaire CSS non fermé');
			i = fin + 1;
		} else sortie += c;
	}
	return sortie;
}

/** L'indice du premier caractère de `cibles` hors chaîne et parenthèses, ou -1. PURE. */
function prochain(texte, debut, cibles) {
	let profondeur = 0;
	for (let i = debut; i < texte.length; i++) {
		const c = texte[i];
		if (c === '"' || c === "'") i = finDeChaine(texte, i);
		else if (c === '(') profondeur++;
		else if (c === ')') profondeur--;
		else if (profondeur === 0 && cibles.includes(c)) return i;
	}
	return -1;
}

/** L'indice du `}` qui ferme le bloc ouvert en `ouverture`. PURE. */
function finDeBloc(texte, ouverture) {
	let i = ouverture + 1;
	for (;;) {
		const j = prochain(texte, i, '{}');
		if (j < 0) throw new Refus('bloc CSS non fermé');
		if (texte[j] === '}') return j;
		i = finDeBloc(texte, j) + 1;
	}
}

const blancs = (s) => s.replace(/\s+/g, ' ').trim();

/** Un sélecteur sous une forme comparable : blancs réduits, guillemets simples. PURE. */
export const normaliser = (s) => blancs(s).replace(/"/g, "'");

/** Les `prop: valeur;` d'un corps de règle, blocs imbriqués sautés. PURE. */
function declarations(corps) {
	const sortie = {};
	let i = 0;
	while (i < corps.length) {
		const j = prochain(corps, i, ';{');
		if (j >= 0 && corps[j] === '{') {
			i = finDeBloc(corps, j) + 1;
			continue;
		}
		const fin = j < 0 ? corps.length : j;
		const morceau = corps.slice(i, fin);
		const deux = morceau.indexOf(':');
		if (deux > 0) sortie[blancs(morceau.slice(0, deux))] = blancs(morceau.slice(deux + 1));
		i = fin + 1;
	}
	return sortie;
}

/** Les règles d'une feuille : `[{ selecteurs, declarations }]`, `@media` traversés. PURE. */
export function reglesCss(texte) {
	const propre = sansCommentaires(texte);
	const regles = [];
	const lireBloc = (debut, fin) => {
		let i = debut;
		while (i < fin) {
			const j = prochain(propre, i, '{;}');
			if (j < 0 || j >= fin) return;
			if (propre[j] !== '{') {
				i = j + 1; //  `@import …;` ou un reste : rien à publier
				continue;
			}
			const prelude = propre.slice(i, j).trim();
			const k = finDeBloc(propre, j);
			if (prelude.startsWith('@')) lireBloc(j + 1, k);
			else
				regles.push({
					selecteurs: prelude.split(',').map(normaliser),
					declarations: declarations(propre.slice(j + 1, k)),
				});
			i = k + 1;
		}
	};
	lireBloc(0, propre.length);
	return regles;
}

/** Le texte CSS d'un fichier : la feuille, ou le `<style>` d'un composant. PURE. */
export function feuille(texte, chemin) {
	if (!chemin.endsWith('.svelte')) return texte;
	const m = /<style[^>]*>([\s\S]*?)<\/style>/.exec(texte);
	if (!m) throw new Refus(`${chemin} : aucun <style>`);
	return m[1];
}

/** La valeur publiée d'une source CSS `chemin@sélecteur`, lue dans `texte`. PURE. */
export function valeurCss(texte, chemin, selecteur) {
	const ou = `${chemin}@${selecteur}`;
	const voulu = normaliser(selecteur);
	const regles = reglesCss(feuille(texte, chemin));
	if (!voulu.includes('*')) {
		const trouvees = regles.filter((r) => r.selecteurs.includes(voulu));
		if (trouvees.length !== 1)
			throw new Refus(`${ou} : ${trouvees.length} règle(s) pour ce sélecteur, une seule attendue`);
		return trouvees[0].declarations;
	}
	const motif = new RegExp(
		`^${voulu
			.split('*')
			.map((m) => m.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'))
			.join('([\\w-]+)')}$`,
	);
	const famille = {};
	for (const r of regles)
		for (const s of r.selecteurs) {
			const m = motif.exec(s);
			if (!m) continue;
			if (m[1] in famille) throw new Refus(`${ou} : deux règles pour « ${m[1]} »`);
			famille[m[1]] = r.declarations;
		}
	if (!Object.keys(famille).length) throw new Refus(`${ou} : aucune règle de cette famille`);
	return famille;
}
