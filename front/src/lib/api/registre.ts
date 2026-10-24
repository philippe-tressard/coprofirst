/**
 * Le REGISTRE DES INSTALLATIONS, vu de la référence — l'onglet « Installations »
 * d'Administration, réservé à l'opérateur (R4 #1880, spec §4.11).
 *
 * `routers/admin/installations.py` : la liste, la fiche (contact, contrat accepté
 * archivé sous l'identifiant, journal des décisions, dernier rapport nocturne), et
 * les gestes — valider, suspendre, rétablir, résilier, accorder des services. Un
 * geste voyage dans le bail : l'installation le lit à son prochain renouvellement.
 * Supprimer une installation résiliée la retire de la liste (`registre/conservation`).
 * Le canal (Urgence ou une version choisie) et la vague décident de la version cible
 * de son bail, que sa mise à jour nocturne installe (`registre/canaux`, #2210).
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
	/** `urgence` (la dernière version publiée) · une version `X.Y.Z` choisie · `main` (la référence) */
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
	/** Ce que son prochain bail portera ; `null` : aucune mise à jour automatique. */
	version_cible: string | null;
}

/**  Une version PUBLIÉE : son tag a sa release et l'archive de déploiement. */
export interface VersionPubliee {
	version: string;
	/** La date du tag, d'où se comptent les 7 jours. */
	publiee_le: string;
}

/**  Les versions publiées, relues chaque nuit par la référence (`registre/versions`). */
export interface VersionsPubliees {
	/** Les 5 dernières mineures, chacune à son dernier correctif — la liste du canal. */
	proposees: VersionPubliee[];
	/** La dernière lecture des releases ; `null` : jamais lues. */
	lues_le: string | null;
}

export interface VagueLue {
	code: number;
	libelle: string;
	/** Ce qu'elle installe, en une phrase. */
	detail: string;
	/** Offerte avec le canal Urgence ; sinon, avec une version choisie (Fixe). */
	avec_urgence: boolean;
	/** Celle d'une inscription neuve, et du canal Urgence quand on y revient. */
	defaut: boolean;
	/** Ce qu'elle installe aujourd'hui, pour une vague du canal Urgence. */
	cible: VersionPubliee | null;
}

/**  Ce que l'opérateur règle : la version cible du prochain bail en découle. */
export interface ReglageDistribution {
	/** `urgence`, ou une version `X.Y.Z` publiée. */
	canal: string;
	vague: number;
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
	/** Les versions publiées, d'où se choisit le canal. */
	versions: VersionsPubliees;
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
	/** Résiliée seulement : la ligne quitte la liste, sa fiche répond 404 ensuite. */
	supprimer: (identifiant: string, motif: string) =>
		api.post<void>(`/admin/installations/${encodeURIComponent(identifiant)}/suppression`, {
			motif,
		}),
};
