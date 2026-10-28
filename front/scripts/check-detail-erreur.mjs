#!/usr/bin/env node
/**
 * Un refus du serveur se lit-il en PHRASE ? (#1327, 25/09/2026) —
 * `#lib/detail-erreur` est transpilé et EXÉCUTÉ sur les formes réelles, et le
 * client doit l'appeler.
 *
 * Signalé à l'écran sur « Nouveau prestataire » : le toast affichait
 * `[{"type":"value_error","loc":["body","contacts"],"msg":"Value error, …"}]`.
 * Le client recopiait le `detail` d'un 422 par `JSON.stringify`.
 */
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { chargerModule } from './lib/charger-module.mjs';

const RACINE = join(dirname(fileURLToPath(import.meta.url)), '..');
const echouer = (m) => {
	console.error(`\n✗ ${m}\n`);
	process.exit(1);
};
const { detailLisible } = await chargerModule(
	join(RACINE, 'src', 'lib', 'detail-erreur.ts'),
	echouer,
);
if (typeof detailLisible !== 'function') {
	echouer('Cas zéro : `#lib/detail-erreur` n’exporte plus `detailLisible` — rien n’est mesuré.');
}

const REPLI = 'Erreur';
//  🔴 La forme EXACTE du toast signalé — le cas qui a fait écrire ce contrôle.
const SIGNALE = [
	{
		type: 'value_error',
		loc: ['body', 'contacts'],
		msg: 'Value error, un contact au moins : son nom, et un téléphone ou un e-mail',
		input: [],
		ctx: { error: {} },
	},
];
const CAS = [
	[SIGNALE, 'Un contact au moins : son nom, et un téléphone ou un e-mail'],
	['Prestataire introuvable', 'Prestataire introuvable'],
	[
		[
			{ msg: 'Field required', loc: ['body', 'nom'] },
			{ msg: 'Field required', loc: ['body', 'specialite'] },
		],
		'Field required',
	],
	[[{ msg: 'a' }, { msg: 'Assertion error, b' }], 'A ; B'],
	[{ inattendu: true }, REPLI],
	[[], REPLI],
	[undefined, REPLI],
	['', REPLI],
];
const echecs = [];
for (const [detail, attendu] of CAS) {
	const rendu = detailLisible(detail, REPLI);
	if (rendu !== attendu)
		echecs.push(`${JSON.stringify(detail)} → « ${rendu} », attendu « ${attendu} »`);
	if (/[[{]"/.test(rendu)) echecs.push(`${JSON.stringify(detail)} rend encore du JSON : ${rendu}`);
}

//  Le client doit passer par elle — une fonction juste que personne n'appelle
//  ne change rien à l'écran.
const client = readFileSync(join(RACINE, 'src', 'lib', 'api', 'client.ts'), 'utf8');
if (!/detailLisible\(/.test(client))
	echecs.push('`api/client.ts` n’appelle pas `detailLisible` — le toast retomberait en JSON');
if (/JSON\.stringify\(\s*err\.detail/.test(client))
	echecs.push('`api/client.ts` recopie encore `err.detail` par `JSON.stringify`');

if (echecs.length) {
	console.error('\n✗ Un refus du serveur ne se lit pas en phrase :\n');
	for (const e of echecs) console.error(`    ${e}`);
	process.exit(1);
}
console.log(
	`✓ Détail d’erreur : ${CAS.length} formes vérifiées, dont le 422 signalé — et le client l’emploie.`,
);
