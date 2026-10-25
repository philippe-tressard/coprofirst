//  Formes de données échangées avec l'API. Rassemblées ici depuis trois
//  endroits différents de l'ancien `api.ts`, où elles étaient intercalées
//  entre les clients — donc introuvables autrement qu'au grep.
export interface User {
	id: number;
	nom: string;
	prenom: string;
	email: string;
	telephone?: string | null;
	societe?: string | null;
	fonction?: string | null;
	statut: string;
	role: string;
	roles: string[]; // multi-rôles cumulables
	actif: boolean;
	opt_out_telemetrie?: boolean;
	// Modération de la Communauté. Ces champs étaient absents de l'interface
	// alors que `UserRead` les renvoie et que la page Sondages s'en sert pour
	// bloquer un membre suspendu : le contrôle fonctionnait, mais TypeScript ne
	// pouvait pas le vérifier — une faute de frappe sur le nom du champ serait
	// passée inaperçue et aurait rouvert l'accès à un membre banni.
	communaute_interdit?: boolean;
	communaute_ban_count?: number;
	communaute_ban_jusqu_au?: string | null;
	/**
	 * Le MOTIF du refus d'accès à la Communauté, ou `null` si l'accès est ouvert.
	 *
	 * Calculé par l'API (`app/utils/communaute.py`), qui est la seule à porter la
	 * règle. Le front l'AFFICHE, il ne le recalcule pas : il en portait sa propre
	 * copie dans `sondages/+page.svelte`, avec un libellé encore différent de
	 * celui de l'API et de celui de l'administration (29/08/2026).
	 */
	communaute_motif_refus?: string | null;
	onboarding_complete: boolean;
	onboarding_etape: number;
	photo_url?: string;
	preferences_notifications: string;
	/** Préférence d'AFFICHAGE, jamais un droit : n'afficher que ses bâtiments (#339). */
	restreindre_a_mes_batiments?: boolean;
	demarche_arrivant?: string | null;
	batiment_id?: number | null;
	batiment_nom?: string | null; // "Bât. A"
	/** Pour un locataire : le nom de son propriétaire, s'il l'a donné (`UserRead`). */
	nom_proprietaire?: string | null;
	/** Pour un aidant ou mandataire : le copropriétaire aidé, saisi à l'inscription (`UserRead`). */
	nom_aide?: string | null;
	prenom_aide?: string | null;
	/** L'étage où la personne HABITE — distinct de `Lot.etage`, qui décrit un bien. */
	etage?: number | null;
	last_seen_actualites?: string | null;
	delegations_aidant?: { delegation_id: number; mandant_id: number; mandant_nom: string }[];
	cree_le: string;
	derniere_connexion?: string | null;
	/** L'avertissement avant purge pour inactivité (#1580) ; la reconnexion l'efface. */
	purge_avertie_le?: string | null;
}

/**
 * **« Saisi pour »**, tel qu'un écran le REÇOIT — les trois champs, plus le nom
 * déjà composé par le serveur.
 *
 * ⚠️ `saisi_pour_affichage` n'est pas une redite : il vaut `null` quand personne
 * n'est nommé, là où le propriétaire retombe sur l'auteur. C'est lui qui décide
 * si l'écran affiche « Saisi pour X », et le recomposer côté client demanderait
 * de relire la règle des trois cas dans chaque écran.
 *
 * 🔴 Hérité plutôt que recopié (15/09/2026) : la notion sert aux tickets, aux
 * actualités et aux événements. Trois interfaces portant les mêmes quatre
 * lignes auraient divergé au premier ajout — c'est ce qui vient d'arriver au
 * périmètre d'un badge, calculé à deux endroits.
 *
 * Pendants : `PorteSaisiPour` (`$lib/saisi-pour`, ce qu'on ENVOIE) et
 * `SaisiPourSortie` (`api/app/utils/saisi_pour.py`).
 */
export interface PorteSaisiPourLu {
	saisi_pour_user_id?: number | null;
	saisi_pour_nom?: string | null;
	saisi_pour_email?: string | null;
	saisi_pour_affichage?: string | null;
}

//  Les affaires liées et les candidates d'une fusion vivent dans leur module
//  (#2173) ; ré-exportées ici pour les écrans qui les lisent dans `types`.
import type { AffaireLiee } from './affaires-liees';
export type { AffaireLiee, CandidateFusion } from './affaires-liees';

/**  Un transfert de courriel versé dans une affaire (#1482), tel que le voit qui
 *   peut le défaire — celui qui a transféré, ou l'administrateur. */
