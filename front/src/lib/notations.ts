/**
 * La notation d'un prestataire — ses trois états, leur libellé, et le commentaire
 * qui justifie l'état.
 *
 * ## Trois états depuis le 14/11/2026 (arbitré)
 *
 * Mauvais · Neutre · Excellent, au lieu des cinq étoiles. Le serveur écrit 1, 3 ou 5
 * (`api/app/utils/notes_prestataires.py`) et lit les anciennes notes 1 à 5 par
 * `etat_de_note` : 1-2 → Mauvais, 3 → Neutre, 4-5 → Excellent. Cette table est la
 * SEULE du front : rien ne recopie les seuils.
 *
 * ## Le commentaire : généré, puis libre
 *
 * Les cases cochées (points forts, points faibles) composent une phrase ; le
 * commentaire libre s'ajoute après. Le texte enregistré est la somme des deux.
 */

import { parAttribut } from './table-statuts.ts';

export const ETATS = ['mauvais', 'neutre', 'excellent'] as const;
export type Etat = (typeof ETATS)[number];

/**
 * Libellé et teinte de chaque état — UNE table, les colonnes s'en déduisent
 * (`#lib/table-statuts`). Le libellé porte le sens, la teinte (`<Badge>`) le confirme.
 */
export const PAR_ETAT = {
	mauvais: { libelle: 'Mauvais', badge: 'badge-red' },
	neutre: { libelle: 'Neutre', badge: 'badge-gray' },
	excellent: { libelle: 'Excellent', badge: 'badge-green' },
} as const;
export const { libelle: LIBELLE_ETAT, badge: TEINTE_ETAT } = parAttribut(PAR_ETAT);

/**
 * Les seuils de l'état d'une MOYENNE (1 à 5, décimale), dans l'ordre : sous la
 * `borne`, l'`etat` ; au-delà de la dernière, `ETAT_AU_DELA`.
 * 🔒 Tables PUBLIÉES aux apps (`notations`, #2775) — littérales.
 */
export const SEUILS_DE_MOYENNE = [
	{ borne: 2.5, etat: 'mauvais' },
	{ borne: 4, etat: 'neutre' },
] as const satisfies readonly { borne: number; etat: Etat }[];
export const ETAT_AU_DELA: Etat = 'excellent';

/** L'état d'une moyenne — pour la carte du prestataire. */
export function etatDeMoyenne(moyenne: number): Etat {
	return SEUILS_DE_MOYENNE.find((s) => moyenne < s.borne)?.etat ?? ETAT_AU_DELA;
}

/** Les motifs à cocher, par nature — la liste est ce qui compose la phrase. */
export const POINTS_FORTS = [
	'délai respecté',
	'travail soigné',
	'pièces fournies',
	'interlocuteur réactif',
] as const;
export const POINTS_FAIBLES = [
	'retard',
	'travail à refaire',
	'facture contestée',
	'intervenant injoignable',
] as const;

/**
 * La forme de la phrase générée et du commentaire enregistré — UNE table, que la phrase,
 * le commentaire et leur décomposition lisent tous trois.
 * 🔒 Table PUBLIÉE aux apps (`commentaireAvis`, #2816) — littérale : les apps refont les
 * trois gestes depuis elle, sans recopier un libellé.
 */
export const FORME_COMMENTAIRE = {
	prefixeForts: 'Points forts : ',
	prefixeFaibles: 'Points faibles : ',
	/** Entre deux motifs d'un même groupe. */
	entreMotifs: ', ',
	/** À la fin de chaque groupe. */
	finDeGroupe: '.',
	/** Entre le groupe des points forts et celui des points faibles. */
	entreGroupes: ' ',
	/** Entre la phrase générée et le texte libre. */
	avantLibre: '\n',
} as const;
const F = FORME_COMMENTAIRE;

/** La phrase générée d'après les cases cochées. Vide si rien n'est coché. */
export function phraseGeneree(forts: readonly string[], faibles: readonly string[]): string {
	const morceaux: string[] = [];
	if (forts.length) morceaux.push(F.prefixeForts + forts.join(F.entreMotifs) + F.finDeGroupe);
	if (faibles.length) morceaux.push(F.prefixeFaibles + faibles.join(F.entreMotifs) + F.finDeGroupe);
	return morceaux.join(F.entreGroupes);
}

/** Le commentaire enregistré : la phrase générée, puis le texte libre. */
export function commentaireComplet(genere: string, libre: string): string {
	return [genere, libre.trim()].filter((s) => s.length > 0).join(F.avantLibre);
}

/** Un commentaire relu : les cases qu'il cochait, et le texte libre qui suit. */
export interface CommentaireDecompose {
	forts: string[];
	faibles: string[];
	libre: string;
}

const echapper = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
const PHRASE = new RegExp(
	`^(?:${echapper(F.prefixeForts)}(.+?)${echapper(F.finDeGroupe)})?\\s*` +
		`(?:${echapper(F.prefixeFaibles)}(.+?)${echapper(F.finDeGroupe)})?$`,
);

/**
 * L'inverse de `commentaireComplet` (15/11/2026) : corriger un avis RECOCHE ses cases.
 * La première ligne n'est reprise comme phrase générée que si chacun de ses motifs est
 * dans les listes — sinon c'est un texte libre qui y ressemble, et il reste libre.
 */
export function decomposerCommentaire(
	commentaire: string | null | undefined,
): CommentaireDecompose {
	const texte = commentaire ?? '';
	const [premiere, ...suite] = texte.split(F.avantLibre);
	const m = PHRASE.exec(premiere.trim());
	const motifs = (liste: string | undefined) => (liste ? liste.split(F.entreMotifs) : []);
	const forts = motifs(m?.[1]);
	const faibles = motifs(m?.[2]);
	const reconnus =
		m !== null &&
		forts.length + faibles.length > 0 &&
		forts.every((f) => (POINTS_FORTS as readonly string[]).includes(f)) &&
		faibles.every((f) => (POINTS_FAIBLES as readonly string[]).includes(f));
	if (!reconnus) return { forts: [], faibles: [], libre: texte };
	return { forts, faibles, libre: suite.join(F.avantLibre) };
}
