#!/usr/bin/env node
/**
 *  Une couleur et une taille de texte se lisent dans la charte, pas en dur
 *  (#1055, 27/09/2026).
 *
 *  ## Pourquoi
 *
 *  `styles/socle.css` définit la charte — couleurs, et depuis #1055 une échelle
 *  typographique (`--fs-*`). Les écrans l'ignoraient : 265 couleurs et 566
 *  tailles de texte écrites en dur dans leurs `<style>` et leurs `style="…"`,
 *  dont 42 valeurs de taille différentes. Chaque changement de charte demandait
 *  donc de rouvrir cinquante fichiers — et `lint:charte` comme `lint:css-duplique`
 *  contrôlent des RÈGLES et des CLASSES, jamais des VALEURS : ils ne voyaient rien.
 *
 *  ## Ce qu'il mesure
 *
 *  Les couleurs hexadécimales et les `font-size` en `rem`, commentaires
 *  retirés : dans les fichiers `.svelte` (blocs `<style>` et attributs
 *  `style="…"`) **et** dans les feuilles de `src/styles/` — sauf `socle.css`,
 *  qui DÉFINIT les jetons et n'a donc que des valeurs.
 *
 *  🔴 Les feuilles étaient hors relevé jusqu'au 30/09/2026 (#1460), comme « la
 *  charte ». Remonter une règle d'un composant vers `src/styles/` faisait alors
 *  BAISSER le plafond sans rien solder : #779 l'a fait pour huit couleurs, et
 *  l'historique le disait en toutes lettres pendant que le compteur, lui, ne
 *  le distinguait pas. Un seul plafond pour les deux lieux : un déménagement
 *  est neutre, seule une valeur remplacée par un jeton le fait descendre.
 *
 *  ## Un PLAFOND, et il ne fait que baisser
 *
 *  Tout convertir d'un coup changerait des rendus avant qu'on en ait regardé un
 *  seul (R5 du cadre #430). Le plafond empêche d'en AJOUTER ; il échoue aussi
 *  quand le compte passe DESSOUS — le plafond se baisse alors dans le même lot,
 *  sinon la marge regagnée serait reprise sans un mot par le suivant.
 *
 *  Lancer : node scripts/check-charte-valeurs.mjs [--selftest]
 */
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { dirname, join, relative, sep } from 'node:path';
import { fileURLToPath } from 'node:url';
import {
	contraste,
	contrastesBadges,
	egalesAUnJeton,
	jetonsDe,
	repliMortsDe,
	resoudre,
} from './lib-charte-jetons.mjs';

export { contraste, contrastesBadges, egalesAUnJeton, jetonsDe, repliMortsDe, resoudre };

/**
 *  Le compte autorisé, et son historique : c'est lui qui dit à quel rythme la
 *  dette se solde.
 *  27/09/2026 (#1055) : relevé 266 couleurs et 569 tailles. Le même jour, après
 *  arbitrage sur maquette : 124 et 62 — les tailles hors échelle rangées au cran
 *  supérieur, les couleurs d'état de Tailwind remplacées par la charte.
 *  30/09/2026 (#1460) : les feuilles de `src/styles/` entrent dans le relevé
 *  (172 couleurs, 129 tailles) ; 29/09 (#779) avait DÉPLACÉ huit teintes de
 *  rôle vers `composants.css`, sans les solder.
 *  Octobre 2026 (#779, #1537, #1571) : 167 → 81 couleurs et 129 → 69 tailles.
 *  Les valeurs ÉGALES à un jeton (`egalesAUnJeton`) et les repliements morts
 *  (`repliMortsDe`) sont devenus INTERDITS, sans plafond ; les classes mortes
 *  des feuilles globales sont retirées. Le détail ligne à ligne : `git log` de
 *  ce fichier.
 *  29/10/2026 (#2174, mode sombre S1) : ZÉRO couleur — les 81 dernières (47
 *  nuances) se rangent sur 31 jetons de `socle.css` (12 neufs) — redéfinis au sombre.
 */
