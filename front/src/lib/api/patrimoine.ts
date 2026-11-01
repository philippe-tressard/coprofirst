//  La COPROPRIÉTÉ physique et ses occupations : la fiche, les lots, les baux,
//  l'arborescence des périmètres, les règles de vie et les diagnostics
//  réglementaires. Tout ce qui décrit le bâtiment et qui y habite.
//
//  ⚠️ Fragment de `lib/api/` — extrait de `index.ts` le 27/08/2026 (#453). Ce
//  fichier portait VINGT ET UN domaines et 437 lignes ; `client.ts`, `types.ts`,
//  `documents.ts` et `communaute.ts` en étaient déjà sortis en leur temps, la
//  coupe suit donc une couture existante et non le compteur de lignes.
//
//  ⚠️ La surface publique NE BOUGE PAS : `index.ts` réexporte tout, et les
//  quarante et un `from '#lib/api/index.ts'` du front ne changent pas d'une ligne.
import { api, buildQuery, postFormData, BASE } from './client';
import type { ConstatPatrimoine } from './etat-descriptif';
import { uploadExcel, type CompteImportTableur } from './documents';
import type { ExerciceLu, ResumeAffaires, SyntheseAffaire } from './synthese';

//  ── Ce que le serveur RENVOIE (#1572) ───────────────────────────────────────────
//
//  Lus dans le code serveur, route par route — jamais supposés (même motif que
//  `communaute.ts`). Les dates arrivent en chaîne ISO (`AAAA-MM-JJ` pour une
//  `date`, sans fuseau pour un instant).

/**  La fiche de la copropriété — `CoproprieteRead` (`routers/copropriete.py`), que
 *   rendent la lecture et la correction. Les champs `assurance_*` et `syndic_*`
 *   suivent le contrat désigné quand il y en a un ; `*_reconduit` et `*_echu`
 *   sont DÉDUITS par le serveur, jamais saisis. */
export interface Copropriete {
	id: number;
	nom: string;
	adresse: string;
	annee_construction: number | null;
	nb_lots_total: number | null;
	nb_lots_principaux: number | null;
	numero_immatriculation: string | null;
	mois_debut_exercice: number | null;
	assurance_compagnie: string | null;
	assurance_numero_police: string | null;
	assurance_echeance: string | null;
	assurance_contrat_id: number | null;
	assurance_telephone: string | null;
	assurance_email: string | null;
	assurance_debut: string | null;
	assurance_document_id: number | null;
	assurance_reconduit: boolean;
	assurance_echu: boolean;
	syndic_contrat_id: number | null;
	syndic_cabinet: string | null;
	syndic_telephone: string | null;
	syndic_email: string | null;
	syndic_numero_mandat: string | null;
	syndic_debut: string | null;
	syndic_echeance: string | null;
	syndic_document_id: number | null;
	syndic_reconduit: boolean;
	syndic_echu: boolean;
	syndic_interlocuteur: string | null;
	syndic_interlocuteur_email: string | null;
	photo_url: string | null;
	nb_parkings_communs: number;
}

/**  Un bâtiment de la résidence — `BatimentRead` (`routers/copropriete.py`). */
export interface Batiment {
	id: number;
	/** « A », « B »… — le NUMÉRO, pas le libellé « Bât. A ». */
	numero: string;
	nb_etages: number;
	specificites: string | null;
	nb_appartements: number;
	nb_caves: number;
	nb_parkings: number;
	nb_locaux_commerciaux: number;
}

/** L'état d'une ligne de l'import des lots — `StatutLotImport` (`models/lot_import.py`). */
export type StatutLigneImportLot =
	'en_attente' | 'utilisateur_lie' | 'lot_lie' | 'resolu' | 'ignore';

/**  Une ligne de l'import des lots — `lots_imports._imp_row` : la ligne du classeur,
 *   son lot et ses occupants résolus. La liste ET la correction la rendent. */
