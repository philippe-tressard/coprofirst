#!/usr/bin/env node
/**
 * Garde-fou : le périmètre HÉRITÉ par une nouvelle entrée d'historique.
 *
 * ## Le défaut (31/08/2026, signalé à l'écran)
 *
 * > *« quand on fait un commentaire sur un Ticket, par défaut le périmètre du
 * > dernier commentaire (ou du ticket original si 1er commentaire) n'est pas
 * > conservé »*
 *
 * Le formulaire proposait « Copropriété entière » sur un ticket situé
 * « Bât. 1 › Escaliers ». Il ne mentait pas sur ce qui allait s'écrire — le
 * serveur ne touche à rien quand le champ est vide — mais il **montrait un choix
 * par défaut qui n'était pas celui qui s'appliquerait**. Pour qui lit l'écran,
 * cela revient au même.
 *
 * ## Pourquoi un contrôle et pas une relecture
 *
 * `perimetreHerite` est une fonction PURE dont tout le sens tient dans trois cas
 * qui se ressemblent, et dont deux sont contre-intuitifs :
 *
 *   1. aucune entrée n'a précisé → le périmètre de l'objet ;
 *   2. une entrée a précisé → **la plus récente**, pas l'objet ;
 *   3. une entrée qui ne dit RIEN ne compte pas — elle n'a rien changé.
 *
 * Le cas 3 est celui qui se perd : il est tentant de prendre « la dernière
 * entrée » sans regarder si elle disait quelque chose, et l'on ferait alors
 * revenir le périmètre de l'objet à chaque commentaire vide.
 *
 * ⚠️ Ce dépôt n'a pas de lanceur de tests côté front : la fonction est
 * **transpilée et exécutée** ici, comme `lint:libelle-perimetre` le fait déjà
 * pour `perimetreLabel`. Vérifier le code à l'œil ne prouverait rien.
 *
 * Usage : npm run lint:perimetre-herite
 */
import { existsSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { chargerModule } from './lib/charger-module.mjs';

const RACINE = join(dirname(fileURLToPath(import.meta.url)), '..');
//  ⚠️ `#lib/perimetres` est un PAQUET depuis le 10/09/2026 (le fichier unique
//  avait franchi les 500 lignes). Le chemin ci-dessous pointe le module qui
//  porte réellement ce que ce contrôle mesure — l'`index.ts` ne fait que
//  réexporter, et transpiler une réexportation ne donne rien à lire.
const SOURCE = join(RACINE, 'src', 'lib', 'perimetres', 'arbre.ts');

function echouer(message) {
	console.error(`\n✗ ${message}\n`);
	process.exit(1);
}

if (!existsSync(SOURCE)) echouer(`Cas zéro : ${SOURCE} est introuvable — contrôle inopérant.`);

const module = await chargerModule(SOURCE, echouer);

const { perimetreHerite } = module;
if (typeof perimetreHerite !== 'function') {
	echouer(
		"Cas zéro : lib/perimetres.ts n'exporte plus `perimetreHerite` — la fonction " +
			'a disparu ou changé de nom, et ce contrôle ne mesure plus rien.',
	);
}

const CAS = [
	{
		quoi: "aucune entrée : le périmètre de l'objet",
		objet: ['bat:1', 'bat:1/escaliers'],
		entrees: [],
		attendu: ['bat:1', 'bat:1/escaliers'],
	},
	{
		quoi: 'une entrée qui ne précise RIEN ne change rien',
		objet: ['bat:1'],
		entrees: [{ contenu: 'vu sur place' }, { perimetre_cible: [] }],
		attendu: ['bat:1'],
	},
	{
		quoi: 'une entrée qui précise l’emporte sur l’objet',
		objet: ['bat:1'],
		entrees: [{ perimetre_cible: ['bat:1/escaliers'] }],
		attendu: ['bat:1/escaliers'],
	},
	{
		quoi: 'la PLUS RÉCENTE des entrées qui précisent',
		objet: ['bat:1'],
		entrees: [
			{ perimetre_cible: ['bat:1/escaliers'] },
			{ contenu: 'relance' },
			{ perimetre_cible: ['bat:1/cave'] },
		],
		attendu: ['bat:1/cave'],
	},
	{
		quoi: 'une entrée vide APRÈS une entrée qui précise ne revient pas en arrière',
		objet: ['bat:1'],
		entrees: [{ perimetre_cible: ['bat:1/escaliers'] }, { contenu: 'merci' }],
		attendu: ['bat:1/escaliers'],
	},
	{
		quoi: 'objet sans périmètre et rien de précisé : liste vide, jamais `undefined`',
		objet: null,
		entrees: [],
		attendu: [],
	},
];

const echecs = [];
for (const { quoi, objet, entrees, attendu } of CAS) {
	const obtenu = perimetreHerite(objet, entrees);
	if (JSON.stringify(obtenu) !== JSON.stringify(attendu)) {
		echecs.push(
			`   ${quoi}\n       attendu ${JSON.stringify(attendu)}, obtenu ${JSON.stringify(obtenu)}`,
		);
	}
}

//  Et la garantie qui ne se voit pas dans un résultat : la fonction ne doit pas
//  rendre le tableau d'origine, sinon le formulaire modifierait le ticket en
//  cochant une case.
const source = ['bat:1'];
const copie = perimetreHerite(source, []);
copie.push('bat:2');
if (source.length !== 1) {
	echecs.push(
		'   la valeur rendue PARTAGE le tableau de l’appelant\n' +
			'       cocher une case dans le formulaire modifierait le ticket lui-même',
	);
}

if (echecs.length) {
	console.error('\n✗ `perimetreHerite` ne se comporte pas comme prévu :\n');
	console.error(echecs.join('\n'));
	console.error(
		'\n  Le formulaire de commentaire propose ce périmètre par défaut. S’il se' +
			'\n  trompe, l’écran montre un choix qui n’est pas celui qui s’appliquera —' +
			'\n  c’est le défaut signalé le 31/08/2026.\n',
	);
	process.exit(1);
}

console.log(`✓ Périmètre hérité : ${CAS.length} cas vérifiés, et la valeur rendue est une copie.`);
