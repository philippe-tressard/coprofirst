//  Le domaine **Communauté** : sondages, boîte à idées, petites annonces et
//  signalements. Quatre clients qui servent une seule page (`/sondages`, ses
//  trois onglets) et qui vivaient dispersés sur 130 lignes d'`index.ts`.
//
//  Extrait quand le contrôle de modularité a refusé qu'`index.ts` dépasse 500
//  lignes en recevant `deleteEvolution` (#512). Le refus disait vrai : un
//  fichier qui expose vingt-six domaines n'a pas un problème de taille, il a un
//  problème de découpage — et `documents.ts` avait déjà montré la voie.
import { api, postFormData } from './client';

//  ── Ce que le serveur RENVOIE (#1572) ───────────────────────────────────────────
//
//  Ces types sont LUS dans le code serveur, route par route — jamais supposés. Le
//  client rendait `any`, et chaque écran croyait recevoir ce qu'il lisait : la
//  carte d'une idée affiche `assiste_ia`, que la liste des idées n'a pas transporté
//  jusqu'au #1660. Un type honnête le montre ; un `any` le cache.
//
//  ⚠️ Plusieurs routes n'ont pas de `response_model` : elles rendent un dict
//  composé à la main, ou la LIGNE de la table telle quelle. Une ligne brute porte
//  le ciblage en JSON TEXTE (`perimetre_cible: '["résidence"]'`), pas en liste —
//  d'où les types `…Cree` distincts de ceux des listes, qui convertissent.
//
//  Les dates arrivent en chaîne ISO sans fuseau (UTC naïf, comme la base).

/**  Une réponse de la Communauté — à une idée, une annonce, ou le commentaire d'un
 *   sondage. `utils/reponses.enrich_reponse` + `auteur_meta`, seule écriture. */
export interface ReponseCommunaute {
	id: number;
	/** Vide quand le compte de l'auteur a été supprimé (#1821). */
	auteur_id: number | null;
	contenu: string;
	cree_le: string;
	/** « Utilisateur supprimé » quand le compte n'existe plus — jamais absent. */
	auteur_nom: string;
	auteur_batiment: string | null;
	auteur_role: string | null;
	/** CS ou admin : réponse mise en avant, et triée en tête par le serveur. */
	est_cs: boolean;
}

/**  La réponse qu'on vient de publier sur une idée ou une annonce
 *   (`reponses_communaute.create_reponse`) : la même, plus sa cible. */
export interface ReponseCommunauteCreee extends ReponseCommunaute {
	cible_id: number;
}

/**  Un sondage de la LISTE — `SondageRead`, le seul `response_model` du domaine. */
export interface Sondage {
	id: number;
	question: string;
	description: string | null;
	cloture_le: string | null;
	cloture_forcee: boolean;
	resultats_publics: boolean;
	/** Vide quand le compte de l'auteur a été supprimé (#1821). */
	auteur_id: number | null;
	cree_le: string;
	perimetre_cible: string[];
	public_cible: string[];
	nb_votants: number;
	/** Tranché par le serveur (`sondage_clos`), jamais par l'écran (#468). */
	cloture: boolean;
	/** La règle d'archivage du site (`utils/archivage`, #515). */
	archivee: boolean;
	assiste_ia: boolean;
}

/**  Une option sur la FICHE d'un sondage. `nb_votes` et `reponses_libres` sont
 *   ABSENTS — pas à zéro — quand les résultats ne sont pas visibles : « 0 vote » se
 *   lirait « personne n'a voté » (`crud.get_sondage`). */
export interface OptionSondage {
	id: number;
	libelle: string;
	ordre: number;
	champ_libre: boolean;
	nb_votes?: number;
	reponses_libres?: string[];
}

/**  La FICHE d'un sondage — `GET /sondages/{id}`, un dict composé à la main.
 *
 *   ⚠️ Ce n'est PAS le schéma `SondageDetail` du serveur, qu'aucune route ne
 *   déclare : la fiche ne porte ni `nb_votants`, ni `archivee`, ni `assiste_ia`
 *   de la liste, et ajoute ses options, ses commentaires et la décision
 *   d'affichage des résultats. */
export interface SondageDetail extends Omit<Sondage, 'nb_votants' | 'archivee' | 'assiste_ia'> {
	options: OptionSondage[];
	/** L'option votée par l'utilisateur, ou `null` s'il n'a pas voté. */
	mon_vote: number | null;
	commentaires: ReponseCommunaute[];
	/** Source UNIQUE de la décision d'afficher les résultats (#397). */
	resultats_visibles: boolean;
}

/**  `POST /sondages` — la LIGNE `sondage` telle quelle, sans `response_model` :
 *   colonnes brutes, ciblage en JSON texte, canaux de diffusion compris. */
