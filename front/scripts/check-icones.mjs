#!/usr/bin/env node
/**
 * Garde-fou : tout nom d'icône écrit dans le front existe dans le catalogue.
 *
 * ## Pourquoi (#1045, point 2 — 24/09/2026)
 *
 * `Icon.svelte` rend `icons[name] ?? icons['help-circle']` : un nom inconnu ne
 * lève rien, ne journalise rien, et affiche un point d'interrogation à la place
 * de l'icône voulue. La règle « icône vérifiée dans `icones-svg.json` » était
 * écrite dans la checklist front (aujourd'hui dans `ux-patterns`) — et **aucun script ne lisait le
 * catalogue** du côté du code du front.
 *
 * Le jour où ce contrôle a été écrit, il a trouvé la faute qu'il décrit :
 * un composant de l'administration passait `icone="database"`, absent du
 * catalogue, depuis v2.19.0. La section s'affichait avec un « ? ».
 *
 * ## Ce qu'il lit — les quatre voies par lesquelles un nom arrive à `<Icon>`
 *
 *   1. `<Icon name="x">`, et tout littéral dans `<Icon name={… 'x' …}>` ;
 *   2. la prop `icone="x"` (ou `icone={… 'x' …}`) des composants qui la
 *      relaient — `SectionFormulaire`, `Pastille`, `EntetePage`… ;
 *   3. les champs `icon: 'x'` / `icone: 'x'` des tables (`pages.ts`,
 *      `raccourcis.ts`…) ;
 *   4. le repli d'une valeur d'icône : `…site_icone'] ?? 'x'`.
 *
 * Et une cinquième règle, qui tient les quatre premières : un composant qui
 * relaie une prop à `<Icon name={…}>` l'appelle **`icone`**. Un relais nommé
 * autrement (`symbole`, `picto`…) ferait passer ses noms sous la voie 2 sans
 * que personne le voie.
 *
 * ## Ce qu'il ne lit PAS, et qui le fait
 *
 * `ICONES_PERIMETRE`, `ICONES_EQUIPEMENT` et les icônes du seed sont tenues par
 * `api/tests/test_icones_svg.py`, avec l'égalité des deux copies du catalogue.
 * Une icône choisie en administration (`site_icone`, icône d'un périmètre)
 * vient de `ChampIcone`, qui ne propose QUE les clés du catalogue.
 *
 * Et une sixième (#2975, 24/11/2026) : **une icône se dessine par `Icon`, jamais
 * par un `<svg>` écrit dans un composant.** `SectionFormulaire` dessinait ses deux
 * chevrons à la main (12 × 8, tracés recopiés), à côté de `chevron-down` du
 * catalogue que `PastilleDeroulante` rendait déjà. Un `<svg>` hors d'`Icon.svelte`
 * est refusé, sauf un DESSIN déclaré dans `DESSINS` avec sa raison — et un dessin
 * déclaré qui n'a plus de `<svg>` fait échouer.
 *
 * Usage : npm run lint:icones            (auto-test : --selftest)
 */
import { readdirSync, readFileSync } from 'node:fs';
import { join, relative } from 'node:path';
import { fileURLToPath } from 'node:url';
import { neutraliserCommentaires } from './lib-commentaires.mjs';

const FRONT = fileURLToPath(new URL('..', import.meta.url));
const SRC = join(FRONT, 'src');

