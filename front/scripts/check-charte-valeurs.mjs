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
	stylesDe,
	stylesDeFeuille,
	sansCommentairesHtml,
	sansVoilesSurPhoto,
	VOILES_SUR_PHOTO,
} from './lib-charte-jetons.mjs';
import {
	COULEURS_ETAT_ETRANGERES,
	interditsDe,
	TAILLES_HORS_ECHELLE,
} from './lib-charte-interdits.mjs';

export { contraste, contrastesBadges, egalesAUnJeton, jetonsDe, repliMortsDe, resoudre };
export { stylesDe, stylesDeFeuille };
export { COULEURS_ETAT_ETRANGERES, interditsDe, TAILLES_HORS_ECHELLE };

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
 *  30/10/2026 (#1571) : 69 → 43 tailles — l'échelle gagne ses deux crans
 *  d'intertitres aux valeurs exactes déjà les plus employées (`--fs-xl` 1 rem ×19,
 *  `--fs-2xl` 1,1 rem ×7) : aucun rendu ne change. Puis (#2313, sur maquette) ZÉRO
 *  taille : cran micro, titres, pictogrammes, second cran de chiffres — aucune ne baisse.
 */
const PLAFOND = { couleurs: 0, tailles: 0 };

const RACINE = join(dirname(fileURLToPath(import.meta.url)), '..', 'src');

/**
 *  La feuille qui DÉFINIT les jetons : hors relevé des valeurs.
 *  ⚠️ `app.css` n'a que des `@import` (#453) ; s'il reprenait des règles, il
 *  faudrait le relever aussi — le contrôle ne le devinerait pas.
 */
export const FEUILLE_DES_JETONS = 'socle.css';
/** …celle qui les REDÉFINIT au sombre (#2174, S3) et celle des palettes de la copropriété
 *  (#2379), hors relevé pour la même raison. */
const FEUILLES_DES_JETONS = [FEUILLE_DES_JETONS, 'palette-sombre.css', 'palettes.css'];

/** Couleurs (hexadécimales, et `rgb()`/`hsl()` depuis #2946) et tailles en `rem` écrites en dur. */
export function valeursEnDur(css) {
	return {
		couleurs: [...css.matchAll(/#[0-9a-fA-F]{3,8}\b|\b(?:rgba?|hsla?)\([^)]*\)/g)].map((m) => m[0]),
		tailles: [...css.matchAll(/font-size\s*:\s*([0-9]*\.?[0-9]+)rem/g)].map((m) => m[1]),
	};
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
	//  Un commentaire HTML que le retrait reformerait ne survit pas (CodeQL, #3087).
	cas('commentaire HTML reformé, puis sans fin', sansCommentairesHtml('a<!<!---->--b<!-- c'), 'a');
	//  🔴 #2946 : 22 couleurs en notation fonctionnelle passaient sous le relevé.
	cas(
		'rgb(), rgba(), hsl() comptent comme l’hexadécimal',
		valeursEnDur('.a{background:rgba(0, 0, 0, 0.45);color:rgb(26 26 46 / 0.14);fill:hsl(0 0% 50%)}')
			.couleurs.length,
		3,
	);
	cas(
		'un voile sur photo déclaré sort du compte, une autre valeur du fichier y reste',
		sansVoilesSurPhoto(
			'lib/components/Vignette.svelte',
			['rgba(0, 0, 0, 0.55)', 'rgba(0, 0, 0, 0.9)'],
			new Set(),
		),
		['rgba(0, 0, 0, 0.9)'],
	);
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
	--fs-titre-page: 1.5rem;
	--fs-picto: 1.5rem;
	--radius: 0.5rem;
}`,
	);
	cas(
		'valeur égale à un jeton : couleur courte ou longue, taille, et les deux noms d’une valeur',
		egalesAUnJeton(
			'.a{color:#FFF;background:#ffffff;font-size:.80rem}.b{color:#f2efe9;font-size:1.5rem}',
			jetons,
		),
		[
			['.80rem', 'var(--fs-sm)'],
			['1.5rem', 'var(--fs-titre-page) ou var(--fs-picto)'],
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
const voilesServis = new Set();
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
	v.couleurs = sansVoilesSurPhoto(
		relative(RACINE, chemin).split(sep).join('/'),
		v.couleurs,
		voilesServis,
	);
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
for (const [f, vs] of Object.entries(VOILES_SUR_PHOTO)) {
	vs.forEach((v, i) => {
		if (voilesServis.has(`${f}#${i}`)) return;
		echec = 1;
		console.error(
			`\n✗ Voile sur photo déclaré sans objet : ${f} ${v} — le retirer de VOILES_SUR_PHOTO.`,
		);
	});
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
