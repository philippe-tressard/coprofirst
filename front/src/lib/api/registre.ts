/**
 * Le REGISTRE DES INSTALLATIONS, vu de la référence — l'onglet « Installations »
 * d'Administration, réservé à l'opérateur (R4 #1880, spec §4.11).
 *
 * `routers/admin/installations.py` : la liste, la fiche (contact, contrat accepté
 * archivé sous l'identifiant, journal des décisions, dernier rapport nocturne), et
 * les gestes — valider, suspendre, rétablir, résilier, accorder des services. Un
 * geste voyage dans le bail : l'installation le lit à son prochain renouvellement.
 * Supprimer une installation résiliée la retire de la liste (`registre/conservation`).
 * Le canal, la vague et l'épinglage décident de la version cible de son bail, que sa
 * mise à jour nocturne installe (`registre/canaux`, R5 #1881).
 *
 * À part d'`instance.ts`, qui parle de CETTE installation : ici, ce sont les AUTRES.
 */

import { api } from './client';

/**  `en_attente` · `active` · `suspendue` · `resiliee` — l'état au registre. */
export type EtatRegistre = 'en_attente' | 'active' | 'suspendue' | 'resiliee';

/**  Les décisions de l'opérateur (`registre/decisions.TRANSITIONS`). */
export type DecisionInscription = 'valider' | 'suspendre' | 'retablir' | 'resilier';

/**  Les gestes qu'une fiche peut offrir : les décisions, et supprimer une résiliée. */
export type GesteRegistre = DecisionInscription | 'supprimer';

/**  Une alerte de la référence sur une installation (`registre/alertes.GENRES`, R4b
 *   #1960) — calculée par le serveur à chaque lecture ; l'écran n'en tient pas la liste. */
export interface AlerteRegistre {
	code: string;
	libelle: string;
	/** Ce qui a été constaté, avec sa mesure. */
	message: string;
	/** Grave : l'opérateur en reçoit un courriel (muette, clone, deux références, correctifs du système). */
	grave: boolean;
}

export interface ResumeInstallation {
	identifiant: string;
	etat: EtatRegistre;
	/** `main` (la référence) · `replica` · `special-<nom>` */
	canal: string;
	version_logicielle: string | null;
	cree_le: string;
	/** La dernière fois que l'installation s'est adressée à la référence. */
	vue_le: string | null;
	/** « Prénom NOM » de l'administrateur d'installation. */
	administrateur: string | null;
	conditions_acceptees: number | null;
	dernier_rapport_le: string | null;
	/** Les services que la référence lui accorde — le bail les porte. */
	services_autorises: string[];
	/** Ce que la référence lui reproche, dans l'ordre de la spec. */
	alertes: AlerteRegistre[];
	/** Quand elle reçoit la version de son canal (`VagueLue.code`). */
	vague: number;
	/** La version que l'opérateur lui impose — épinglage, ou ordre de revenir. */
	version_epinglee: string | null;
	/** Ce que son prochain bail portera ; `null` : aucune mise à jour automatique. */
	version_cible: string | null;
}

/**  Un canal de distribution : un pointeur vers une version de `main` (D21). */
export interface CanalDistribution {
	nom: string;
	version: string | null;
	version_precedente: string | null;
	/** Quand il a avancé — l'instant d'où se comptent les vagues. */
	avance_le: string | null;
	/** `replica` avance seul, à la lecture de sa branche ; un canal spécial, par l'opérateur. */
	modifiable: boolean;
}

export interface VagueLue {
	code: number;
	libelle: string;
}

/**  Ce que l'opérateur règle : la version cible du prochain bail en découle. */
export interface ReglageDistribution {
	canal: string;
	vague: number;
	/** `null` ou vide : suivre le canal. */
	version_epinglee: string | null;
}

export interface ServiceAccordable {
	code: string;
	libelle: string;
}

