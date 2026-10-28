//  Les répartitions croisées du Suivi des affaires (#2043) — la légende.
//
//  🔴 La TEINTE de chaque tranche vient du SERVEUR depuis #2082
//  (`utils/suivi_affaires/repartition.teinter`) : le PDF du point CS / Syndic
//  la peint aussi, et la règle « une teinte suit l'entité, jamais son rang »
//  ne s'écrit qu'une fois. Les couleurs restent les jetons `--serie-*` et
//  `--palier-*` de `socle.css` (`test_teintes_repartition.py`).

import type { TrancheRepartition } from '#lib/api/index.ts';

/** La légende d'un graphique : chaque tranche une fois, dans l'ordre où elles paraissent. */
export function legende(tranches: readonly TrancheRepartition[][]): TrancheRepartition[] {
	const vues = new Map<string, TrancheRepartition>();
	for (const t of tranches.flat()) if (!vues.has(t.cle)) vues.set(t.cle, t);
	return [...vues.values()];
}
