/**
 *  Le classement d'un PRESTATAIRE et d'un CONTRAT dans la gouttière de leur
 *  carte (la page Affaires devenue le standard du site, 10/10/2026, #1819).
 *
 *  Les tables (`EQUIPEMENTS`, `TYPES_PRESTATAIRE`) restent dans
 *  `#lib/prestataires` : ce module n'y ajoute que la marque de gouttière de
 *  chaque valeur — pictogramme au trait (`#lib/icones-svg.json`) et mot abrégé.
 *  Une valeur sans marque n'a pas de classement : `classeDe` rend `null`.
 */
import { classeDe, type ClasseGouttiere, type MarqueGouttiere } from '#lib/gouttiere.ts';
import { EQUIPEMENTS, TYPES_PRESTATAIRE } from '#lib/prestataires.ts';

/**  ⚠️ Deux types n'ont pas de pictogramme au catalogue — `nettoyage` (balai)
 *   et `vmc` (ventilateur) : ils prennent celui de « Autre », et leur mot
 *   abrégé dit la vérité. À remplacer quand le catalogue les aura. */
const MARQUES_EQUIPEMENT: Record<string, MarqueGouttiere> = {
	ascenseur: ['arrow-up-down', 'ASC.'],
	chauffage_collectif: ['flame', 'CHAUF.'],
	eau: ['droplet', 'EAU'],
	electricite: ['zap', 'ÉLEC.'],
	espaces_verts: ['trees', 'VERTS'],
	extincteurs: ['shield-half', 'EXTINC.'],
	interphone_digicode: ['bell', 'INTERPH.'],
	menuiseries: ['door-closed', 'MENUIS.'],
	nettoyage: ['wrench', 'NETT.'],
	plomberie: ['droplet', 'PLOMB.'],
	pompe: ['settings', 'POMPE'],
	porte_parking: ['square-parking', 'PARK.'],
	serrurerie: ['key-round', 'SERR.'],
	toiture: ['home', 'TOIT.'],
	vmc: ['wrench', 'VMC'],
	assurance: ['shield', 'ASSUR.'],
	syndic: ['building-2', 'SYNDIC'],
	autre: ['wrench', 'AUTRE'],
};

const MARQUES_PRESTATAIRE: Record<string, MarqueGouttiere> = {
	maintenance_depannage: ['wrench', 'MAINT.'],
	travaux: ['hard-hat', 'TRAV.'],
	reglementaire: ['shield-check', 'RÉGL.'],
	etudes_expertise: ['search', 'ÉTUDES'],
	gestion: ['building-2', 'GEST.'],
};

/**  Le classement d'un CONTRAT : son type d'équipement — la clé qui range déjà
 *   les contrats en groupes (`OngletContrats`) ; la fréquence est un rythme et
 *   reste sur la dernière ligne. */
export function classeEquipement(val: string | null | undefined): ClasseGouttiere | null {
	return classeDe(EQUIPEMENTS, MARQUES_EQUIPEMENT, val);
}

/**  Le classement d'un PRESTATAIRE : sa catégorie, la clé qui range déjà
 *   l'annuaire en groupes (`OngletPrestataires`). */
export function classeTypePrestataire(val: string | null | undefined): ClasseGouttiere | null {
	return classeDe(TYPES_PRESTATAIRE, MARQUES_PRESTATAIRE, val);
}
