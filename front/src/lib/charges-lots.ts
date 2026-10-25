/**
 * Les charges de mes lots, lues de `MonLot.quotes_parts` — des fonctions PURES (#2215, #2251).
 *
 * Un copropriétaire de plusieurs lots (un logement, une cave, deux places) contribue à une
 * clé par la SOMME de ses parts. Le tableau croisé de « Mes lots » (maquette A, arbitrée le
 * 25/10/2026) le montre d'un coup : une ligne par clé, une colonne par lot, puis le total.
 * Il remplace trois rendus qui disaient la même chose (le total par clé, le tableau de
 * chaque lot, la phrase de la carte) et ne nommaient pas les lots — « où est ma cave ? ».
 *
 * Le serveur reste la source de chaque part, de ce que finance la clé et de sa note ; ici
 * on ne fait que les RANGER et les ADDITIONNER — jamais les recalculer.
 */
import { writable } from 'svelte/store';
import type { MonLot, QuotePartLot } from '$lib/api';
import { lotTypeLabel } from '$lib/utils';

/** Ce que vaut un tableau de charges : une lecture du règlement, jamais un décompte. */
/** La fiche du syndic dans l'annuaire — ses coordonnées, déjà dans l'application. */
export const FICHE_DU_SYNDIC = '/annuaire#syndic';

export const AVIS_CHARGES =
	'À titre d’information : ces parts sont lues dans le règlement de copropriété. Ce que ' +
	'vous payez, seuls les appels de fonds et les comptes tenus par le syndic le disent.';

/** « Logement 15 », « Cave 417 », « Place 450 » — la nature du règlement, sinon le type. */
export function nomDuLot(lot: Pick<MonLot, 'numero' | 'nature' | 'type'>): string {
	const nature = lot.nature ?? lot.type;
	//  « Place » et non « Parking » : c'est ainsi qu'un résident nomme son emplacement.
	return `${nature === 'parking' ? 'Place' : lotTypeLabel(nature)} ${lot.numero}`;
}

export interface ColonneDeLot {
	id: number;
	nom: string;
}

export interface LigneDeCle {
	cle: string;
	libelle: string;
	/** Ce que la clé finance, selon le règlement — `null` si l'acte ne le dit pas. */
	description: string | null;
	/** Ce qu'il faut savoir de la clé (ses parts ne font pas le dénominateur), du serveur. */
	note: string | null;
	/** Faux : prévue au règlement, non appelée par le syndic en ce moment (#2252). */
	appelee: boolean;
	/** Son libellé sur l'appel de fonds — le rapprochement ligne à ligne (#2252). */
	libelleSyndic: string | null;
	nbLots: number;
	denominateur: number;
	/** La part de chacun de mes lots, par identifiant ; absent = il n'y contribue pas. */
	parts: Record<number, number>;
	total: number;
}

export interface TableauDesCharges {
	colonnes: ColonneDeLot[];
	/** Les clés que le syndic appelle : les lignes de l'appel de fonds. */
	lignes: LigneDeCle[];
	/** Prévues au règlement, non appelées en ce moment : repliées, jamais cachées — le jour
	 *  où le syndic en appelle une, la question inverse se poserait (#2252). */
	nonAppelees: LigneDeCle[];
}

/** Le tableau croisé de mes charges, dans l'ordre des clés que le serveur rend. */
export function tableauDesCharges(
	lots: Pick<MonLot, 'id' | 'numero' | 'nature' | 'type' | 'quotes_parts'>[],
): TableauDesCharges {
	const avecParts = lots.filter((l) => l.quotes_parts?.length);
	const lignes = new Map<string, LigneDeCle>();
	for (const lot of avecParts) {
		for (const part of lot.quotes_parts ?? ([] as QuotePartLot[])) {
			let ligne = lignes.get(part.cle);
			if (!ligne) {
				ligne = {
					cle: part.cle,
					libelle: part.libelle,
					description: part.description ?? null,
					note: part.note ?? null,
					appelee: part.appelee ?? true,
					libelleSyndic: part.libelle_syndic ?? null,
					nbLots: part.nb_lots,
					denominateur: part.denominateur,
					parts: {},
					total: 0,
				};
				lignes.set(part.cle, ligne);
			}
			ligne.parts[lot.id] = part.numerateur;
			ligne.total += part.numerateur;
		}
	}
	const toutes = [...lignes.values()];
	return {
		colonnes: avecParts.map((l) => ({ id: l.id, nom: nomDuLot(l) })),
		lignes: toutes.filter((l) => l.appelee),
		nonAppelees: toutes.filter((l) => !l.appelee),
	};
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
