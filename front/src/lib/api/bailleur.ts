//  La GESTION LOCATIVE : les baux d'un bailleur, l'inventaire de ce qu'il remet,
//  et les accès qu'il confie à son locataire — vus des deux côtés du bail.
//
//  ⚠️ Fragment de `lib/api/` — extrait de `patrimoine.ts` le 04/10/2026 (#1572) :
//  typer ses retours le portait au-delà des 500 lignes, et le bail est une couture
//  existante (`routers/bailleur/`, son propre paquet côté serveur).
//
//  ⚠️ La surface publique NE BOUGE PAS : `index.ts` réexporte tout, et les
//  `from '$lib/api'` du front ne changent pas d'une ligne.
import { api } from './client';

/**
 *  Un objet remis au locataire — clé, badge, télécommande. C'est la ligne de
 *  l'inventaire d'un bail.
 *
 *  ⚠️ Le type vit ICI et non dans l'écran qui l'affiche (#806) : c'est une
 *  réponse d'API, et il était déclaré à l'identique dans `mon-lot` et dans le
 *  composant qui rend le tableau.
 */
export interface ObjetRemis {
	id: number;
	bail_id: number;
	type: string;
	libelle: string;
	quantite: number;
	reference: string | null;
	statut: string;
	remis_le: string | null;
	rendu_le: string | null;
	notes: string | null;
	cree_le: string;
}

/**
 *  Un bail, tel que le rend l'API (`BailOut`, `routers/bailleur/commun.py`).
 *
 *  ⚠️ Il était déclaré dans l'écran `mon-lot` (#1044) pendant que le client
 *  rendait `any` : l'écran retypait ce que le client aurait dû dire, et il en
 *  omettait trois champs du contrat. Même raison qu'`ObjetRemis` juste au-dessus.
 */
export interface Bail {
	id: number;
	lot_id: number;
	bailleur_id: number;
	locataire_id: number | null;
	locataire_nom: string | null;
	locataire_prenom: string | null;
	locataire_email: string | null;
	locataire_telephone: string | null;
	date_entree: string;
	date_sortie_prevue: string | null;
	date_sortie_reelle: string | null;
	statut: string;
	notes: string | null;
	cree_le: string;
	mis_a_jour_le: string;
	objets: ObjetRemis[];
}

/**
 *  Un Vigik ou une télécommande vu depuis un bail (`AccesOut`,
 *  `routers/bailleur/acces.py`) : où il est, et s'il peut être confié au
 *  locataire. Déclaré dans `ModaleAccesBail` jusqu'au #1044.
 *
 *  ⚠️ Ne pas le confondre avec `AccesAdmin` (`./acces`) : même objet, autre
 *  point de vue — l'inventaire du parc, sans la question du bail.
 */
export interface AccesBail {
	id: number;
	code: string;
	type: 'vigik' | 'telecommande';
	lot_id: number | null;
	lot_type: 'appartement' | 'parking' | 'cave' | string | null;
	lot_label: string | null;
	statut: string;
	chez_locataire: boolean;
	bail_id: number | null;
	eligible_transfert: boolean;
	recommande: boolean;
	motif_non_eligible: string | null;
	cree_le: string;
}

/**  Un compte locataire proposé au bailleur — `LocataireInfo` (`routers/bailleur/baux.py`).
 *
 *   Monté de `RechercheLocataire` (#1044), qui le déclarait sous le nom `Compte`.
 *   🔴 L'adresse arrive MASQUÉE (`p***@domaine.fr`, #2153) : entière, elle faisait
 *   de la recherche un annuaire de la résidence pour tout copropriétaire. */
export interface LocataireTrouve {
	id: number;
	nom: string;
	prenom: string;
	email_masque: string;
	actif: boolean;
}

/**  Le bail du locataire connecté — `BailLocataireOut` (`routers/bailleur/acces.py`) :
 *   son lot, son bailleur, et les accès qui lui ont été confiés. `null` sans bail. */
export interface BailLocataire {
	id: number;
	lot_id: number;
	lot_numero: string | null;
	lot_type: string | null;
	lot_type_appartement: string | null;
	lot_etage: number | null;
	lot_superficie: number | null;
	lot_batiment_nom: string | null;
	bailleur_nom: string;
	bailleur_prenom: string;
	bailleur_email: string | null;
	bailleur_telephone: string | null;
	date_entree: string;
	date_sortie_prevue: string | null;
	/** La valeur de `StatutBail`. */
	statut: string;
	acces: AccesBail[];
}

