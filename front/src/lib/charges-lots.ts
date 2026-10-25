/**
 * Les charges d'un ou de plusieurs lots, lues de `MonLot.quotes_parts` — des fonctions PURES.
 *
 * Un copropriétaire de plusieurs lots (un logement, une cave, deux places) ne contribue pas
 * à une clé par lot mais par TOTAL : « Ascenseur A » pèse sur lui pour la somme de ses
 * parts. L'écran le dit, au lieu de laisser faire l'addition. Le serveur reste la source de
 * chaque part ; ici on ne fait que les ADDITIONNER — jamais les recalculer.
 */
import type { MonLot, QuotePartLot } from '$lib/api';

export interface TotalDeCle {
	cle: string;
	libelle: string;
	perimetre: string | null;
	numerateur: number;
	denominateur: number;
	/** Combien de lots du lecteur contribuent à cette clé. */
	lots: number;
}

/** Le total de mes parts par clé, dans l'ordre où le serveur les rend. Vide si aucun lot n'en lit. */
export function totauxParCle(lots: Pick<MonLot, 'quotes_parts'>[]): TotalDeCle[] {
	const totaux = new Map<string, TotalDeCle>();
	for (const lot of lots) {
		for (const part of lot.quotes_parts ?? ([] as QuotePartLot[])) {
			const deja = totaux.get(part.cle);
			if (deja) {
				deja.numerateur += part.numerateur;
				deja.lots += 1;
			} else {
				totaux.set(part.cle, {
					cle: part.cle,
					libelle: part.libelle,
					perimetre: part.perimetre,
					numerateur: part.numerateur,
					denominateur: part.denominateur,
					lots: 1,
				});
			}
		}
	}
	return [...totaux.values()];
}

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
