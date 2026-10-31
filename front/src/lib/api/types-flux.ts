//  Ce que l'ACCUEIL reçoit de `GET /flux` : le fil, ses pastilles (`FluxSante`)
//  et le prochain rendez-vous (#2397).
//
//  Sortis de `types.ts` le 31/10/2026 : le rendez-vous de l'agenda y entrait, et
//  le fichier passait son plafond de 500 lignes — la même raison et la même forme
//  que `affaires-liees.ts` (#2173). `types.ts` les ré-exporte : les écrans qui les
//  lisent là n'ont rien à changer.

export interface FluxItem {
	id: string;
	type: string;
	date: string;
	cree_le?: string;
	titre: string;
	detail?: string;
	badges: string[];
	icon: string;
	lien?: string;
	meta: Record<string, unknown>;
	/** « Me concerne », posé par le serveur (#2215) ; `null` pour ce qui ne porte aucun lieu. */
	me_concerne?: boolean | null;
}
export interface FluxProchain {
	id: string;
	date: string;
	titre: string;
	type: string;
	icon: string;
	ev_type?: string;
	description?: string;
	lieu?: string;
	perimetre?: string;
	prestataire?: string;
	fin?: string;
	statut_kanban?: string;
}
/** Le prochain rendez-vous de l'agenda : une affaire datée, visible de qui lit (#2397). */
export interface RendezVous {
	id: number;
	titre: string;
	debut: string;
	fin?: string | null;
}
export interface FluxSante {
	tickets_ouverts: number;
	tickets_urgents: number;
	resolution_moyenne_heures: number | null;
	sondages_actifs: number;
	/** File de l'onglet « Comptes & accès » de l'Espace CS : comptes + demandes d'accès. */
	validations_cs: number;
	/** File de `/admin` : les deux mêmes, plus les demandes de modification de profil. */
	validations_admin: number;
	tickets_relance_syndic: number;
	prochains: FluxProchain[];
	/** Absent ou `null` : aucun rendez-vous à venir — la pastille se tait. */
	rendez_vous?: RendezVous | null;
}
export interface FluxResponse {
	items: FluxItem[];
	sante: FluxSante;
	/**  Le délai d'archivage du site, en jours : le seuil « récent » de l'accueil (#2060). */
	delai_recent_jours: number;
}
