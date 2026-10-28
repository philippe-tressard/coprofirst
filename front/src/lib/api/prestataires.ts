//  Les PRESTATAIRES : fiches, contrats d'entretien, relevés de compteurs et
//  notations.
//
//  ⚠️ Les huit méthodes « devis » sont parties avec la prestation ponctuelle
//  (#603). `ApiError` et `BASE` les ont suivies : ils ne servaient qu'à
//  `deleteDevisFichier`, seul appel de ce fichier à ne pas passer par `api`.
//
//  ⚠️ Fragment de `lib/api/` — extrait de `index.ts` le 27/08/2026 (#453). Ce
//  fichier portait VINGT ET UN domaines et 437 lignes ; `client.ts`, `types.ts`,
//  `documents.ts` et `communaute.ts` en étaient déjà sortis en leur temps, la
//  coupe suit donc une couture existante et non le compteur de lignes.
//
//  ⚠️ La surface publique NE BOUGE PAS : `index.ts` réexporte tout, et les
//  quarante et un `from '#lib/api/index.ts'` du front ne changent pas d'une ligne.
import { api, postFormData } from './client';
import type { ExerciceLu, ResumeAffaires } from './synthese';

/**  Les affaires closes d'un prestataire (#1646) — `routers/prestataires_metriques`.
 *   L'ensemble, puis chaque exercice comptable, le plus récent d'abord. */
export interface MetriquesPrestataire {
	prestataire_id: number;
	ensemble: ResumeAffaires;
	exercices: (ResumeAffaires & ExerciceLu)[];
}

//  ── Ce que le serveur RENVOIE (#1572) ───────────────────────────────────────────
//
//  Lus dans `routers/prestataires.py`, `prestataires_schemas.py` et `compteurs.py`,
//  route par route — jamais supposés (même motif que `communaute.ts`). Les dates
//  arrivent en chaîne ISO (`AAAA-MM-JJ` pour une `date`, sans fuseau pour un instant).

/**  Une personne à joindre chez un prestataire — `PrestataireContact`. */
export interface ContactPrestataire {
	telephone: string | null;
	prenom: string | null;
	nom: string | null;
	fonction: string | null;
	email: string | null;
}

/**  Un prestataire — `PrestataireRead`, que rendent la liste, les archives, la
 *   création et la correction. */
export interface Prestataire {
	id: number;
	nom: string;
	/** La VALEUR d'un `TypeEquipement` — l'écran en rend le libellé. */
	specialite: string;
	/** La valeur de `TypePrestataire` (`maintenance_depannage`, `travaux`…). */
	type_prestataire: string;
	telephone: string | null;
	email: string | null;
	contacts: ContactPrestataire[];
	adresse: string | null;
	/** Texte riche (HTML). */
	description: string | null;
	actif: boolean;
	/** Calculé par la règle d'archivage (`REGLES["prestataire"]`, #1538). */
	archivee: boolean;
	assiste_ia: boolean;
}

/**  Un contrat d'entretien — `ContratRead` (`routers/prestataires.py`). */
export interface ContratEntretien {
	id: number;
	copropriete_id: number;
	/** Le périmètre couvert, en codes de l'arbre — `null` si absent ou illisible. */
	perimetre_cible: string[] | null;
	/** DÉRIVÉ du périmètre, gardé pour les lectures qui s'y appuient encore. */
	batiment_id: number | null;
	prestataire_id: number;
	/** La valeur de `TypeEquipement`. */
	type_equipement: string;
	libelle: string;
	numero_contrat: string | null;
	date_debut: string;
	duree_initiale_valeur: number | null;
	/** `mois` ou `ans`. */
	duree_initiale_unite: string | null;
	/** `semaines`, `mois` ou `fois_par_an`. */
	frequence_type: string | null;
	frequence_valeur: number | null;
	prochaine_visite: string | null;
	actif: boolean;
	/** Calculé par `REGLES["contrat"]` (#1538). */
	archivee: boolean;
	notes: string | null;
	document_id: number | null;
	/** L'échéance DÉDUITE (`utils/echeance_contrat.py`), jamais stockée. */
	date_fin: string | null;
	reconduit: boolean;
	/** Terme passé sans reconduction. */
	echu: boolean;
	/** Le geste ✨ est-il proposable ? Le SERVEUR répond, pas l'écran. */
	synthese_disponible: boolean;
}