export interface LigneImportLot {
	id: number;
	/** `null` pour un parking. */
	batiment_id: number | null;
	/** Le libellé du bâtiment, son identifiant s'il a disparu, « P » pour un parking. */
	batiment_nom: string;
	numero: string;
	/** Le type tel que le classeur l'écrit (`AP`, `T2`, `CA`, `PS`…). */
	type_raw: string;
	etage_raw: string | null;
	no_coproprietaire: string | null;
	nom_coproprietaire: string | null;
	statut: StatutLigneImportLot;
	lot_id: number | null;
	lot_label: string | null;
	utilisateurs: {
		user_id: number | null;
		/** `propriétaire` ou `locataire`. */
		type_lien: string;
		utilisateur: { id: number; prenom: string; nom: string } | null;
	}[];
	notes_admin: string | null;
	importe_le: string | null;
	resolu_le: string | null;
}

/** Les compteurs de l'import des lots — `lots_imports.stats_imports`. */
export interface StatsImportLots {
	total: number;
	en_attente: number;
	utilisateur_lie: number;
	lot_lie: number;
	resolu: number;
	ignore: number;
	/** Les lignes qui portent au moins un occupant. */
	avec_user: number;
}

/**  La résolution automatique des copropriétaires — `resolution_lots.resoudre_imports`. */
export interface ResolutionImportLots {
	resolus: number;
	sans_occupant: number;
	hors_perimetre: number;
	/** Une phrase par lot en échec. */
	erreurs: string[];
}

/**  Une règle de vie de la résidence, telle que la LISTE la rend
 *   (`routers/regles_residence.list_regles`, un dict composé à la main). */
export interface RegleResidence {
	id: number;
	titre: string;
	/** Texte riche (HTML), `""` par défaut. */
	contenu: string;
	ordre: number;
	cree_par_id: number;
	cree_le: string | null;
	modifie_le: string | null;
}

/**  Ce que rendent la création et la correction d'une règle : quatre champs
 *   seulement, ni auteur ni dates. */
export type RegleResidenceEcrite = Pick<RegleResidence, 'id' | 'titre' | 'contenu' | 'ordre'>;

/**  Un rapport de diagnostic — `RapportRead` (`routers/diagnostics.py`). */
export interface RapportDiagnostic {
	id: number;
	diagnostic_type_id: number;
	titre: string;
	date_rapport: string | null;
	fichier_nom: string;
	taille_octets: number | null;
	mime_type: string;
	synthese: string | null;
	publie_le: string;
}

/**  Un diagnostic réglementaire et ses rapports, le plus récent d'abord —
 *   `DiagnosticTypeRead` (`routers/diagnostics.py`). */
export interface DiagnosticType {
	id: number;
	code: string;
	nom: string;
	texte_legislatif: string;
	frequence: string | null;
	ordre: number;
	non_applicable: boolean;
	rapports: RapportDiagnostic[];
}

/**  Un contrat proposable comme référence de la fiche de copropriété.
 *
 *   ⚠️ Volontairement pauvre : de quoi reconnaître le contrat dans une liste, et
 *   rien de plus. Les détails viennent de la fiche elle-même une fois le choix
 *   fait — deux chemins pour la même donnée en feraient deux vérités. */
export type ContratCandidat = {
	id: number;
	libelle: string;
	prestataire?: string | null;
	numero_contrat?: string | null;
	date_debut: string;
	actif: boolean;
};

/**  Une entrée du carnet d'entretien — un fait daté qui concerne le bâti.
 *
 *   `equipement` porte le CODE d'un équipement (`'ascenseur'`), pas son
 *   libellé : celui-ci vient du cache des équipements (`#lib/equipements`),
 *   administrés depuis #2442.
 */
export interface EntreeCarnet {
	date: string;
	libelle: string;
	origine: 'contrat' | 'intervention' | 'affaire';
	detail: string;
	/**  Le n° d'une affaire (`TK-109008`) — le pied de la carte le dit, comme celui
	 *   d'une carte d'affaire. Vide pour un contrat ou une intervention. */
	numero?: string | null;
	/**  La VALEUR de la catégorie d'une affaire — l'écran rend son libellé. */
	categorie?: string | null;
	equipement: string | null;
	/**  Les codes de périmètre de la ligne — rendus par `perimetreLabel`, comme
	 *   partout ailleurs. Remplace `batiment_id` : un contrat sur « Parking » n'a
	 *   pas de bâtiment, et n'en est pas moins situé. */
	perimetre: string[];
	lien: string;
	alerte: string | null;
	/**  La synthèse VALIDÉE de l'affaire (#1643) — rendue dans la partie pliée. */
	synthese?: SyntheseAffaire | null;
	/**  L'aperçu de la carte, en HTML riche : « Ce qui s'est passé » d'une synthèse
	 *   validée, sinon la demande de l'affaire ; vide pour un contrat. Le choix est
	 *   fait par le serveur (`carnet_entretien._joindre_syntheses`). */
	extrait: string;
}

