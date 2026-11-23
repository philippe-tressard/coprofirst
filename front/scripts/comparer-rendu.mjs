/**
 *  **Le rendu compilé a-t-il changé ?** — pour un lot de REFORMATAGE (#2900).
 *
 *  Un reformatage se dit « sans effet », et ne le prouve pas : prettier-plugin-svelte
 *  4.2 a coupé `{compte} {…'entrées'}` en deux lignes. L'écran restait le même, mais
 *  le texte du DOM portait « 5\n\t\t…entrées », et deux tests e2e qui lisent ce texte
 *  brut sont tombés. Deux cas trouvés par les tests ne prouvaient rien pour les 196
 *  autres fichiers. Ce qui le prouve, c'est de compiler chaque composant AVANT et
 *  APRÈS, en client et en serveur, et de comparer le code produit, espaces compris.
 *
 *  Il liste les composants dont le code compilé diffère. Un lot de reformatage n'en
 *  laisse aucun sans l'expliquer dans sa PR (`mep-precheck`, piège 4). Le code d'un
 *  composant réécrit exprès diffère, c'est attendu : on le dit, on ne le tait pas.
 *
 *  Lancer, depuis front/ : node scripts/comparer-rendu.mjs <réf. d'avant> [--selftest]
 */
import { execFileSync } from 'node:child_process';
import { readFileSync } from 'node:fs';
import { compile } from 'svelte/compiler';

/** Le code produit par un source, client et serveur, CSS compris. PURE. */
export function rendu(source, filename = 'C.svelte') {
	return ['client', 'server']
		.map((generate) => {
			const r = compile(source, { filename, generate, dev: false });
			return r.js.code + '\n/*css*/\n' + (r.css?.code ?? '');
		})
		.join('\n/*serveur*/\n');
}

/** Deux sources rendent-ils le même code ? PURE. */
export const memeRendu = (avant, apres) => rendu(avant) === rendu(apres);

const cas = [
	//  La forme collée et la forme dépliée de la 4.2 : Svelte 5 retire ces espaces.
	['<b>{a}</b>', '<b>\n\t{a}\n</b>', true],
	[
		'<button on:click={f}><Icone /></button>',
		'<button on:click={f}>\n\t<Icone />\n</button>',
		true,
	],
	//  Le défaut du lot : `{a} {b}` coupé en deux lignes, le texte du DOM change.
	[
		'<span>{n} {n > 1 ? "entrées" : "entrée"}</span>',
		'<span>\n\t{n}\n\t{n > 1 ? "entrées" : "entrée"}\n</span>',
		false,
	],
	['<p>Résilié le {d}</p>', '<p>Résilié le\n\t{d}</p>', false],
];

if (process.argv.includes('--selftest')) {
	let echecs = 0;
	for (const [avant, apres, attendu] of cas) {
		const obtenu = memeRendu(avant, apres);
		console.log(
			`${obtenu === attendu ? 'PASS' : 'FAIL'}  ${JSON.stringify(apres)} → ${obtenu ? 'même rendu' : 'rendu changé'}`,
		);
		if (obtenu !== attendu) echecs++;
	}
	console.log(echecs ? `✗ ${echecs} cas en défaut` : '== TOUS OK ==');
	process.exit(echecs ? 1 : 0);
}

const ref = process.argv[2];
if (!ref) {
	console.error('usage : node scripts/comparer-rendu.mjs <réf. d’avant> [--selftest]');
	process.exit(2);
}
const git = (...a) => execFileSync('git', a, { encoding: 'utf8' });
const racine = git('rev-parse', '--show-toplevel').trim();
const fichiers = git('-C', racine, 'diff', '--name-only', '--diff-filter=M', ref, '--', '*.svelte')
	.split('\n')
	.filter(Boolean);
const changes = fichiers.filter(
	(f) =>
		!memeRendu(git('-C', racine, 'show', `${ref}:${f}`), readFileSync(`${racine}/${f}`, 'utf8')),
);
changes.forEach((f) => console.log(`RENDU CHANGÉ  ${f}`));
console.log(
	`${fichiers.length} composant(s) comparé(s) depuis ${ref} : ${changes.length} au rendu changé.`,
);
process.exit(changes.length ? 1 : 0);
