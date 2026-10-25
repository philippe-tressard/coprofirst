//  Le CONTRÔLE D'ACCÈS : badges Vigik, télécommandes, et les imports Excel qui
//  les alimentent. Un domaine à part parce qu'il a ses propres écrans
//  d'administration et son propre cycle d'appariement.
//
//  ⚠️ Fragment de `lib/api/` — extrait de `index.ts` le 27/08/2026 (#453). Ce
//  fichier portait VINGT ET UN domaines et 437 lignes ; `client.ts`, `types.ts`,
//  `documents.ts` et `communaute.ts` en étaient déjà sortis en leur temps, la
//  coupe suit donc une couture existante et non le compteur de lignes.
//
//  ⚠️ La surface publique NE BOUGE PAS : `index.ts` réexporte tout, et les
//  quarante et un `from '$lib/api'` du front ne changent pas d'une ligne.
import { api, BASE } from './client';
import { uploadExcel } from './documents';
import type { ConstatPatrimoine } from './etat-descriptif';

//  ── Ce que le serveur RENVOIE (#1572) ───────────────────────────────────────────
//
//  Lus dans `routers/acces/` (`resident.py`, `vues.py`, `parc.py`, `commun.py`,
//  `socle_imports.py`) — jamais supposés (même motif que `communaute.ts`). Les dates
//  arrivent en chaîne ISO sans fuseau (UTC naïf, comme la base).

/** L'état d'un badge — `StatutAcces` (`models/acces.py`). */
export type StatutAcces = 'actif' | 'suspendu' | 'perdu';

/**
 *  Un badge vu par son PORTEUR — `AccesOut` (`routers/acces/vues.py`) : ce qu'il
 *  ouvre, son lot, et s'il a été confié au locataire.
 */
export interface AccesPorteur {
	id: number;
	code: string;
	statut: StatutAcces;
	/** Vrai quand le bailleur a transféré le badge à son locataire. */
	chez_locataire: boolean;
	/** Le bail au titre duquel il a été confié — la vue du bailleur s'en sert. */
	bail_id: number | null;
	lot_id: number | null;
	/**  🔹 Ce que le badge OUVRE — des CODES, jamais un libellé.
	 *
	 *   ⚠️ L'écran les met en forme (`BadgePerimetre`), comme partout ailleurs :
	 *   un libellé venu du serveur obligerait celui-ci à décider d'un rendu, et
	 *   c'est le défaut que le fil d'activité portait jusqu'au 14/09/2026. */
	perimetre_cible: string[];
	/** Le ou les lots de sa NATURE (`libelle_lots`), séparés comme partout ailleurs. */
	lot_libelle: string | null;
	cree_le: string;
}

/**
 *  Un badge vu par le conseil syndical — le code, et surtout **qui le porte**
 *  (`AccesAdminOut`, `routers/acces/parc.py`, qui dérive d'`AccesOut`).
 *
 *  ⚠️ Le type vit ici parce que c'est une réponse d'API (même raison que
 *  `ObjetRemis`). Il ne décrit PAS la table : `user_id` et
 *  `lot_id` y sont résolus en nom et en libellé côté serveur, une fois, plutôt
 *  que par un rapprochement que chaque écran referait à sa façon.
 */
export interface AccesAdmin extends AccesPorteur {
	porteur_nom: string;
	porteur_id: number | null;
}

/**  Un badge tel que sa TABLE le porte (`Vigik`, `Telecommande`) — ce que rend la
 *   résolution d'une ligne d'import, sans vue : `user_id` brut, ciblage en JSON texte. */
export interface ObjetAccesBrut {
	id: number;
	code: string;
	lot_id: number | null;
	user_id: number | null;
	statut: StatutAcces;
	chez_locataire: boolean;
	bail_id: number | null;
	/** JSON TEXTE (`'["bat:2"]'`), pas une liste — la ligne n'est pas relue par une vue. */
	perimetre_cible: string | null;
	cree_le: string;
}

/**  Une commande de badge — `CommandeAccesRead` (`routers/acces/resident_schemas.py`). */
export interface CommandeAcces {
	id: number;
	user_id: number;
	lot_id: number;
	/** `vigik` ou `telecommande`. */
	type: string;
	quantite: number;
	motif: string | null;
	/** La valeur de `StatutCommande`. */
	statut: string;
	cree_le: string;
}

/**  Ce que rend la déclaration d'un badge par son porteur (`resident._declarer_acces`). */
export interface BadgeDeclare {
	/** La clé du type (`vigik`, `telecommande`). */
	type: string;
	id: number;
	code: string;
	/** Une ligne du fichier du syndic a été rattachée au passage. */
	import_resolu: boolean;
}

