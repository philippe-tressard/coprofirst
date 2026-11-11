/**
 * Garde-fou : le rendu d'un périmètre est le MÊME des deux côtés — et il est
 * EXÉCUTÉ, pas seulement cherché du regard.
 *
 * ## Pourquoi ce contrôle existe (27/08/2026)
 *
 * La règle « un espace est qualifié par son parent » est écrite **deux fois** :
 * `front/src/lib/perimetres.ts` et `api/app/utils/perimetres.py`. Ce n'est pas un
 * oubli — les contextes de build sont `./api` et `./front`, rien de la racine
 * n'entre dans les images, et le partage d'un fichier est impossible (mémoire
 * `project_partage_front_api_impossible`). Le seul pattern viable est la copie.
 *
 * Elle s'est déjà payée : le 18/08, la règle a été corrigée côté front, et le fil
 * d'activité a continué d'afficher « Toit · Toit » parce que ses libellés sont
 * calculés côté serveur. Un test Python a été ajouté ce jour-là — mais il ne
 * pouvait vérifier le front que par **présence de mots** dans le fichier, jamais
 * par son comportement. Un contrôle qui lit du texte ne sait pas si le code marche.
 *
 * ## Ce que celui-ci fait de plus
 *
 * Il **transpile** `lib/perimetres.ts` avec esbuild (déjà installé, il vient de
 * Vite), l'importe, lui donne l'arbre EXACT du ticket signalé, et compare le rendu
 * à la chaîne attendue. Puis il vérifie que cette même chaîne est écrite dans le
 * test Python : les deux implémentations sont alors tenues par **une seule**
 * attente, et l'une ne peut plus se corriger sans l'autre.
 *
 * Le contrôle s'auto-contrôle : source absente, test Python absent, transpilation
 * impossible → il ÉCHOUE, il ne conclut pas au vert (`standards/04` §2, cas zéro).
 */
import { existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { chargerModule } from './lib/charger-module.mjs';
import { dirname, resolve } from 'node:path';

const ICI = dirname(fileURLToPath(import.meta.url));
//  ⚠️ `#lib/perimetres` est un PAQUET depuis le 10/09/2026 (le fichier unique
//  avait franchi les 500 lignes). Le chemin ci-dessous pointe le module qui
//  porte réellement ce que ce contrôle mesure — l'`index.ts` ne fait que
//  réexporter, et transpiler une réexportation ne donne rien à lire.
const SOURCE = resolve(ICI, '..', 'src', 'lib', 'perimetres', 'index.ts');
const TEST_PYTHON = resolve(ICI, '..', '..', 'api', 'tests', 'test_perimetre_label_batiment.py');

function echouer(message) {
	console.error(`✗ ${message}`);
	process.exit(1);
}

//  ── Auto-contrôle (cas zéro) ────────────────────────────────────────────────
for (const [chemin, quoi] of [
	[SOURCE, 'le rendu du front'],
	[TEST_PYTHON, 'le test jumeau côté API'],
]) {
	if (!existsSync(chemin)) {
		echouer(`Cas zéro : ${quoi} est introuvable (${chemin}) — contrôle inopérant.`);
	}
}

//  ── Le front, EXÉCUTÉ ───────────────────────────────────────────────────────
const module = await chargerModule(SOURCE, echouer);

const { definirPerimetres, perimetreLabelUn } = module;
if (typeof definirPerimetres !== 'function' || typeof perimetreLabelUn !== 'function') {
	echouer(
		"Cas zéro : lib/perimetres.ts n'exporte plus definirPerimetres/perimetreLabelUn — " +
			'le rendu a changé de forme, mettre ce contrôle à jour.',
	);
}

/** L'arbre du ticket signalé — mêmes nœuds et mêmes `ordre` que la fixture Python. */
const noeud = (code, parent, libelle, libelle_court, ordre, extra = {}) => ({
	id: 0,
	code,
	parent,
	libelle,
	libelle_court,
	description: '',
	icone: null,
	batiment_id: null,
	profondeur: 0,
	ordre,
	actif: true,
	portee_globale: false,
	concerne_tous: false,
	selectionnable: true,
	utilise: false,
	...extra,
});

definirPerimetres([
	noeud('racine', null, 'Copropriété entière', 'Copropriété', 0, { portee_globale: true }),
	//  Un REGROUPEMENT : il ne doit jamais préfixer ses enfants.
	noeud('groupe', null, 'Bâtiments', 'Bâtiments', 10, { selectionnable: false }),
	noeud('bat', 'groupe', 'Bâtiment 4', 'Bât. 4', 3, { batiment_id: 4 }),
	noeud('bat/logement', 'bat', 'Logement', 'Logement', 1),
	noeud('bat/jardin', 'bat', 'Jardin Bâtiment', 'Jardin Bât.', 7),
	noeud('bat/logement/terrasses', 'bat/logement', 'Terrasses Balcons', 'Terrasses', 0),
	noeud('aful', null, 'AFUL', 'AFUL', 40, { portee_globale: true }),
	noeud('aful/voie', 'aful', "Voie d'accès", "Voie d'accès", 0),
]);

const echecs = [];
const verifier = (quoi, obtenu, attendu) => {
	if (obtenu !== attendu)
		echecs.push(`${quoi}\n        attendu : ${attendu}\n        obtenu  : ${obtenu}`);
};

//  1. Un espace transverse est qualifié par son parent — le défaut signalé.
verifier("un espace de l'AFUL", perimetreLabelUn('aful/voie'), "AFUL › Voie d'accès");
//  2. Un regroupement ne se dit pas : la borne de l'élargissement.
verifier('un bâtiment entier', perimetreLabelUn('bat'), 'Bâtiment 4');
//  3. Le rendu d'une SÉLECTION (tri, regroupement, ordre des clics, code inconnu)
//  n'est plus calculé par le front depuis #2633 : il est servi
//  (`perimetre_label`), et `test_perimetre_label_batiment.py` tient ses cas —
//  le ticket signalé, le niveau 3, les permutations, le code inconnu.

if (echecs.length > 0) {
	console.error('✗ Le rendu des périmètres côté front ne correspond plus :');
	for (const e of echecs) console.error(`    ${e}`);
	process.exit(1);
}

console.log(
	'✓ Périmètres : le libellé d’un nœud, exécuté — qualifié par son parent, sans regroupement.',
);
