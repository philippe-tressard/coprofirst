//  L'ENTRETIEN PÉRIODIQUE à l'écran — le nom et la teinte de chaque état de
//  visite, et les compteurs du bilan de l'année (#2043).
//
//  Ils vivaient dans `VueEntretienPeriodique`, retirée quand le Suivi des
//  affaires a pris le mode « Suivi entretiens périodiques » : le tableau du
//  suivi et le bilan les lisent ici. L'état est CALCULÉ au serveur
//  (`utils/entretien_periodique.etat_visite`) ; ce module ne fait que le nommer.

import type { EtatVisite } from '#lib/api/index.ts';

/** Le nom de chaque état, et la teinte de son badge (`Badge teinte=`). */
export const ETATS_VISITE: Record<EtatVisite, { libelle: string; teinte: string }> = {
	realisee: { libelle: '✅ Réalisée', teinte: 'badge-green' },
	non_realisee: { libelle: '⚠️ Non réalisée', teinte: 'badge-red' },
	a_venir: { libelle: '⏳ À venir', teinte: 'badge-blue' },
	a_planifier: { libelle: '📅 À planifier', teinte: 'badge-orange' },
	annulee: { libelle: 'Annulée', teinte: 'badge-gray' },
};

/** Les compteurs du bilan : « Annulée » n'en a pas, elle ne dit rien d'un entretien fait. */
export const COMPTEURS_VISITE: readonly { etat: EtatVisite; libelle: string }[] = [
	{ etat: 'realisee', libelle: 'Réalisées' },
	{ etat: 'non_realisee', libelle: 'Non réalisées' },
	{ etat: 'a_venir', libelle: 'À venir' },
	{ etat: 'a_planifier', libelle: 'À planifier' },
];