const LITTERAL = /['"]([a-z][a-z0-9-]*)['"]/g;

/** Le seul composant qui pose un `<svg>` autour d'une icône du catalogue. */
const ENVELOPPE = 'src/lib/components/Icon.svelte';

/**  Les `<svg>` qui sont des DESSINS, pas des icônes — avec leur raison. Une entrée
 *   qui n'a plus de `<svg>` fait échouer. */
const DESSINS = {
	'src/lib/components/DecorFeteDessin.svelte':
		'le décor d’une fête : une illustration composée, pas un pictogramme du catalogue',
	'src/lib/components/DecorFeteMouvement.svelte':
		'les décors animés des fêtes : des dessins en mouvement, pas des pictogrammes',
};

/** Les lignes d'un source qui ouvrent un `<svg>`, hors commentaires. PURE. */
export function svgEcrits(source) {
	return neutraliserCommentaires(source)
		.split('\n')
		.flatMap((l, i) => (/<svg\b/.test(l) ? [i + 1] : []));
}

/**
 * Les noms d'icônes écrits dans un source, avec leur ligne. Fonction PURE.
 */
export function nomsIcones(source) {
	const trouves = [];
	const ligne = (i) => source.slice(0, i).split('\n').length;
	const lire = (m) => {
		if (m[1] !== undefined) trouves.push({ ligne: ligne(m.index), nom: m[1] });
		else
			for (const l of m[2].matchAll(LITTERAL)) trouves.push({ ligne: ligne(m.index), nom: l[1] });
	};
	//  1. `<Icon … name="x">` ou `name={… 'x' …}`
	for (const m of source.matchAll(/<Icon\b[^>]*?\bname=(?:"([^"]*)"|\{([^}]*)\})/g)) lire(m);
	//  2. la prop relayée `icone="x"` ou `icone={… 'x' …}`
	for (const m of source.matchAll(/\bicone=(?:"([^"]*)"|\{([^}]*)\})/g)) lire(m);
	//  3. un champ de table `icon: 'x'` / `icone: 'x'`
	for (const m of source.matchAll(/\bicone?\s*:\s*['"]([a-z][a-z0-9-]*)['"]/g))
		trouves.push({ ligne: ligne(m.index), nom: m[1] });
	//  4. le repli d'une valeur d'icône : `…icone'] ?? 'x'`, `icon || 'x'`
	for (const m of source.matchAll(/icone?\b[^\n;]*?(?:\?\?|\|\|)\s*['"]([a-z][a-z0-9-]*)['"]/g))
		trouves.push({ ligne: ligne(m.index), nom: m[1] });
	//  ⚠️ `icone=""` (aucune icône) est un choix, pas un nom.
	return trouves.filter((t) => t.nom !== '');
}

/**
 * Les props d'un composant relayées à `<Icon name={prop}>` sous un autre nom
 * que `icone`. Fonction PURE.
 */
export function relaisMalNommes(source) {
	const props = new Set([...source.matchAll(/export let (\w+)/g)].map((m) => m[1]));
	return [...source.matchAll(/<Icon\b[^>]*?\bname=\{\s*(\w+)\s*\}/g)]
		.map((m) => m[1])
		.filter((p) => props.has(p) && p !== 'icone');
}

function fichiers(dossier) {
	return readdirSync(dossier, { withFileTypes: true }).flatMap((d) => {
		const chemin = join(dossier, d.name);
		if (d.isDirectory()) return fichiers(chemin);
		return /\.(svelte|ts)$/.test(d.name) ? [chemin] : [];
	});
}

function selftest() {
	let echecs = 0;
	const verifier = (nom, obtenu, attendu) => {
		const ok = JSON.stringify(obtenu) === JSON.stringify(attendu);
		if (!ok) echecs++;
		console.log(`${ok ? 'PASS' : 'ÉCHEC'}  ${nom} → ${JSON.stringify(obtenu)}`);
	};
	const noms = (s) => nomsIcones(s).map((t) => t.nom);
	verifier('voie 1 : littéral', noms('<Icon name="bell" size={16} />'), ['bell']);
	verifier('voie 1 : ternaire', noms("<Icon name={v ? 'eye-off' : 'eye'} />"), ['eye-off', 'eye']);
	verifier('voie 1 : repli dans la balise', noms("<Icon name={pg.icone || 'help-circle'} />"), [
		'help-circle',
		'help-circle',
	]);
	verifier('voie 2 : prop relayée', noms('<SectionFormulaire titre="x" icone="database" />'), [
		'database',
	]);
	verifier('voie 2 : prop vide = aucune icône', noms('<Pastille icone="">x</Pastille>'), []);
	verifier(
		'voie 3 : champ de table',
		noms("{ href: '/x', icon: 'home' }, { icone: 'key-round' }"),
		['home', 'key-round'],
	);
	verifier(
		'voie 4 : repli de configuration',
		noms("$: b = $configStore['site_icone'] ?? 'building-2';"),
		['building-2'],
	);
	verifier('slot nommé : pas une icône', noms('<slot name="actions" />'), []);
	verifier('classe de badge : pas une icône', noms("const c = STATUT[s] ?? 'badge-gray';"), []);
	verifier('cas zéro : source vide', noms(''), []);
	//  🔴 Le chevron de `SectionFormulaire`, dessiné à la main (#2975).
	verifier(
		'svg écrit dans un composant',
		svgEcrits('<button>\n\t<svg class="section-chev" width="12" height="8">\n</svg></button>'),
		[2],
	);
	verifier('svg cité en commentaire', svgEcrits('<!-- un <svg> écrit à la main -->'), []);
	verifier('icône du catalogue', svgEcrits('<Icon name="chevron-down" size={20} />'), []);
	verifier(
		'relais nommé `icone` : accepté',
		relaisMalNommes('export let icone = "";\n<Icon name={icone} />'),
		[],
	);
	verifier(
		'relais nommé autrement : refusé',
		relaisMalNommes('export let picto;\n<Icon name={picto} />'),
		['picto'],
	);
	verifier(
		'variable locale (pas une prop) : pas un relais',
		relaisMalNommes('let brandIcon = "x";\n<Icon name={brandIcon} />'),
		[],
	);
	console.log(echecs ? `== ${echecs} ÉCHEC(S) ==` : '== TOUS OK ==');
	return echecs ? 1 : 0;
}

if (process.argv.includes('--selftest')) process.exit(selftest());

let catalogue;
try {
	catalogue = JSON.parse(readFileSync(join(SRC, 'lib', 'icones-svg.json'), 'utf8'));
} catch (e) {
	console.error(`\n⚠️  INCONNU — catalogue illisible : ${e.message}\n`);
	process.exit(2);
}

const inconnus = [];
const relais = [];
const svg = [];
const dessinsServis = new Set();
let enveloppe = false;
let lus = 0;
for (const f of fichiers(SRC)) {
	const source = readFileSync(f, 'utf8');
	const chemin = relative(FRONT, f).split('\\').join('/');
	const lignesSvg = f.endsWith('.svelte') ? svgEcrits(source) : [];
	if (chemin === ENVELOPPE) enveloppe = lignesSvg.length > 0;
	else if (chemin in DESSINS) {
		if (lignesSvg.length) dessinsServis.add(chemin);
	} else for (const l of lignesSvg) svg.push(`${chemin}:${l}`);
	for (const t of nomsIcones(source)) {
		lus++;
		if (!Object.hasOwn(catalogue, t.nom)) inconnus.push(`${chemin}:${t.ligne} — « ${t.nom} »`);
	}
	for (const p of relaisMalNommes(source)) relais.push(`${chemin} — prop \`${p}\``);
}

//  🔴 CAS ZÉRO — un motif devenu muet rendrait « aucune faute » sans rien lire.
//  Plus de cent noms le jour de l'écriture : sous cinquante, le relevé a cassé.
if (lus < 50) {
	console.error(
		`\n⚠️  INCONNU — ${lus} nom(s) d'icône relevé(s) : le motif ne lit plus le code.\n`,
	);
	process.exit(2);
}

//  Le témoin : `Icon.svelte` pose l'enveloppe. Sans elle, « aucun <svg> ailleurs »
//  ne prouverait plus rien.
if (!enveloppe) {
	console.error(
		`\n⚠️  INCONNU — ${ENVELOPPE} ne pose plus de <svg> : le relevé a perdu son témoin.\n`,
	);
	process.exit(2);
}
const dessinsMorts = Object.keys(DESSINS).filter((d) => !dessinsServis.has(d));
if (dessinsMorts.length) {
	console.error(
		`\n✗ lint:icones — dessin(s) déclaré(s) sans <svg> : ${dessinsMorts.join(', ')} — les retirer de DESSINS.\n`,
	);
}
if (svg.length) {
	console.error(
		`\n✗ lint:icones — ${svg.length} <svg> écrit(s) hors d’\`Icon\` :\n\n  ` +
			svg.join('\n  ') +
			'\n\n  Une icône se rend par `<Icon name="…" />`, tracé pris dans le catalogue.\n' +
			'  Un dessin qui n’est pas une icône se déclare dans DESSINS, avec sa raison.\n',
	);
}
if (relais.length) {
	console.error(
		`\n✗ lint:icones — ${relais.length} composant(s) relaient une icône sous un autre nom que \`icone\` :\n\n  ` +
			relais.join('\n  ') +
			'\n\n  Les noms qu’on leur passe échapperaient à ce contrôle. Renommer la prop `icone`.\n',
	);
}
if (inconnus.length) {
	console.error(
		`\n✗ lint:icones — ${inconnus.length} nom(s) d’icône absent(s) de \`#lib/icones-svg.json\` :\n\n  ` +
			inconnus.join('\n  ') +
			'\n\n  `Icon` les rendrait en « ? » (help-circle), sans un mot. Choisir un nom du\n' +
			'  catalogue, ou y ajouter le tracé Lucide — dans les DEUX copies :\n' +
			'    cp front/src/lib/icones-svg.json api/app/utils/icones-svg.json\n',
	);
}
if (relais.length || inconnus.length || svg.length || dessinsMorts.length) process.exit(1);

console.log(
	`✓ lint:icones — ${lus} nom(s) d’icône relevé(s), tous dans le catalogue ` +
		`(${Object.keys(catalogue).length} icônes).`,
);
