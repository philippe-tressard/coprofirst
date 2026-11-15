/**
 * **La gravité d'un constat du patrimoine** — libellé, teinte et ordre (#2756).
 *
 * Les constats de l'état descriptif et de l'onglet Lots (`utils/constats` côté
 * serveur) se rendent par `ConstatsLots.svelte`. La table vivait dans ce composant :
 * les apps natives la recopiaient (iOS `ProvisoireAcces.swift`, Android
 * `ProvisoireMonLot`). Publiée dans `tables-clients.json`, elle se génère.
 *
 * L'ORDRE des clés est celui de l'affichage, du plus grave au moins grave : ce qui
 * bloque ou ne se calcule pas d'abord, puis ce qu'il faut savoir. Il est publié tel
 * quel (l'ordre d'un objet JSON se conserve), et le rang se déduit de lui.
 */

import { parAttribut } from '#lib/table-statuts.ts';

//  🔒 Table PUBLIÉE aux clients (`gravitesConstat`) — littérale ; la retirer ou en
//  changer la forme s'annonce (`npm run lint:tables-clients`).
export const GRAVITES_CONSTAT = {
	bloquant: { libelle: 'Bloquant', badge: 'badge-red' },
	inconnu: { libelle: 'Inconnu', badge: 'badge-gray' },
	avertissement: { libelle: 'À savoir', badge: 'badge-orange' },
	information: { libelle: 'Information', badge: 'badge-blue' },
};

const GRAVITE = parAttribut(GRAVITES_CONSTAT);

export const LIBELLE_GRAVITE: Record<string, string> = GRAVITE.libelle;
export const BADGE_GRAVITE: Record<string, string> = GRAVITE.badge;

const RANGS: Record<string, number> = Object.fromEntries(
	Object.keys(GRAVITES_CONSTAT).map((g, i) => [g, i]),
);

/** Le rang d'une gravité, 0 pour la plus grave ; une gravité inconnue passe en dernier. */
export const rangGravite = (gravite: string): number => RANGS[gravite] ?? Object.keys(RANGS).length;
