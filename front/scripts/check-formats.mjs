#!/usr/bin/env node
/**
 *  Une taille en octets et un nombre affiché se formatent par `fmtOctets` et
 *  `fmtNombre` (`#lib/utils`), jamais à la main (#1576, 02/10/2026).
 *
 *  🔴 La règle 2 de `CLAUDE.md` (« dates et montants : ne jamais réimplémenter
 *  un format dans une page ») n'avait de garde-fou que pour les dates. Les
 *  tailles et les nombres, eux, s'écrivaient à la main :
 *
 *  | Où | Ce qu'il rendait |
 *  |---|---|
 *  | `taches-colonnes.ts` | Mo / Go, seuil 1024 Mo, `toFixed(1)` puis `toFixed(2)` — point décimal |
 *  | `HistoriqueAnnoncesHall` | Ko / Mo, `Math.round` puis `toFixed(1)` — point décimal |
 *  | `BlocUsageIA`, `OngletConsommations`, `ConsommationIA` | `toLocaleString('fr-FR')` recopié |
 *
 *  Deux unités, deux seuils, deux arrondis pour une même grandeur. Ce contrôle
 *  refuse la forme qui les produisait : `toFixed(`, une division par 1024 et
 *  `toLocaleString('fr-FR')` (ou sans argument) hors de la source.
 *
 *  La source est `src/lib/utils.ts` ; `src/lib/date.ts` porte, lui, les dates
 *  (`toLocaleString(LOCALE, { timeZone… })` — le contrôle `lint:dates`).
 *
 *  Ce qui reste déclaré en exception ne passe pas par ces deux fonctions pour
 *  une raison écrite ci-dessous : une exception qui ne sert plus fait échouer.
 *
 *  Câblé dans `npm run lint:dates` (déjà lancé par la CI) : la notion est la
 *  même — « un format ne se réimplémente pas dans une page ».
 *
 *  Lancer : node scripts/check-formats.mjs [--selftest]
 */
import { readFileSync } from 'node:fs';
import ts from 'typescript';
import { controler, lignesPortant } from './lib-source-unique.mjs';

/**  Écarts déclarés, avec leur raison. Une entrée qui ne sert plus fait échouer. */
//  Vide depuis #2358 : le pourcentage du Top pages passe par `fmtPartEnPourcent(…, 1)`.
const EXCEPTIONS = {};

/**
 *  Les formes d'un format écrit à la main :
 *  - `.toFixed(` — l'arrondi d'une taille ou d'un nombre, point décimal compris ;
 *  - `/ 1024`, `/ (1024 * 1024)` — le changement d'échelle d'un octet ;
 *  - `.toLocaleString('fr-FR')` ou `.toLocaleString()` — un nombre groupé à la
 *    main (celui d'une DATE passe par `#lib/date`, qui épingle `LOCALE`).
 */