/**  Un relevé de compteur — `ReleveRead` (`routers/compteurs.py`). */
export interface ReleveCompteur {
	id: number;
	type_compteur: string;
	date_releve: string;
	index: number | null;
	note: string | null;
	photo_url: string | null;
	prestataire_id: number | null;
	cree_le: string;
	cree_par_id: number | null;
}

/**  La configuration d'un compteur — `CompteurConfigRead` (`routers/compteurs.py`). */
export interface CompteurConfig {
	id: number;
	type_compteur: string;
	label: string;
	prestataire_id: number | null;
	actif: boolean;
	ordre: number;
}

/**  Un avis sur un prestataire — `NotationRead`. */
export interface Notation {
	id: number;
	prestataire_id: number;
	/** De 1 à 5. */
	note: number;
	commentaire: string | null;
	contrat_id: number | null;
	/** Vide quand le compte de l'auteur a été supprimé (#1821). */
	auteur_id: number | null;
	/** « ? » quand l'auteur n'existe plus. */
	auteur_nom: string | null;
	cree_le: string;
}

/**  La synthèse d'un prestataire pour le reporting — `GET /prestataires/synthese/{id}`,
 *   un dict composé à la main : la fiche, ses contrats ACTIFS et ses avis.
 *
 *   Les contrats sont lus par `lire_contrats`, comme ceux de la liste : `date_fin`,
 *   `reconduit`, `echu`, `archivee` et `synthese_disponible` y sont calculés. Ils
 *   gardaient leur valeur par défaut jusqu'à #1687. */
export interface SynthesePrestataire extends Prestataire {
	contrats: ContratEntretien[];
	notations: Omit<Notation, 'prestataire_id' | 'auteur_id'>[];
	note_moyenne: number | null;
	nb_notations: number;
	nb_contrats: number;
	/** Le libellé du contrat et sa prochaine visite. */
	prochaines_visites: { contrat: string; date: string }[];
}

