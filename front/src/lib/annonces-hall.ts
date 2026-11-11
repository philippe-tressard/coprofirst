//  Les formats d'une affiche de hall — sortis d'`OngletAnnoncesHall.svelte` (#2634).
//  Le type était écrit deux fois (l'onglet et `FormulaireAnnonceHall`).

export type AhFormat = 'auto' | 'a4' | 'a5' | 'a6' | 'a7';

/** Les formats qu'on peut demander pour une affiche, dans leur ordre. */
//  🔒 Table PUBLIÉE aux clients (`tables-clients.json`, #2634) — littérale ; la retirer
//  ou en changer la forme s'annonce (`npm run lint:tables-clients`).
export const AH_FORMATS: { val: AhFormat; label: string }[] = [
	{ val: 'auto', label: 'Auto' },
	{ val: 'a4', label: 'A4' },
	{ val: 'a5', label: 'A5' },
	{ val: 'a6', label: 'A6' },
	{ val: 'a7', label: 'A7' },
];
