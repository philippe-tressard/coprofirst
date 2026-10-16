/**
 * La CONSERVATION des affaires (#2014) — le constat de ce qui partira, et quand :
 * Admin › Maintenance, carte `CarteConservationAffaires`.
 *
 * `routers/admin/conservation_affaires.py` ; la règle vit au serveur
 * (`utils/conservation_affaires`), l'écran n'en recalcule rien. Lot L1 : constat
 * seul, rien n'est archivé ni retiré.
 */

import { api } from './client';

/**  Un exercice et un type : les affaires qui partiront ensemble. */
export interface EcheanceConservation {
	/** `travaux` · `entretien` · `breves` */
	type: string;
	libelle: string;
	/** Gardées ce nombre d'exercices complets après celui de leur clôture. */
	exercices: number;
	/** Pourquoi cette durée — à valider avec le syndic. */
	fondement: string;
	/** L'exercice de clôture : « 2025 », ou « 2025-2026 » s'il ne suit pas l'année civile. */
	exercice_cloture: string;
	dernier_exercice_garde: string;
	/** Le jour où elles échoient (AAAA-MM-JJ). */
	echoit_le: string;
	affaires: number;
	fichiers: number;
	octets: number;
	/** Pièces jointes référencées mais absentes du disque — rien à archiver. */
	absents: number;
}

export interface ConstatConservation {
	/** Le mois où commence l'exercice ; `null` : l'année civile. */
	mois_debut_exercice: number | null;
	/** Lot L1 : toujours faux — le constat ne retire rien. */
	application_active: boolean;
	echeances: EcheanceConservation[];
}

export const conservation = {
	constat: () => api.get<ConstatConservation>('/admin/conservation-affaires'),
};