export const prestataires = {
	list: () => api.get<Prestataire[]>('/prestataires'),
	create: (data: unknown) => api.post<Prestataire>('/prestataires', data),
	update: (id: number, data: unknown) => api.patch<Prestataire>(`/prestataires/${id}`, data),
	//  📦 UN mot pour UN geste (#1538) : c'était `delete`, une route `DELETE`
	//  qui ne supprimait rien, sous une corbeille intitulée « Archiver ».
	//  `archivee: false` ressort l'objet des Archives.
	archiver: (id: number, archivee: boolean) =>
		api.patch<void>(`/prestataires/${id}/archivage`, { archivee }),
	/**  Ce qui est rangé — à part, pour que les autres lecteurs de `list` ne
	 *   voient pas surgir une entreprise archivée. */
	archives: () => api.get<Prestataire[]>('/prestataires/archives'),
	contrats: () => api.get<ContratEntretien[]>('/prestataires/contrats'),
	contratsArchives: () => api.get<ContratEntretien[]>('/prestataires/contrats/archives'),
	/**  Propose la synthèse d'un contrat — et n'enregistre RIEN.
	 *
	 *   🔴 Appelée UNIQUEMENT par l'icône ✨ d'une carte de contrat, cliquée par
	 *   un membre du conseil syndical. Aucune tâche, aucun automatisme : chaque
	 *   synthèse est facturée, et chacune doit être voulue. */
	synthetiserContrat: (id: number) =>
		api.post<{ synthese: string }>(`/prestataires/contrats/${id}/synthese`, {}),
	createContrat: (data: unknown) => api.post<ContratEntretien>('/prestataires/contrats', data),
	updateContrat: (id: number, data: unknown) =>
		api.patch<ContratEntretien>(`/prestataires/contrats/${id}`, data),
	archiverContrat: (id: number, archivee: boolean) =>
		api.patch<void>(`/prestataires/contrats/${id}/archivage`, { archivee }),
	releves: (type_compteur?: string) =>
		api.get<ReleveCompteur[]>(
			`/prestataires/releves${type_compteur ? '?type_compteur=' + encodeURIComponent(type_compteur) : ''}`,
		),
	createReleve: (data: unknown) => api.post<ReleveCompteur>('/prestataires/releves', data),
	updateReleve: (id: number, data: unknown) =>
		api.patch<ReleveCompteur>(`/prestataires/releves/${id}`, data),
	deleteReleve: (id: number) => api.delete(`/prestataires/releves/${id}`),
	uploadRelevePhoto: (id: number, file: File) =>
		postFormData<ReleveCompteur>(`/prestataires/releves/${id}/photo`, { file }),
	compteurConfigs: () => api.get<CompteurConfig[]>('/prestataires/compteurs-config'),
	createCompteurConfig: (data: unknown) =>
		api.post<CompteurConfig>('/prestataires/compteurs-config', data),
	updateCompteurConfig: (id: number, data: unknown) =>
		api.patch<CompteurConfig>(`/prestataires/compteurs-config/${id}`, data),
	deleteCompteurConfig: (id: number) => api.delete(`/prestataires/compteurs-config/${id}`),
	// Notations
	notations: (prestataireId?: number) =>
		api.get<Notation[]>(
			`/prestataires/notations${prestataireId ? '?prestataire_id=' + prestataireId : ''}`,
		),
	createNotation: (data: {
		prestataire_id: number;
		note: number;
		commentaire?: string;
		contrat_id?: number;
	}) => api.post<Notation>('/prestataires/notations', data),
	//  ✅ Appelée par `NotationsPrestataire.svelte` depuis le 06/09/2026 (#807).
	//  Elle a porté la déclaration « sans appelant » quelques heures : l'endpoint
	//  existait, réservé au CS, et aucun écran ne l'appelait — l'écran ne montrait
	//  que la MOYENNE des avis, donc il n'y avait nulle part où poser le bouton.
	deleteNotation: (id: number) => api.delete(`/prestataires/notations/${id}`),
	// Synthèse
	synthese: (prestataireId: number) =>
		api.get<SynthesePrestataire>(`/prestataires/synthese/${prestataireId}`),
	/**  Les métriques des affaires où il était l'intervenant désigné — RÉSERVÉES au
	 *   conseil syndical (`require_cs_or_admin`, arbitré le 04/10/2026). */
	metriques: (prestataireId: number) =>
		api.get<MetriquesPrestataire>(`/prestataires/${prestataireId}/metriques`),
};

/** L'état d'une visite d'entretien périodique — CALCULÉ au serveur
 *  (`utils/entretien_periodique.etat_visite`), jamais par l'écran. */
export type EtatVisite = 'non_realisee' | 'a_venir' | 'a_planifier' | 'realisee' | 'annulee';

/** Une visite de l'exercice : une affaire Entretien sous contrat ou à récurrence
 *  — `GET /tickets/entretiens-periodiques`, que `tickets.entretiensPeriodiques`
 *  appelle (Reporting › Suivi des affaires, mode « Suivi entretiens périodiques », #2043). */
export interface VisitePeriodique {
	id: number;
	numero: string;
	titre: string;
	statut: string;
	debut: string | null;
	ferme_le: string | null;
	prestataire_nom: string | null;
	contrat_libelle: string | null;
	etat: EtatVisite;
}

export interface EntretienPeriodiqueResponse {
	exercice: number;
	visites: VisitePeriodique[];
}