export interface TransfertVerse {
	id: number;
	cree_le: string;
	transfere_par_nom: string;
	/** Les Suites qu'il a écrites dans l'affaire. */
	suites: number;
	/** Il a créé l'affaire : l'annuler l'archive. */
	affaire_creee: boolean;
	/** Pourquoi il ne se défait plus — absent s'il se défait. */
	bloque?: string | null;
	/** Réaffecter ou détacher : il faut aussi modérer. */
	peut_deplacer: boolean;
}

/** L'affaire où un transfert est désormais — l'écran y conduit. */
export interface AffaireVisee {
	ticket_id: number;
	numero: string;
}

/**  Une affaire trouvée par la recherche libre (27/09/2026) : OÙ le texte a été
 *   trouvé, et le passage découpé en segments — jamais du HTML, donc rien à
 *   assainir. Rendu par `GET /tickets/recherche`, dans l'ordre de pertinence. */
export interface CorrespondanceAffaire {
	ticket_id: number;
	ou:
		| 'numero'
		| 'titre'
		| 'categorie'
		| 'lieu'
		| 'personne'
		| 'prestataire'
		| 'equipement'
		| 'description'
		| 'suite'
		| 'message'
		| 'piece_jointe';
	extrait: { texte: string; surligne: boolean }[];
	date?: string | null;
	auteur?: string | null;
}