//  Carte des plafonds décroissants : #1571.
const PLAFOND = { couleurs: 0, tailles: 69 };

const RACINE = join(dirname(fileURLToPath(import.meta.url)), '..', 'src');

/** Le CSS d'un composant : ses blocs `<style>` et ses attributs `style="…"`. */
export function stylesDe(source) {
	const sans = source.replace(/<!--[\s\S]*?-->/g, '');
	const blocs = [...sans.matchAll(/<style[^>]*>([\s\S]*?)<\/style>/g)].map((m) => m[1]);
	const attributs = [...sans.matchAll(/\bstyle="([^"]*)"/g)].map((m) => m[1]);
	return [...blocs, ...attributs].join('\n').replace(/\/\*[\s\S]*?\*\//g, '');
}

/** Le CSS d'une feuille : tout le fichier, commentaires retirés. */
export function stylesDeFeuille(source) {
	return source.replace(/\/\*[\s\S]*?\*\//g, '');
}

/**
 *  La feuille qui DÉFINIT les jetons : hors relevé des valeurs.
 *  ⚠️ `app.css` n'a que des `@import` (#453) ; s'il reprenait des règles, il
 *  faudrait le relever aussi — le contrôle ne le devinerait pas.
 */
export const FEUILLE_DES_JETONS = 'socle.css';
/** …et celle qui les REDÉFINIT au sombre (#2174, S3), hors relevé pour la même raison. */
const FEUILLES_DES_JETONS = [FEUILLE_DES_JETONS, 'palette-sombre.css'];

/** Couleurs hexadécimales et tailles de texte en `rem` écrites en dur. */
export function valeursEnDur(css) {
	return {
		couleurs: [...css.matchAll(/#[0-9a-fA-F]{3,8}\b/g)].map((m) => m[0]),
		tailles: [...css.matchAll(/font-size\s*:\s*([0-9]*\.?[0-9]+)rem/g)].map((m) => m[1]),
	};
}

/**
 *  ## Ce qui est INTERDIT, sans plafond (arbitré le 27/09/2026, sur maquette)
 *
 *  Le plafond tolère une dette ; ces valeurs-ci ont été TRANCHÉES, elles ne se
 *  tolèrent plus nulle part — ni dans un composant, ni dans `src/styles/`.
 *
 *  - une taille hors échelle se range au cran SUPÉRIEUR : aucun texte ne
 *    rétrécit en se normalisant (lisibilité au pouce) ;
 *  - une couleur d'ÉTAT vient de la charte, jamais de la palette de Tailwind —
 *    le bloc des urgences de l'accueil portait deux rouges côte à côte ;
 *  - le texte sur un fond d'avertissement prend `--color-warning-texte` :
 *    `--color-warning` (3,62 sur blanc) ne sert pas au texte.
 *
 *  Le tableau dit la valeur de REMPLACEMENT : le message d'échec la donne.
 *
 *  ⚠️ Les palettes CATÉGORIELLES ne sont pas des états et restent hors de ce
 *  contrôle : la teinte d'un type du fil (`#lib/flux`), d'un périmètre
 *  (`#lib/perimetres/teinte`), d'une colonne de kanban, d'une nature
 *  (`--nature-fort`), l'orange de l'urgence, `.badge-yellow` (#495).
 */
export const TAILLES_HORS_ECHELLE = {
	0.65: '--fs-2xs',
	0.68: '--fs-2xs',
	0.7: '--fs-2xs',
	0.78: '--fs-sm',
	0.82: '--fs-md',
	0.875: '--fs-base',
	0.88: '--fs-base',
	0.92: '--fs-lg',
};

/**
 *  La DÉFINITION d'un jeton de palette catégorielle (`--fil-rouge: #b91c1c;`,
 *  #2174 S2) est la seule place où ces teintes s'écrivent : ce ne sont pas des
 *  états. Partout ailleurs, la même valeur reste refusée.
 */
const DEFINITION_CATEGORIELLE = /--(?:fil|teinte|kanban)-[\w-]+\s*:\s*#[0-9a-fA-F]{6}\s*;/g;

export const COULEURS_ETAT_ETRANGERES = {
	'#dc2626': '--color-danger',
	'#b91c1c': '--color-danger',
	'#991b1b': '--color-danger',
	'#7f1d1d': '--color-danger',
	'#ef4444': '--color-danger',
	'#fef2f2': '--color-danger-fond',
	'#fee2e2': '--color-danger-fond',
	'#fecaca': '--color-danger-bordure',
	'#16a34a': '--color-success',
	'#15803d': '--color-success',
	'#22c55e': '--color-success',
	'#166534': '--color-success',
	'#065f46': '--color-success',
	'#059669': '--color-success',
	'#10b981': '--color-success',
	'#f0fdf4': '--color-success-fond',
	'#dcfce7': '--color-success-fond',
	'#d1fae5': '--color-success-fond',
	'#ecfdf5': '--color-success-fond',
	'#bbf7d0': '--color-success-bordure',
	'#f59e0b': '--color-warning',
	'#d97706': '--color-warning',
	'#fbbf24': '--color-warning',
	'#b45309': '--color-warning',
	'#92400e': '--color-warning-texte',
	'#78350f': '--color-warning-texte',
	'#fffbeb': '--color-warning-fond',
	'#fef3c7': '--color-warning-fond',
	'#fde68a': '--color-warning-bordure',
	'#fcd34d': '--color-warning-bordure',
};

/** Les mêmes rouges, verts et ambres écrits en `rgb()` / `rgba()`. */
const RGB_ETAT =
	/rgba?\(\s*(220\s*,\s*38\s*,\s*38|239\s*,\s*68\s*,\s*68|22\s*,\s*163\s*,\s*74|245\s*,\s*158\s*,\s*11|217\s*,\s*119\s*,\s*6)\b/g;

/**
 *  Ce qui est interdit dans une source, commentaires retirés — le HISTORIQUE
 *  d'une couleur (« elle était `#f59e0b` ») reste lisible en commentaire.
 *  Les couleurs sont cherchées dans TOUT le fichier : une chaîne de style
 *  composée en JavaScript rend autant qu'un `<style>`.
 */
export function interditsDe(source) {
	const code = source
		.replace(DEFINITION_CATEGORIELLE, '')
		.replace(/<!--[\s\S]*?-->/g, '')
		.replace(/\/\*[\s\S]*?\*\//g, '')
		.replace(/(^|[^:'"])\/\/.*$/gm, '$1');
	const trouves = [];
	for (const m of code.matchAll(/font-size\s*:\s*([0-9]*\.?[0-9]+)rem/g)) {
		const jeton = TAILLES_HORS_ECHELLE[parseFloat(m[1])];
		if (jeton) trouves.push([`${m[1]}rem`, `var(${jeton})`]);
	}
	for (const m of code.matchAll(/#[0-9a-fA-F]{6}\b/g)) {
		const jeton = COULEURS_ETAT_ETRANGERES[m[0].toLowerCase()];
		if (jeton) trouves.push([m[0], `var(${jeton})`]);
	}
	for (const m of code.matchAll(RGB_ETAT))
		trouves.push([m[0] + '…)', 'color-mix(… var(--color-…) …)']);
	return trouves;
}

/**
 *  Les exceptions : aucune. Une entrée s'écrit `'chemin': 'raison'`, et le
 *  contrôle échoue si elle ne sert plus — une exception sans objet est un
 *  passe-droit en attente.
 */
const EXCEPTIONS = {};

if (process.argv.includes('--selftest')) {
	let ko = 0;
	const cas = (libelle, obtenu, attendu) => {
		const ok = JSON.stringify(obtenu) === JSON.stringify(attendu);
		if (!ok) ko = 1;
		console.log(`${ok ? 'PASS' : 'FAIL'}  ${libelle} → ${JSON.stringify(obtenu)}`);
	};
	const composant = `<div style="font-size:.8rem;color:#fff">a</div>
<!-- <p style="color:#123456"></p> -->
<style>
	/* #abcdef dans un commentaire ne compte pas */
	.a { color: #dc2626; font-size: 0.85rem; }
	.b { color: var(--color-danger); font-size: var(--fs-sm); }
</style>`;
	const v = valeursEnDur(stylesDe(composant));
	cas('couleurs du bloc et de l’attribut, pas des commentaires', v.couleurs, ['#dc2626', '#fff']);
	cas('tailles en rem du bloc et de l’attribut', v.tailles, ['0.85', '.8']);
	cas('une variable de charte ne compte pas', valeursEnDur('.b{color:var(--x)}').couleurs, []);
	cas(
		'le hors-style ne compte pas (texte, script)',
		valeursEnDur(stylesDe('<p>#1 font-size: 2rem</p><script>const c="#fff"</script>')),
		{ couleurs: [], tailles: [] },
	);
	cas(
		'taille hors échelle → cran supérieur',
		interditsDe('<style>.a{font-size:.78rem}.b{font-size: 0.875rem}.c{font-size:0.8rem}</style>'),
		[
			['.78rem', 'var(--fs-sm)'],
			['0.875rem', 'var(--fs-base)'],
		],
	);
	cas(
		'couleur d’état étrangère, en style ET en chaîne JavaScript',
		interditsDe(
			'<script>const s = "color:#92400e"</script><style>.a{border:1px solid #DC2626}</style>',
		),
		[
			['#92400e', 'var(--color-warning-texte)'],
			['#DC2626', 'var(--color-danger)'],
		],
	);
	cas(
		'une palette catégorielle se DÉFINIT en hexadécimal, et nulle part ailleurs',
		interditsDe(':root{--fil-rouge:#b91c1c;--teinte-1:#ef4444;}.a{color:#b91c1c}'),
		[['#b91c1c', 'var(--color-danger)']],
	);
	cas(
		'rgba d’un rouge Tailwind',
		interditsDe('.a{box-shadow:0 2px 8px rgba(220, 38, 38, 0.15)}').length,
		1,
	);
	cas(
		'un commentaire garde l’historique, une couleur de charte passe',
		interditsDe('<!-- #f59e0b --><style>/* #dc2626 */ .a{color:#c0392b} // #16a34a\n</style>'),
		[],
	);
	cas(
		'une feuille : tout compte, sauf les commentaires',
		valeursEnDur(stylesDeFeuille('/* #abcdef */\n.a { color: #123; font-size: 0.8rem; }')),
		{ couleurs: ['#123'], tailles: ['0.8'] },
	);
	cas(
		'déplacer une règle d’un composant vers une feuille ne change pas le compte',
		[
			valeursEnDur(stylesDe('<style>.p{color:#8e44ad;font-size:.9rem}</style>')),
			valeursEnDur(stylesDeFeuille('.p{color:#8e44ad;font-size:.9rem}')),
		].map((v) => v.couleurs.length + v.tailles.length),
		[2, 2],
	);
	cas(
		'contraste du vert de la charte sur son fond',
		contraste('#2e7d52', '#e6f4ee').toFixed(2),
		'4.44',
	);
	cas(
		'un badge se résout par les jetons, et une valeur inconnue rend null',
		contrastesBadges(
			'.badge-a {\n\tbackground: var(--f);\n\tcolor: var(--t);\n}\n.badge-b {\n\tbackground: var(--absent);\n\tcolor: #000000;\n}',
			':root {\n\t--f: #ffffff;\n\t--t: #000000;\n}',
		).map((b) => [b.nom, b.rapport && Math.round(b.rapport)]),
		[
			['a', 21],
			['b', null],
		],
	);
	const jetons = jetonsDe(
		`:root {
	--color-surface: #ffffff;
	--color-bg: #f2efe9;
	--color-text-inverse: #f2efe9;
	--fs-sm: 0.8rem;
	--radius: 0.5rem;
}`,
	);
	cas(
		'valeur égale à un jeton : couleur courte ou longue, taille, et les deux noms d’une valeur',
		egalesAUnJeton('.a{color:#FFF;background:#ffffff;font-size:.80rem}.b{color:#f2efe9}', jetons),
		[
			['.80rem', 'var(--fs-sm)'],
			['#FFF', 'var(--color-surface)'],
			['#ffffff', 'var(--color-surface)'],
			['#f2efe9', 'var(--color-bg) ou var(--color-text-inverse)'],
		],
	);
	cas(
		'ni une transparence, ni un jeton hors charte (rayon), ni une taille sans nom',
		egalesAUnJeton('.a{color:#ffffff80;padding:.5rem;font-size:0.5rem;font-size:1rem}', jetons),
		[],
	);
	cas(
		'repli mort : un jeton défini avec un repli, pas une propriété de composant ni un jeton sans repli',
		repliMortsDe(
			'.a{border:1px solid var(--color-border, #e5e7eb);width:var(--avatar-size, 2.5rem);color:var(--color-border)}',
			':root {\n\t--color-border: #d0d8e4;\n}',
		),
		[['var(--color-border, #e5e7eb)', 'var(--color-border)']],
	);
	console.log(ko ? '== ÉCHECS ==' : '== TOUS OK ==');
	process.exit(ko);
}

function fichiers(dir, acc = []) {
	for (const nom of readdirSync(dir)) {
		const chemin = join(dir, nom);
		if (statSync(chemin).isDirectory()) fichiers(chemin, acc);
		else if (nom.endsWith('.svelte')) acc.push(chemin);
	}
	return acc;
}

const total = { couleurs: 0, tailles: 0 };
const parFichier = [];
let blocsLus = 0;
let feuillesLues = 0;
const STYLES = join(RACINE, 'styles');
const feuilles = readdirSync(STYLES)
	.filter((n) => n.endsWith('.css'))
	.map((n) => join(STYLES, n));
const releves = [
	...fichiers(RACINE).map((chemin) => [chemin, stylesDe(readFileSync(chemin, 'utf8'))]),
	...feuilles
		.filter((chemin) => !FEUILLES_DES_JETONS.some((f) => chemin.endsWith(sep + f)))
		.map((chemin) => [chemin, stylesDeFeuille(readFileSync(chemin, 'utf8'))]),
];
for (const [chemin, css] of releves) {
	if (css.trim() && chemin.endsWith('.css')) feuillesLues++;
	else if (css.trim()) blocsLus++;
	const v = valeursEnDur(css);
	total.couleurs += v.couleurs.length;
	total.tailles += v.tailles.length;
	const n = v.couleurs.length + v.tailles.length;
	if (n) parFichier.push([relative(RACINE, chemin).split(sep).join('/'), n]);
}

if (!blocsLus || !feuillesLues) {
	console.error(
		`\n✗ ${blocsLus} composant(s) et ${feuillesLues} feuille(s) lus : contrôle inopérant (INCONNU).\n`,
	);
	process.exit(2);
}

let echec = 0;

//  Les interdits se cherchent aussi dans `src/styles/`, `socle.css` compris : la
//  charte elle-même ne doit pas les porter.
const sources = [...fichiers(RACINE), ...feuilles];
const exceptionsServies = new Set();
const interdits = [];
for (const chemin of sources) {
	const rel = relative(RACINE, chemin).split(sep).join('/');
	const trouves = interditsDe(readFileSync(chemin, 'utf8'));
	if (!trouves.length) continue;
	if (rel in EXCEPTIONS) {
		exceptionsServies.add(rel);
		continue;
	}
	for (const [valeur, par] of trouves) interdits.push(`   ${rel} : ${valeur} → ${par}`);
}
const socleCss = readFileSync(join(STYLES, FEUILLE_DES_JETONS), 'utf8');
const jetons = jetonsDe(socleCss);
if (!Object.keys(jetons.couleurs).length || !Object.keys(jetons.tailles).length) {
	console.error(`
✗ Aucun jeton lu dans ${FEUILLE_DES_JETONS} : contrôle inopérant (INCONNU).
`);
	process.exit(2);
}
/** Les trouvailles d'une règle sur chaque relevé, en lignes `chemin : valeur → jeton`. */
const parReleve = (regle) =>
	releves.flatMap(([chemin, css]) =>
		regle(css).map(
			([valeur, par]) => `   ${relative(RACINE, chemin).split(sep).join('/')} : ${valeur} → ${par}`,
		),
	);
/** Une règle sans plafond : la moindre ligne fait échouer, les 40 premières se lisent. */
function refuser(lignes, entete) {
	if (!lignes.length) return;
	echec = 1;
	console.error(`\n✗ ${lignes.length} ${entete} :`);
	lignes.slice(0, 40).forEach((l) => console.error(l));
	if (lignes.length > 40) console.error(`   … et ${lignes.length - 40} de plus`);
}
refuser(
	parReleve((css) => egalesAUnJeton(css, jetons)),
	'valeur(s) égale(s) à un jeton de la charte, à écrire par lui',
);
refuser(
	parReleve((css) => repliMortsDe(css, socleCss)),
	'repli(s) mort(s) sur un jeton défini de la charte, à écrire sans repli',
);
refuser(
	interdits,
	'valeur(s) tranchée(s) le 27/09/2026 encore écrite(s) ' +
		'(taille au cran supérieur, couleur d’état de la charte)',
);
const badges = contrastesBadges(
	readFileSync(join(STYLES, 'composants.css'), 'utf8'),
	readFileSync(join(STYLES, 'socle.css'), 'utf8'),
);
if (!badges.length) {
	echec = 1;
	console.error(
		'\n✗ Aucun badge lu dans composants.css : contrôle de contraste inopérant (INCONNU).',
	);
}
for (const { nom, rapport } of badges) {
	if (rapport == null) {
		echec = 1;
		console.error(`\n✗ .badge-${nom} : couleur non résolue — contraste INCONNU.`);
	} else if (rapport < 4.5) {
		echec = 1;
		console.error(
			`\n✗ .badge-${nom} : texte à ${rapport.toFixed(2)}:1 sur son fond, sous 4,5 ` +
				'— un dérivé `-texte` (socle.css), comme --color-warning-texte.',
		);
	}
}
for (const rel of Object.keys(EXCEPTIONS)) {
	if (!exceptionsServies.has(rel)) {
		echec = 1;
		console.error(`\n✗ Exception sans objet : ${rel} ne porte plus rien d’interdit — la retirer.`);
	}
}
for (const cle of ['couleurs', 'tailles']) {
	if (total[cle] > PLAFOND[cle]) {
		echec = 1;
		console.error(
			`\n✗ ${total[cle]} ${cle} en dur, plafond ${PLAFOND[cle]}. Employer la charte : ` +
				(cle === 'couleurs' ? '`var(--color-…)`' : '`var(--fs-…)`') +
				' (styles/socle.css). Les plus chargés :',
		);
		parFichier
			.sort((a, b) => b[1] - a[1])
			.slice(0, 8)
			.forEach(([f, n]) => console.error(`   ${n}  ${f}`));
	} else if (total[cle] < PLAFOND[cle]) {
		echec = 1;
		console.error(
			`\n✗ ${total[cle]} ${cle} en dur, sous le plafond de ${PLAFOND[cle]} : ` +
				`le baisser à ${total[cle]} dans ce lot (PLAFOND, en tête du fichier).`,
		);
	}
}
if (echec) process.exit(1);
console.log(
	`✓ Charte : ${total.couleurs} couleurs et ${total.tailles} tailles en dur, ` +
		`au plafond — aucune ajoutée (${parFichier.length} fichiers portent encore de la dette).`,
);
