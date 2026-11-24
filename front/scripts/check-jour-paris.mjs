#!/usr/bin/env node
/**
 *  Un JOUR se lit à Paris, par `#lib/date` — jamais tronqué d'un instant UTC,
 *  jamais recomposé de `getDate()` et `getMonth()` (#2944, 24/11/2026).
 *
 *  🔴 `check-dates.mjs` refuse un formatage sans fuseau, mais il laissait passer
 *  « `toISOString()` seul », et sa forme tronquée avec lui :
 *
 *  | Où | Ce qu'il rendait |
 *  |---|---|
 *  | `prestataires.ts` (date de début d'un contrat) | le jour UTC : la veille entre minuit et deux heures |
 *  | `OngletConsommations` (date d'un relevé, ×2) | idem |
 *  | `OngletReporting` (date du titre imprimé) | idem |
 *  | `VueRenouvellementsContrats` (étiquette de la frise) | `getDate()}/{getMonth() + 1` : le fuseau du navigateur |
 *
 *  `jourIso()` existait depuis le 11/10/2026, et dix fichiers l'employaient :
 *  les quatre copies dataient du 07/09. Ce contrôle refuse les deux formes hors
 *  de `src/lib/date.ts`, qui porte la notion.
 *
 *  Câblé dans `npm run lint:dates` (déjà lancé par la CI).
 *
 *  Lancer : node scripts/check-jour-paris.mjs [--selftest]
 */
import { controler, lignesPortant } from './lib-source-unique.mjs';

/**  Écarts déclarés, avec leur raison. Une entrée qui ne sert plus fait échouer. */
const EXCEPTIONS = {
	'src/lib/fetes.ts':
		'`decaler` construit sa date par `Date.UTC` : son jour UTC EST le jour voulu, ' +
		'et le calendrier des fêtes ne dépend d’aucun fuseau.',
};

/**
 *  Les deux formes d'un jour écrit à la main :
 *  - `.toISOString().slice(0, 10)` — le jour UTC d'un instant ;
 *  - `.getDate()` puis `.getMonth()` sur la même ligne — un jour et un mois
 *    recomposés dans le fuseau de l'appareil.
 */
const COPIE =
	/\.toISOString\(\)\s*\.slice\(\s*0\s*,\s*10\s*\)|\.getDate\(\)[^\n]{0,40}\.getMonth\(\)/;

export const fautes = lignesPortant(COPIE);

process.exit(
	controler({
		extensions: ['.svelte', '.ts'],
		sources: ['src/lib/date.ts'],
		exceptions: EXCEPTIONS,
		fautes,
		cas: [
			//  Les formes qui ont existé.
			['\t\tdate_debut: new Date().toISOString().slice(0, 10),', 1],
			["\tlet releveForm = { date_releve: new Date().toISOString().slice(0, 10), index: '' };", 1],
			['\t\tconst dateStr = new Date().toISOString().slice(0, 10);', 1],
			['\t\t{c.dateFin.getDate()}/{c.dateFin.getMonth() + 1}', 1],
			['\tconst j = `${d.getDate()}/${d.getMonth() + 1}`;', 1],
			//  Les formes voulues, jamais signalées.
			['\t\tdate_debut: jourIso(),', 0],
			['\t\t{fmtJourMoisChiffres(c.dateFin)}', 0],
			//  Un instant sérialisé pour l'API : `toISOString()` seul reste permis.
			['\tconst corps = { envoye_le: new Date().toISOString() };', 0],
			//  Un mois seul (la position d'une frise) n'est pas un jour recomposé.
			['\t{@const moisFin = c.dateFin.getMonth()}', 0],
			//  Un commentaire qui cite la forme refusée.
			['\t// jamais toISOString().slice(0, 10)', 0],
		],
		ok: 'Jours : lus à Paris par #lib/date seulement',
		ko: 'jour(s) tronqué(s) d’un instant UTC ou recomposé(s) à la main',
		conseil:
			'Employer `jourIso()` (la valeur d’un champ date) ou un format de `#lib/date` ' +
			'(`fmtJourMoisChiffres`, `fmtDate`…). Un écart légitime se déclare dans EXCEPTIONS ' +
			'de scripts/check-jour-paris.mjs, avec sa raison.',
	}),
);
