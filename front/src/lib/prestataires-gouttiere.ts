/**
 *  Le classement d'un PRESTATAIRE dans la gouttière de sa carte (la page
 *  Affaires devenue le standard du site, 10/10/2026, #1819).
 *
 *  La table (`TYPES_PRESTATAIRE`) reste dans `#lib/prestataires` : ce module n'y
 *  ajoute que la marque de gouttière de chaque valeur — pictogramme au trait
 *  (`#lib/icones-svg.json`) et mot abrégé. Une valeur sans marque n'a pas de
 *  classement : `classeDe` rend `null`.
 *
 *  Celui d'un CONTRAT — son équipement — est parti avec les équipements, qui
 *  s'administrent et portent leur icône et leur abréviation (#2442) :
 *  `classeEquipement` de `#lib/equipements`.
 */
import { classeDe, type ClasseGouttiere, type MarqueGouttiere } from '#lib/gouttiere.ts';
import { TYPES_PRESTATAIRE } from '#lib/prestataires.ts';

const MARQUES_PRESTATAIRE: Record<string, MarqueGouttiere> = {
	maintenance_depannage: ['wrench', 'MAINT.'],
	travaux: ['hard-hat', 'TRAV.'],
	reglementaire: ['shield-check', 'RÉGL.'],
	etudes_expertise: ['search', 'ÉTUDES'],
	gestion: ['building-2', 'GEST.'],
};

/**  Le classement d'un PRESTATAIRE : sa catégorie, la clé qui range déjà
 *   l'annuaire en groupes (`OngletPrestataires`). */
export function classeTypePrestataire(val: string | null | undefined): ClasseGouttiere | null {
	return classeDe(TYPES_PRESTATAIRE, MARQUES_PRESTATAIRE, val);
}
