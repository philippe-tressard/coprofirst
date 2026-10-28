#!/usr/bin/env node
/**
 * Garde-fou : aucune date affichée ne doit dépendre du fuseau de l'appareil.
 *
 * `#lib/date.ts` fige `LOCALE = 'fr-FR'` et `TZ = 'Europe/Paris'` précisément pour
 * cela. Le 26/07/2026, deux contournements ont échappé à toute vérification :
 *
 *   1. `vite.config.ts` construisait l'horodatage du footer avec
 *      `new Date().toISOString()` — TOUJOURS en UTC → le footer annonçait « 08:48 »
 *      pour une mise en production faite à 10:48, sans mention du fuseau.
 *   2. `tableau-de-bord/+page.svelte` formatait les heures d'événement avec
 *      `toLocaleTimeString('fr-FR', …)` SANS `timeZone` → suivait le fuseau du
 *      navigateur, juste par coïncidence pour un résident en France.
 *
 * Le pendant Python (`api/tests/test_dates_fr.py`) ne scanne que `api/app/` : ces
 * deux cas étaient hors de sa portée. Ce script couvre le front, `vite.config.ts`
 * inclus — c'est là que se cachait le premier.
 *
 * Script Node sans dépendance (pas de vitest) : le projet n'a pas de lanceur de
 * tests front, et `front/Dockerfile` documente un build cassé par une résolution de
 * dépendance. Un contrôle de type lint ne justifie pas ce risque.
 *
 * RESTE AUTORISÉ :
 *   - `toISOString()` seul → sérialisation UTC des payloads d'API, c'est correct ;
 *   - `toLocaleString()` sur un NOMBRE → pas une date, et pas ce contrôle : un nombre
 *     ou une taille passe par `fmtNombre` / `fmtOctets` (`scripts/check-formats.mjs`,
 *     lancé avec celui-ci par `npm run lint:dates`) ;
 *   - tout appel épinglant explicitement `timeZone`.
 *
 * Usage : npm run lint:dates   (exit 1 si violation)
 */
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { dirname, join, relative } from 'node:path';
import { fileURLToPath } from 'node:url';

const RACINE = join(dirname(fileURLToPath(import.meta.url)), '..');

/** Porte légitimement la convention de fuseau : c'est la source de vérité. */
const EXEMPTS = new Set(['src/lib/date.ts']);

/**
 * `toLocaleDateString` / `toLocaleTimeString` / `Intl.DateTimeFormat` ne
 * s'appliquent QU'À des dates. `toLocaleString` n'est ciblé que précédé de
 * `new Date(...)`, car il sert aussi au formatage des nombres.
 */
const MOTIFS = [
	/\.toLocaleDateString\s*\(/,
	/\.toLocaleTimeString\s*\(/,
	/new\s+Intl\.DateTimeFormat\s*\(/,
	/new\s+Date\s*\([^)]*\)\s*\.toLocaleString\s*\(/,
];

const estCommentaire = (l) => {
	const t = l.trim();
	return t.startsWith('//') || t.startsWith('*') || t.startsWith('/*');
};

function collecter(dir, acc = []) {
	for (const e of readdirSync(dir)) {
		if (e === 'node_modules' || e === '.svelte-kit' || e === 'build') continue;
		const p = join(dir, e);
		if (statSync(p).isDirectory()) collecter(p, acc);
		else if (/\.(ts|js|mjs|svelte)$/.test(e)) acc.push(p);
	}
	return acc;
}

function analyser(chemins) {
	const fautifs = [];
	for (const p of chemins) {
		const rel = relative(RACINE, p).replace(/\\/g, '/');
		if (EXEMPTS.has(rel)) continue;
		const lignes = readFileSync(p, 'utf-8').split('\n');
		lignes.forEach((ligne, i) => {
			if (estCommentaire(ligne)) return;
			if (!MOTIFS.some((m) => m.test(ligne))) return;
			// Options parfois écrites sur plusieurs lignes : on regarde en avant.
			const contexte = ligne + (lignes[i + 1] ?? '') + (lignes[i + 2] ?? '');
			if (/timeZone\s*:/.test(contexte)) return;
			fautifs.push(`  ${rel}:${i + 1}\n      ${ligne.trim()}`);
		});
	}
	return fautifs;
}

const cibles = [...collecter(join(RACINE, 'src')), join(RACINE, 'vite.config.ts')];
const fautifs = analyser(cibles);

if (fautifs.length > 0) {
	console.error(
		`\n✗ ${fautifs.length} formatage(s) de date sans fuseau épinglé :\n\n` +
			fautifs.join('\n') +
			`\n\n  Utiliser les helpers de #lib/date.ts (fmtDate, fmtDateLong, fmtTime,` +
			`\n  fmtDatetime, fmtMonthYear…), qui figent fr-FR + Europe/Paris.` +
			`\n  Si le formatage est légitimement spécifique, épingler` +
			`\n  \`timeZone: 'Europe/Paris'\` explicitement dans les options.\n`,
	);
	process.exit(1);
}

console.log(`✓ ${cibles.length} fichiers analysés — aucun formatage de date sans fuseau épinglé.`);