const COPIE = /\.toFixed\s*\(|\/\s*\(?\s*1024\b|\.toLocaleString\s*\(\s*(?:\)|['"]fr-FR['"]\s*\))/;

export const fautes = lignesPortant(COPIE);

const NBSP = '\u202f'; // le séparateur de milliers de fr-FR

/**
 *  Le COMPORTEMENT de la source, pas sa forme : le front n'a pas de lanceur de
 *  tests, et un contrôle qui ne lisait que le texte de `utils.ts` laisserait
 *  passer un seuil faux. Le morceau `fmtNombre` → `fmtOctets` est extrait de
 *  `utils.ts`, transpilé (TypeScript est déjà là pour `svelte-check`) et
 *  exécuté ; `utils.ts` lui-même ne s'importe pas hors de Vite (`#lib/…`).
 */
const CAS_COMPORTEMENT = [
	['fmtNombre', [null], '—'],
	['fmtNombre', [undefined], '—'],
	['fmtNombre', [0], '0'],
	['fmtNombre', [0.5], '0,5'],
	['fmtNombre', [1234567], `1${NBSP}234${NBSP}567`],
	['fmtOctets', [null], '—'],
	['fmtOctets', [undefined], '—'],
	['fmtOctets', [0], '0 o'],
	['fmtOctets', [512], '512 o'],
	['fmtOctets', [1024], '1 Ko'],
	['fmtOctets', [51200], '50 Ko'],
	//  Le seuil est celui de l'arrondi : jamais « 1 024 Ko ».
	['fmtOctets', [1048000], `1${NBSP}023 Ko`],
	['fmtOctets', [1048500], '1,0 Mo'],
	['fmtOctets', [1048576], '1,0 Mo'],
	['fmtOctets', [1258291], '1,2 Mo'],
	['fmtOctets', [524288000], '500,0 Mo'],
	//  Le seuil est celui de l'arrondi : jamais « 1 024,0 Mo ».
	['fmtOctets', [1073700000], '1,00 Go'],
	['fmtOctets', [1073741824], '1,00 Go'],
	['fmtOctets', [3435973837], '3,20 Go'],
];

async function comportement() {
	const src = readFileSync('src/lib/utils.ts', 'utf8');
	const debut = src.indexOf('const NOMBRE = ');
	const fin = src.indexOf('\n}\n', src.indexOf('export function fmtOctets'));
	if (debut < 0 || fin < 0) {
		console.error('✗ fmtNombre / fmtOctets introuvables dans src/lib/utils.ts : contrôle INCONNU.');
		return 1;
	}
	const js = ts.transpileModule(src.slice(debut, fin + 3), {
		compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 },
	}).outputText;
	const mod = await import('data:text/javascript;base64,' + Buffer.from(js).toString('base64'));
	let ko = 0;
	for (const [nom, args, attendu] of CAS_COMPORTEMENT) {
		const obtenu = mod[nom](...args);
		const ok = obtenu === attendu;
		console.log(`${ok ? 'PASS' : 'FAIL'}  ${nom}(${args}) → « ${obtenu} »`);
		if (!ok) {
			console.log(`      attendu « ${attendu} »`);
			ko = 1;
		}
	}
	return ko;
}

//  `--selftest` rejoue aussi le comportement ; sans lui, seul le relevé de `src/`.
const koComportement = process.argv.includes('--selftest') ? await comportement() : 0;

process.exit(
	koComportement ||
		controler({
			extensions: ['.svelte', '.ts'],
			sources: ['src/lib/date.ts'],
			temoin: 'src/lib/utils.ts',
			exceptions: EXCEPTIONS,
			fautes,
			cas: [
				//  Les six formes qui ont existé.
				['\treturn mo >= 1024 ? `${(mo / 1024).toFixed(2)} Go` : `${mo.toFixed(1)} Mo`;', 1],
				['\t\t\t? `${Math.round(octets / 1024)} Ko`', 1],
				['\t\t\t: `${(octets / (1024 * 1024)).toFixed(1)} Mo`;', 1],
				["\tconst nombre = (n: number) => n.toLocaleString('fr-FR');", 1],
				["\t<strong>{r.index.toLocaleString('fr-FR')}</strong>", 1],
				['\t{((p.total / diviseur) * 100).toFixed(1)}%', 1],
				['\tn.toLocaleString()', 1],
				//  Les formes voulues, jamais signalées.
				['\t{fmtOctets(l.taille_octets)}', 0],
				['\t{fmtNombre(r.index)}', 0],
				//  Une date épinglée : le contrôle des dates, pas celui-ci.
				["\treturn new Date(d).toLocaleString(LOCALE, { timeZone: 'Europe/Paris' });", 0],
				//  Une division sans rapport avec l'échelle des octets.
				['\tconst moitie = total / 10240;', 0],
				//  Un commentaire qui cite la forme refusée.
				['\t// on écrivait (n / 1024).toFixed(1)', 0],
			],
			ok: 'Tailles et nombres : formatés par fmtOctets / fmtNombre seulement',
			ko: 'format(s) de taille ou de nombre écrit(s) à la main',
			conseil:
				'Employer `fmtOctets(n)` (tailles) ou `fmtNombre(n)` (nombres) de `#lib/utils`. ' +
				'Un écart légitime se déclare dans EXCEPTIONS de scripts/check-formats.mjs, avec sa raison.',
		}),
);
