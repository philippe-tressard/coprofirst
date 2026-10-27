//  Les AFFAIRES LIÉES (#1342) — ce qu'un lecteur voit d'une affaire nommée : dans
//  la section « Affaires liées », le choix (`GET /tickets/choix`), la fiche, et
//  les candidates d'une fusion (#1704, #2083).
//
//  Sortis de `types.ts` le 23/10/2026 (#2173) : la date de création y entrait, et
//  le fichier passait son plafond de 500 lignes. Une notion qui a sa section, son
//  choix et sa fusion a sa place à elle — `types.ts` les ré-exporte, les écrans
//  qui les lisent là n'ont rien à changer. Les types sont lus sur
//  `schemas_communs.AffaireLieeLue` et `routers/tickets/fusion.CandidateFusion`.

/**  Une affaire liée, telle que CE lecteur la voit (#1342) : de quoi la
 *   reconnaître. Le serveur ne rend que celles qu'il peut lire. */
export interface AffaireLiee {
	id: number;
	numero: string;
	titre: string;
	/** L'état — le « Suivi » de l'écran. */
	statut: string;
	/** ISO, rendu en UTC (`Z`) — `fmtDate` le lit (#2173). */
	cree_le: string;
	/** 🔀 Absorbée par une autre affaire (#2186) : son état est HÉRITÉ de la
	 *  principale, elle ne se fusionne plus. */
	fusionnee?: boolean;
}

/**  Une affaire liée proposée à la FUSION (#1704, #2173) — `routers/tickets/fusion`.
 *   `fusionnable` faux : lue par moins de monde que l'affaire qui l'absorberait, et `motif` le dit. */
export interface CandidateFusion extends AffaireLiee {
	fusionnable: boolean;
	motif: string | null;
	/** Le plan pour AUTORISER une fusion refusée pour fuite de lecture (`null` si elle est possible). */
	conciliation: Conciliation | null;
}

/**  Une personne que la fusion ferait lire autrement — nommée : la confirmation du conseil l'est. */
export interface PersonneConcernee {
	id: number;
	nom: string;
}

/** Une section d'accès qui diffère entre la principale et l'autre affaire. */
export interface EcartFusion {
	champ: string;
	libelle: string;
	principale: string;
	absorbee: string;
}

export type CodeConciliation = 'inverser' | 'restreindre' | 'elargir';

/** Ce que dirait la principale une fois l'option posée. */
export interface ResultatConciliation {
	perimetre: string;
	destinataires: string;
	acces: string;
}

/**  Une façon d'autoriser la fusion, avec ce qu'elle fait lire (`utils/fusion_conciliation`). */
export interface OptionConciliation {
	code: CodeConciliation;
	libelle: string;
	disponible: boolean;
	/** Pourquoi elle ne l'est pas. */
	pourquoi: string | null;
	/** Ceux qui liront ce qu'ils ne lisaient pas — à confirmer par leur nom. */
	exposes: PersonneConcernee[];
	/** Combien perdent l'accès à un fil qu'ils lisaient. */
	perdants: number;
	resultat: ResultatConciliation | null;
	/** Vrai si `exposes` n'est pas vide : la confirmation nominative est exigée. */
	consentement: boolean;
}

export interface Conciliation {
	ecarts: EcartFusion[];
	options: OptionConciliation[];
}

/** Ce que le corps d'une clôture ou d'une fusion envoie pour UNE affaire conciliée. */
export interface ChoixConciliation {
	affaire_id: number;
	option: 'restreindre' | 'elargir';
	/** Les identifiants des personnes montrées à l'écran — le serveur exige la même liste. */
	confirmes: number[];
}
