//  Les réponses du tableau de bord de télémétrie (#1631, #1628, #1632) — le
//  client qui les rend est `admin.telemetryDashboard` (`administration.ts`).
//  Rangées ici le 03/10/2026 : `administration.ts` passait au-dessus du plafond
//  de modularité, et ces types ne servent qu'à l'onglet Télémétrie.

/** Une erreur vue par les résidents (#1631) — `utils/erreurs_navigateur.synthese_erreurs`. */
export interface ErreurNavigateur {
	page: string;
	code: string;
	total: number;
	premiere_le: string;
	derniere_le: string;
}

/** Médiane et 75ᵉ centile d'un ensemble de durées, en millisecondes (#1632). */
export interface ResumeDurees {
	mesures: number;
	mediane: number;
	p75: number;
}

/** Les durées d'affichage (#1632) — `utils/mesures_affichage.synthese_mesures`. */
export type IndicateurDuree = 'chargement' | 'navigation' | 'donnees';
export interface SyntheseDurees {
	indicateurs: (ResumeDurees & { indicateur: IndicateurDuree })[];
	pages: (ResumeDurees & { page: string; indicateur: IndicateurDuree })[];
}

/** Un geste mesuré (#1633) — `utils/gestes_formulaire.synthese_gestes`. `geste` est
 *  un identifiant de `#lib/aboutissement`, qui en porte le libellé. */
export interface GesteAbouti {
	geste: string;
	ouvertures: number;
	envois: number;
	/** `null` sans ouverture mesurée. */
	taux: number | null;
}

/** Les arrivées par une notification (#1634) — `utils/arrivees_notification.synthese_arrivees`. */
export interface ArriveeNotification {
	canal: 'courriel' | 'whatsapp';
	/** Le code du modèle d'un courriel ; `null` pour le groupe WhatsApp. */
	modele: string | null;
	/** Le libellé du modèle, tel qu'il est en base ; `null` s'il n'y est pas. */
	libelle: string | null;
	/** Vues arrivées par ce lien, anonymes comprises (renvoyées à la connexion). */
	arrivees: number;
	/** Comptes distincts parmi elles. */
	comptes: number;
	/** Messages envoyés sur la période ; `null` : inconnu. Un envoi groupé compte pour un. */
	envois: number | null;
}

/** Une ligne de « Qui vient » : comptes venus sur comptes mesurés (#1628). */
export interface LigneAdoption {
	libelle: string;
	actifs: number;
	comptes: number;
	/** `null` quand la ligne n'a aucun compte. */
	taux: number | null;
}

/** Le taux d'adoption (#1628) — `utils/adoption.adoption`, sur la fenêtre de la vue. */
export interface Adoption {
	/** Ce que couvre la fenêtre : « aujourd’hui », « 30 derniers jours », « 12 derniers mois ». */
	periode: string;
	global: LigneAdoption;
	/** Comptes qui ont refusé la mesure d'audience, exclus du calcul. */
	refus: number;
	par_profil: LigneAdoption[];
	par_type: LigneAdoption[];
	par_batiment: LigneAdoption[];
}

/** Les quatre vues de l'onglet (03/10/2026) : le jour, 30 jours, 12 mois, 10 ans par année. */
export type PorteeTelemetrie = 'jour' | 'mois' | 'annee' | 'total';
/** Le filtre « avec / sans gestionnaire du site » (03/10/2026). */
export type FiltreGestionnaire = 'avec' | 'sans';

/** Ce que le serveur dit du filtre — `utils/telemetrie_tableau`. */
export interface EtatFiltreGestionnaire {
	/** Proposé seulement s'il changerait quelque chose : un gestionnaire qui a des vues, et d'autres aussi. */
	propose: boolean;
	/** Faux : aucun administrateur n'est désigné gestionnaire du site — le filtre n'a rien à écarter. */
	gestionnaire_designe: boolean;
	/** Ce qui a été appliqué — « avec » quoi qu'on demande si le filtre n'est pas proposé. */
	applique: FiltreGestionnaire;
	/** Dernier jour dont l'agrégat ne sépare pas le gestionnaire (compté dans les deux lectures). */
	non_distingue_jusqu_au: string | null;
}

