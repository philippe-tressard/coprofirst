//  Le ton d'une ligne de journal et sa pastille — sortis de `JournalVerdicts.svelte` (#2634).

/** La gravité d'un verdict, jamais son nom : elle choisit la pastille de la charte. */
export type TonVerdict = 'succes' | 'info' | 'attention' | 'danger' | 'neutre';

/** La pastille (`.badge-*`, `<Badge teinte>`) de chaque ton. */
//  🔒 Table PUBLIÉE aux clients (`tables-clients.json`, #2634) — littérale ; la retirer
//  ou en changer la forme s'annonce (`npm run lint:tables-clients`).
export const TEINTE_DU_TON: Record<TonVerdict, string> = {
	succes: 'badge-green',
	info: 'badge-blue',
	attention: 'badge-orange',
	danger: 'badge-red',
	neutre: 'badge-gray',
};