export interface RegistreLu {
	/** Le registre est-il servi ici ? Seulement sur la référence. */
	actif: boolean;
	installations: ResumeInstallation[];
	services_accordables: ServiceAccordable[];
	/** `replica` en tête, puis les canaux spéciaux. */
	canaux: CanalDistribution[];
	vagues: VagueLue[];
}

export interface ContratAccepte {
	version: number;
	empreinte: string;
	/** Le texte EXACT accepté, tel qu'archivé (D26). */
	texte: string;
	accepte_par: string;
	accepte_le: string;
}

export interface DecisionRegistre {
	geste: string;
	motif: string;
	/** « système », ou « opérateur #N » — un identifiant, jamais un nom. */
	auteur: string;
	cree_le: string;
}

/**  Le dernier rapport nocturne (`registre/contrat.Rapport`) — des nombres et des
 *   oui/non, aucune donnée de résident ; une mesure impossible vaut `null`. */
export interface RapportInstallation {
	identite: {
		version_logicielle: string;
		revision_base: string | null;
		derniere_mise_a_jour: string | null;
	};
	hebergement: {
		hebergeur: string | null;
		pays_donnees: string | null;
		architecture: string | null;
		memoire_mo: number | null;
		disque_total_mo: number | null;
		disque_occupe_mo: number | null;
		moteur_base: string | null;
		taille_bases_mo: number | null;
		certificat_expire_le: string | null;
	};
	sauvegarde: {
		derniere_reussie_le: string | null;
		copie_hors_machine: boolean | null;
		dernier_essai_restauration_le: string | null;
	};
	posture: {
		documentation_api_coupee: boolean | null;
		cookie_securise: boolean | null;
		secret_suffisant: boolean | null;
		lien_source_present: boolean | null;
	};
	coproprietes: {
		identifiant: string;
		nom: string;
		lots: number | null;
		utilisateurs_actifs: number | null;
		utilisateurs_inscrits: number | null;
	}[];
}

export interface FicheInstallation extends ResumeInstallation {
	contact: {
		prenom: string;
		nom: string;
		courriel: string;
		telephone: string | null;
		mis_a_jour_le: string;
	} | null;
	contrats: ContratAccepte[];
	decisions: DecisionRegistre[];
	dernier_rapport: RapportInstallation | null;
	/** Les gestes que l'opérateur peut faire maintenant — la règle est au serveur. */
	gestes_possibles: GesteRegistre[];
	/** Ses services peuvent-ils s'accorder ? Pas pour la référence. */
	services_modifiables: boolean;
}

export const registre = {
	installations: () => api.get<RegistreLu>('/admin/installations'),
	fiche: (identifiant: string) =>
		api.get<FicheInstallation>(`/admin/installations/${encodeURIComponent(identifiant)}`),
	decider: (identifiant: string, geste: DecisionInscription, motif: string) =>
		api.post<FicheInstallation>(
			`/admin/installations/${encodeURIComponent(identifiant)}/decisions`,
			{ geste, motif },
		),
	accorderServices: (identifiant: string, services: string[], motif: string) =>
		api.put<FicheInstallation>(`/admin/installations/${encodeURIComponent(identifiant)}/services`, {
			services,
			motif,
		}),
	distribuer: (identifiant: string, reglage: ReglageDistribution, motif: string) =>
		api.put<FicheInstallation>(
			`/admin/installations/${encodeURIComponent(identifiant)}/distribution`,
			{ ...reglage, motif },
		),
	/** Crée un canal spécial, ou le fait pointer vers une version ; rend tous les canaux. */
	pointerCanal: (nom: string, version: string, motif: string) =>
		api.put<CanalDistribution[]>(`/admin/canaux-distribution/${encodeURIComponent(nom)}`, {
			version,
			motif,
		}),
	/** Résiliée seulement : la ligne quitte la liste, sa fiche répond 404 ensuite. */
	supprimer: (identifiant: string, motif: string) =>
		api.post<void>(`/admin/installations/${encodeURIComponent(identifiant)}/suppression`, {
			motif,
		}),
};
