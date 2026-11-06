/**
 * Reporting CS › Renouvellements — le RELEVÉ servi (#2525).
 *
 * `routers/reporting_renouvellements.py` : l'échéance et l'urgence des diagnostics
 * (`utils/echeance_diagnostic`), celles des contrats (`utils/echeance_contrat`),
 * l'ordre des deux listes, les compteurs du bandeau et l'année de référence — le
 * jour de Paris. L'app iOS lit le même relevé ; l'écran n'en recalcule rien.
 */

import { api } from './client';
import type { DiagnosticType } from './patrimoine';
import type { ContratEntretien } from './prestataires';

export interface ContratARenouveler extends ContratEntretien {
	prestataire_nom: string;
	note_moyenne: number | null;
	nb_notations: number;
	/** Le terme OU le début du préavis tombe dans l'année du relevé. */
	echeance_dans_l_annee: boolean;
}

export interface DiagnosticAEcheance extends DiagnosticType {
	/** « Permanent (…) » : pas d'échéance, même si le texte porte un chiffre. */
	permanent: boolean;
	dernier_rapport_le: string | null;
	prochaine_echeance: string | null;
	/** `null` : sans échéance connue (permanent, ou sans rapport daté). */
	urgence_echeance: 'depasse' | 'annee' | 'futur' | null;
}

export interface ReleveRenouvellements {
	/** L'année de référence, celle du jour de Paris. */
	annee: number;
	preavis_mois: number;
	compteurs: {
		contrats_en_preavis: number;
		echeances_contrats_annee: number;
		audits_a_planifier: number;
	};
	/** La pire note d'abord, puis le terme le plus proche. */
	contrats: ContratARenouveler[];
	/** Les APPLICABLES, l'échéance la plus proche d'abord. */
	diagnostics: DiagnosticAEcheance[];
}

export const reporting = {
	renouvellements: () => api.get<ReleveRenouvellements>('/reporting/renouvellements'),
};