export interface Ticket extends PorteSaisiPourLu {
	id: number;
	/** « Me concerne » pour qui lit, par la règle de l'accès (#2215) ; `null` sans lecteur. */
	me_concerne?: boolean | null;
	/** « Rédigé avec l'assistant IA » (#985). */
	assiste_ia?: boolean;
	numero: string;
	titre: string;
	description: string;
	categorie: string;
	statut: string;
	priorite: string;
	/** Vide quand le compte de l'auteur a été supprimé : « Ancien résident » (#1688). */
	auteur_id: number | null;
	auteur_nom?: string | null;
	auteur_batiment_nom?: string | null;
	lot_id?: number;
	batiment_id?: number;
	perimetre_cible?: string[];
	photos_urls?: string[];
	/** Documents joints (PDF, bureautique) — les images restent dans photos_urls. */
	fichiers_urls?: string[];
	destinataire_syndic?: boolean;
	destinataire_cs?: boolean;
	/**  À QUI le ticket appartient : le « Saisi pour » s'il existe, l'auteur
	 *   sinon. C'est ce nom que le fil affiche et que la case « Envoyer une
	 *   copie à … » annonce — le même, parce que c'est la même personne qui
	 *   recevra le courriel (12/09/2026). */
	proprietaire_nom?: string | null;
	relance_count?: number;
	cree_le: string;
	mis_a_jour_le: string;
	/**  Ce que la carte repliée montre en vignette : les pièces du ticket, ou
	     celles de l'entrée d'Historique la plus récente qui en porte. Calculé par
	     le serveur (#464) — le front ne rejoue pas la règle. */
	apercu_pieces?: string[];
	/**  Les affaires liées, dans les deux sens — celles que le lecteur peut lire (#1342). */
	affaires_liees?: AffaireLiee[];
	/**  🔀 L'affaire qui l'a absorbée à sa clôture (#1704) — si le lecteur la lit. */
	fusionnee_dans?: AffaireLiee | null;
	/**  …et le fait, pour tous : son suivi est clos, plus de Suite (`refuser_si_absorbee`). */
	fusionnee?: boolean;
	/**  Le ticket a-t-il quitté la liste active pour les Archives ? Calculé par la
	     règle du SITE (`app/utils/archivage.py`, #515) : 30 jours après « Résolu »,
	     immédiat sur « Annulé », le délai étant réglable en administration.

	     🔴 L'écran appliquait sa propre règle — 7 jours, en dur, sur
	     `mis_a_jour_le` — pendant que le site en annonçait 30. Le front ne la rejoue
	     plus : deux règles pour la même notion trancheraient différemment, et un
	     ticket apparaîtrait dans la liste sans être dans les Archives. */
	archivee?: boolean;
	/**  ✨ Une synthèse VALIDÉE l'accompagne (#1643) — la pastille de la carte repliée.
	     Calculé par le serveur (`lecture_groupee.syntheses_validees`). */
	synthese_validee?: boolean;
	/** 🔒 Réservé à l'auteur, à la personne concernée et au conseil syndical.
	     Le contrepoids de l'ouverture en lecture par périmètre (#710).

	     ⚠️ Ce n'est PAS le 🔒 d'une actualité, qui restreint au périmètre visé :
	     celui-là s'appelle `reserve_perimetre`. Celui-ci referme sans regarder le
	     périmètre — sinon il ne mordrait pas sur un ticket à portée
	     « résidence », le cas le plus fréquent. */
	confidentiel?: boolean;
	/**  À QUI l'on parle — une actualité (#1091). Absent = tout le monde ;
	 *   « Conseil syndical » SEUL la réserve au conseil : rien ne sort (#1096). */
	public_cible?: string[] | null;
	/**  🔒 L'Accès d'une actualité : lisible du seul périmètre visé. */
	reserve_perimetre?: boolean;
	/**  Archivée par une personne, et non par le temps (#1091). */
	archive_manuel?: boolean;
	/**  Les filtres de la vue Affaires où elle paraît — `actualite`, `calendrier`,
	 *   `activite` (#1092). DÉRIVÉS par le serveur : l'écran ne redérive rien. */
	natures?: string[];
	/**  ⚠️ DÉRIVÉE par le serveur, en LECTURE SEULE — ne jamais l'envoyer.
	 *   La date où une actualité cesse d'être utile (`fin`, sinon `debut`,
	 *   sinon jamais) — `null` pour une affaire suivie, qui se clôt (#1093). */
	perime_le?: string | null;
	/**  Section « Intervenant » et récurrence d'un Entretien (#1092, lot 5).
	 *   `prestataire_nom` est dérivé par le serveur, en lecture seule. */
	prestataire_id?: number | null;
	prestataire_nom?: string | null;
	/**  Le cadre de l'intervention (#1445) : le contrat, `null` hors contrat.
	 *   `contrat` est DÉRIVÉ par le serveur — le rythme pour tous, le libellé
	 *   et le numéro pour le conseil seul. */
	contrat_id?: number | null;
	contrat?: {
		id: number;
		libelle?: string | null;
		numero_contrat?: string | null;
		frequence_type?: string | null;
		frequence_valeur?: number | null;
	} | null;
	/**  La valeur de `TypeEquipement`, posée par le conseil (#1097). */
	equipement?: string | null;
	frequence_type?: string | null;
	frequence_valeur?: number | null;
	/**  Section « Quand » (#1092), en ISO — quand ça se passe. C'est ce qui
	 *   fait paraître l'objet au calendrier, devenu une vue et non plus un
	 *   objet. */
	debut?: string | null;
	fin?: string | null;
	/**  📌 Épinglé — maintenu en tête de la liste (05/09/2026).
	 *
	 *   ⚠️ Il n'y a pas de champ `urgente` en face : l'urgence d'un ticket EST sa
	 *   `priorite`, que la catégorie « Urgence » met à `haute`. La case 🚨 de
	 *   l'écran pilote celle-là — voir `optionsDuTicket()`. */
	epingle?: boolean;
	/**  Le ticket paraît-il au KANBAN ? Coché d'office pour « Étude & travaux »,
	 *   décochable par le conseil (#833).
	 *
	 *   ⚠️ Elle dit SI, jamais OÙ : la colonne se déduit du `statut`. Un second
	 *   champ d'état créerait deux notions de suivi sur le même objet.
	 *   Correspondance : `colonneDuTicket()` dans `$lib/kanban`. */
	suivi_kanban?: boolean;
	/**  Le suivi d'une ACTUALITÉ (10/10/2026) : `null` sans suivi, sinon « ouvert »,
	 *   « résolu » ou « annulé » — un repère, `statut` restant « publie »
	 *   (`$lib/suivi-actualite`). */
	suivi_actualite?: string | null;
	/**  Conservée (#2014) : le jour où, échue, l'affaire a perdu ses pièces jointes —
	 *   archivées hors ligne — et ses auteurs. `null` : intacte. */
	conservee_le?: string | null;
}

/** Une réponse du syndic à une relance GROUPÉE — jamais ventilée dans les fils.
 *
 *  ⚠️ `tickets` liste ce que la RELANCE contenait, pas ce que la réponse
 *  mentionne : aucune machine ne sait à quel dossier chaque phrase se rapporte,
 *  et c'est précisément pourquoi on ne la ventile pas. C'est un contexte de
 *  lecture, jamais un rattachement. */
export interface ReponseRelance {
	id: number;
	expediteur: string;
	contenu: string;
	recue_le: string;
	relance_le: string | null;
	tickets: string[];
}

/** Message d'un fil de ticket. Vit ici, pas dans la page : le client TypeScript
 *  est la source unique des types d'API (cf. CLAUDE.md, checklist backend). */
export interface TicketMessage {
	id: number;
	contenu: string;
	interne: boolean;
	auteur: { id: number; prenom: string; nom: string; role: string };
	cree_le: string;
	fichiers_urls?: string[];
}

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
}

