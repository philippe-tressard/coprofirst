#!/usr/bin/env node
/**
 *  Le badge d'ÉTAT d'une affaire — son « Suivi » — se rend par
 *  `BadgeEtatAffaire`, et la table des teintes (`STATUT_TICKET_BADGE`) ne se lit
 *  que là (#2173, 23/10/2026).
 *
 *  Il était écrit trois fois — `PastillesAffaire`, `TableauAffaires`,
 *  `FluxCorps` —, chacun avec son repli gris ; la section « Affaires liées »
 *  allait en faire la quatrième. Une copie de plus diverge sur le cas limite
 *  (un état que la table ne connaît pas) : `standards/02` §1 bis.
 *
 *  Lancer : node scripts/check-badge-etat-affaire.mjs [--selftest]
 */
import { controler, lignesPortant } from './lib-source-unique.mjs';

const COPIE = /\bSTATUT_TICKET_BADGE\b/;

process.exit(
	controler({
		extensions: ['.svelte', '.ts'],
		//  La table elle-même.
		sources: ['src/lib/tickets.ts'],
		temoin: 'src/lib/components/BadgeEtatAffaire.svelte',
		fautes: lignesPortant(COPIE),
		cas: [
			["\t\t<Badge teinte={STATUT_TICKET_BADGE[etat] ?? 'badge-gray'}>", 1],
			["\timport { STATUT_TICKET_BADGE, statutTicketLabel } from '#lib/tickets.ts';", 1],
			//  La forme voulue, jamais signalée.
			['\t\t<BadgeEtatAffaire statut={a.statut} compact />', 0],
			//  Une autre table de teintes : hors portée.
			["\t\t<Badge teinte={STATUT_BADGE[imp.statut] ?? 'badge-gray'}>", 0],
		],
		ok: "Badge d'état d'une affaire : rendu par BadgeEtatAffaire seul",
		ko: 'lecture(s) de STATUT_TICKET_BADGE hors de BadgeEtatAffaire',
		conseil: 'Employer `<BadgeEtatAffaire statut={…} />` (`compact` pour une liste dense).',
	}),
);
