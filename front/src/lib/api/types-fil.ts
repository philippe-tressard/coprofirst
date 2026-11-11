//  Une entrée du fil d'une affaire (l'Historique) et la correction de sa Suite.
//
//  Sortis de `types.ts` le 10/11/2026 : les deux champs servis par entrée
//  (#2646) le faisaient passer son plafond de 500 lignes — la même raison et la
//  même forme que `types-flux.ts` (#2397). `types.ts` les ré-exporte : les écrans
//  qui les lisent là n'ont rien à changer.

export interface TicketEvolution {
	id: number;
	assiste_ia?: boolean;
	/** Le texte reçu, quand l'assistant a mis en forme une réponse par courriel (#1322). */
	contenu_origine?: string | null;
	ticket_id: number;
	/** `synthese` : la Suite porteuse d'une synthèse d'affaire close (`models/synthese.py`). */
	type: 'commentaire' | 'etat' | 'reponse' | 'synthese';
	contenu?: string;
	ancien_statut?: string;
	nouveau_statut?: string;
	/** L'état donné, en clair — servi (`etat_affaire.libelle_etat`, #2633). */
	nouveau_statut_libelle?: string;
	/** Vide quand le compte de l'auteur a été supprimé : « Ancien résident » (#1688). */
	auteur_id: number | null;
	auteur_nom?: string;
	cree_le: string;
	fichiers_urls?: string[];
	/**  Le périmètre que CETTE entrée déclare — absent quand elle n'en parle pas,
	     ce qui est le cas de l'immense majorité des commentaires (#497). */
	perimetre_cible?: string[];
	/**  L'état en vigueur JUSTE AVANT cette entrée, calculé par le serveur sur tout
	 *   le fil (`suivi_fil.statuts_avant`) : la pastille qui, en correction,
	 *   ramène la Suite à un commentaire (01/10/2026). */
	statut_avant?: string | null;
	/**  ✏️ Ce que CE lecteur peut faire de CETTE entrée — servi par le serveur
	 *   (`auth/gestes_evolution`, #2646), jamais recomposé. Absent (installation plus
	 *   ancienne) = « non ». */
	peut_modifier?: boolean;
	/**  🗑️ L'administrateur, sur une entrée saisie (jamais une réponse). */
	peut_supprimer?: boolean;
}

/**  La CORRECTION d'une Suite (`PATCH`) — toutes ses sections sauf la Diffusion
 *   (01/10/2026). Composée par `chargeCorrection` (`#lib/evolutions`), seule
 *   écriture : un relais qui énumérerait ses champs en perdrait (#529). */
export interface CorrectionEvolution {
	contenu: string;
	fichiers_urls?: string[];
	perimetre_cible?: string[];
	assiste_ia?: boolean;
	/** Absents, la Suite garde son Suivi ; envoyés, il est corrigé SUR elle. */
	type?: string;
	nouveau_statut?: string | null;
	affaires_liees?: number[];
	public_cible?: string[];
	epingle?: boolean;
	urgente?: boolean;
	confidentiel?: boolean;
	[planification: string]: unknown;
}
