//  La PASTILLE DE LECTURE — « qui la lit » —, servie par l'API (#2633).
//
//  Le site la composait dans son front (`lectureDe`) ; le serveur la calcule
//  (`api/app/utils/lecture_pastille`) et la sert avec chaque objet enregistré
//  (`lecture` d'une affaire, d'une ligne du fil, d'une annonce, d'une idée, d'un
//  sondage) et pour une saisie en cours (`POST /lectures/apercu`). Les deux
//  clients la LISENT.
import { api } from './client';

/**  La pastille — `utils/lecture_pastille/modele.Lecture`. */
export interface Lecture {
	/** `tous`, `residents`, `coproprietaires`, `cs`, `concerne`, ou des profils joints par « + ». */
	cle: string;
	icones: string[];
	/** Le libellé de la carte — « Copropriétaires », « CS ». */
	court: string;
	/** Le libellé de la section — « Copropriétaires (occupants et bailleurs) ». */
	long: string;
	/** Le titre de la pastille longue : le libellé, et le cadenas en toutes lettres. */
	titre: string;
	/** Les profils qui lisent ; vide : le conseil seul. */
	profils: string[];
	/** Le cadenas : seuls ceux du périmètre lisent. */
	perimetre_reserve: boolean;
	hors_perimetre: string[];
	du_perimetre: string;
	/** La phrase de l'infobulle : « Lue par… ». */
	phrase: string;
	/** « Pas les locataires, ni… ». */
	exclus: string;
	/** Personne n'est exclu : rien sur la carte, « Tous » dans la section. */
	par_defaut: boolean;
	/** Une actualité au périmètre choisi mais non réservé. */
	avertissement: string;
}

/**  Ce qu'une saisie dit de ses lecteurs — `ApercuLectureEntree`. */
export interface SaisieLecture {
	/** `actualite` pour une actualité ; absente, une Suite sans nature. */
	categorie?: string | null;
	statut?: string | null;
	confidentiel?: boolean;
	public_cible?: string[];
	perimetre_cible?: string[];
	reserve_perimetre?: boolean;
}

/**  L'aperçu d'une saisie — `ApercuLecture`. */
export interface ApercuLecture {
	lecture: Lecture;
	/** Les Destinataires d'une affaire SANS choix du conseil — vide pour une actualité. */
	destinataires_par_defaut: string[];
	/** Personne d'autre que le conseil (et l'auteur) ne la lit, périmètre mis à part. */
	lue_du_seul_conseil: boolean;
}

export const lectures = {
	apercu: (saisie: SaisieLecture) => api.post<ApercuLecture>('/lectures/apercu', saisie),
};
