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
}
