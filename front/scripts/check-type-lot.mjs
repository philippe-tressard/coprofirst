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
 *  04/11/2026 (#2507) : `lotTypeLabel` et `lotTypeComplet` ont quitté le front. Le
 *  type en clair est SERVI par l'API (`libelle_type`, `libelle_type_complet`,
 *  `libelle_nature`, `lot_libelle_type` — `api/app/utils/libelles_lot.py`), que l'app
 *  iOS lit aussi ; `lint:regles-partagees` refuse le retour des deux fonctions, ce
 *  contrôle-ci la recomposition à la main.
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
		sources: [],
		fautes: lignesPortant(COPIE),
		cas: [
			["\t\t\t\t>{lot.type.replace('_', ' ')}{lot.type_appartement", 1],
			["\t\t{monBailData.lot_type.replace('_', ' ')}{monBailData.lot_type_appartement", 1],
			['\t\tconst t = lot.type.replaceAll(/_/g, " ");', 1],
			['\t\t{lot.type.charAt(0).toUpperCase() + lot.type.slice(1)} - {lot.numero}', 1],
			//  La forme voulue, jamais signalée : le champ servi.
			['\t\t\t{lot.libelle_type_complet}', 0],
			//  Un `replace('_')` sur autre chose qu'un type de lot : hors portée.
			["\t\t\t{statut.replace('_', ' ')}", 0],
			//  Un commentaire qui cite la forme refusée.
			["\t// on écrivait lot.type.replace('_', ' ') ici", 0],
		],
		ok: 'Type de lot : aucun libellé recalculé — le front lit celui que l’API sert',
		ko: 'libellé(s) de type de lot recalculé(s) à la main',
		conseil:
			'Lire le champ servi : `libelle_type`, `libelle_type_complet`, `libelle_nature` (`LotRead`) ou `lot_libelle_type` (`AccesBail`).',
	}),
);