export interface SondageCree {
	id: number;
	question: string;
	description: string | null;
	cloture_le: string | null;
	resultats_publics: boolean;
	auteur_id: number;
	cree_le: string;
	perimetre_cible: string | null;
	public_cible: string | null;
	cloture_forcee: boolean;
	partager_whatsapp: boolean;
	envoyer_syndic: boolean;
	envoyer_cs: boolean;
	assiste_ia: boolean;
}

/**  `PATCH /sondages/{id}` — ce que la correction touche, et rien d'autre : les
 *   libellés corrigés reviennent dans l'ordre d'affichage. */
export interface SondageCorrige {
	id: number;
	question: string;
	description: string | null;
	cloture_le: string | null;
	resultats_publics: boolean;
	options: Pick<OptionSondage, 'id' | 'libelle' | 'ordre'>[];
}

/**  Une idée — `idees._enrich`, que rendent la liste ET la correction : le schéma
 *   `IdeeRead`, lu sur le modèle (#1660). */
export interface Idee {
	id: number;
	titre: string;
	description: string;
	/** Vide quand le compte de l'auteur a été supprimé (#1821). */
	auteur_id: number | null;
	/** `ouverte | retenue | rejetee | realisee` — une chaîne libre côté serveur. */
	statut: string;
	perimetre_cible: string[];
	/** Vide = tous les résidents. */
	public_cible: string[];
	cree_le: string;
	nb_votes: number;
	mon_vote: boolean;
	archivee: boolean;
	/** Rédigée avec l'assistant IA — la marque que `MarqueIA` rend. */
	assiste_ia: boolean;
	reponses: ReponseCommunaute[];
	nb_reponses: number;
}

/**  `POST /idees` — la LIGNE `idee` telle quelle (ciblage en JSON texte). */
export interface IdeeCreee {
	id: number;
	titre: string;
	description: string;
	auteur_id: number;
	statut: string;
	cree_le: string;
	statut_change_le: string | null;
	perimetre_cible: string | null;
	public_cible: string | null;
	assiste_ia: boolean;
}

export type TypeAnnonce = 'vente' | 'don' | 'recherche';
export type CategorieAnnonce =
	| 'appartement'
	| 'parking_cave'
	| 'mobilier'
	| 'electromenager'
	| 'high_tech'
	| 'vehicule'
	| 'vetements'
	| 'services'
	| 'divers';
/** Le workflow d'une annonce — `archive` n'en est pas : l'archivage se calcule. */
export type StatutAnnonce = 'en_cours' | 'reserve' | 'vendu' | 'donne' | 'annule';

/**  Une petite annonce — `annonces._enrich` : la ligne entière (`model_dump`),
 *   ciblage converti en listes, plus l'auteur, les photos et les réponses. La
 *   liste, la création et la correction rendent la même. */
export interface PetiteAnnonce {
	id: number;
	titre: string;
	/** Texte riche (HTML). */
	description: string;
	type_annonce: TypeAnnonce;
	categorie: CategorieAnnonce;
	prix: number | null;
	negotiable: boolean;
	/** La colonne brute ; `photos` en est la lecture. */
	photos_json: string;
	photos: string[];
	perimetre_cible: string[];
	/** Vide = tous les résidents. */
	public_cible: string[];
	statut: StatutAnnonce;
	statut_change_le: string | null;
	contact_visible: boolean;
	auteur_id: number;
	cree_le: string;
	mis_a_jour_le: string | null;
	assiste_ia: boolean;
	auteur_prenom: string;
	auteur_nom: string;
	/** `null` quand l'auteur masque son contact. */
	auteur_email: string | null;
	est_auteur: boolean;
	archivee: boolean;
	reponses: ReponseCommunaute[];
	nb_reponses: number;
}

export type CibleSignalement = 'idee' | 'annonce' | 'sondage' | 'reponse' | 'commentaire';

/**  Une entrée de la file de modération — `signalements._enrich`. */
export interface Signalement {
	id: number;
	cible_type: CibleSignalement;
	cible_type_label: string;
	cible_id: number;
	apercu: string;
	motif: string;
	/** `en_attente | traite | rejete`. */
	statut: string;
	cree_le: string;
	/** Le nom de qui signale, ou « Inconnu ». */
	signale_par: string;
	auteur_cible: string | null;
	auteur_cible_id: number | null;
}

/** Les gestes qui ne rendent qu'un message (`voter`, `cloturer`). */
interface Message {
	message: string;
}

export const sondages = {
	list: () => api.get<Sondage[]>('/sondages'),
	get: (id: number) => api.get<SondageDetail>(`/sondages/${id}`),
	create: (data: unknown) => api.post<SondageCree>('/sondages', data),
	modifier: (id: number, data: unknown) => api.patch<SondageCorrige>(`/sondages/${id}`, data),
	supprimer: (id: number) => api.delete(`/sondages/${id}`),
	cloturer: (id: number) => api.patch<Message>(`/sondages/${id}/cloturer`, {}),
	voter: (id: number, option_id: number, commentaire?: string, reponse_libre?: string) =>
		api.post<Message>(`/sondages/${id}/voter`, {
			option_id,
			commentaire: commentaire || null,
			reponse_libre: reponse_libre || null,
		}),
	commenter: (id: number, contenu: string) =>
		api.post<ReponseCommunaute>(`/sondages/${id}/commenter`, { contenu }),
	supprimerCommentaire: (sondageId: number, commentaireId: number) =>
		api.delete(`/sondages/${sondageId}/commentaires/${commentaireId}`),
};

