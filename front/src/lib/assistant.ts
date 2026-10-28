/**
 *  Le CONTEXTE que la section Description transmet à l'assistant (#985) — ce
 *  que le modèle doit comprendre sans le réécrire.
 *
 *  Arbitré le 17/09/2026, par entité :
 *
 *  | Entité      | Contexte                                    |
 *  |-------------|---------------------------------------------|
 *  | ticket      | catégorie, périmètre, état                  |
 *  | actualité   | catégorie, périmètre, urgent / épinglé      |
 *  | événement   | date, lieu, périmètre                       |
 *  | commentaire | titre et description de l'objet porteur, nouvel état |
 *  | sondage, idée, annonce | périmètre, type                  |
 *
 *  🔴 Ce module ne connaît ni l'API, ni un composant : il compose un objet
 *  `{ libellé: valeur }` à partir de ce que chaque formulaire sait. Les
 *  valeurs vides sont écartées ICI, une fois — sinon chaque écran testerait
 *  ses champs avant de les passer.
 */
import { perimetreLabel, stripHtml } from '#lib/utils.ts';

/**
 *  La nature d'un commentaire, telle que le modele la lit.
 *
 *  Ecrite une fois : le prompt de l'usage « description » reserve a ce cas la
 *  phrase de rappel (« Pour rappel : … »), et l'ecran adapte l'invite du champ
 *  Precision pour que l'auteur sache qu'il peut la demander. Deux litteraux
 *  « commentaire » divergeraient au premier renommage, et le rappel
 *  disparaitrait sans que rien n'echoue.
 */
export const ENTITE_COMMENTAIRE = 'commentaire';

/** Ce que la section Description transmet — l'entité et son contexte. */
export interface ContexteAssistant {
	/** La nature de l'objet, dans les mots de l'écran : « ticket », « actualité »… */
	entite: string;
	contexte: Record<string, string>;
}

/**
 *  Compose le contexte en écartant les valeurs vides.
 *
 *  Les valeurs sont des chaînes ou `null`/`undefined` ; un périmètre (liste de
 *  codes) se passe déjà rendu par `perimetreContexte`.
 */
export function contexteAssistant(
	entite: string,
	champs: Record<string, string | number | boolean | null | undefined>,
): ContexteAssistant {
	const contexte: Record<string, string> = {};
	for (const [libelle, valeur] of Object.entries(champs)) {
		if (valeur === null || valeur === undefined || valeur === '' || valeur === false) continue;
		contexte[libelle] = valeur === true ? 'oui' : String(valeur);
	}
	return { entite, contexte };
}

/** Le périmètre, rendu comme l'écran le lit — jamais les codes bruts. */
export function perimetreContexte(codes: string[] | null | undefined): string {
	return codes && codes.length ? perimetreLabel(codes) : '';
}

/** Le geste a-t-il quelque chose à retravailler ? — désactivé si TOUT est vide. */
export function peutSolliciter(
	titre: string | null | undefined,
	description: string | null | undefined,
): boolean {
	return !!(titre && titre.trim()) || !!(description && description.replace(/<[^>]*>/g, '').trim());
}

/**
 *  Le contexte d'un COMMENTAIRE : l'objet porteur, pour que le modèle sache de
 *  quoi parle le fil. Le titre et la description de l'objet, jamais le fil
 *  entier — un commentaire se relit à la lumière de l'objet, pas de tout ce
 *  qui a été dit avant. Le « nouvel état » est ajouté par `EvolForm`, seul à
 *  le connaître au moment du geste.
 */
export function contexteCommentaire(
	porteur: {
		titre?: string | null;
		question?: string | null;
		description?: string | null;
		contenu?: string | null;
	},
	etat?: string | null,
): ContexteAssistant {
	return contexteAssistant(ENTITE_COMMENTAIRE, {
		'Titre de l’objet': porteur.titre ?? porteur.question ?? '',
		'Description de l’objet': stripHtml(porteur.description ?? porteur.contenu ?? '').slice(0, 500),
		'État actuel': etat ?? '',
	});
}

/**
 *  Le contexte d'un commentaire, complété du NOUVEL état quand l'entrée en pose
 *  un — c'est-à-dire quand le geste est une transition (`etat`) et qu'un état
 *  est choisi. Le libellé vient de la table de l'écran, jamais du code.
 */
export function avecNouvelEtat(
	assistant: ContexteAssistant | null,
	geste: string,
	nouveauStatut: string,
	libelles: Record<string, string>,
): ContexteAssistant | null {
	if (!assistant || geste !== 'etat' || !nouveauStatut) return assistant;
	const libelle = libelles[nouveauStatut] ?? nouveauStatut;
	return { ...assistant, contexte: { ...assistant.contexte, 'Nouvel état': libelle } };
}
