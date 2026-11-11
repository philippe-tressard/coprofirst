//  Les civilités d'une fiche de l'annuaire — sorties de `CarteMembre.svelte` (#2634).

/**  Les civilités proposées, dans leur ordre — écrites une fois : les deux fiches
 *   (conseil, syndic) les listaient chacune avant `CarteMembre`. */
//  🔒 Table PUBLIÉE aux clients (`tables-clients.json`, #2634) — littérale ; la retirer
//  ou en changer la forme s'annonce (`npm run lint:tables-clients`).
export const CIVILITES = ['Mme', 'Mlle', 'Mr'] as const;