export const bailleur = {
	mesBaux: () => api.get<Bail[]>('/bailleur/mes-baux'),
	//  🔴 `creerBail` A ÉTÉ RETIRÉE (12/09/2026, #932), avec son endpoint.
	//
	//  `POST /bailleur/lots/{lot_id}/bail` était `creer-multi` **recopié pour un
	//  seul lot** : même garde « ce lot a déjà un bail en cours », même
	//  construction du `LocationBail`, à la boucle près. Deux copies d'un même
	//  invariant divergent — et celle-ci n'avait aucun appelant, masquée dans le
	//  relevé par l'homonyme `creerBailMulti`.
	//
	//  Créer un bail sur un lot, c'est `creerBailMulti({ lot_ids: [id], … })`.
	creerBailMulti: (data: unknown) => api.post<Bail[]>('/bailleur/baux/creer-multi', data),
	//  🔴 `getBail` A ÉTÉ RETIRÉE (#801) : l'écran `mon-lot` tient déjà ses baux
	//  par `mesBaux()` / `tousBaux()` / `monBail()`, et travaille dessus. Relire
	//  un bail seul depuis le serveur donnerait un second exemplaire du même
	//  objet, libre de diverger de celui de la liste affichée.
	updateBail: (id: number, data: unknown) => api.patch<Bail>(`/bailleur/baux/${id}`, data),
	terminerBail: (id: number, data: unknown) =>
		api.post<Bail>(`/bailleur/baux/${id}/terminer`, data),
	//  ✅ Ces deux méthodes ont porté la déclaration « sans appelant » de #806
	//  pendant quelques heures : rien ne les appelait, et il était donc impossible
	//  d'enregistrer un objet remis dans l'inventaire d'un bail — ni d'en corriger
	//  un. `InventaireBail.svelte` les appelle depuis le 06/09/2026.
	//
	//  ⚠️ La déclaration a été retirée le jour même, et `lint:client-appele` l'a
	//  EXIGÉ : une tolérance qui ne sert plus finit par en couvrir une qui compte.
	//
	//  ⚠️ Le motif n'est pas cité littéralement ci-dessus, et c'est délibéré : le
	//  contrôle lit les commentaires, et une citation le réactiverait. Un
	//  garde-fou qui se déclenche sur le récit de sa propre application est un
	//  faux positif qu'on apprend à ignorer.
	ajouterObjet: (bail_id: number, data: unknown) =>
		api.post<ObjetRemis>(`/bailleur/baux/${bail_id}/objets`, data),
	updateObjet: (bail_id: number, obj_id: number, data: unknown) =>
		api.patch<ObjetRemis>(`/bailleur/baux/${bail_id}/objets/${obj_id}`, data),
	retourObjet: (bail_id: number, obj_id: number, data: unknown) =>
		api.post<ObjetRemis>(`/bailleur/baux/${bail_id}/objets/${obj_id}/retour`, data),
	supprimerObjet: (bail_id: number, obj_id: number) =>
		api.delete(`/bailleur/baux/${bail_id}/objets/${obj_id}`),
	supprimerBail: (bail_id: number) => api.delete(`/bailleur/baux/${bail_id}`),
	tousBaux: () => api.get<Bail[]>('/bailleur/tous-les-baux'),
	// Recherche locataire & gestion accès
	searchLocataire: (q: string) =>
		api.get<LocataireTrouve[]>(`/bailleur/search-locataire?q=${encodeURIComponent(q)}`),
	locatairesSuggeres: () => api.get<LocataireTrouve[]>('/bailleur/locataires-suggeres'),
	accesBail: (bail_id: number) => api.get<AccesBail[]>(`/bailleur/baux/${bail_id}/acces`),
	transfererAcces: (bail_id: number, data: { vigik_ids: number[]; tc_ids: number[] }) =>
		api.post<AccesBail[]>(`/bailleur/baux/${bail_id}/transferer-acces`, data),
	recupererAcces: (bail_id: number, data?: { vigik_ids: number[]; tc_ids: number[] }) =>
		api.post<AccesBail[]>(`/bailleur/baux/${bail_id}/recuperer-acces`, data ?? {}),
	mesAccesRecus: () => api.get<AccesBail[]>('/bailleur/mes-acces-recus'),
	monBail: () => api.get<BailLocataire | null>('/bailleur/mon-bail'),
};
