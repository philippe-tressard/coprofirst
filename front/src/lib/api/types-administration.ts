//  Ce que le serveur RENVOIE au client de l'ADMINISTRATION (`administration.ts`),
//  route par route (#1572).
//
//  Ces types sont LUS dans le code serveur — `routers/admin/*`, `routers/config.py`,
//  `routers/delegations.py` et les utilitaires qu'ils appellent —, jamais supposés.
//  Le client rendait `any` quarante et une fois, et chaque écran croyait recevoir
//  ce qu'il lisait.
//
//  ⚠️ Dans un fichier à part, et non en tête du client comme pour `communaute.ts` :
//  `administration.ts` en portait déjà 455 lignes, et la modularité est de rang 1.
//  Le client les RÉEXPORTE (`export type * from`) : `index.ts`, et donc chaque
//  `from '#lib/api/index.ts'`, les voient sans qu'on y touche.
//
//  ⚠️ Plusieurs routes n'ont pas de `response_model` : elles rendent un dict
//  composé à la main, ou la LIGNE de la table telle quelle (`model_dump`). Les
//  dates arrivent en chaîne ISO sans fuseau (UTC naïf, comme la base).
import type { User } from './types';
import type { CommandeAcces } from './acces';

/**  Un « OK » sans autre contenu — les écritures de l'annuaire, d'un message
 *   WhatsApp planifié. */
export interface Accuse {
	ok: true;
}

//  ── Annuaire du conseil et du syndic (`routers/admin/annuaire.py`) ─────────────

/**  Un membre du conseil, tel que l'ADMINISTRATION le lit
 *   (`utils/annuaire.membres_du_conseil(pour_administration=True)`). */
export interface MembreConseilAdmin {
	id: number;
	genre: string;
	prenom: string;
	nom: string;
	batiment_id: number | null;
	/** Le NUMÉRO du bâtiment (« A »), pas son libellé (« Bât. A »). */
	batiment_nom: string | null;
	etage: number | null;
	est_gestionnaire_site: boolean;
	est_president: boolean;
	photo_url: string | null;
	ordre: number;
	user_id: number | null;
}

/**  `GET /admin/annuaire/cs`. */
export interface CompositionConseil {
	ag_annee: number | null;
	/** ISO « AAAA-MM-JJ », ou `null`. */
	ag_date: string | null;
	/** `""` quand aucun lien n'est posé — jamais `null` ici. */
	whatsapp_url: string;
	membres: MembreConseilAdmin[];
}

/**  Un interlocuteur du syndic, tel que l'ADMINISTRATION le lit
 *   (`utils/annuaire.membres_du_syndic(pour_administration=True)`). */
export interface MembreSyndicAdmin {
	id: number;
	genre: string;
	prenom: string;
	nom: string;
	fonction: string | null;
	email: string | null;
	/** Plusieurs numéros séparés par des virgules, s'il y en a. */
	telephone: string | null;
	est_principal: boolean;
	photo_url: string | null;
	ordre: number;
	user_id: number | null;
}

/**  `GET /admin/annuaire/syndic`. Le nom vient du CONTRAT quand il y en a un
 *   (#535) : `nom_syndic_source` dit si la saisie sert encore. */
export interface InfoSyndicAdmin {
	nom_syndic: string;
	nom_syndic_source: 'contrat' | 'saisie' | 'aucune';
	adresse: string;
	site_web: string | null;
	membres: MembreSyndicAdmin[];
}

//  ── Délégations d'aidant (`routers/delegations.py`, `_to_read`) ────────────────

export type StatutDelegation = 'en_attente' | 'active' | 'revoquee' | 'expiree';

export interface Delegation {
	id: number;
	mandant_id: number;
	/** « ? » quand le compte n'existe plus. */
	mandant_nom: string;
	aidant_id: number;
	aidant_nom: string;
	statut: StatutDelegation;
	motif: string;
	date_debut: string | null;
	/** `null` = sans limite. */
	date_fin: string | null;
	cree_le: string | null;
	revoque_le: string | null;
}

//  ── Comptes (`routers/admin/comptes.py`, `routers/admin/utilisateurs.py`) ──────

/**  Ce que l'appariement automatique a trouvé
 *   (`utils/auto_match_service.auto_match_pour_utilisateur`). */
export interface ResultatAutoMatch {
	lots: number;
	lots_resolus: number;
	tc: number;
	vigik: number;
	baux: number;
	rattache: number;
	/** Lots où un locataire sans bailleur inscrit est rattaché d'office, par le fichier des lots (#2267). */
	lots_d_office: number;
	/** Badges remis à un locataire déjà lié à ses lots, qui ne les avait pas en main (#2267). */
	badges_remis: number;
	annuaire_cs: number;
	annuaire_syndic: number;
	total: number;
}