/**  La CORRECTION d'une Suite (`PATCH`) — toutes ses sections sauf la Diffusion
 *   (01/10/2026). Composée par `chargeCorrection` (`$lib/evolutions`), seule
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

/**  Un canal de diffusion, tel qu'il partira — ou pourquoi il ne partira pas (#498).
 *
 *   ⚠️ `inactif_motif` est ce qui distingue cet aperçu d'une maquette : bridge
 *   éteint, aucun destinataire joignable, droit manquant. L'écran doit le dire
 *   AVANT l'envoi plutôt que laisser croire à une diffusion qui n'aura pas lieu. */
export interface ApercuCanal {
	canal: 'email' | 'whatsapp';
	actif: boolean;
	inactif_motif?: string | null;
	destinataires: string[];
	/** Ceux que le canal visait et qui ne recevront rien, avec le motif (#2006). */
	ecartes: { qui: string; motif: string }[];
	sujet?: string | null;
	corps_html?: string | null;
	texte?: string | null;
	/** Le message WhatsApp est réduit à « avertissement + périmètre + lien ». */
	ampute: boolean;
	avec_photo: boolean;
}

export interface ApercuDiffusion {
	canaux: ApercuCanal[];
	/** Champs qui n'existeront qu'après la création — nommés, jamais inventés. */
	attribues_a_la_creation: string[];
}

/**  Un élément du fil qu'une affiche de hall peut reprendre.
 *
 *   `cle` — et non `id` — parce que trois familles peuvent porter le même
 *   numéro : c'est le couple type + id qui désigne. */
export interface SourceAffiche {
	cle: string;
	type: string;
	famille: string;
	id: number;
	titre: string;
	date: string;
	epingle: boolean;
}

export interface Notification {
	id: number;
	type: string;
	titre: string;
	corps: string;
	lien?: string;
	lue: boolean;
	urgente: boolean;
	cree_le: string;
}

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
}
export interface FluxResponse {
	items: FluxItem[];
	sante: FluxSante;
	/**  Le délai d'archivage du site, en jours : le seuil « récent » de l'accueil (#2060). */
	delai_recent_jours: number;
}
export interface EpinglesCompte {
	total: number;
	publications: number;
	evenements: number;
}

export interface AnnonceHall {
	id: number;
	titre: string;
	message: string;
	/** « Rédigé avec l'assistant IA » (#1089). */
	assiste_ia?: boolean;
	apercu: string;
	perimetre_cible: string[];
	perimetre_label: string;
	format_demande: string;
	format_effectif: string;
	format_label: string;
	images: string[];
	pdf_nom: string;
	taille_octets: number | null;
	destinataires: string[];
	envoye_le: string | null;
	/**  État EFFECTIF : archivée à la main, **ou** par la règle du site — 30 jours
	     après l'envoi (#515). C'est ce que les deux listes emploient. */
	archivee: boolean;
	/**  La décision HUMAINE seule. « Restaurer » n'a d'effet que sur elle : sur
	     une affiche archivée par le TEMPS, retirer le drapeau manuel ne la
	     ramènerait pas, et l'écran ne propose donc pas le geste. */
	archivee_manuellement?: boolean;
	/**  L'actualité reprise, s'il y en a une — c'est ce qui donne son lien au
	 *   message WhatsApp de l'affiche. `publication_id` avant le 23/09/2026. */
	ticket_id: number | null;
	cree_le: string;
	auteur_nom: string;
}

export interface AnnonceHallInput {
	titre: string;
	message: string;
	assiste_ia?: boolean;
	perimetre_cible: string[];
	format_demande: string;
	images?: string[];
	//  Les TROIS canaux de la Diffusion (#480). Ils étaient absents : l'écran ne
	//  portait qu'une case, et le serveur ne consommait qu'un canal sur trois.
	envoyer_cs?: boolean;
	envoyer_syndic?: boolean;
	partager_whatsapp?: boolean;
	envoyer_auteur?: boolean;
}

/** Champs d'une actualité, prêts à alimenter le formulaire d'annonce de hall. */
export interface AnnonceHallPrefill {
	titre: string;
	message: string;
	perimetre_cible: string[];
	images: string[];
}

/**  Le miroir : une actualité pré-remplie DEPUIS une annonce de hall (#832).
 *
 *   ⚠️ Les noms de champs sont ceux de l'AFFAIRE (`description`,
 *   `photos_urls`), pas ceux de l'affiche (`message`, `images`) : c'est le
 *   formulaire d'actualité qui les consomme, et un renommage au point de
 *   collage se paierait à chaque lecture.
 */
export interface ActualitePrefill {
	titre: string;
	description: string;
	perimetre_cible: string[];
	photos_urls: string[];
}
