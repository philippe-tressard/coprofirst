#!/usr/bin/env node
/**
 *  La palette SOMBRE couvre la charte, et se lit (#2174, lot S3, 29/10/2026).
 *
 *  ## Pourquoi
 *
 *  Le thème sombre redéfinit les jetons de `socle.css` dans un bloc à part
 *  (`styles/palette-sombre.css`). Deux défauts ne s'y voient pas à l'œil :
 *  - un jeton OUBLIÉ garde sa valeur claire — un texte foncé sur le bleu nuit,
 *    illisible, sur le seul écran qui l'emploie ;
 *  - une valeur sombre qui ne tient pas l'AA. La maquette a mesuré 58 paires ;
 *    rien ne les remesurait au réglage suivant.
 *
 *  ## Ce qu'il refuse
 *
 *  1. un jeton de thème du clair (`FAMILLES`) sans valeur sombre — sauf s'il
 *     DÉRIVE d'un autre (`var()`, `color-mix`, il suit alors sa source) ou s'il
 *     est déclaré IDENTIQUE avec sa raison (`palette-sombre-paires.mjs`) ;
 *  2. un jeton sombre que le clair ne définit pas, une valeur sombre égale à
 *     la valeur claire (à déclarer identique), une déclaration identique qui
 *     est aussi redéfinie ou n'existe plus ;
 *  3. une couleur de `:root` hors des familles du thème ;
 *  4. une paire de la table, ou un badge de `composants.css`, sous son seuil
 *     au SOMBRE ; au CLAIR, une paire sous son seuil qui n'en déclare pas
 *     l'écart, ou un écart déclaré qui ne sert plus ;
 *  5. une valeur qui ne se résout pas — INCONNU, jamais OK (standards/04 §2) ;
 *  6. un thème décidé HORS de la palette : `prefers-color-scheme` ou
 *     `data-theme` écrit dans un composant, une feuille ou un module de `src/`.
 *     Un écran ne porte pas de règle sombre — il lit les jetons ; sinon la
 *     règle se disperse et la bascule de S5 doit la retrouver partout.
 *
 *  Lancer : node scripts/check-palette-sombre.mjs [--selftest]
 */
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { contraste, declarationsDe, resoudre } from './lib-charte-jetons.mjs';
import { neutraliserCommentaires } from './lib-commentaires.mjs';
import { fichiersSources } from './lib-source-unique.mjs';
import { FAMILLES, IDENTIQUES, PAIRES } from './palette-sombre-paires.mjs';

const SRC = join(dirname(fileURLToPath(import.meta.url)), '..', 'src');
const STYLES = join(SRC, 'styles');
/** Où le thème se DÉCIDE : la palette, et rien d'autre (règle 6). */
const LIEUX_DU_THEME = ['styles/palette-sombre.css'];
const DECIDE_LE_THEME = /prefers-color-scheme|data-theme/;
export const SELECTEUR_SOMBRE = ":root[data-theme='dark']";

