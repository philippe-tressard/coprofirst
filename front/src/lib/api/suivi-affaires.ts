/**
 * Le SUIVI DES AFFAIRES du Reporting CS (16/10/2026, maquette D2) — toutes les
 * affaires ni résolues ni annulées, leur nombre, leur répartition, la synthèse
 * de l'assistant et le PDF.
 *
 * `routers/suivi_affaires.py` ; la règle d'entrée et l'ancienneté vivent au
 * serveur (`utils/suivi_affaires`), l'écran n'en recalcule rien.
 */

import { api } from './client';

export interface AffaireOuverte {
	id: number;
	numero: string;
	titre: string;
	/** Du TEXTE (le HTML de la description, aplati par le serveur) — jamais `{@html}`. */
	descriptif: string;
	categorie: string;
	libelle_categorie: string;
	statut: string;
	libelle_statut: string;
	/** AAAA-MM-JJ, le jour de Paris. */
	ouverte_le: string;
	age_jours: number;
	/** `ancienne` (> 90 j), `moyenne` (> 30 j), `recente` — les seuils restent au serveur. */
	anciennete: 'ancienne' | 'moyenne' | 'recente';
}

export interface RepartitionCategorie {
	categorie: string;
	libelle: string;
	nombre: number;
}

export interface SuiviAffaires {
	jour: string;
	total: number;
	/** Ouvertes depuis plus de 90 jours. */
	anciennes: number;
	/** La catégorie la plus nombreuse en tête. */
	par_categorie: RepartitionCategorie[];
	/** La plus ancienne en tête. */
	affaires: AffaireOuverte[];
	/** Le ✨ a-t-il un sens ? — l'assistant est réglé et l'usage activé. */
	synthese_disponible: boolean;
}

/** Du TEXTE : un résumé et quelques points, affichés tels quels. */
export interface SyntheseAffaires {
	resume: string;
	points: string[];
}

export const suiviAffaires = {
	lire: () => api.get<SuiviAffaires>('/suivi-affaires'),
	synthese: () => api.post<SyntheseAffaires>('/suivi-affaires/synthese'),
	/** Le PDF — avec la synthèse affichée, si l'écran en a une. */
	pdf: (synthese: SyntheseAffaires | null) => api.postFichier('/suivi-affaires/pdf', { synthese }),
};
