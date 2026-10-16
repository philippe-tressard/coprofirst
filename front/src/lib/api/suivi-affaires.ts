/**
 * Le SUIVI DES AFFAIRES du Reporting CS (16/10/2026, maquette D2) — les
 * affaires que la relance du syndic retient, leur nombre, leur répartition, le
 * résumé de chacune par l'assistant et le PDF ; et, en mode « Relancer le
 * syndic », ce qu'il faut pour composer la relance (#2035).
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
	/** Les codes du périmètre — `BadgePerimetre` tait celui par défaut. */
	perimetre_cible: string[];
	/** Depuis la dernière avancée — le repère de la relance. */
	jours_sans_avancee: number;
	/** Au-delà du délai de relance : cochée d'office. */
	a_relancer: boolean;
	/** Les jours (AAAA-MM-JJ) des relances déjà envoyées, la plus ancienne en tête. */
	relances: string[];
	/** Ce qui s'affiche sous le titre : le résumé de l'assistant, sinon le descriptif — du TEXTE. */
	apercu: string;
	/** L'aperçu est-il le résumé de l'assistant ? */
	apercu_ia: boolean;
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
	/** Le délai de relance réglé, en jours. */
	delai_jours: number;
	/** Le ✨ a-t-il un sens ? — l'assistant est réglé et l'usage activé. */
	resumes_disponibles: boolean;
}

export const suiviAffaires = {
	lire: () => api.get<SuiviAffaires>('/suivi-affaires'),
	/**  Fait rédiger le résumé de chaque affaire, gardé au serveur : l'écran les
	 *   relit par `lire`. La synthèse d'ensemble de #2034 n'existe plus (#2035). */
	resumer: () => api.post<{ rediges: number }>('/suivi-affaires/resumes'),
	/** Le PDF du relevé, rendu par le serveur. */
	pdf: () => api.postFichier('/suivi-affaires/pdf', {}),
};
