/**
 * Demander la suppression de SON compte, et la traiter (#2699) —
 * `routers/auth_suppression.py` et `routers/admin/demandes_suppression.py`.
 *
 * L'app iOS lit les mêmes routes par son client généré : le délai annoncé et ce
 * qui est effacé (`consequences`) sont SERVIS par l'API, jamais recopiés ici.
 */

import { api } from './client';
import type { Annonce } from './types-administration';

export type StatutDemandeSuppression = 'ouverte' | 'traitee' | 'retiree';

/** Une demande de suppression, telle que la personne la lit. */
export interface DemandeSuppression {
	id: number;
	statut: StatutDemandeSuppression;
	cree_le: string;
	traitee_le: string | null;
	/** Le délai maximal annoncé pour la traiter, en jours. */
	delai_annonce_jours: number;
}

/** `GET /auth/demande-suppression` : ma demande en cours, ou rien, et ce qu'il faut savoir avant. */
export interface EtatDemandeSuppression {
	demande: DemandeSuppression | null;
	delai_annonce_jours: number;
	/** Ce qui est effacé et ce qui reste, phrase par phrase. */
	consequences: string[];
}

/** Une demande de la file de l'administration. */
export interface DemandeSuppressionEnAttente extends DemandeSuppression {
	utilisateur_id: number;
	/** « ? » quand le compte n'existe plus. */
	utilisateur_nom: string;
	utilisateur_email: string | null;
	motif: string | null;
}

export interface DemandeSuppressionTraitee {
	statut: StatutDemandeSuppression;
	/** Faux en démonstration : le compte publié est conservé. */
	compte_efface: boolean;
	annonce: Annonce;
}

export const suppressionCompte = {
	etat: () => api.get<EtatDemandeSuppression>('/auth/demande-suppression'),
	/** 400 : mot de passe faux ; 409 : une demande est déjà en cours. */
	demander: (data: { mot_de_passe: string; motif?: string | null }) =>
		api.post<DemandeSuppression>('/auth/demande-suppression', data),
	retirer: () => api.delete('/auth/demande-suppression'),
	/** La file de l'administration (administrateur seul). */
	enAttente: () => api.get<DemandeSuppressionEnAttente[]>('/admin/demandes-suppression'),
	traiter: (id: number) =>
		api.post<DemandeSuppressionTraitee>(`/admin/demandes-suppression/${id}/traiter`),
};
