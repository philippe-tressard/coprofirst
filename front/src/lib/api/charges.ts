//  Le tableau de MES charges selon le règlement — `GET /lots/mes-charges` (#2507).
//
//  Le serveur le range et l'additionne (`api/app/utils/tableau_charges.py`) : le site
//  et l'app iOS le lisent tels quels. Sorti de `patrimoine.ts`, qui touchait les 500
//  lignes ; le client qui l'appelle (`lots.mesCharges`) y reste, avec les lots.

/** Une colonne du tableau des charges : un de mes lots — `ColonneDeLot` (`utils/tableau_charges`). */
export interface ColonneDeLot {
	lot_id: number;
	nom: string;
}

/** Une clé de charges et ma part lot par lot — `LigneDeCle`. */
export interface LigneDeCle {
	cle: string;
	libelle: string;
	/** Ce que la clé finance, selon le règlement — `null` si l'acte ne le dit pas. */
	description: string | null;
	/** Ce qu'il faut savoir de la clé (ses parts ne font pas le dénominateur). */
	note: string | null;
	/** Faux : prévue au règlement, non appelée par le syndic en ce moment (#2252). */
	appelee: boolean;
	/** Son libellé sur l'appel de fonds (#2252). */
	libelle_syndic: string | null;
	nb_lots: number;
	denominateur: number;
	/** La part de chacun de mes lots qui y contribue, dans l'ordre des colonnes. */
	parts: { lot_id: number; numerateur: number }[];
	total: number;
}

/**  Le tableau de mes charges selon le règlement, rangé et additionné par le serveur —
 *   `TableauCharges` (`GET /lots/mes-charges`, #2507). */
export interface TableauDesCharges {
	colonnes: ColonneDeLot[];
	/** Les clés que le syndic appelle : les lignes de l'appel de fonds. */
	lignes: LigneDeCle[];
	/** Prévues au règlement, non appelées en ce moment : repliées, jamais cachées. */
	non_appelees: LigneDeCle[];
}