/** L'état d'une ligne d'import — `StatutImport` (`models/acces.py`). */
export type StatutLigneImport = 'en_attente' | 'proprietaire_lie' | 'resolu' | 'ignore';

/**  Une ligne du fichier du syndic telle que la TABLE la porte (`_LigneImportAcces`),
 *   commune aux deux imports. C'est ce que rend la correction d'une ligne. */
export interface LigneImportAccesBrute {
	id: number;
	statut: StatutLigneImport;
	user_proprietaire_id: number | null;
	user_locataire_id: number | null;
	lot_id: number | null;
	chez_locataire: boolean;
	refuse_par_locataire: boolean;
	notes_admin: string | null;
	importe_le: string;
	resolu_le: string | null;
	nom_proprietaire: string;
	nom_locataire: string | null;
}

/** Une ligne de l'import des télécommandes — `TelecommandeImport`. */
export interface LigneImportTelecommandeBrute extends LigneImportAccesBrute {
	reference: string | null;
	telecommande_id: number | null;
}

/** Une ligne de l'import Vigik — `VigikImport`. */
export interface LigneImportVigikBrute extends LigneImportAccesBrute {
	batiment_raw: string | null;
	appartement_raw: string | null;
	code: string | null;
	vigik_id: number | null;
}

/** Un compte rattaché à une ligne d'import, ou `null`. */
type CompteLie = { id: number; nom: string; prenom: string } | null;

/**  Une ligne de la LISTE d'un import (`commun._lister_imports`) : la ligne brute,
 *   plus ses comptes, son lot et ce que le rattachement donnera. */
export type LigneImportAcces<L extends LigneImportAccesBrute = LigneImportAccesBrute> = L & {
	proprietaire: CompteLie;
	locataire: CompteLie;
	lot_label: string | null;
	/** Le nombre de copropriétaires du lot — `null` sans lot. */
	lot_porteurs: number | null;
	rattachable: boolean;
};

/**  Les compteurs d'un import (`commun._stats_socle`) : un par statut, plus ceux
 *   du rattachement. Chaque import y ajoute les siens. */
export interface StatsImportAcces {
	total: number;
	en_attente: number;
	proprietaire_lie: number;
	resolu: number;
	ignore: number;
	avec_locataire: number;
	a_rattacher: number;
	lot_a_preciser: number;
}

/** L'appariement automatique (`socle_imports.auto_match`). */
export interface AppariementImport {
	matches: number;
	total: number;
	/** Des lignes « résolues » sans lot, rendues au rapprochement (#1338). */
	reprises: number;
}

/** Le rattachement en masse (`resolution_acces.rattacher_les_reconnues`). */
export interface RattachementImport {
	rattachees: number;
	restantes: number;
}

/** Un lot tel que le proposent les deux formulaires de badge (import, parc) —
 *  `GET /acces/admin/imports-lots`. Venu de `$lib/imports-acces` à côté de son client. */
export interface LotPourBadge {
	id: number;
	libelle: string;
	/** La valeur de `TypeLot` (`appartement`, `parking`…). */
	type: string;
	/** Le nom que le FICHIER DES LOTS donne au copropriétaire, ou `null`. */
	coproprietaire: string | null;
}

/**  Ce qu'un type d'accès a le droit d'ouvrir, et comment son défaut se décide.
 *
 *   ⚠️ `suitLeLot` n'est pas cosmétique : sans lui, l'écran devrait écrire
 *   `type === 'vigik'` pour choisir son libellé d'aide — reconnaître un type par
 *   son nom, exactement ce que le descripteur `TypeAcces` a supprimé côté
 *   serveur. Un objet dit ce qu'il est ; on ne le devine pas à sa clé. */
export interface ChoixAcces {
	codes: string[];
	suit_le_lot: boolean;
}

/**  Une porte que les lots d'un badge justifient, et la raison qui se lit à
 *   l'écran (« dessert votre place ») — `PorteProposee` (#2217).
 *
 *   🔴 Une PROPOSITION : le conseil la reprend ou non, et c'est l'enregistrement
 *   qui décide. Rien n'est posé sans lui (« proposer, jamais poser »). */
export interface PorteProposee {
	code: string;
	raison: string;
}

