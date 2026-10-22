/**
 *  La synthèse d'une affaire close (#1643) — la lire, et les gestes du conseil.
 *
 *  Le serveur décide de tout : qui lit un brouillon (le conseil seul), si l'on
 *  peut produire une synthèse (`produisible`), et les métriques, CALCULÉES et
 *  figées à la production. L'écran ne recompose rien — il dessine.
 *
 *  Routes : `api/app/routers/tickets/synthese.py`.
 */
import { api } from './client';

/** Une étape du kanban et ses jours ouvrés (au demi-jour). */
export interface EtapeSynthese {
	statut: string;
	jours: number;
}

/** Un jalon de la chronologie : ouverture, état, relance, réouverture. */
export interface JalonSynthese {
	quand: string;
	type: 'creation' | 'etat' | 'relance' | 'reouverture';
	statut: string | null;
	/** Jours ouvrés depuis le jalon précédent — `null` pour le premier. */
	ecart: number | null;
}

/** La moyenne des autres affaires closes de même catégorie sur l'exercice. */
export interface ComparaisonSynthese {
	nombre: number;
	categorie: string;
	exercice: string;
	duree_totale: number | null;
	premiere_reponse_syndic: number | null;
	relances: number;
	suites: number;
}

/** La récidive d'un équipement (#1647) — `utils/synthese_affaire/recidive.py`.
 *  Envoyée au CONSEIL seul : le serveur retire la clé pour tout autre lecteur. */
export interface RecidiveSynthese {
	equipement: string;
	/** La fenêtre, en mois avant la clôture. */
	mois: number;
	/** Les AUTRES affaires résolues, de la plus récente à la plus ancienne. */
	autres: { id: number; numero: string; titre: string; ferme_le: string }[];
}

/** Les métriques figées — `utils/synthese_affaire/metriques.py`. */
export interface MetriquesSynthese {
	version: number;
	issue: string;
	ouverte_le: string;
	close_le: string;
	duree_totale: number;
	premiere_reponse_syndic: number | null;
	relances: number;
	suites: number;
	etapes: EtapeSynthese[];
	etape_plus_longue: string | null;
	reaction_relance: number | null;
	semaines: number[];
	semaines_muettes: number;
	chronologie: JalonSynthese[];
	reouvertures: number;
	comparaison: ComparaisonSynthese | null;
	/** Absente sous le seuil, et pour tout lecteur qui n'est pas du conseil. */
	recidive?: RecidiveSynthese | null;
}

/** Une étape du kanban dans un ENSEMBLE d'affaires : sa durée moyenne (jours
 *  ouvrés) et combien d'affaires y sont passées — `schemas_synthese.EtapeMoyenne`. */
export interface EtapeMoyenne {
	statut: string;
	jours: number;
	nombre: number;
}

/** Les moyennes d'un ensemble d'affaires closes (#1645, #1646) —
 *  `schemas_synthese.ResumeAffaires`, calculées par `utils/synthese_affaire/agregats`.
 *  Une moyenne `null` : rien ne se mesurait — l'écran dit « — », jamais « 0 j ». */
export interface ResumeAffaires {
	nombre: number;
	annulees: number;
	duree_totale: number | null;
	etapes: EtapeMoyenne[];
	/** Le TOTAL des relances au syndic. */
	relances: number;
	relances_par_affaire: number | null;
	/** Délai moyen de réaction du syndic après la dernière relance… */
	reaction_relance: number | null;
	/** …et le nombre d'affaires où il se mesure. */
	reactions: number;
	premiere_reponse_syndic: number | null;
	suites: number | null;
}

/** Un exercice comptable : l'année où il commence, et son nom (« 2025-2026 »). */
export interface ExerciceLu {
	annee: number;
	libelle: string;
}

/** `SyntheseLue` — la synthèse telle que la fiche et le carnet la lisent. */
export interface SyntheseAffaire {
	id: number;
	ticket_id: number;
	evolution_id: number | null;
	statut: 'brouillon' | 'validee';
	metriques: MetriquesSynthese | null;
	synthese: string | null;
	difficultes: string | null;
	amelioration: string | null;
	prompt_complement: string | null;
	assiste_ia: boolean;
	/** Pourquoi l'assistant n'a rien rédigé — le bandeau « Synthèse à rédiger ». */
	motif_vide: string | null;
	produite_le: string | null;
	validee_le: string | null;
	validee_par_nom: string | null;
}

/** `SyntheseEtat` — ce que la fiche demande pour une affaire. */
export interface EtatSynthese {
	synthese: SyntheseAffaire | null;
	/** Le bouton « Produire la synthèse » (conseil, affaire close sans synthèse). */
	produisible: boolean;
	/** Une demande attend ses trente minutes : la synthèse arrive. */
	en_attente: boolean;
}

/** `PropositionSynthese` — ce que « Relancer » et « Recommencer » rendent : une
 *  rédaction PROPOSÉE, rien n'est remplacé avant « Appliquer ». `actuelle` est la
 *  synthèse relue, métriques recalculées. */
export interface PropositionSynthese {
	tentative_id: number;
	synthese: string;
	difficultes: string;
	amelioration: string;
	prompt_complement: string | null;
	actuelle: SyntheseAffaire;
}

export interface ModificationSynthese {
	synthese?: string;
	difficultes?: string;
	amelioration?: string;
}

//  Les chemins s'écrivent EN ENTIER, jamais composés d'un préfixe :
//  `test_endpoints_orphelins.py` reconnaît un consommateur à son chemin.
export const syntheses = {
	lire: (ticketId: number) => api.get<EtatSynthese>(`/tickets/${ticketId}/synthese`),
	modifier: (ticketId: number, corps: ModificationSynthese) =>
		api.patch<SyntheseAffaire>(`/tickets/${ticketId}/synthese`, corps),
	relancer: (ticketId: number, promptComplement: string) =>
		api.post<PropositionSynthese>(`/tickets/${ticketId}/synthese/relancer`, {
			prompt_complement: promptComplement,
		}),
	recommencer: (ticketId: number) =>
		api.post<PropositionSynthese>(`/tickets/${ticketId}/synthese/recommencer`),
	appliquer: (ticketId: number, tentativeId: number) =>
		api.post<SyntheseAffaire>(
			`/tickets/${ticketId}/synthese/propositions/${tentativeId}/appliquer`,
		),
	valider: (ticketId: number) => api.post<SyntheseAffaire>(`/tickets/${ticketId}/synthese/valider`),
	produire: (ticketId: number) =>
		api.post<SyntheseAffaire>(`/tickets/${ticketId}/synthese/produire`),
	supprimer: (ticketId: number) => api.delete(`/tickets/${ticketId}/synthese`),
};
