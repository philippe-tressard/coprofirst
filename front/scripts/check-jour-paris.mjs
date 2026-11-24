#!/usr/bin/env node
/**
 *  Un JOUR, un MOIS, une ANNÉE se lisent à Paris, par `#lib/date` — jamais
 *  tronqués d'un instant UTC, jamais lus par `getDate()`, `getMonth()` ou
 *  `getFullYear()`, qui suivent le fuseau de l'appareil (#2944, #3059).
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
 *  🔴 #3059 (24/11/2026) : restaient 17 lectures d'une année ou d'un mois seuls
 *  — frise des contrats et des diagnostics, archives et relevés groupés par
 *  année, exercice des visites, année du pied de page. Elles passent par
 *  `anneeDe()` et `moisDe()` ; un calcul d'instant qui ne dépend d'aucun
 *  calendrier (« il y a trois ans ») s'écrit en UTC (`getUTCFullYear`).
 *  `--selftest` éprouve aussi les deux aides, sous un fuseau d'appareil autre
 *  que Paris.
 *
 *  Câblé dans `npm run lint:dates` (déjà lancé par la CI).
 *
 *  Lancer : node scripts/check-jour-paris.mjs [--selftest]
 */
import { readFileSync } from 'node:fs';
import ts from 'typescript';
import { controler, lignesPortant } from './lib-source-unique.mjs';

/**  Écarts déclarés, avec leur raison. Une entrée qui ne sert plus fait échouer. */
const EXCEPTIONS = {
	'src/lib/fetes.ts':
		'`decaler` construit sa date par `Date.UTC` : son jour UTC EST le jour voulu, ' +
		'et le calendrier des fêtes ne dépend d’aucun fuseau.',
};

/**
 *  Les formes d'une date lue à la main :
 *  - `.toISOString().slice(0, 10)` — le jour UTC d'un instant ;
 *  - `.getDate()` puis `.getMonth()` sur la même ligne — un jour et un mois
 *    recomposés dans le fuseau de l'appareil ;
 *  - `.getMonth()` ou `.getFullYear()` seuls — un mois ou une année dans ce même
 *    fuseau (#3059). `getUTCFullYear()` et `getUTCMonth()` restent permis : ils
 *    disent leur fuseau.
 */
const COPIE =
	/\.toISOString\(\)\s*\.slice\(\s*0\s*,\s*10\s*\)|\.getDate\(\)[^\n]{0,40}\.getMonth\(\)|\.get(?:FullYear|Month)\(\)/;

/**
 *  Le COMPORTEMENT des deux aides, sous un fuseau d'appareil qui n'est pas Paris :
 *  un contrôle qui ne lirait que le texte laisserait passer une aide qui
 *  appellerait `getFullYear()` elle-même. `date.ts` n'importe rien : il se
 *  transpile et s'exécute tel quel.
 */
const CAS_COMPORTEMENT = [
	//  Le 31 décembre à 23 h 30 UTC : déjà le 1er janvier à Paris.
	['anneeDe', ['2026-12-31T23:30:00Z'], 2027],
	['moisDe', ['2026-12-31T23:30:00Z'], 0],
	//  Le 1er mars à minuit UTC : encore mars à Paris, février à New York.
	['anneeDe', ['2027-03-01'], 2027],
	['moisDe', ['2027-03-01'], 2],
	['moisDe', ['2026-07-15T12:00:00Z'], 6],
	['anneeDe', ['pas une date'], NaN],
	['moisDe', ['pas une date'], NaN],
];

async function comportement() {
	const fuseau = process.env.TZ;
	process.env.TZ = 'America/New_York';
	try {
		if (new Date('2027-03-01').getMonth() !== 1) {
			console.error('✗ Le fuseau de l’appareil ne se simule pas : contrôle INCONNU.');
			return 1;
		}
		const js = ts.transpileModule(readFileSync('src/lib/date.ts', 'utf8'), {
			compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 },
		}).outputText;
		const mod = await import('data:text/javascript;base64,' + Buffer.from(js).toString('base64'));
		let ko = 0;
		for (const [nom, args, attendu] of CAS_COMPORTEMENT) {
			const obtenu = mod[nom](...args);
			const ok = Object.is(obtenu, attendu);
			console.log(`${ok ? 'PASS' : 'FAIL'}  ${nom}(${args}) → ${obtenu}`);
			if (!ok) {
				console.log(`      attendu ${attendu}`);
				ko = 1;
			}
		}
		return ko;
	} finally {
		if (fuseau === undefined) delete process.env.TZ;
		else process.env.TZ = fuseau;
	}
}

const koComportement = process.argv.includes('--selftest') ? await comportement() : 0;

export const fautes = lignesPortant(COPIE);

process.exit(
	koComportement ||
		controler({
			extensions: ['.svelte', '.ts'],
			sources: ['src/lib/date.ts'],
			exceptions: EXCEPTIONS,
			fautes,
			cas: [
				//  Les formes qui ont existé.
				['\t\tdate_debut: new Date().toISOString().slice(0, 10),', 1],
				[
					"\tlet releveForm = { date_releve: new Date().toISOString().slice(0, 10), index: '' };",
					1,
				],
				['\t\tconst dateStr = new Date().toISOString().slice(0, 10);', 1],
				['\t\t{c.dateFin.getDate()}/{c.dateFin.getMonth() + 1}', 1],
				['\tconst j = `${d.getDate()}/${d.getMonth() + 1}`;', 1],
				//  Les formes voulues, jamais signalées.
				['\t\tdate_debut: jourIso(),', 0],
				['\t\t{fmtJourMoisChiffres(c.dateFin)}', 0],
				//  Un instant sérialisé pour l'API : `toISOString()` seul reste permis.
				['\tconst corps = { envoye_le: new Date().toISOString() };', 0],
				//  Un mois ou une année seuls, au fuseau de l'appareil (#3059).
				['\t{@const moisFin = c.dateFin.getMonth()}', 1],
				['\t\t\tconst annee = new Date(d).getFullYear();', 1],
				['\tconst anneeCourante = new Date().getFullYear();', 1],
				//  Leurs formes voulues, et un calcul d'instant en UTC.
				['\t{@const moisFin = moisDe(c.dateFin)}', 0],
				['\tconst anneeCourante = anneeDe();', 0],
				['\tTROIS_ANS.setUTCFullYear(TROIS_ANS.getUTCFullYear() - 3);', 0],
				//  Un commentaire qui cite la forme refusée.
				['\t// jamais toISOString().slice(0, 10)', 0],
			],
			ok: 'Jours, mois et années : lus à Paris par #lib/date seulement',
			ko: 'jour(s), mois ou année(s) lu(s) au fuseau de l’appareil ou tronqué(s) d’un instant UTC',
			conseil:
				'Employer `jourIso()` (la valeur d’un champ date), `anneeDe()`, `moisDe()` ou un format de `#lib/date` ' +
				'(`fmtJourMoisChiffres`, `fmtDate`…). Un écart légitime se déclare dans EXCEPTIONS ' +
				'de scripts/check-jour-paris.mjs, avec sa raison.',
		}),
);
