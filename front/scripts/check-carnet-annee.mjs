#!/usr/bin/env node
/**
 * Le filtre par année du carnet d'entretien fait-il ce que le décret demande ?
 * (24/09/2026) — `#lib/carnet` est transpilé et EXÉCUTÉ, jamais relu.
 *
 * Décret n° 2001-477 : les travaux se datent par leur « année de réalisation »
 * (art. 4) ; les contrats EN VIGUEUR y figurent (art. 3 et 4) ; aucune durée de
 * conservation. Un contrat ne doit donc jamais disparaître d'une année filtrée.
 */
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { chargerModule } from './lib/charger-module.mjs';

const RACINE = join(dirname(fileURLToPath(import.meta.url)), '..');
const echouer = (m) => {
	console.error(`\n✗ ${m}\n`);
	process.exit(1);
};
const { anneesDuCarnet, entreesDeLAnnee } = await chargerModule(
	join(RACINE, 'src', 'lib', 'carnet.ts'),
	echouer,
);
if (typeof anneesDuCarnet !== 'function' || typeof entreesDeLAnnee !== 'function') {
	echouer(
		'Cas zéro : `#lib/carnet` n’exporte plus ses deux fonctions — ce contrôle ne mesure plus rien.',
	);
}

const E = [
	{ date: '2019-03-01', origine: 'contrat' },
	{ date: '2026-09-17', origine: 'affaire' },
	{ date: '2025-06-02', origine: 'intervention' },
	{ date: '2025-01-10', origine: 'affaire' },
];
const echecs = [];
const egal = (a, b) => JSON.stringify(a) === JSON.stringify(b);
if (!egal(anneesDuCarnet(E), ['2026', '2025']))
	echecs.push(
		`années : ${JSON.stringify(anneesDuCarnet(E))} — le contrat n’en propose pas, l’ordre est décroissant`,
	);
if (entreesDeLAnnee(E, '').length !== 4) echecs.push('« Toutes » doit rendre tout le carnet');
const de2025 = entreesDeLAnnee(E, '2025');
if (de2025.length !== 3)
	echecs.push(`2025 : ${de2025.length} entrée(s), 3 attendues (deux faits + le contrat)`);
if (!entreesDeLAnnee(E, '2026').some((e) => e.origine === 'contrat'))
	echecs.push(
		'un contrat en vigueur a disparu d’une année filtrée — le décret veut ceux en vigueur',
	);
if (anneesDuCarnet([]).length !== 0) echecs.push('un carnet vide ne propose aucune année');

if (echecs.length) {
	console.error('\n✗ Le filtre par année du carnet ne suit pas le décret n° 2001-477 :\n');
	for (const e of echecs) console.error(`    ${e}`);
	process.exit(1);
}
console.log(
	'✓ Carnet par année : 5 cas vérifiés — les contrats en vigueur restent, « Toutes » rend tout.',
);
