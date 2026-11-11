//  Ce que la relève des courriels affaires a fait d'un message — sorti
//  d'`OngletCourriels.svelte` (#2634).

import type { CourrielReleve } from '#lib/api/index.ts';
import type { TonVerdict } from '#lib/journal-verdicts.ts';

/** Le verdict de la relève, teinté par sa gravité et non par son nom : un refus est
 *  orange — le conseil a été prévenu, rien n'est cassé —, un message ignoré est gris. */
//  🔒 Table PUBLIÉE aux clients (`tables-clients.json`, #2634) — littérale ; la retirer
//  ou en changer la forme s'annonce (`npm run lint:tables-clients`).
export const VERDICTS_RELEVE: Record<
	CourrielReleve['decision'],
	{ libelle: string; ton: TonVerdict }
> = {
	accepte: { libelle: 'Ajouté au fil', ton: 'succes' },
	relance: { libelle: 'Transmis au conseil', ton: 'info' },
	refuse: { libelle: 'Refusé', ton: 'attention' },
	ignore: { libelle: 'Ignoré', ton: 'neutre' },
	//  Aucune affaire désignée, d'un correspondant connu : le conseil le classe (#2555).
	a_classer: { libelle: 'À classer', ton: 'attention' },
};

/** Une fois classé, ce qui a été fait du message — le motif le précise. */
//  🔒 Table PUBLIÉE aux clients (`tables-clients.json`, #2634) — littérale ; la retirer
//  ou en changer la forme s'annonce (`npm run lint:tables-clients`).
export const CLASSES_RELEVE: Record<string, { libelle: string; ton: TonVerdict }> = {
	rattache: { libelle: 'Rattaché', ton: 'succes' },
	cree: { libelle: 'Affaire créée', ton: 'succes' },
	ecarte: { libelle: 'Écarté', ton: 'neutre' },
};
