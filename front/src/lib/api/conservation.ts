/**
 * La CONSERVATION des affaires (#2014) — le constat de ce qui partira, et quand :
 * Admin › Maintenance, carte `CarteConservationAffaires`.
 *
 * `routers/admin/conservation_affaires.py` ; la règle vit au serveur
 * (`utils/conservation_affaires`), l'écran n'en recalcule rien. La case qui
 * l'applique se coche dans Administration › Services (lot L2) ; les archives
 * produites partent sur le PC par la sauvegarde hors site (lot L3).
 */

import { api, BASE } from './client';

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

/** Une archive des pièces jointes d'affaires échues : un exercice, un type. */
export interface ArchiveAffaires {
	id: number;
	/** `affaires-<copropriété>-<exercice>-<type>.zip` — le même nom sur le PC. */
	nom: string;
	exercice: string;
	type: string;
	libelle: string;
	affaires: number;
	fichiers: number;
	octets: number;
	cree_le: string;
	/** `null` : le PC ne l'a pas encore copiée. */
	copiee_le: string | null;
	/** `null` : le serveur la garde — téléchargeable. */
	retiree_le: string | null;
}

export interface ConstatConservation {
	/** Le mois où commence l'exercice ; `null` : l'année civile. */
	mois_debut_exercice: number | null;
	/** La case d'Administration › Services : cochée, les affaires échues sont traitées la nuit. */
	application_active: boolean;
	/** La politique de confidentialité servie porte la phrase de conservation. */
	politique_annonce: boolean;
	/** Le serveur retire sa copie d'une archive ce nombre de jours après sa copie sur le PC. */
	delai_retrait_jours: number;
	echeances: EcheanceConservation[];
	archives: ArchiveAffaires[];
}

export const conservation = {
	constat: () => api.get<ConstatConservation>('/admin/conservation-affaires'),
	/** L'adresse de téléchargement d'une archive, tant que le serveur la garde. */
	archiveUrl: (id: number) => `${BASE}/admin/conservation-affaires/archives/${id}/fichier`,
};
