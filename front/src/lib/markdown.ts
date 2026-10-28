/**
 * **Un texte de référence écrit en Markdown, rendu en HTML** (#1930, 14/10/2026).
 *
 * Les conditions d'inscription au registre (`api/app/registre/conditions/v*.md`)
 * s'affichaient BRUTES — astérisques, liens entre crochets, chevrons de citation.
 * Le texte archivé et accepté reste le texte SOURCE, avec son empreinte (D26) :
 * seul l'affichage passe par ici.
 *
 * 🔒 Ce module rend du HTML NON assaini. L'appelant le passe à un assainisseur de
 * `#lib/sanitize` dans son gabarit (`{@html safeHtml(html)}`, `npm run lint:html`) —
 * et il le faut : le texte archivé d'une fiche du registre vient d'une AUTRE
 * installation, et `marked` laisse passer le HTML brut qu'un Markdown contient.
 *
 * `marked` (MIT) n'est chargé qu'à l'appel : il n'entre dans l'ouverture d'aucun
 * écran (`lint:poids-ouverture`, `A_LA_DEMANDE`).
 */

/** Le premier niveau de titre du texte rendu : ses `#` se lisent SOUS le titre de l'écran. */
const NIVEAU_DE_DEPART = 4;

export async function markdownEnHtml(texte: string): Promise<string> {
	const { Marked } = await import('marked');
	const moteur = new Marked({
		gfm: true,
		//  Un `# Titre` du texte n'est pas le titre de la PAGE : un second `<h1>`
		//  casserait le plan que lit un lecteur d'écran. Les niveaux descendent.
		walkTokens(jeton) {
			if (jeton.type === 'heading') {
				jeton.depth = Math.min(6, jeton.depth + NIVEAU_DE_DEPART - 1) as 1 | 2 | 3 | 4 | 5 | 6;
			}
		},
		renderer: {
			//  Un lien du texte s'ouvre à côté : on ne quitte pas un formulaire en
			//  cours pour lire la licence.
			link({ href, title, tokens }) {
				const libelle = this.parser.parseInline(tokens);
				const infobulle = title ? ` title="${title}"` : '';
				return `<a href="${href}"${infobulle} target="_blank" rel="noopener noreferrer">${libelle}</a>`;
			},
		},
	});
	return moteur.parse(texte, { async: false });
}
