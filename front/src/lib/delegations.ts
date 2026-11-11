//  L'état d'une délégation « aidant » — sorti de `routes/(app)/delegations/+page.svelte` (#2634).
//
//  🔒 Table PUBLIÉE aux clients (`tables-clients.json`, #2634) — littérale ; la retirer
//  ou en changer la forme s'annonce (`npm run lint:tables-clients`).

/**  Le libellé et la pastille de chaque état servi (`DelegationRead.statut`). */
export const STATUTS_DELEGATION = {
	en_attente: { libelle: 'En attente', badge: 'badge-orange' },
	active: { libelle: 'Active', badge: 'badge-green' },
	revoquee: { libelle: 'Révoquée', badge: 'badge-red' },
	expiree: { libelle: 'Expirée', badge: 'badge-gray' },
};