export const acces = {
	mesVigiks: () => api.get<AccesPorteur[]>('/acces/mes-vigiks'),
	mesTelecommandes: () => api.get<AccesPorteur[]>('/acces/mes-telecommandes'),
	creerCommande: (data: unknown) => api.post<CommandeAcces>('/acces/commandes', data),
	signalerVigiKPerdu: (id: number) =>
		api.patch<{ statut: StatutAcces }>(`/acces/vigiks/${id}/perdu`, {}),
	signalerTcPerdu: (id: number) =>
		api.patch<{ statut: StatutAcces }>(`/acces/telecommandes/${id}/perdu`, {}),
	//  🔴 `supprimerVigik` et `supprimerTc` sont partis le 15/09/2026, avec
	//  leurs routes : un résident ne supprime pas un accès, il signale une perte.
	//  La suppression définitive reste à l'administrateur (`supprimerAcces`).
	declarerBadge: (data: { type: string; code: string }) =>
		api.post<BadgeDeclare>('/acces/declarer-badge', data),
	//  ── CS/Admin — LE PARC : qui a quoi, et que peut-on en faire ──────────────
	//
	//  🔴 Cet écran a été **en lecture seule du 06/09 au 14/09/2026**, et ce
	//  n'était pas un oubli : trois routes d'écriture avaient été supprimées ce
	//  jour-là (#805) au motif qu'enregistrer un badge était déjà couvert deux
	//  fois — l'import Excel en masse, et `declarerBadge` par le résident.
	//
	//  Le choix est **renversé sur demande explicite** (#953) : le conseil
	//  syndical remet des badges en main propre, et rien ne le lui permettait.
	//
	//  ⚠️ Ce qui aurait été fautif n'était pas d'ouvrir l'écriture, c'était de la
	//  RECOPIER. Côté serveur, les gestes passent par le descripteur
	//  `utils/types_acces` — celui dont l'absence avait laissé diverger le report
	//  du `lot_id` entre vigik et télécommande (corrigé en v1.36.8).
	//
	//  ⚠️ La réponse rendait l'objet BRUT avant #805, donc `user_id` : un écran
	//  bâti dessus aurait affiché « badge 4521 → utilisateur 37 ». Une route sans
	//  appelant n'est jamais mise à l'épreuve de la question à laquelle elle est
	//  censée répondre.
	//  🔹 Ce que chaque type d'accès a le DROIT d'ouvrir, par clé de type.
	//
	//  ⚠️ L'écran s'en sert pour PROPOSER ; ce qui contraint est la validation
	//  côté serveur, sur les deux gestes d'écriture. Une restriction qui ne
	//  vivrait que dans le formulaire n'en serait pas une — la route accepterait
	//  toujours n'importe quel code.
	//
	//  ⚠️ Des codes, pas des libellés : l'écran les met en forme depuis l'arbre
	//  qu'il a déjà chargé, comme `BadgePerimetre` et `PerimetrePicker` partout
	//  ailleurs. Deux mises en forme du même objet, c'est la divergence de demain.
	choixAcces: () => api.get<Record<string, ChoixAcces>>('/acces/admin/choix-acces'),
	//  Les portes que les lots du badge justifient — une proposition, jamais posée.
	portesProposees: (porteurId: number | null, lotId: number | null) => {
		const q = new URLSearchParams();
		if (porteurId) q.set('porteur_id', String(porteurId));
		if (lotId) q.set('lot_id', String(lotId));
		return api.get<PorteProposee[]>(`/acces/admin/portes-proposees?${q}`);
	},
	//  Les badges dont l'accès diffère de ce que leurs lots justifient — jamais bloquant.
	constatsBadges: () => api.get<ConstatPatrimoine[]>('/acces/admin/constats-badges'),
	listVigiks: () => api.get<AccesAdmin[]>('/acces/admin/vigiks'),
	listTelecommandes: () => api.get<AccesAdmin[]>('/acces/admin/telecommandes'),
	//  Le TYPE est un paramètre de chemin, pas deux méthodes : `vigik` et
	//  `telecommande` répondent à la même question, et deux méthodes jumelles
	//  auraient divergé au premier champ ajouté — c'est ce qui est arrivé à
	//  `declarerBadge`.
	creerAcces: (type: string, data: unknown) => api.post<AccesAdmin>(`/acces/admin/${type}`, data),
	modifierAcces: (type: string, id: number, data: unknown) =>
		api.patch<AccesAdmin>(`/acces/admin/${type}/${id}`, data),
	//  🔒 Réservé à l'ADMIN côté serveur : le conseil syndical passe un badge en
	//  « perdu » par `modifierAcces`. Un badge perdu a existé, et le parc doit
	//  pouvoir le dire (`ux-patterns` §8).
	supprimerAcces: (type: string, id: number) => api.delete(`/acces/admin/${type}/${id}`),
	//: L'adresse de l'export d'UN type — le navigateur la suit, on ne la lit pas ici.
	//
	//  ⚠️ Pas de `api.get` : la réponse est un FICHIER, et la passer par le client
	//  obligerait à fabriquer un `blob:` puis un lien de téléchargement. Le
	//  navigateur sait le faire ; les cookies de session partent avec.
	//
	//  🔴 **Un export PAR TYPE depuis le 15/09/2026.** Le fichier unique de la
	//  veille obligeait à filtrer sur une colonne « Type » avant tout usage : un
	//  vigik et une télécommande n'ont ni les mêmes accès possibles, ni le même
	//  rapport au lot. La fonction reste **une seule**, paramétrée — deux
	//  fonctions jumelles auraient divergé au premier ajustement d'URL.
	urlExportParc: (type: string) => `${BASE}/acces/admin/${type}/export.csv`,
	// CS/Admin — import vigik
	uploadImportVigik: (file: File, remplacer = false) =>
		uploadExcel('/acces/admin/imports-vigik/upload', file, remplacer),
	listImportsVigik: (statut?: string) =>
		api.get<LigneImportAcces<LigneImportVigikBrute>[]>(
			`/acces/admin/imports-vigik${statut ? `?statut=${statut}` : ''}`,
		),
	statsImportsVigik: () =>
		api.get<StatsImportAcces & { avec_code: number; avec_lot: number }>(
			'/acces/admin/imports-vigik/stats',
		),
	autoMatchImportsVigik: () =>
		api.post<AppariementImport>('/acces/admin/imports-vigik/auto-match', {}),
	rattacherImportsVigik: () =>
		api.post<RattachementImport>('/acces/admin/imports-vigik/rattacher', {}),
	/** Les lots, avec le copropriétaire que le FICHIER leur donne — pour les deux imports. */
	lotsImports: () => api.get<LotPourBadge[]>('/acces/admin/imports-lots'),
	patchImportVigik: (id: number, data: unknown) =>
		api.patch<LigneImportVigikBrute>(`/acces/admin/imports-vigik/${id}`, data),
	resoudreImportVigik: (id: number) =>
		api.post<{ vigik: ObjetAccesBrut; import_id: number }>(
			`/acces/admin/imports-vigik/${id}/resoudre`,
			{},
		),
	ignorerImportVigik: (id: number) =>
		api.post<{ statut: StatutLigneImport }>(`/acces/admin/imports-vigik/${id}/ignorer`, {}),
	/** 🔒 Administrateur : une ligne erronée disparaît, son badge éventuel reste. */
	supprimerImportVigik: (id: number) => api.delete(`/acces/admin/imports-vigik/${id}`),
	remettreEnAttenteImportVigik: (id: number) =>
		api.post<{ statut: StatutLigneImport }>(
			`/acces/admin/imports-vigik/${id}/remettre-en-attente`,
			{},
		),
	// CS/Admin — import télécommandes
	uploadImportTC: (file: File, remplacer = false) =>
		uploadExcel('/acces/admin/imports/upload', file, remplacer),
	listImportsTC: (statut?: string) =>
		api.get<LigneImportAcces<LigneImportTelecommandeBrute>[]>(
			`/acces/admin/imports${statut ? `?statut=${statut}` : ''}`,
		),
	statsImportsTC: () =>
		api.get<StatsImportAcces & { avec_reference: number }>('/acces/admin/imports/stats'),
	autoMatchImportsTC: () => api.post<AppariementImport>('/acces/admin/imports/auto-match', {}),
	rattacherImportsTC: () => api.post<RattachementImport>('/acces/admin/imports/rattacher', {}),
	patchImportTC: (id: number, data: unknown) =>
		api.patch<LigneImportTelecommandeBrute>(`/acces/admin/imports/${id}`, data),
	resoudreImportTC: (id: number) =>
		api.post<{ telecommande: ObjetAccesBrut; import_id: number }>(
			`/acces/admin/imports/${id}/resoudre`,
			{},
		),
	ignorerImportTC: (id: number) =>
		api.post<{ statut: StatutLigneImport }>(`/acces/admin/imports/${id}/ignorer`, {}),
	supprimerImportTC: (id: number) => api.delete(`/acces/admin/imports/${id}`),
	remettreEnAttenteImportTC: (id: number) =>
		api.post<{ statut: StatutLigneImport }>(`/acces/admin/imports/${id}/remettre-en-attente`, {}),
};
