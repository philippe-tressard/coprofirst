/**
 * Le POINT CONSEIL SYNDICAL / SYNDIC du Reporting CS (#2041, maquettes A1 et C1)
 * — le Quand, le Où, le Qui d'une réunion, le compte rendu de chaque affaire
 * saisi en direct, et le CR global.
 *
 * `routers/points_conseil.py` ; les règles (un point par mode, reprise à moins
 * de deux heures, non traitées figées à « Terminer ») vivent au serveur
 * (`utils/points_conseil`), l'écran n'en recalcule rien.
 */

import { api } from './client';
import type { ModeReleve } from './suivi-affaires';

/** Le mode du rapport dont le point traite les affaires — les clés du relevé. */
export type ModePoint = ModeReleve;
export type EtatPoint = 'en_cours' | 'a_valider' | 'valide';
export type NaturePresent = 'cs' | 'syndic' | 'invite';

export interface PresentPoint {
	id: number;
	nature: NaturePresent;
	membre_cs_id: number | null;
	membre_syndic_id: number | null;
	prenom: string | null;
	nom: string | null;
	entreprise: string | null;
	fonction: string | null;
	telephone: string | null;
	email: string | null;
	/** A reçu la demande de validation (#2042) — jamais un invité. */
	destinataire: boolean;
	valide_le: string | null;
	/** Validé POUR lui par l'administrateur, avec son accord (#2082). */
	par_derogation: boolean;
}

/** Ce que l'écran envoie : un membre par sa fiche, un invité par ses champs. */
export interface PresentEntree {
	nature: NaturePresent;
	membre_id?: number | null;
	prenom?: string | null;
	nom?: string | null;
	entreprise?: string | null;
	fonction?: string | null;
	telephone?: string | null;
	email?: string | null;
}

export interface PointConseil {
	id: number;
	mode: ModePoint;
	etat: EtatPoint;
	/** Heure murale, telle que saisie (« AAAA-MM-JJTHH:MM »). */
	debut: string;
	fin: string | null;
	moyen: string | null;
	a_distance: boolean;
	lieu: string | null;
	/** Le Où tel que le CR l'écrit — « Sur place — Cabinet du syndic ». */
	ou: string;
	cree_le: string;
	termine_le: string | null;
	valide_le: string | null;
	/** Le nombre d'envois aux présents — la révision qu'ils ont reçue (#2082). */
	revision: number;
	/** Le PDF du CR validé est-il rangé ? */
	pdf_range: boolean;
}

export interface CrAffaire {
	ticket_id: number;
	/** Texte riche — à rendre par un assainisseur de `$lib/sanitize`. */
	contenu: string;
	brouillon: boolean;
	/** « CS et présents » (#2082) — le nom de champ est resté. */
	conseil_seul: boolean;
	/** L'état que l'affaire prend À LA VALIDATION — `null` : inchangé. */
	etat_cible: string | null;
	mis_a_jour_le: string;
}

export interface AffaireCitee {
	id: number;
	numero: string;
	titre: string;
}

export interface CompteRenduPoint {
	point: PointConseil;
	presents: PresentPoint[];
	/** Dans l'ordre d'ouverture des affaires ; `marque` : « Modifié en révision N » (#2082). */
	abordees: { affaire: AffaireCitee; cr: CrAffaire; marque: string | null }[];
	/** Lues dans le relevé tant que le point est en cours, figées à « Terminer ». */
	non_traitees: AffaireCitee[];
	/** Où en est la validation par les présents (#2042). */
	validation: ValidationPoint;
	commentaires: CommentairePoint[];
	/** La révision que le document montre — 0 tant que rien n'est parti (#2082). */
	revision: number;
}

export interface ValidationPoint {
	destinataires: number;
	valides: number;
	/** Un commentaire reçu depuis l'envoi : les 7 jours ne courent plus. */
	suspendue: boolean;
	/** Quand le CR sera validé sans réponse — `null` s'il ne l'est pas d'office. */
	echeance: string | null;
}

export interface CommentairePoint {
	auteur: string;
	contenu: string;
	cree_le: string;
	/** L'accord écrit par l'administrateur pour le présent (#2082). */
	par_derogation: boolean;
}

/** Ce que le porteur d'un lien de validation lit — le CR entier, « CS et présents » compris (#2082). */
export interface CompteRenduParLien {
	etat: EtatPoint;
	debut: string;
	fin: string | null;
	a_distance: boolean;
	lieu: string | null;
	ou: string;
	presents: string[];
	abordees: {
		numero: string;
		titre: string;
		contenu: string;
		conseil_seul: boolean;
		marque: string | null;
		/** « Qui la lit », le mot de la pastille de la page Affaires (#2089). */
		lecture: string;
	}[];
	non_traitees: string[];
	deja_valide: boolean;
	echeance: string | null;
	revision: number;
}

/** Un CR validé, dans la rubrique « Comptes rendus » d'une affaire. */
export interface CrPublie {
	cr_id: number;
	point_id: number;
	debut: string;
	a_distance: boolean;
	lieu: string | null;
	ou: string;
	contenu: string;
	conseil_seul: boolean;
	/**  Le lien vers le PDF du CR : sur une affaire lue du SEUL conseil — ses
	 *   lecteurs peuvent l'ouvrir (#2082, précisé le 21/10/2026). */
	pdf_disponible: boolean;
}