/**  L'aidé retrouvé (ou non) à la validation d'un compte d'aidant ou de
 *   mandataire — `aide_result` dans `traiter_compte`. */
export interface AppariementAide {
	aide_trouve: boolean;
	/** Présent seulement quand l'aidé est trouvé. */
	aide_nom?: string;
	lots: number;
	tc: number;
	vigik: number;
	delegation: boolean;
}

/**  `POST /admin/comptes/{id}/traiter` (`CompteTraiteResult`).
 *
 *   ⚠️ `auto_match` est VIDE sur un refus : l'appariement ne tourne qu'à la
 *   validation — d'où `Partial`. */
export interface CompteTraite {
	user: User;
	auto_match: Partial<ResultatAutoMatch> & { aide_match?: AppariementAide };
}

/**  `POST /admin/utilisateurs/{id}/auto-match`. */
export interface AutoMatchRelance {
	ok: true;
	auto_match: ResultatAutoMatch;
}

/**  `GET /admin/comptes-en-attente/enrichis` (`CompteEnAttenteItem`). */
export interface CompteEnAttenteEnrichi {
	user: User;
	/** Lots trouvés au nom du compte dans l'import — `0` = absent du fichier Lots. */
	lots_prevus: number;
}

/**  L'état d'une étiquette de compte (`utils/etiquettes_compte.etat`). */
export type EtatEtiquette = 'ok' | 'manque' | 'sans_objet';

/**  Une ligne de `GET /admin/utilisateurs` : le compte, plus ses liens.
 *
 *   ⚠️ `UserRead` porte aussi `nom_proprietaire`, `nom_aide`, `prenom_aide` et
 *   `email_verifie`, que `User` (`types.ts`) ne déclare pas encore : ils sont
 *   déclarés ici, où l'administration les lit. */
export interface UtilisateurAdmin extends User {
	email_verifie?: boolean;
	nom_proprietaire?: string | null;
	nom_aide?: string | null;
	prenom_aide?: string | null;
	has_lots: boolean;
	has_tc: boolean;
	has_vigik: boolean;
	has_bail: boolean;
	etiquettes: Record<'loti' | 'tc' | 'vigik' | 'bail', EtatEtiquette>;
}

/**  `POST /admin/utilisateurs/{id}/accueil-arrivant`. */
export interface AccueilArrivantResultat {
	ok: true;
	notifications_envoyees: number;
	email_syndic: boolean;
	/** Le NUMÉRO du ticket de suivi, `null` s'il existait déjà. */
	ticket_suivi: string | null;
	annonce_publiee: boolean;
	consignes_transmises: boolean;
}

//  ── Demandes à traiter (`routers/admin/acces.py`, `profils.py`) ─────────────────

/**  Une commande de badge en attente : la LIGNE `commande_acces`, plus ce qui la
 *   rend lisible (#1679) — l'espace CS et l'onglet « À traiter » la lisent ici.
 *   La ligne elle-même est `CommandeAcces` (`./acces`) : déclarée UNE fois. */
export interface CommandeAccesEnAttente extends CommandeAcces {
	statut: 'en_attente' | 'acceptee' | 'refusee';
	traite_par_id: number | null;
	motif_refus: string | null;
	cree_le: string;
	traite_le: string | null;
	/** « ? » quand le compte ou le lot a disparu — vaut pour le suivant. */
	demandeur_nom: string;
	/** « Parking 12 ». */
	lot: string;
	/** « Bât. 4 », `null` pour un lot sans bâtiment. */
	batiment: string | null;
}

/**  Une demande de modification de profil en attente : la ligne
 *   `demande_modification_profil`, plus ce qui la rend lisible. */
export interface DemandeProfil {
	id: number;
	utilisateur_id: number;
	statut_souhaite: string | null;
	batiment_id_souhaite: number | null;
	motif: string | null;
	statut_demande: 'en_attente' | 'approuvee' | 'rejetee';
	motif_refus: string | null;
	traite_par_id: number | null;
	cree_le: string;
	traite_le: string | null;
	/** « ? » quand le compte n'existe plus. */
	utilisateur_nom: string;
	utilisateur_email: string | null;
	statut_actuel: string | null;
	batiment_actuel: string | null;
	batiment_nom_souhaite: string | null;
}

