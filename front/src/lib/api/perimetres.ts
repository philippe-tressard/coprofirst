//  L'ARBORESCENCE des périmètres — lecture pour tout connecté, gestes
//  d'administration (créer, corriger, supprimer, dupliquer, copier, déplacer).
//
//  ⚠️ Fragment de `lib/api/` — sorti de `patrimoine.ts` le 01/11/2026 (#2450),
//  quand la copie et les flèches l'ont fait passer au-delà de 500 lignes. La
//  surface publique ne bouge pas : `index.ts` réexporte tout.
import { api } from './client';
import type { Perimetre as PerimetreDTO, SensDeplacement } from '#lib/perimetres/index.ts';

/**
 * Périmètres — l'arborescence « où se situe une demande ».
 *
 * Lecture pour tout utilisateur connecté, écriture réservée à l'administration.
 * Le type `Perimetre` vit dans `#lib/perimetres`, qui n'importe rien : c'est ce
 * qui permet à `perimetreLabel()` de rester synchrone dans les gabarits.
 */
/**  Ce qu'une écriture envoie : la lecture rend toujours un `libelle_court`, mais
 *   `PerimetreCreate` / `PerimetreUpdate` l'acceptent à `null` — un abrégé vidé. */
type EcriturePerimetre = Partial<Omit<PerimetreDTO, 'libelle_court'>> & {
	libelle_court?: string | null;
};

export const perimetres = {
	list: () => api.get<PerimetreDTO[]>('/perimetres'),
	create: (data: EcriturePerimetre & { code: string; libelle: string }) =>
		api.post<PerimetreDTO>('/perimetres', data),
	update: (id: number, data: EcriturePerimetre) =>
		api.patch<PerimetreDTO>(`/perimetres/${id}`, data),
	/**  `avecDescendants` : la branche entière, après une confirmation qui la
	 *   compte. Sans lui, le serveur refuse un nœud qui a des enfants. */
	remove: (id: number, avecDescendants = false) =>
		api.delete(`/perimetres/${id}${avecDescendants ? '?avec_descendants=true' : ''}`),
	/**  Copie le nœud et toute sa descendance. `batiment_id` est exigé quand la
	 *   source est un bâtiment : il décide qui lit, il ne se recopie pas. */
	dupliquer: (
		id: number,
		data: {
			code: string;
			libelle: string;
			description: string;
			batiment_id: number | null;
			/**  Le numéro d'un bâtiment que le serveur crée pour la copie (#1945),
			 *   exclusif de `batiment_id`. */
			nouveau_batiment: string | null;
		},
	) => api.post<PerimetreDTO>(`/perimetres/${id}/dupliquer`, data),
	/**  Pose une copie du nœud — et de sa branche — sous chacun des `parents`
	 *   (leurs codes) : même nom, mêmes caractéristiques. Tout ou rien. */
	copier: (id: number, parents: string[]) =>
		api.post<PerimetreDTO[]>(`/perimetres/${id}/copier`, { parents }),
	/**  Une des quatre flèches d'un nœud ; le serveur renumérote la fratrie. */
	deplacer: (id: number, sens: SensDeplacement) =>
		api.post<PerimetreDTO>(`/perimetres/${id}/deplacer`, { sens }),
};
