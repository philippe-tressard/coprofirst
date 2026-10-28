#!/usr/bin/env node
/**
 *  Le libellé du TYPE d'un lot ne se réécrit pas dans un écran (#779, 30/09/2026).
 *
 *  🔴 `#lib/utils` exportait déjà `lotTypeLabel`, et `mon-lot` l'importait — mais
 *  le même libellé était recalculé À LA MAIN six fois (cinq dans `mon-lot`, une
 *  dans `OngletGestionLocative`) : `type.replace('_', ' ')` suivi de
 *  `type_appartement`. Les deux écritures divergeaient déjà : la fonction rendait
 *  `local_commercial` brut et taisait le « T3 », les copies non.
 *
 *  La fonction a été ENRICHIE de ce que traitaient les copies (`lotTypeComplet`),
 *  et ce contrôle refuse la septième : la FORME d'une copie, c'est-à-dire le
 *  remplacement du soulignement d'un champ `type` / `lot_type`. Un `replace('_')`
 *  sur une autre valeur n'est pas concerné.
 *
 *  01/10/2026 : une copie qui avait échappé au motif — `lot.type.charAt(0)
 *  .toUpperCase() + lot.type.slice(1)`, le sélecteur de lots de « Mes lots », qui
 *  écrivait « Local_commercial ». Le motif couvre désormais cette forme aussi.
 *
 *  Lancer : node scripts/check-type-lot.mjs [--selftest]
 */
import { controler, lignesPortant } from './lib-source-unique.mjs';

/**  `lot.type.replace('_', ' ')`, `lot.type.charAt(0).toUpperCase()`… : le
 *   libellé d'un TYPE de lot recomposé à la main. */
const COPIE =
	/\b(?:lot_)?type\s*\.\s*(?:replace(?:All)?\(\s*(?:['"`]_['"`]|\/_\/g?)|charAt\(\s*0\s*\)\s*\.\s*toUpperCase)/;

process.exit(
	controler({
		extensions: ['.svelte', '.ts'],
		sources: ['src/lib/utils.ts'],
		fautes: lignesPortant(COPIE),
		cas: [
			["\t\t\t\t>{lot.type.replace('_', ' ')}{lot.type_appartement", 1],
			["\t\t{monBailData.lot_type.replace('_', ' ')}{monBailData.lot_type_appartement", 1],
			['\t\tconst t = lot.type.replaceAll(/_/g, " ");', 1],
			['\t\t{lot.type.charAt(0).toUpperCase() + lot.type.slice(1)} - {lot.numero}', 1],
			//  La forme voulue, jamais signalée.
			['\t\t\t{lotTypeComplet(lot.type, lot.type_appartement)}', 0],
			//  Un `replace('_')` sur autre chose qu'un type de lot : hors portée.
			["\t\t\t{statut.replace('_', ' ')}", 0],
			//  Un commentaire qui cite la forme refusée.
			["\t// on écrivait lot.type.replace('_', ' ') ici", 0],
		],
		ok: 'Type de lot : aucun libellé recalculé hors de `lotTypeLabel` / `lotTypeComplet`',
		ko: 'libellé(s) de type de lot recalculé(s) à la main',
		conseil:
			'Employer `lotTypeComplet(type, typeAppartement)` ou `lotTypeLabel(type)` (`#lib/utils`).',
	}),
);