/** Le corps de la règle sombre, commentaires retirés, ou null. PURE. */
export function blocSombre(css) {
	const sans = css.replace(/\/\*[\s\S]*?\*\//g, '');
	const i = sans.indexOf(SELECTEUR_SOMBRE + ' {');
	if (i < 0) return null;
	const debut = i + SELECTEUR_SOMBRE.length + 2;
	const fin = sans.indexOf('}', debut);
	return fin < 0 ? null : sans.slice(debut, fin);
}

/** Le corps de la PREMIÈRE règle `:root {` d'une feuille, ou null — `:root, .ilot-clair {`
 *  compris : l'îlot clair reprend les jetons du thème clair (`styles/ilots-clairs.css`). PURE. */
export function blocRacine(css) {
	const m = css
		.replace(/\/\*[\s\S]*?\*\//g, '')
		.match(/^:root(?:\s*,\s*\.ilot-clair)?\s*\{([\s\S]*?)^\}/m);
	return m ? m[1] : null;
}

const COULEUR = /#[0-9a-f]{3,8}\b|rgba?\(|color-mix\(|\b(?:white|black)\b/i;
const DERIVE = /^(?:var|color-mix)\(/;

/** Les fautes de COUVERTURE (règles 1 à 3). PURE. */
export function fautesCouverture(clair, sombre, identiques = IDENTIQUES, familles = FAMILLES) {
	const fautes = [];
	const duTheme = (n) => familles.some((f) => n.startsWith(f));
	for (const [nom, valeur] of Object.entries(clair)) {
		if (!duTheme(nom)) {
			if (COULEUR.test(valeur))
				fautes.push(`${nom} : couleur hors des familles du thème (FAMILLES)`);
			continue;
		}
		if (nom in sombre) {
			if (nom in identiques) fautes.push(`${nom} : déclaré identique ET redéfini au sombre`);
			else if (sombre[nom].toLowerCase() === valeur.toLowerCase())
				fautes.push(`${nom} : même valeur qu'au clair — le déclarer dans IDENTIQUES`);
		} else if (!(nom in identiques) && !DERIVE.test(valeur)) {
			fautes.push(`${nom} : aucune valeur sombre, ni identique déclarée, ni dérivée`);
		}
	}
	for (const nom of Object.keys(sombre))
		if (!(nom in clair)) fautes.push(`${nom} : redéfini au sombre, absent du clair`);
	for (const nom of Object.keys(identiques))
		if (!(nom in clair)) fautes.push(`${nom} : déclaré identique, n'existe plus (IDENTIQUES)`);
	return fautes;
}

/** Le rapport d'une paire dans des jetons, ou null s'il échappe. PURE. */
export function rapport(avant, fond, jetons) {
	const [a, f] = [resoudre(avant, jetons), resoudre(fond, jetons)];
	if (!a || !f) return null;
	const r = contraste(a, f);
	return Number.isFinite(r) ? r : null;
}

const fmt = (r) => r.toFixed(2).replace('.', ',');

/** Les fautes de CONTRASTE (règles 4 et 5) dans les deux thèmes. PURE. */
export function fautesContraste(clair, sombre, paires = PAIRES) {
	const fautes = [];
	const themes = { clair, sombre: { ...clair, ...sombre } };
	for (const [usage, avant, fond, seuil, ecartClair] of paires) {
		for (const [theme, jetons] of Object.entries(themes)) {
			const r = rapport(avant, fond, jetons);
			if (r == null) {
				fautes.push(`${usage} (${theme}) : couleur non résolue — INCONNU`);
				continue;
			}
			const admis = theme === 'clair' && ecartClair;
			if (r < seuil && !admis) fautes.push(`${usage} (${theme}) : ${fmt(r)}:1, sous ${fmt(seuil)}`);
			if (r >= seuil && admis)
				fautes.push(`${usage} (clair) : ${fmt(r)}:1 tient désormais — retirer l'écart déclaré`);
		}
	}
	return fautes;
}

/** Les sources qui décident du thème hors de `LIEUX_DU_THEME` (règle 6). PURE. */
export function fautesLieux(sources, lieux = LIEUX_DU_THEME) {
	return sources
		.filter(([chemin]) => !lieux.some((l) => chemin.endsWith(l)))
		.filter(([, texte]) => DECIDE_LE_THEME.test(neutraliserCommentaires(texte)))
		.map(([chemin]) => `${chemin} : décide du thème hors de la palette (${lieux.join(', ')})`);
}

/** Les badges (`.badge-x { background; color }`) mesurés au sombre. PURE. */
export function fautesBadges(composants, jetons) {
	const fautes = [];
	const regles = [...composants.matchAll(/^\.badge-([a-z]+)\s*\{([^}]*)\}/gm)];
	for (const [, nom, corps] of regles) {
		const fond = corps.match(/background\s*:\s*([^;]+);/);
		const texte = corps.match(/(?:^|[\s;])color\s*:\s*([^;]+);/);
		if (!fond || !texte) continue;
		const r = rapport(texte[1], fond[1], jetons);
		if (r == null) fautes.push(`.badge-${nom} (sombre) : couleur non résolue — INCONNU`);
		else if (r < 4.5) fautes.push(`.badge-${nom} (sombre) : ${fmt(r)}:1, sous 4,5`);
	}
	return { fautes, lus: regles.length };
}

if (process.argv.includes('--selftest')) {
	let ko = 0;
	const cas = (libelle, obtenu, attendu) => {
		const ok = JSON.stringify(obtenu) === JSON.stringify(attendu);
		if (!ok) ko = 1;
		console.log(`${ok ? 'PASS' : 'FAIL'}  ${libelle} → ${JSON.stringify(obtenu)}`);
	};
	const clair = {
		'--color-bg': '#ffffff',
		'--color-text': '#000000',
		'--color-plein': 'var(--color-text)',
		'--color-sur': '#ffffff',
		'--radius': '0.5rem',
	};
	const sombre = { '--color-bg': '#000000', '--color-text': '#ffffff' };
	const id = { '--color-sur': 'raison' };
	const fam = ['--color-'];
	cas('cas zéro : couverture complète', fautesCouverture(clair, sombre, id, fam), []);
	cas(
		'un jeton oublié est refusé',
		fautesCouverture(clair, { '--color-bg': '#000000' }, id, fam).length,
		1,
	);
	cas(
		'jeton orphelin, valeur égale, identique redéfini, identique disparu, couleur hors famille',
		fautesCouverture(
			{ ...clair, '--autre': '#123456' },
			{ ...sombre, '--color-x': '#111111', '--color-sur': '#eeeeee' },
			{ ...id, '--color-parti': 'r' },
			fam,
		).length,
		4,
	);
	cas(
		'une valeur sombre égale à la claire',
		fautesCouverture(clair, { ...sombre, '--color-bg': '#FFFFFF' }, id, fam).length,
		1,
	);
	const paireOk = ['texte', 'var(--color-text)', 'var(--color-bg)', 4.5];
	cas(
		'cas zéro : une paire qui tient dans les deux thèmes',
		fautesContraste(clair, sombre, [paireOk]),
		[],
	);
	cas(
		'une paire FAUTIVE au sombre échoue',
		fautesContraste(clair, { '--color-bg': '#000000', '--color-text': '#111111' }, [paireOk])
			.length,
		1,
	);
	cas(
		'un écart clair déclaré qui ne sert plus échoue',
		fautesContraste(clair, sombre, [[...paireOk, 'raison']]).length,
		1,
	);
	cas(
		'une valeur non résolue est INCONNU',
		fautesContraste(clair, sombre, [['x', 'var(--absent)', 'var(--color-bg)', 3]]).length,
		2,
	);
	cas(
		'color-mix et rgba se résolvent',
		[
			rapport('rgba(255, 255, 255, 0.55)', '#1e3a5f', {}).toFixed(2),
			rapport('#000000', 'color-mix(in srgb, #ffffff 50%, black)', {}).toFixed(2),
		],
		['4.66', '5.32'],
	);
	cas(
		'bloc sombre et bloc racine lus, commentaires retirés',
		[
			blocSombre(
				`/* ${SELECTEUR_SOMBRE} { } */\n@media screen {\n${SELECTEUR_SOMBRE} {\n --a: #000; }\n}`,
			),
			blocRacine(':root {\n --a: #fff;\n}\n:root[x] {\n}'),
		],
		['\n --a: #000; ', '\n --a: #fff;\n'],
	);
	cas(
		'le bloc racine partagé avec l’îlot clair est lu',
		blocRacine(':root,\n.ilot-clair {\n --a: #fff;\n}'),
		'\n --a: #fff;\n',
	);
	cas(
		'un badge sous 4,5 au sombre échoue',
		fautesBadges('.badge-a {\n\tbackground: var(--f);\n\tcolor: var(--t);\n}', {
			'--f': '#222222',
			'--t': '#333333',
		}).fautes.length,
		1,
	);
	cas(
		'un composant qui écrit son thème est refusé, un commentaire ou la palette non',
		fautesLieux([
			[
				'src/lib/A.svelte',
				'<style>@media (prefers-color-scheme: dark) { a { color: red } }</style>',
			],
			['src/app.css', '/* [data-theme] */'],
			['src/styles/palette-sombre.css', ":root[data-theme='dark'] {}"],
		]).length,
		1,
	);
	console.log(ko ? '== ÉCHECS ==' : '== TOUS OK ==');
	process.exit(ko);
}

const lire = (nom) => readFileSync(join(STYLES, nom), 'utf8');
const racine = blocRacine(lire('socle.css'));
const bloc = blocSombre(lire('palette-sombre.css'));
const clair = racine && declarationsDe(racine);
const sombre = bloc && declarationsDe(bloc);
if (!clair || !sombre || Object.keys(clair).length < 20 || Object.keys(sombre).length < 20) {
	console.error(
		`\n✗ Jetons non lus (${clair ? Object.keys(clair).length : 0} clairs, ` +
			`${sombre ? Object.keys(sombre).length : 0} sombres) : contrôle inopérant (INCONNU).\n`,
	);
	process.exit(2);
}
const badges = fautesBadges(lire('composants.css'), { ...clair, ...sombre });
if (!badges.lus) {
	console.error('\n✗ Aucun badge lu dans composants.css : contrôle inopérant (INCONNU).\n');
	process.exit(2);
}
const sources = fichiersSources(SRC, ['.svelte', '.css', '.ts', '.js']).map((c) => [
	c,
	readFileSync(c, 'utf8'),
]);
if (sources.length < 100) {
	console.error(`
✗ ${sources.length} source(s) lue(s) dans src/ : contrôle inopérant (INCONNU).
`);
	process.exit(2);
}
const fautes = [
	...fautesCouverture(clair, sombre),
	...fautesContraste(clair, sombre),
	...badges.fautes,
	...fautesLieux(sources),
];
if (fautes.length) {
	console.error(`\n✗ Palette sombre : ${fautes.length} faute(s) —`);
	for (const f of fautes) console.error(`   ${f}`);
	console.error(
		'\n   Les valeurs : styles/palette-sombre.css ; la table : scripts/palette-sombre-paires.mjs.\n',
	);
	process.exit(1);
}
console.log(
	`✓ Palette sombre : ${Object.keys(sombre).length} jetons redéfinis, ` +
		`${PAIRES.length} paires et ${badges.lus} badges à l'AA.`,
);