//  ── Relevés d'audit (`routers/admin/acces.py`) ──────────────────────────────────

/**  `GET /admin/audit/user-lots` — un lien actif compte ↔ lot. */
export interface LienCompteLot {
	user_lot_id: number;
	user_id: number;
	/** « ? » quand le compte ou le lot a disparu — vaut pour les trois suivants. */
	user_nom: string;
	user_statut: string;
	lot_id: number;
	lot_numero: string;
	lot_type: string;
	/** Le libellé du bâtiment, « — » s'il n'y en a pas. */
	batiment: string;
	type_lien: string;
}

/**  `GET /admin/audit/baux-sans-locataire` (#808). La CATÉGORIE est tranchée par
 *   le serveur, jamais par l'écran. */
export interface BailSansLocataire {
	bail_id: number;
	lot: string;
	batiment: string;
	/** « — » quand le bail ne nomme personne. */
	locataire_nom: string;
	locataire_email: string | null;
	date_entree: string;
	categorie: 'compte_probable' | 'sans_compte';
	/** Les comptes actifs du même NOM — vide pour `sans_compte`. */
	candidats: { id: number; nom: string; email: string }[];
}

/**  Une catégorie de ticket proposée par `utils/reclassement_tickets.proposer`. */
export interface PropositionReclassement {
	ticket_id: number;
	numero: string;
	titre: string;
	statut: string;
	actuelle: string;
	actuelle_libelle: string;
	proposee: string;
	proposee_libelle: string;
	confiance: 'haute' | 'moyenne';
	/** Le mot qui a déclenché la règle. */
	indice: string;
}

/**  `GET /admin/audit/reclassement-tickets` — une PROPOSITION, rien n'est écrit. */
export interface ReleveReclassement {
	total_tickets: number;
	propositions: PropositionReclassement[];
	/** Le compte par catégorie proposée. */
	par_categorie: Record<string, number>;
}

//  ── Sauvegardes et modèles d'e-mail (`exploitation.py`, `communications.py`) ───

/**  La configuration des sauvegardes — la LIGNE `config_sauvegarde`. */
export interface ConfigSauvegarde {
	id: number;
	/** 0 à 23. */
	heure_execution: number;
	nb_versions_conservees: number;
	modifie_par_id: number | null;
	modifie_le: string | null;
}

/**  Un modèle d'e-mail — la LIGNE `modele_email`.
 *
 *   ⚠️ `variables_disponibles` est du JSON en TEXTE (`'["destinataire"]'`). La
 *   liste les CALCULE (`_variables_du_modele`) ; la modification et la remise à
 *   zéro rendent la colonne stockée, qui peut être périmée. */
export interface ModeleEmail {
	id: number;
	code: string;
	libelle: string;
	sujet: string;
	corps_html: string;
	variables_disponibles: string;
	/** `information` | `action_requise` | `reponse_attendue` | `archive`, ou `""`. */
	intention: string;
	desactivable: boolean;
	actif: boolean;
	modifie_par_id: number | null;
	modifie_le: string | null;
}

/**  Un envoi d'e-mail journalisé — la LIGNE `historique_email`. */
export interface EnvoiEmail {
	id: number;
	code: string;
	destinataire: string;
	sujet: string;
	/** `succes` | `erreur` | `ignore`. */
	statut: string;
	erreur: string | null;
	cree_le: string;
}

//  ── Tâches planifiées (`routers/admin/exploitation.py`, `utils/sante_taches`) ───

/**  Ce que `_sante_par_noeud` conclut d'une exécution — huit états (#488, #2072). */
export type StatutSanteTache =
	| 'ok'
	| 'en_cours'
	| 'pas_actif'
	| 'vigilance'
	| 'erreur'
	| 'rapport_perdu'
	| 'manquante'
	| 'aucune_execution';

export type PorteeExecution = 'applicative' | 'hygiene_locale';

/**  L'état d'une tâche sur UN nœud. */
export interface SanteTacheNoeud {
	noeud: string;
	statut: StatutSanteTache;
	portee: PorteeExecution;
	derniere: string;
	retard_heures: number;
}

/**  Une ligne de la santé des tâches (`_entree_sante`).
 *
 *   ⚠️ Sans aucune exécution, `portee` est ABSENTE et `derniere` vaut `null`. */
export interface SanteTache {
	tache: string;
	noeud: string | null;
	noeuds: SanteTacheNoeud[];
	noeud_enregistre: boolean;
	portee?: PorteeExecution;
	statut: StatutSanteTache;
	derniere: string | null;
	retard_heures: number | null;
	periodicite_heures: number;
	/** Nommé seulement s'il est PLUS grave que la dernière exécution. */
	noeud_en_retard: string | null;
	statut_en_retard: StatutSanteTache | null;
}

