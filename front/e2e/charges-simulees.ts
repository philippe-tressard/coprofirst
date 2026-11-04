/**
 * **Ce que `GET /lots/mes-charges` rendrait pour ces lots simulés** (#2507) — la
 * réponse à simuler, pas la règle : le serveur range et additionne
 * (`api/app/utils/tableau_charges.py`, éprouvé par `test_libelles_lot_servis.py`).
 * Un spec qui simule des lots avec leurs `quotes_parts` simule ainsi le tableau
 * qui va avec ; le nom de chaque colonne est celui que le lot porte (`nom_du_lot`).
 */
export function chargesSimulees(
	lots: {
		id: number;
		nom_du_lot: string;
		quotes_parts:
			| {
					cle: string;
					libelle: string;
					numerateur: number;
					denominateur: number;
					nb_lots: number;
					description?: string | null;
					note?: string | null;
					appelee?: boolean;
					libelle_syndic?: string | null;
			  }[]
			| null;
	}[],
): {
	colonnes: { lot_id: number; nom: string }[];
	lignes: unknown[];
	non_appelees: unknown[];
} {
	const avecParts = lots.filter((l) => l.quotes_parts?.length);
	type Ligne = Record<string, unknown> & {
		appelee: boolean;
		parts: { lot_id: number; numerateur: number }[];
		total: number;
	};
	const lignes = new Map<string, Ligne>();
	for (const l of avecParts) {
		for (const q of l.quotes_parts ?? []) {
			const ligne =
				lignes.get(q.cle) ??
				lignes
					.set(q.cle, {
						cle: q.cle,
						libelle: q.libelle,
						description: q.description ?? null,
						note: q.note ?? null,
						appelee: q.appelee ?? true,
						libelle_syndic: q.libelle_syndic ?? null,
						nb_lots: q.nb_lots,
						denominateur: q.denominateur,
						parts: [],
						total: 0,
					})
					.get(q.cle)!;
			ligne.parts.push({ lot_id: l.id, numerateur: q.numerateur });
			ligne.total += q.numerateur;
		}
	}
	const toutes = [...lignes.values()];
	return {
		colonnes: avecParts.map((l) => ({ lot_id: l.id, nom: l.nom_du_lot })),
		lignes: toutes.filter((x) => x.appelee),
		non_appelees: toutes.filter((x) => !x.appelee),
	};
}