/** Un point d'un autre mode ouvert il y a moins de deux heures : son Qui/Quand/Où. */
export interface ReprisePoint {
	mode: ModePoint;
	debut: string;
	fin: string | null;
	moyen: string | null;
	a_distance: boolean;
	lieu: string | null;
	cree_le: string;
	presents: PresentPoint[];
}

export interface PointCourant {
	compte_rendu: CompteRenduPoint | null;
	reprise: ReprisePoint | null;
}

export interface MembrePoint {
	id: number;
	prenom: string;
	nom: string;
	fonction: string | null;
}

export interface LieuPropose {
	libelle: string;
	adresse: string;
}

/** Un moyen de réunion — la liste vient du serveur (`regles.MOYENS`). */
export interface MoyenPoint {
	cle: string;
	libelle: string;
	/** Quelqu'un est sur place : le lieu se saisit. */
	avec_lieu: boolean;
}

/** Un état proposé pour la validation d'un CR — la liste vient du serveur. */
export interface EtatValidation {
	cle: string;
	libelle: string;
}

export interface ParticipantsPoint {
	conseil: MembrePoint[];
	syndic: MembrePoint[];
	lieux: LieuPropose[];
	moyens: MoyenPoint[];
	/** Ce que la saisie d'un CR propose pour l'état à la validation (#2082). */
	etats_validation: EtatValidation[];
	/** Les catégories d'une affaire ouverte en séance (#2084) — clé et libellé. */
	categories_seance: EtatValidation[];
}

/** Un point validé, dans l'historique du mode (#2082). */
export interface PointHistorique {
	id: number;
	debut: string;
	ou: string;
	valide_le: string | null;
	abordees: number;
	pdf_range: boolean;
}

export interface PointEntree {
	debut: string;
	fin: string | null;
	moyen: string;
	lieu: string | null;
	presents: PresentEntree[];
}

export interface CrEntree {
	contenu: string;
	brouillon: boolean;
	conseil_seul: boolean;
	etat_cible: string | null;
}

export const pointsConseil = {
	participants: () => api.get<ParticipantsPoint>('/points-conseil/participants'),
	courant: (mode: ModePoint) =>
		api.get<PointCourant>(`/points-conseil/courant?mode=${encodeURIComponent(mode)}`),
	/** Les points validés du mode, le plus récent en tête (#2082). */
	historique: (mode: ModePoint) =>
		api.get<PointHistorique[]>(`/points-conseil/historique?mode=${encodeURIComponent(mode)}`),
	ouvrir: (mode: ModePoint, corps: PointEntree) =>
		api.post<CompteRenduPoint>('/points-conseil', { mode, ...corps }),
	corriger: (id: number, corps: Partial<PointEntree>) =>
		api.patch<CompteRenduPoint>(`/points-conseil/${id}`, corps),
	/** Un contenu vide retire le compte rendu de l'affaire. */
	ecrireCr: (id: number, ticketId: number, corps: CrEntree) =>
		api.put<CompteRenduPoint>(`/points-conseil/${id}/affaires/${ticketId}`, corps),
	terminer: (id: number) => api.post<CompteRenduPoint>(`/points-conseil/${id}/terminer`),
	/** Ouvrir une affaire en séance : elle rejoint la liste du point (#2084). */
	ouvrirAffaire: (id: number, corps: { titre: string; categorie: string; description: string }) =>
		api.post<CompteRenduPoint>(`/points-conseil/${id}/affaires`, corps),
	abandonner: (id: number) => api.delete<void>(`/points-conseil/${id}`),
	//  ── La validation (#2042) ──
	renvoyer: (id: number) => api.post<{ envoyes: number }>(`/points-conseil/${id}/renvoyer`),
	valider: (id: number) => api.post<void>(`/points-conseil/${id}/valider`),
	/** Le PDF d'un CR validé — celui qui a été rangé et envoyé aux présents. */
	pdf: (id: number) => api.postFichier(`/points-conseil/${id}/pdf`, {}),
	/**  Le PDF du point à tout instant — « Projet — révision N » tant qu'il n'est
	 *   pas validé : c'est « Exporter en PDF » pendant un point (#2089). */
	apercu: (id: number) => api.postFichier(`/points-conseil/${id}/apercu`, {}),
	/** L'administrateur valide POUR un présent qui a donné son accord (#2082). */
	derogation: (id: number, presentId: number, commentaire: string | null) =>
		api.post<void>(`/points-conseil/${id}/presents/${presentId}/derogation`, { commentaire }),
	/** La rubrique « Comptes rendus » d'une affaire : ses CR validés. */
	crsAffaire: (ticketId: number) => api.get<CrPublie[]>(`/points-conseil/affaires/${ticketId}`),
	/** « CS et présents » d'un CR publié — le conseil le restreint, ou le rouvre. */
	confidentialite: (crId: number, conseilSeul: boolean) =>
		api.patch<void>(`/points-conseil/comptes-rendus/${crId}`, { conseil_seul: conseilSeul }),
	//  ── Le lien d'un présent : sans compte, le jeton seul l'identifie ──
	lien: (jeton: string) =>
		api.get<CompteRenduParLien>(`/points-conseil/lien/${encodeURIComponent(jeton)}`),
	validerParLien: (jeton: string) =>
		api.post<CompteRenduParLien>(`/points-conseil/lien/${encodeURIComponent(jeton)}/valider`),
	commenterParLien: (jeton: string, contenu: string) =>
		api.post<CompteRenduParLien>(`/points-conseil/lien/${encodeURIComponent(jeton)}/commentaire`, {
			contenu,
		}),
};