export interface Carnet {
	entrees: EntreeCarnet[];
	total: number;
}

/**  Un intervenant et la durée moyenne de son étape « Chez le prestataire ». */
export interface PrestataireLent {
	prestataire_id: number;
	nom: string;
	jours: number;
	nombre: number;
}

/**  Les moyennes d'une catégorie d'affaire du carnet sur l'exercice. */
export interface CategorieBilan extends ResumeAffaires {
	categorie: string;
	prestataires: PrestataireLent[];
}

/**  Le bilan d'un exercice (#1645) — `routers/carnet.BilanCarnet`. `fin` est le
 *   DERNIER jour de l'exercice, inclus. */
export interface BilanCarnet {
	exercice: ExerciceLu & { debut: string; fin: string };
	exercices: ExerciceLu[];
	categories: CategorieBilan[];
	nombre: number;
}

/**  Le carnet d'entretien — réservé aux copropriétaires, au CS et à l'admin
 *   (décret n° 2001-477, arbitré le 10/09/2026). Le droit est tenu par
 *   `require_proprietaire` côté serveur ; l'écran ne fait que s'y conformer. */
export const carnet = {
	/**  `perimetre` est un CODE de l'arborescence (`'bat:3'`, `'parking'`), pas un
	 *   identifiant de bâtiment : c'est ce qui rend le filtre dynamique — un
	 *   périmètre créé en administration devient filtrable sans rien déployer. */
	lire: (perimetre?: string | null) =>
		api.get<Carnet>(
			`/carnet-entretien${perimetre ? `?perimetre=${encodeURIComponent(perimetre)}` : ''}`,
		),
	/**  Le bilan d'un exercice — RÉSERVÉ au conseil syndical (`require_cs_or_admin`,
	 *   arbitré le 04/10/2026). `exercice` est l'année où il commence ; absent,
	 *   l'exercice en cours. */
	metriques: (exercice?: number | null) =>
		api.get<BilanCarnet>(`/carnet-entretien/metriques${exercice ? `?exercice=${exercice}` : ''}`),
};

export const copropriete = {
	get: () => api.get<Copropriete>('/copropriete'),
	update: (data: unknown) => api.patch<Copropriete>('/copropriete', data),
	batiments: () => api.get<Batiment[]>('/copropriete/batiments'),
	/**  Les contrats parmi lesquels la fiche DÉSIGNE sa référence.
	 *
	 *   `section` vaut `'assurance'` ou `'syndic'` — le serveur la valide contre
	 *   une liste blanche, jamais contre l'énumération brute. */
	contratsCandidats: (section: 'assurance' | 'syndic') =>
		api.get<ContratCandidat[]>(`/copropriete/contrats-candidats/${section}`),
};

/**
 *  Un de MES lots — `LotRead` (`api/app/routers/lots.py`).
 *
 *  Déclaré dans « Mes lots » sous le nom `LotDetail` jusqu'au 01/10/2026 (#779,
 *  #1044) : le client rendait `any[]`, l'écran retypait. Le jour où la vue de la
 *  gestion locative en a eu besoin aussi, il aurait fallu une deuxième copie.
 */
