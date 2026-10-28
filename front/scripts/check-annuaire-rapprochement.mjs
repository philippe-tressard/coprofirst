#!/usr/bin/env node
/**
 * Auto-test de `#lib/annuaire-rapprochement.ts` — retrouver, par le NOM saisi
 * dans une fiche de l'annuaire, l'inscrit et le logement d'un membre.
 *
 * 🔴 POURQUOI (29/09/2026, #779). Ces règles vivaient dans
 * `espace-cs/+page.svelte`, et **rien ne les éprouvait** : le front n'a pas de
 * lanceur de tests. Elles passent dans un module pour servir aux deux
 * composants de l'annuaire (conseil syndical, syndic) — et c'est le moment de
 * les tenir, avant qu'un déplacement de plus ne les altère sans un mot.
 *
 * Les cas qui comptent sont ceux qu'on ne relit pas : un parking ou une cave
 * ne localise pas un membre, un lot résolu l'emporte sur une ligne brute, et
 * la casse porte le sens de l'étage (« 1ER », « RDC »).
 *
 * Le module est chargé tel que le site l'exécute (`lib/charger-module.mjs`).
 *
 * Usage : node scripts/check-annuaire-rapprochement.mjs --selftest
 */
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { chargerModule } from './lib/charger-module.mjs';

const ICI = dirname(fileURLToPath(import.meta.url));
const SOURCE = resolve(ICI, '..', 'src', 'lib', 'annuaire-rapprochement.ts');

function echouer(message) {
	console.error(`\n✗ ${message}\n`);
	process.exit(1);
}

const { inscritParNom, etageDepuisBrut, localisationParNom } = await chargerModule(SOURCE, echouer);

const echecs = [];
let cas = 0;
const verifier = (nom, obtenu, attendu) => {
	cas++;
	const a = JSON.stringify(obtenu);
	const b = JSON.stringify(attendu);
	if (a !== b) echecs.push(`  ✗ ${nom}\n      attendu ${b}\n      obtenu  ${a}`);
};

//  ── L'inscrit ───────────────────────────────────────────────────────────────
const inscrits = [
	{ id: 7, prenom: 'Anne', nom: 'Hélène', email: '', telephone: null, batiment_id: 1 },
	{ id: 8, prenom: 'Luc', nom: 'Martin', email: '', telephone: null, batiment_id: 2 },
];
verifier('nom exact', inscritParNom(inscrits, 'Martin')?.id, 8);
verifier('casse et accents ignorés', inscritParNom(inscrits, 'HELENE')?.id, 7);
verifier('une lettre ne cherche pas', inscritParNom(inscrits, 'M'), null);
verifier('inconnu', inscritParNom(inscrits, 'Durand'), null);

//  ── L'étage ─────────────────────────────────────────────────────────────────
verifier('rez-de-chaussée', etageDepuisBrut('RDC'), 0);
verifier('premier', etageDepuisBrut('1er'), 1);
verifier('deuxième, accent et espaces', etageDepuisBrut(' 2ème '), 2);
verifier('sous-sol', etageDepuisBrut('2SS'), -2);
verifier('inconnu', etageDepuisBrut('mezzanine'), null);
verifier('absent', etageDepuisBrut(null), null);

//  ── Le logement ─────────────────────────────────────────────────────────────
const lots = [
	{ id: 1, numero: '12', type: 'appartement', etage: 3, batiment_id: 2, batiment_nom: 'Bât. 2' },
	{ id: 2, numero: 'P4', type: 'parking', etage: -1, batiment_id: 9, batiment_nom: 'Bât. 9' },
];
const batiments = { 2: 'Bât. 2' };
const sources = (imports) => ({ lots, imports, batiments });

verifier(
	'un lot résolu donne son bâtiment, l’étage vient de la ligne',
	localisationParNom(
		sources([{ nom_coproprietaire: 'MARTIN Luc', type_raw: 'AP', etage_raw: '3EME', lot_id: 1 }]),
		'martin',
	),
	{ batiment_id: 2, batiment_nom: '2', etage: 3 },
);
verifier(
	'le parking ne localise pas : l’appartement l’emporte',
	localisationParNom(
		sources([
			{ nom_coproprietaire: 'MARTIN Luc', type_raw: 'PS', etage_raw: '1SS', lot_id: 2 },
			{ nom_coproprietaire: 'MARTIN Luc', type_raw: 'AP', etage_raw: '3EME', lot_id: 1 },
		]),
		'Martin',
	),
	{ batiment_id: 2, batiment_nom: '2', etage: 3 },
);
verifier(
	'une cave seule ne localise rien',
	localisationParNom(sources([{ nom_coproprietaire: 'MARTIN Luc', type_raw: 'CA 3' }]), 'Martin'),
	null,
);
verifier(
	'ligne non résolue : son propre bâtiment',
	localisationParNom(
		sources([
			{
				nom_coproprietaire: 'DURAND',
				type_raw: 'AP',
				etage_raw: 'RDC',
				batiment_id: 4,
				batiment_nom: 'Bât. 4',
			},
		]),
		'Durand',
	),
	{ batiment_id: 4, batiment_nom: '4', etage: 0 },
);
verifier('aucune ligne', localisationParNom(sources([]), 'Martin'), null);

if (echecs.length) {
	console.error(`\n✗ Rapprochement de l'annuaire — ${echecs.length} cas sur ${cas} :\n`);
	console.error(echecs.join('\n'));
	process.exit(1);
}
console.log(`✓ Rapprochement de l'annuaire : ${cas} cas éprouvés.`);