/** Un bâton du graphe : une heure, un jour, un mois ou une année selon la vue. */
export interface BatonTelemetrie {
	label: string;
	total: number;
	uniques: number | null;
}

/** Une page du palmarès. */
export interface PageTelemetrie {
	page: string;
	total: number;
	uniques: number;
}

/** Un utilisateur du palmarès (`telemetrie_calculs._palmares`). */
export interface UtilisateurActif {
	nom: string;
	statut: string | null;
	batiment_id: number | null;
	total: number;
	pages: number;
	derniere_connexion: string | null;
}

/** Un record : le jour (ou le mois) et ses utilisateurs uniques. */
export interface RecordTelemetrie {
	uniques: number;
	jour?: string;
	mois?: string;
}

/**
 * Les nombres clés de la vue — `utils/telemetrie_tableau`. Toutes les clés sont
 * facultatives : elles changent avec la vue, et l'écran les lit une à une.
 */
export interface IndicateursTelemetrie {
	vues?: number;
	utilisateurs?: number;
	pages?: number;
	heure_pointe?: string | null;
	moy_vues_utilisateur?: number | null;
	moy_vues_jour?: number | null;
	moy_utilisateurs_jour?: number | null;
	moy_vues_mois?: number | null;
	moy_vues_an?: number | null;
	mois_actifs?: number | null;
	annees_actives?: number | null;
	jour_pointe?: RecordTelemetrie | null;
	record_jour?: RecordTelemetrie | null;
	record_mois?: RecordTelemetrie | null;
	vues_non_attribuees?: number;
}

/** Un compte sans visite depuis le plus court des seuils (#1629) — nominatif, réservé à l'administrateur. */
export interface CompteDormant {
	user_id: number;
	nom: string;
	/** Le type de résident, libellé. */
	type: string;
	/** Le jour de la dernière visite connue ; `null` : aucune depuis la validation. */
	derniere_visite: string | null;
	jours: number;
}

/** Le retour des comptes validés sur la période (#1629). */
export interface RetourArrivants {
	periode: string;
	fenetre_jours: number;
	valides: number;
	revenus: number;
	jamais_revenus: number;
	/** Fenêtre encore ouverte, pas encore venus : issue inconnue. */
	en_attente: number;
	/** Sur les issues connues seulement ; `null` : aucune. */
	taux: number | null;
}

/** Comptes dormants et retour des arrivants (#1629) — `utils/retour_comptes.retour_comptes`. */
export interface RetourComptes {
	comptes_mesures: number;
	/** Comptes qui ont refusé la mesure d'audience, exclus des deux calculs. */
	refus: number;
	dormants: { seuil: number; nombre: number }[];
	liste_dormants: CompteDormant[];
	arrivants: RetourArrivants;
}

/** Ce que le profil exporte de sa mesure d'audience (`GET /auth/me/telemetrie`). */
export interface ExportTelemetrie {
	evenements: unknown[];
	mois_de_presence: string[];
	jour_de_derniere_visite: string | null;
}

/** Le tableau de bord de télémétrie. */
export interface TableauTelemetrie {
	scope: PorteeTelemetrie;
	kpi: IndicateursTelemetrie;
	chart: BatonTelemetrie[];
	chart_label: string;
	top_pages: PageTelemetrie[];
	top_users: UtilisateurActif[];
	erreurs: ErreurNavigateur[];
	performance: SyntheseDurees;
	gestes: GesteAbouti[];
	arrivees: ArriveeNotification[];
	/** `null` : la vue ne sait pas qui est venu (Total). */
	adoption: Adoption | null;
	/** Dormants et arrivants, à seuils fixes quelle que soit la vue (#1629). */
	retour: RetourComptes;
	filtre_gestionnaire: EtatFiltreGestionnaire;
}
