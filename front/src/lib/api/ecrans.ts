//  Les écrans de hall du conseil syndical (#2770) — `routers/ecrans.py`.
//  Le site ne connaît que les gestes du conseil : lister, confirmer un code court,
//  retirer. L'appairage et la lecture des affiches sont ceux de l'écran (app Apple
//  TV), qui génère son client du contrat publié.
import { api } from './client';

/**  Un écran appairé, tel que le conseil le voit — jamais son jeton. */
export interface EcranHall {
	id: number;
	nom: string;
	perimetre: string;
	/**  Le badge 🔹, servi — vide pour le périmètre par défaut, que le badge tait. */
	perimetre_libelle: string;
	cree_le: string;
	/**  La dernière lecture des affiches — `null` tant qu'il n'a rien lu. */
	vu_le: string | null;
	expire_le: string;
	/**  Échu : il ne lit plus rien jusqu'à un nouvel appairage. */
	echu: boolean;
}

export interface AppairageConfirme {
	nom: string;
	perimetre: string;
	perimetre_libelle: string;
}

export const ecrans = {
	lister: () => api.get<EcranHall[]>('/ecrans'),
	/**  Le code court que l'écran affiche, son nom et son périmètre (un code). */
	confirmer: (corps: { code_court: string; nom: string; perimetre: string }) =>
		api.post<AppairageConfirme>('/ecrans', corps),
	retirer: (id: number) => api.delete(`/ecrans/${id}`),
};