export interface MonLot {
	id: number;
	numero: string;
	type: string;
	type_appartement: string | null;
	etage: number | null;
	superficie: number | null;
	batiment_id: number | null;
	batiment_nom: string | null;
	est_logement_de_reference: boolean;
	/** Mon lien à ce lot : `locataire` pour un lot que je LOUE, sinon propriétaire, bailleur… */
	type_lien: string | null;
	/** La nature selon le règlement — `logement`, `commerce`, `cave`, `parking`, `divers` (#2212). */
	nature: string | null;
	/** La porte ou la place, ce que le résident dit (« 5 & 6 »). */
	numero_usage: string | null;
	/** Le nœud qui DESSERT le lot — `null` pour un accès direct. */
	circulation: PerimetreDuLot | null;
	/** Les périmètres qui le concernent : situé dans, desservi par. */
	perimetres: PerimetreDuLot[];
	/** Ses tantièmes par clé — `null` quand le lecteur n'a pas à les voir (un locataire). */
	quotes_parts: QuotePartLot[] | null;
	/** La phrase qui explique ce que le lot emporte (`utils/lots_explication`). */
	explication: string | null;
	/** Ce que le propriétaire doit savoir de son lot (`utils/alertes_lot`) — jamais bloquant. */
	alertes: ConstatPatrimoine[];
}

/** Un périmètre d'un lot — `PerimetreDuLot` (`utils/lecture_lots.py`). */
export interface PerimetreDuLot {
	code: string;
	libelle: string;
	relation: 'situe_dans' | 'desservi_par' | 'circulation';
	/** Posé par la dérivation, ou à la main dans l'administration. */
	derive: boolean;
}

/** La part d'un lot dans une clé de charges — `QuotePart` (`utils/lecture_lots.py`). */
export interface QuotePartLot {
	cle: string;
	libelle: string;
	numerateur: number;
	denominateur: number;
	/** Ce que la clé finance — « Bât. 3 › Ascenseur » —, `null` si le règlement ne le rattache à rien. */
	perimetre: string | null;
	/** Combien de lots contribuent à cette clé. */
	nb_lots: number;
	/** La somme des parts de tous les lots : ce qu'on contrôle contre le dénominateur. */
	somme: number;
	/** Ce que la clé finance, selon le règlement (« l'escalier des deux sous-sols », #2251). */
	description: string | null;
	/** Ce qu'il faut savoir de la clé quand ses parts ne font pas le dénominateur (#2251). */
	note: string | null;
	/** Faux : prévue au règlement, non appelée par le syndic en ce moment (#2252). */
	appelee: boolean;
	/** Son libellé sur l'appel de fonds, quand le conseil l'a saisi (#2252). */
	libelle_syndic: string | null;
}

/** Un lot que le locataire peut se dire louer — `LotPropose` (`routers/lots.py`). */
export interface LotPropose extends MonLot {
	/** Les badges que la location de ce lot remet, par type d'accès. */
	acces: Record<string, number>;
}

/** Les trois questions du locataire — `PropositionsLocation` (`routers/lots.py`). */
export interface PropositionsLocation {
	proprietaire: string | null;
	appartement: LotPropose[];
	cave: LotPropose[];
	parking: LotPropose[];
}

/**  Le compte rendu de l'import des lots — `upload_import_lots` (`routers/lots_imports.py`) :
 *   celui du tableur, puis celui de la résolution automatique (`resoudre_imports`),
 *   ses clés préfixées par `auto_`. L'écran lisait d'anciens noms de compteurs
 *   (`auto_skipped_…`) que le serveur ne rendait plus (#1685). */
export interface ResultatImportLots extends CompteImportTableur {
	auto_resolus: number;
	auto_sans_occupant: number;
	auto_hors_perimetre: number;
	auto_erreurs: string[];
}

/**  « Mes périmètres » (#2214) — `MesPerimetres`. L'écran n'y lit qu'une chose :
 *   y a-t-il de quoi filtrer ? Le verdict de chaque élément vient du serveur
 *   (`me_concerne`), jamais d'une règle recomposée ici (#2215). */
export interface MesPerimetres {
	batiments: string[];
	desservis: string[];
}

