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
import type { EtatVisite } from './prestataires';

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
	/** Les bâtiments visés — vide pour toute la résidence (#2043). */
	batiments: number[];
	/** L'état de la visite, en mode `entretien` seulement. */
	etat_visite: EtatVisite | null;
	/**  Nouvelle, ou une entrée au fil depuis le dernier résumé (#2044) ; le motif
	 *   est `nouvelle` ou le type de cette entrée (`commentaire`, `etat`…). */
	a_evolue: boolean;
	motif_evolution: string | null;
	/**  Ce que lit la pastille « qui la lit » de la page Affaires (#2089) —
	 *   `PastilleLecture` la rend à l'identique. */
	confidentiel: boolean;
	public_cible: string[];
	reserve_perimetre: boolean;
	/** L'état coché d'office à la saisie de son CR — « À l'AG » reste à l'AG. */
	etat_par_defaut: string;
	/** Le groupe des affaires liées rassemblées (#2083) : l'id de la plus ancienne. */
	groupe: number | null;
	/** L'historique de fusion, cité au point : « TK-12 — Titre » des absorbées. */
	fusionnees: string[];
}

/** Ce que l'assistant — ou, sans lui, le serveur — propose pour une fusion (#2083). */
export interface PropositionFusion {
	titre: string;
	/** HTML — à rendre par l'éditeur, qui l'assainit. */
	description: string;
	assiste_ia: boolean;
}

/** Une tranche d'une barre de répartition : un bâtiment, ou une catégorie. */
export interface TrancheRepartition {
	cle: string;
	libelle: string;
	nombre: number;
	/** La teinte, choisie par le serveur (`repartition.teinter`, #2082) : `s1`…`s8`,
	 *  `p1`…`p4`, `plusieurs`, `autre` — l'écran la peint, il ne la choisit pas. */
	teinte: string;
}

/**  Une barre de répartition, découpée selon l'autre (#2043) : une catégorie
 *   découpée par bâtiment, ou un bâtiment découpé par catégorie. Les clés de
 *   bâtiment : `racine`, `bat:<id>`, `plusieurs` — `utils/suivi_affaires/repartition`. */
export interface BarreRepartition {
	cle: string;
	libelle: string;
	nombre: number;
	tranches: TrancheRepartition[];
}

/** Les deux relevés : le Suivi des affaires, et celui des entretiens périodiques. */
export type ModeReleve = 'affaires' | 'entretien';

export interface SuiviAffaires {
	jour: string;
	total: number;
	/** Ouvertes depuis plus de 90 jours. */
	anciennes: number;
	/** Les affaires fusionnées dans celles du relevé (#2083) — le troisième chiffre. */
	fusionnees: number;
	/** La catégorie la plus nombreuse en tête ; tranches par bâtiment. */
	par_categorie: BarreRepartition[];
	/** La racine en tête ; tranches par catégorie. */
	par_batiment: BarreRepartition[];
	mode: ModeReleve;
	/** La plus ancienne en tête. */
	affaires: AffaireOuverte[];
	/** Le délai de relance réglé, en jours. */
	delai_jours: number;
	/** Le ✨ a-t-il un sens ? — l'assistant est réglé et l'usage activé. */
	resumes_disponibles: boolean;
}

export const suiviAffaires = {
	/**  `point` : les affaires du point en cours y restent jusqu'à sa validation,
	 *   même closes ailleurs (#2082) — la relance lit sans. */
	lire: (mode: ModeReleve = 'affaires', point = false) =>
		api.get<SuiviAffaires>(`/suivi-affaires?mode=${mode}${point ? '&point=true' : ''}`),
	/**  Fait rédiger le résumé de chaque affaire, gardé au serveur : l'écran les
	 *   relit par `lire`. La synthèse d'ensemble de #2034 n'existe plus (#2035). */
	resumer: () => api.post<{ rediges: number }>('/suivi-affaires/resumes'),
	/**  Les affaires liées (#2083) : la proposition (n'écrit rien), la fusion — la
	 *   plus ancienne absorbe —, et « Ne pas fusionner ». */
	fusions: {
		proposer: (ids: number[]) =>
			api.post<PropositionFusion>('/suivi-affaires/fusions/proposition', { ids }),
		fusionner: (ids: number[], titre: string, description: string) =>
			api.post<{ principale_id: number; absorbees: number[] }>('/suivi-affaires/fusions', {
				ids,
				titre,
				description,
			}),
		ecarter: (ids: number[]) => api.post<void>('/suivi-affaires/fusions/ecarter', { ids }),
	},
	/** Le PDF du relevé, rendu par le serveur. */
	pdf: (mode: ModeReleve = 'affaires') => api.postFichier(`/suivi-affaires/pdf?mode=${mode}`, {}),
};
