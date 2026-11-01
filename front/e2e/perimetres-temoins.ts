/*
 *  Un nœud d'arborescence témoin, tel que `GET /perimetres` le rend : les specs
 *  qui ouvrent Admin › Périmètres ne posent que ce qui les distingue.
 */
import type { Perimetre } from '../src/lib/perimetres';

export function noeud(
	champs: Partial<Perimetre> & Pick<Perimetre, 'id' | 'code' | 'libelle'>,
): Perimetre {
	return {
		parent: null,
		libelle_court: champs.libelle,
		description: '',
		icone: null,
		batiment_id: null,
		profondeur: 0,
		ordre: 0,
		actif: true,
		portee_globale: false,
		concerne_tous: false,
		selectionnable: true,
		privatif: false,
		hors_copropriete: false,
		utilise: false,
		nb_descendants: 0,
		dupliquable: false,
		copiable: false,
		deplacements: [],
		...champs,
	};
}
