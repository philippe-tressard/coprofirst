#!/usr/bin/env node
/**
 *  Dans la Suite, une section ÉTEIGNABLE lit ses motifs d'extinction (#1321).
 *
 *  ## Pourquoi
 *
 *  `sectionsDeLaSuite` (`#lib/evolutions`) décidait du Périmètre et de la
 *  Diffusion par `sectionPresente(entite, 'evolution', …)` — présente ou non,
 *  sans lire `inactivePour`. La Suite d'un Bogue les offrait donc, alors que la
 *  déclaration les dit inactives et que la création les éteint.
 *
 *  ## Ce qu'il refuse
 *
 *  Dans le corps de `sectionsDeLaSuite`, un `sectionPresente(entite,
 *  'evolution', '<id>')` dont l'id figure dans `SECTIONS_ETEIGNABLES`
 *  (`#lib/formulaire-affaire`, la liste des sections qu'une nature, un rôle ou
 *  une catégorie éteignent) : il doit passer par `sectionDeLaSuite(…, conditions)`.
 *
 *  Lancer : node scripts/check-suite-eteignable.mjs [--selftest]
 */
import { readFileSync } from 'node:fs';

const EVOLUTIONS = 'src/lib/evolutions.ts';
const AFFAIRE = 'src/lib/formulaire-affaire.ts';

/** Les ids de `SECTIONS_ETEIGNABLES`. PURE. */
export function eteignables(source) {
	const m = source.match(/SECTIONS_ETEIGNABLES[^=]*=\s*\[([\s\S]*?)\]/);
	return m ? [...m[1].matchAll(/'(\w+)'/g)].map((x) => x[1]) : [];
}

/** Les ids éteignables lus SANS leurs motifs dans `sectionsDeLaSuite`. PURE. */
export function lusSansMotif(source, ids) {
	const debut = source.indexOf('export function sectionsDeLaSuite');
	if (debut < 0) return null;
	const corps = source.slice(debut, source.indexOf('\n}\n', debut));
	return [...corps.matchAll(/sectionPresente\(\s*entite,\s*'evolution',\s*'(\w+)'\s*\)/g)]
		.map((x) => x[1])
		.filter((id) => ids.includes(id));
}

if (process.argv.includes('--selftest')) {
	let ko = 0;
	const t = (libelle, attendu, obtenu) => {
		const ok = JSON.stringify(attendu) === JSON.stringify(obtenu);
		console.log(`${ok ? 'PASS' : 'FAIL'}  ${libelle} → ${JSON.stringify(obtenu)}`);
		if (!ok) ko = 1;
	};
	const ids = ['perimetre', 'diffusion', 'destinataires'];
	const f = (lignes) => `export function sectionsDeLaSuite() {\n\treturn {\n${lignes}\n\t};\n}\n`;
	//  🔴 La forme du 26/09/2026 : le Périmètre sans ses motifs.
	t(
		'périmètre sans motif',
		['perimetre'],
		lusSansMotif(f("perimetre: d && sectionPresente(entite, 'evolution', 'perimetre'),"), ids),
	);
	t(
		'avec motifs',
		[],
		lusSansMotif(f("perimetre: d && sectionDeLaSuite(entite, 'perimetre', conditions),"), ids),
	);
	t(
		'non éteignable',
		[],
		lusSansMotif(f("piecesJointes: sectionPresente(entite, 'evolution', 'pieces_jointes'),"), ids),
	);
	t(
		'liste lue',
		['a', 'b'],
		eteignables("const SECTIONS_ETEIGNABLES: readonly IdSection[] = [\n\t'a',\n\t'b',\n];"),
	);
	console.log(ko ? '== ÉCHECS ==' : '== TOUS OK ==');
	process.exit(ko);
}

const ids = eteignables(readFileSync(AFFAIRE, 'utf8'));
const fautifs = lusSansMotif(readFileSync(EVOLUTIONS, 'utf8'), ids);
//  🔴 CAS ZÉRO (`standards/04` §2) : liste vide ou fonction introuvable.
if (ids.length < 5 || fautifs === null) {
	console.error(
		`\n✗ INCONNU : ${ids.length} section(s) éteignable(s) lue(s), sectionsDeLaSuite ${fautifs === null ? 'INTROUVABLE' : 'trouvée'} — mettre le contrôle à jour.\n`,
	);
	process.exit(2);
}
if (fautifs.length) {
	console.error(
		`\n✗ La Suite lit ${fautifs.join(', ')} sans leurs motifs d'extinction :\n  → \`sectionDeLaSuite(entite, '<id>', conditions)\`, comme la création.\n`,
	);
	process.exit(1);
}
console.log(`✓ Suite : les ${ids.length} sections éteignables lisent leurs motifs.`);
