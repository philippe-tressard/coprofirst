/**
 * Les **pastilles de périmètre** d'une carte du calendrier — leur couleur, leur
 * libellé, et le dédoublonnage qui rend les deux sûrs.
 *
 * Extrait de `calendrier/+page.svelte` le 02/09/2026 : le plafond de modularité a
 * refusé les dix-neuf lignes que le dédoublonnage y ajoutait. Comme les refus
 * précédents, il désignait un PLACEMENT — le rendu d'une pastille n'a rien à
 * faire dans l'écran qui gère aussi le kanban, les événements et leur formulaire.
 *
 * ⚠️ Ces fonctions sont **pures** et ne lisent aucun store : `noeudPerimetre` et
 * `perimetreLabelUn` viennent de `#lib/utils`, qui porte déjà l'arbre. Les
 * remonter ici aurait fait une seconde lecture de la même source.
 */
import {
	estPerimetreParDefaut,
	noeudPerimetre,
	perimetreDefautListe,
	perimetreLabel,
	perimetreLabelUn,
} from '#lib/utils.ts';
import {
	codeDeTeinte,
	rangPremierNiveau,
	TEINTE_COPROPRIETE,
	teinteDuCode,
} from '#lib/perimetres/teinte.ts';
import { codesPremierNiveau } from '#lib/perimetres/index.ts';

/** Une pastille : son code (la clé), son libellé court et sa couleur. */
export interface PastillePerimetre {
	code: string;
	label: string;
	color: string;
}

//  🔴 La teinte vit dans `#lib/perimetres/teinte` — palette, choix de l'ancêtre
//  de premier niveau, et leur self-test. Ce fichier-ci rend des pastilles ; il
//  ne décide pas des couleurs.
export function couleurPerimetre(code: string): string {
	const base = codeDeTeinte(code, noeudPerimetre);
	//  Le rang parmi les nœuds de premier niveau — lu dans l'arbre, jamais
	//  recalculé : c'est lui qui garantit des couleurs DISTINCTES, là où un
	//  condensat sur neuf teintes collisionne dès le quatrième nœud.
	return teinteDuCode(base, rangPremierNiveau(base, codesPremierNiveau()));
}

//  Le CODE est rendu avec la pastille : c'est lui la clé, pas le libellé.
//  Deux codes différents peuvent porter le même libellé court — « Hall d'entrée »
//  sous deux bâtiments —, et deux clés identiques feraient planter Svelte.
//
//  🔴 Et le dédoublonnage corrige un vrai défaut d'affichage : `perimetre` est
//  une liste de codes séparés par des virgules, écrite par plusieurs chemins ;
//  rien n'y garantissait qu'un code n'y figure qu'une fois, et le doublon
//  affichait deux fois la même pastille.
export function perimetreTags(p: string): PastillePerimetre[] {
	if (estPerimetreParDefaut(p))
		return [
			{
				code: '__defaut__',
				label: '\u{1F3D8}️ ' + ' ' + perimetreLabel(perimetreDefautListe()),
				color: TEINTE_COPROPRIETE,
			},
		];
	const codes = [
		...new Set(
			p
				.split(',')
				.map((s) => s.trim())
				.filter(Boolean),
		),
	];
	return codes.map((s) => ({
		code: s,
		label: noeudPerimetre(s)?.libelle_court ?? perimetreLabelUn(s),
		color: couleurPerimetre(s),
	}));
}
