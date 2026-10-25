/**
 * Admin › Copropriété › Lots — constats, re-dérivation, périmètres posés à la main
 * (`routers/lots_admin.py`, #2216). La liste des lots est `lots.tous()`, qui rend
 * déjà leur désignation : ce client n'en rend pas une seconde.
 */
import { api } from './client';
import type { ConstatPatrimoine } from './etat-descriptif';

export type RelationLotPerimetre = 'situe_dans' | 'desservi_par';

/** Une clé de charges et ce que le conseil en règle — `CleRead` (`routers/lots_admin.py`, #2252). */
export interface CleDeChargesReglee {
	id: number;
	code: string;
	libelle: string;
	denominateur: number;
	description: string | null;
	/** Faux : le syndic ne l'appelle pas en ce moment. */
	appelee: boolean;
	/** Son libellé sur l'appel de fonds. */
	libelle_syndic: string | null;
}

export const lotsAdmin = {
	constats: () => api.get<ConstatPatrimoine[]>('/lots/admin/constats'),
	rederiver: () => api.post<{ modifies: number }>('/lots/admin/rederiver', {}),
	poserPerimetre: (lotId: number, perimetreId: number, relation: RelationLotPerimetre) =>
		api.post<{ ok: boolean }>(`/lots/admin/${lotId}/perimetres`, {
			perimetre_id: perimetreId,
			relation,
		}),
	retirerPerimetre: (lotId: number, perimetreId: number, relation: RelationLotPerimetre) =>
		api.delete(`/lots/admin/${lotId}/perimetres/${perimetreId}/${relation}`),
	cles: () => api.get<CleDeChargesReglee[]>('/lots/admin/cles'),
	reglerCle: (
		id: number,
		champs: Partial<Pick<CleDeChargesReglee, 'appelee' | 'libelle_syndic'>>,
	) => api.patch<CleDeChargesReglee>(`/lots/admin/cles/${id}`, champs),
};