export const idees = {
	list: () => api.get<Idee[]>('/idees'),
	create: (data: unknown) => api.post<IdeeCreee>('/idees', data),
	//  La CORRECTION d'une idée (#783). Le `PATCH` n'existait pas côté serveur :
	//  l'idée était la seule entité de la Communauté où une faute de frappe était
	//  définitive — ou imposait de supprimer et redéposer, ce qui perd les votes
	//  et les réponses. Il n'accepte que le titre et la description : le ciblage
	//  et le statut ont leurs propres règles, et un champ qu'on n'expose pas ne
	//  se contourne pas.
	modifier: (id: number, data: unknown) => api.patch<Idee>(`/idees/${id}`, data),
	//  Le vote est une BASCULE : le message dit lequel des deux gestes a eu lieu.
	voter: (id: number) => api.post<Message>(`/idees/${id}/voter`),
	updateStatut: (id: number, statut: string) =>
		api.patch<{ statut: string }>(`/idees/${id}/statut`, { statut }),
	delete: (id: number) => api.delete(`/idees/${id}`),
	//  🔴 `listReponses` A ÉTÉ RETIRÉE le 06/09/2026 (#801) — pour l'idée comme
	//  pour l'annonce, quelques lignes plus bas. Les réponses arrivent DÉJÀ avec
	//  l'objet (`idee.reponses`, `annonce.reponses`), et c'est ce que les écrans
	//  lisent : `ListeIdees` et `AnnonceCard` les passent tels quels. Une seconde
	//  voie de lecture pour la même donnée, ce sont deux états libres de diverger
	//  — et celle-ci n'a jamais eu d'appelant.
	//
	//  ⚠️ Les endpoints `GET /idees/{id}/reponses` et `/annonces/{id}/reponses`
	//  RESTENT : c'est la porte côté client qui disparaît, pas la fonction.
	repondre: (id: number, contenu: string) =>
		api.post<ReponseCommunauteCreee>(`/idees/${id}/reponses`, { contenu }),
	supprimerReponse: (id: number, repId: number) => api.delete(`/idees/${id}/reponses/${repId}`),
};

export const annonces = {
	list: () => api.get<PetiteAnnonce[]>('/annonces'),
	create: (data: unknown) => api.post<PetiteAnnonce>('/annonces', data),
	//  La CORRECTION d'une annonce — `PATCH /annonces/{id}` existait depuis
	//  toujours, avec ses sept champs, et aucun écran ne l'appelait (18/08/2026).
	update: (id: number, data: unknown) => api.patch<PetiteAnnonce>(`/annonces/${id}`, data),
	updateStatut: (id: number, statut: string) =>
		api.patch<{ ok: boolean }>(`/annonces/${id}/statut`, { statut }),
	supprimer: (id: number) => api.delete(`/annonces/${id}`),
	uploadPhoto: (id: number, file: File): Promise<{ url: string; photos: string[] }> =>
		postFormData(`/annonces/${id}/photo`, { file }),
	deletePhoto: (id: number, url: string) =>
		api.delete<{ photos: string[] }>(`/annonces/${id}/photo?url=${encodeURIComponent(url)}`),
	//  `listReponses` retirée ici aussi — voir la note sur les idées ci-dessus.
	repondre: (id: number, contenu: string) =>
		api.post<ReponseCommunauteCreee>(`/annonces/${id}/reponses`, { contenu }),
	supprimerReponse: (id: number, repId: number) => api.delete(`/annonces/${id}/reponses/${repId}`),
};

export const signalements = {
	creer: (cible_type: string, cible_id: number, motif: string) =>
		api.post<{ id: number; statut: string }>('/signalements', { cible_type, cible_id, motif }),
	liste: (statut = 'en_attente') => api.get<Signalement[]>(`/signalements?statut=${statut}`),
	//  🔴 `count` A ÉTÉ RETIRÉE le 06/09/2026 (#801) : l'écran charge déjà
	//  `liste('en_attente')` et connaît donc `signalements.length`. Demander un
	//  compteur au serveur pendant qu'on tient la liste, c'est un aller-retour de
	//  plus pour une valeur qu'on a — et deux nombres libres de se contredire le
	//  temps du chargement. L'endpoint `GET /signalements/count` reste, pour un
	//  écran qui voudrait le compte SANS la liste.
	resoudre: (id: number, statut: 'traite' | 'rejete') =>
		api.patch<{ id: number; statut: string }>(`/signalements/${id}`, { statut }),
};