export const lots = {
	mesList: () => api.get<MonLot[]>('/lots/mes-lots'),
	mesPerimetres: () => api.get<MesPerimetres>('/lots/mes-perimetres'),
	//  Le locataire dit ce qu'il loue, d'après le fichier des lots du syndic
	//  (04/10/2026) : les lots proposés, puis sa réponse.
	propositionsLocation: () => api.get<PropositionsLocation>('/lots/ma-location/propositions'),
	declarerLocation: (lot_ids: number[]) =>
		api.post<Record<string, number>>('/lots/ma-location', { lot_ids }),
	//  🔴 `get` A ÉTÉ RETIRÉE (12/09/2026, #932), avec son endpoint : les écrans
	//  tiennent leurs lots par `mesList()` / `tous()` et travaillent dessus.
	//  Relire un lot seul donnait un second exemplaire du même objet, libre de
	//  diverger de la liste affichée — exactement le motif de `getBail` (#801).
	//  L'étage d'UN de mes lots, depuis le profil (#835). Le seul champ du
	//  patrimoine qu'un occupant écrit lui-même : arbitré le 09/09/2026, c'est
	//  lui qui sait à quel étage il vit.
	majEtage: (id: number, etage: number | null) => api.patch<MonLot>(`/lots/${id}/etage`, { etage }),
	// Admin — tous les lots
	//  `LotRead` aussi : `type_lien` y vaut `null`, le lot n'est celui de personne ici.
	tous: () => api.get<MonLot[]>('/lots/admin/tous'),
	// Admin — import staging
	uploadImport: (file: File, remplacer = false) =>
		uploadExcel<ResultatImportLots>('/lots/admin/imports/upload', file, remplacer),
	listImports: (statut?: string, tri?: string) =>
		api.get<LigneImportLot[]>(`/lots/admin/imports${buildQuery({ statut, tri })}`),
	statsImports: () => api.get<StatsImportLots>('/lots/admin/imports/stats'),
	autoMatchImports: () => api.post<{ matches: number }>('/lots/admin/imports/auto-match', {}),
	autoResoudreImports: () =>
		api.post<ResolutionImportLots>('/lots/admin/imports/auto-resoudre', {}),
	patchImport: (
		id: number,
		data: {
			lot_id?: number | null;
			utilisateurs?: { user_id: number; type_lien: string }[];
			notes_admin?: string | null;
		},
	) => api.patch<LigneImportLot>(`/lots/admin/imports/${id}`, data),
	resoudreImport: (id: number) =>
		api.post<{ ok: boolean; lot_id: number; nb_liens: number }>(
			`/lots/admin/imports/${id}/resoudre`,
			{},
		),
	ignorerimport: (id: number) => api.post<{ ok: boolean }>(`/lots/admin/imports/${id}/ignorer`, {}),
};

export const reglesResidence = {
	list: () => api.get<RegleResidence[]>('/regles-residence'),
	create: (data: { titre: string; contenu?: string }) =>
		api.post<RegleResidenceEcrite>('/regles-residence', data),
	update: (id: number, data: { titre?: string; contenu?: string; ordre?: number }) =>
		api.patch<RegleResidenceEcrite>(`/regles-residence/${id}`, data),
	remove: (id: number) => api.delete(`/regles-residence/${id}`),
};

export const diagnostics = {
	listTypes: () => api.get<DiagnosticType[]>('/diagnostics/types'),
	uploadRapport: async (
		typeId: number,
		titre: string,
		dateRapport: string | undefined,
		file: File,
	): Promise<RapportDiagnostic> => {
		return postFormData<RapportDiagnostic>(`/diagnostics/types/${typeId}/rapports`, {
			titre,
			date_rapport: dateRapport,
			file,
		});
	},
	// `synthese` est bien géré par l'API (`if "synthese" in body.model_fields_set`)
	// et stocké sur le modèle : c'est la signature d'ici qui était en retard.
	updateRapport: (
		id: number,
		data: { titre?: string; date_rapport?: string | null; synthese?: string | null },
	) => api.patch<RapportDiagnostic>(`/diagnostics/rapports/${id}`, data),
	deleteRapport: (id: number) => api.delete(`/diagnostics/rapports/${id}`),
	/** Retirer le fichier du rapport — le geste du document (`documents.retirerFichier`). */
	retirerFichier: (id: number) =>
		api.delete<RapportDiagnostic>(`/diagnostics/rapports/${id}/fichier`),
	downloadUrl: (id: number) => `${BASE}/diagnostics/rapports/${id}/télécharger`,
	toggleNonApplicable: (typeId: number, nonApplicable: boolean) =>
		api.patch<DiagnosticType>(`/diagnostics/types/${typeId}/non-applicable`, {
			non_applicable: nonApplicable,
		}),
};
