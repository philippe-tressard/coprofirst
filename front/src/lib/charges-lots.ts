/**
 * Ce que l'écran des charges de mes lots partage entre ses composants (#2215, #2251).
 *
 * 🔴 Le tableau croisé (une ligne par clé, une colonne par lot, puis le total) se rangeait
 * et s'additionnait ICI jusqu'au 04/11/2026 (`tableauDesCharges`, `nomDuLot`). L'app iOS ne
 * recopie aucune règle du site : elle renvoyait au site. Le serveur le sert prêt à afficher
 * (`GET /lots/mes-charges`, `api/app/utils/tableau_charges.py`, #2507) ; il ne reste ici
 * que la lecture d'une case, le surlignage et les phrases de l'écran.
 */
import { writable } from 'svelte/store';
import type { LigneDeCle, MonLot } from '#lib/api/index.ts';

/** Ce que vaut un tableau de charges : une lecture du règlement, jamais un décompte. */
/** La fiche du syndic dans l'annuaire — ses coordonnées, déjà dans l'application. */
export const FICHE_DU_SYNDIC = '/annuaire#syndic';

export const AVIS_CHARGES =
	'À titre d’information : ces parts sont lues dans le règlement de copropriété. Ce que ' +
	'vous payez, seuls les appels de fonds et les comptes tenus par le syndic le disent.';

/** Ma part d'un lot dans une clé — `undefined` quand ce lot n'y contribue pas. */
export function partDuLot(ligne: Pick<LigneDeCle, 'parts'>, lotId: number): number | undefined {
	return ligne.parts.find((p) => p.lot_id === lotId)?.numerateur;
}

/**  Le lot dont la carte a demandé à voir sa colonne (« Voir sa colonne dans le tableau
 *   des charges ») : le tableau la surligne un instant. */
export const lotSurligne = writable<number | null>(null);

/** « Porte ou place 5 & 6 · Situé dans Bât. 1 · Desservi par Bât. 3 › Ascenseur » — une ligne. */
export function designationDuLot(lot: Pick<MonLot, 'numero_usage' | 'perimetres'>): string {
	const lieux = (relation: 'situe_dans' | 'desservi_par') =>
		lot.perimetres.filter((p) => p.relation === relation).map((p) => p.libelle);
	const situe = lieux('situe_dans');
	const dessert = lieux('desservi_par');
	return [
		lot.numero_usage ? `Porte ou place ${lot.numero_usage}` : null,
		situe.length ? `Situé dans ${situe.join(', ')}` : null,
		dessert.length ? `Desservi par ${dessert.join(', ')}` : null,
	]
		.filter(Boolean)
		.join(' · ');
}