/**  `GET /admin/maintenance/sante`. */
export interface SanteMaintenance {
	taches: SanteTache[];
	anomalies_recentes: {
		tache: string;
		noeud: string | null;
		cree_le: string;
		erreur: string | null;
	}[];
	/** La fenêtre de « récemment », en jours : seuls les échecs de cette fenêtre
	 *  sont rendus (`FENETRE_ANOMALIES_J`, `sante_taches.py`). */
	anomalies_fenetre_jours: number;
	genere_le: string;
}

/**  Une exécution de `historique_maintenance` (`GET /admin/maintenance/historique`) :
 *   toutes les tâches sauf la sauvegarde et l'agrégation. `details` arrive
 *   DÉSÉRIALISÉ — `null` s'il est illisible —, et sa forme dépend de la tâche
 *   (`RapportFiabilite` dans `administration.ts` en est une). */
export interface ExecutionMaintenance {
	id: number;
	tache: string;
	noeud: string | null;
	portee: PorteeExecution;
	/** `cron` | `manuel`. */
	declenchee_par: string;
	/** `succes` | `erreur` | `avertissement` | `en_cours`. */
	statut: string;
	tokens_supprimes: number;
	taille_db_octets: number | null;
	duree_secondes: number | null;
	details: Record<string, unknown> | null;
	erreur: string | null;
	cree_le: string;
	terminee_le: string | null;
}

/**  Une exécution de sauvegarde — la LIGNE `historique_sauvegarde`. */
export interface ExecutionSauvegarde {
	id: number;
	/** `automatique` | `manuelle`. */
	declenchee_par: string;
	declenchee_par_user_id: number | null;
	statut: 'en_cours' | 'reussie' | 'echouee';
	noeud: string | null;
	fichier_nom: string | null;
	fichier_chemin: string | null;
	taille_octets: number | null;
	message_erreur: string | null;
	cree_le: string;
	terminee_le: string | null;
}

/**  Une agrégation de télémétrie — la LIGNE `historique_telemetrie`. */
export interface ExecutionTelemetrie {
	id: number;
	/** `cron` | `manuelle`. */
	declenchee_par: string;
	noeud: string | null;
	/** `en_cours` | `succes` | `erreur`. */
	statut: string;
	jours_agreges: number;
	mois_agreges: number;
	events_purges: number;
	daily_purges: number;
	monthly_purges: number;
	duree_secondes: number | null;
	erreur: string | null;
	cree_le: string;
	terminee_le: string | null;
}

/**  L'historique d'une tâche (`admin.historiqueTache`) : trois tables, trois
 *   formes. Une UNION, et non un type unique : la sauvegarde n'a pas de
 *   `details`, la maintenance n'a pas de `taille_octets`. */
export type ExecutionTache = ExecutionMaintenance | ExecutionSauvegarde | ExecutionTelemetrie;

/**  Un lancement manuel accepté (202, `utils/declenchement.tracer_lancement_manuel`) :
 *   la PRISE EN COMPTE, pas l'exécution. */
export interface LancementTache {
	message: string;
	/** L'entrée d'historique créée, que la tâche remplira. */
	id: number;
}

//  ── Bancs d'essai de la configuration (`routers/config.py`) ─────────────────────

/**  `POST /config/smtp-test` — un 4xx/5xx sinon. */
export interface EssaiSmtp {
	ok: true;
	message: string;
}

/**  `POST /config/imap-test` — rien n'est lu ni traité. */
export interface EssaiImap {
	ok: true;
	non_lus: number;
	dossier: string;
	/** La relève est-elle allumée ? */
	actif: boolean;
	message: string;
}

/**  `GET /config/whatsapp-status` : la réponse du bridge, relayée telle quelle
 *   (`whatsapp-bridge/index.js`, `GET /status`). */
export interface StatutWhatsApp {
	/** `disconnected` | `connecting` | `waiting_qr` | `open`. */
	state: string;
	hasQR: boolean;
	/** ISO, `null` quand la connexion est ouverte. */
	hors_ligne_depuis: string | null;
	dernier_code: number | null;
}

/**  `POST /config/whatsapp-test` — un 5xx sinon. `detail` est la réponse brute
 *   du bridge. */
export interface EssaiWhatsApp {
	ok: true;
	message: string;
	detail: Record<string, unknown>;
}
