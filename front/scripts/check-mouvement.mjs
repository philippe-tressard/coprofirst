#!/usr/bin/env node
/**
 *  Une durée de mouvement se lit dans la charte, jamais en dur (27/09/2026).
 *
 *  ## Pourquoi
 *
 *  Les jetons `--duree-geste` (120 ms), `--duree-apparition` (200 ms) et
 *  `--ease-out` existent depuis le 24/09/2026 (`styles/socle.css`). Trois jours
 *  plus tard, 64 transitions sur 74 les ignoraient : HUIT durées différentes
 *  (0,1 s → 0,4 s) pour deux intentions, et l'accueil — l'écran le plus vu —
 *  entrait en 350 ms `ease`, le double de la règle et avec la courbe molle.
 *  `emil-design-eng` : ce qu'on voit souvent se raccourcit ; un geste répond
 *  tout de suite ; une animation d'interface reste sous 300 ms.
 *
 *  ## Ce qu'il refuse
 *
 *  1. Une durée ou un délai ÉCRIT dans un `transition` ou un `animation` —
 *     sauf `0` (le repli d'un `var(--delay, 0s)`), sauf une animation sans fin
 *     (c'est `lint:animations-infinies` qui la tient), sauf les EXCEPTIONS
 *     déclarées ci-dessous.
 *  2. Une propriété de MISE EN PAGE animée (largeur, hauteur, marge…), qui
 *     recalcule la page à chaque image — hors des MISES_EN_PAGE déclarées.
 *
 *  Une exception qui ne sert plus fait échouer le contrôle.
 *
 *  Lancer : node scripts/check-mouvement.mjs [--selftest]
 */
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join, sep } from 'node:path';
import { neutraliserCommentaires } from './lib-commentaires.mjs';

/** Fichier → [animation, raison] : une durée écrite, et pourquoi. */
const EXCEPTIONS = {
	'styles/normes.css': [
		'cible-lien-pulse',
		'la surbrillance d’une cible de lien dure 2,5 s : elle dit LEQUEL, puis s’efface',
	],
	'styles/decor-fete.css': [
		'decor-fete-reflet',
		'le reflet du message de fête (#2312) traverse le texte en 2,4 s, une fois par apparition, après le fondu : un ornement lent, pas une réponse d’interface',
	],
};

/** Fichier → propriété(s) de mise en page animée(s), séparées par un espace, et pourquoi. */
const MISES_EN_PAGE = {
	'lib/components/FrequentationTelemetrie.svelte': ['height', 'barre de données, remplie une fois'],
	'lib/components/ResultatsSondage.svelte': ['width', 'barre de résultat, remplie une fois'],
	'lib/components/UrgencesAccueil.svelte': ['width', 'barre de progression, remplie une fois'],
	'lib/components/PasswordStrength.svelte': [
		'grid-template-rows margin-top',
		'la seule façon d’ouvrir une hauteur inconnue sans la mesurer',
	],
};

const MISE_EN_PAGE =
	/^(all|width|height|min-width|max-width|min-height|max-height|margin(-\w+)?|padding(-\w+)?|top|right|bottom|left|inset|grid-template-rows|grid-template-columns|flex(-\w+)?|font-size|line-height)$/;

/** Les déclarations `transition` / `animation` d'une source. PURE. */
export function declarations(source) {
	const s = neutraliserCommentaires(source);
	return [...s.matchAll(/(?<![\w-])(transition|animation)\s*:\s*([^;{}]+);/g)].map((m) => ({
		cle: m[1],
		valeur: m[2].replace(/\s+/g, ' ').trim(),
	}));
}

/** Les temps écrits (non nuls) d'une valeur, `var(…)` compris. PURE. */
export function tempsEcrits(valeur) {
	return [...valeur.matchAll(/(?<![\w.-])(\d*\.?\d+)(ms|s)\b/g)]
		.filter((m) => Number(m[1]) !== 0)
		.map((m) => m[0]);
}

/** Les propriétés animées par un `transition`. PURE. */
export function proprietes(valeur) {
	return valeur
		.split(/,(?![^(]*\))/)
		.map((p) => p.trim().split(/\s+/)[0])
		.filter(Boolean);
}

/** Les écarts d'une source : `{ genre, detail }`. PURE. */
export function ecarts(source) {
	const sortie = [];
	for (const { cle, valeur } of declarations(source)) {
		if (/\binfinite\b/.test(valeur) || valeur === 'none') continue;
		const nom = cle === 'animation' ? valeur.split(/\s+/)[0] : null;
		for (const t of tempsEcrits(valeur)) sortie.push({ genre: 'temps', detail: nom ?? t, valeur });
		if (cle === 'transition')
			for (const p of proprietes(valeur))
				if (MISE_EN_PAGE.test(p)) sortie.push({ genre: 'mise-en-page', detail: p, valeur });
	}
	return sortie;
}

if (process.argv.includes('--selftest')) {
	let ko = 0;
	const t = (libelle, attendu, src) => {
		const r = JSON.stringify(ecarts(src).map((e) => `${e.genre}:${e.detail}`));
		const ok = r === JSON.stringify(attendu);
		console.log(`${ok ? 'PASS' : 'FAIL'}  ${libelle} → ${r}`);
		if (!ok) ko = 1;
	};
	//  🔴 La forme du 27/09/2026 : l'accueil en 350 ms, courbe molle.
	t(
		'durée écrite',
		['temps:.35s'],
		'.hero { transition: opacity var(--duree-apparition) var(--ease-out), transform .35s ease; }',
	);
	t(
		'jetons',
		[],
		'.x { transition: color var(--duree-geste), transform var(--duree-geste) var(--ease-out); }',
	);
	t(
		'repli nul du délai',
		[],
		'.x { transition: opacity var(--duree-apparition) var(--ease-out) var(--delay, 0s); }',
	);
	t('délai écrit', ['temps:80ms'], '.x { transition: opacity var(--duree-apparition) 80ms; }');
	t('animation écrite', ['temps:fadeIn'], '.x { animation: fadeIn 0.15s ease; }');
	t('sans fin ignorée', [], '.x { animation: spin 0.7s linear infinite; }');
	t('largeur animée', ['mise-en-page:width'], '.x { transition: width var(--duree-apparition); }');
	t('tout animé', ['mise-en-page:all'], '.x { transition: all var(--duree-geste); }');
	t('commentaire ignoré', [], '/* transition: color 0.2s; */');
	t('none', [], '.x { transition: none; }');
	console.log(ko ? '== ÉCHECS ==' : '== TOUS OK ==');
	process.exit(ko);
}

function fichiers(dir, acc = []) {
	for (const e of readdirSync(dir)) {
		const p = join(dir, e);
		if (statSync(p).isDirectory()) fichiers(p, acc);
		else if (e.endsWith('.svelte') || e.endsWith('.css')) acc.push(p);
	}
	return acc;
}

const fautifs = [];
const servies = new Set();
let total = 0;
for (const f of fichiers('src')) {
	const rel = f
		.split(sep)
		.join('/')
		.replace(/^src\//, '');
	const source = readFileSync(f, 'utf8');
	total += declarations(source).length;
	for (const e of ecarts(source)) {
		const table = e.genre === 'temps' ? EXCEPTIONS : MISES_EN_PAGE;
		if (table[rel]?.[0].split(' ').includes(e.detail)) servies.add(`${e.genre}:${rel}`);
		else
			fautifs.push(
				`${rel} — ${e.genre === 'temps' ? 'durée écrite' : 'mise en page animée'} « ${e.detail} » dans « ${e.valeur} »`,
			);
	}
}
const mortes = [
	...Object.keys(EXCEPTIONS).filter((f) => !servies.has(`temps:${f}`)),
	...Object.keys(MISES_EN_PAGE).filter((f) => !servies.has(`mise-en-page:${f}`)),
];
if (total === 0) {
	console.error('\n✗ Aucune transition lue : contrôle inopérant (INCONNU).\n');
	process.exit(2);
}
if (fautifs.length || mortes.length) {
	if (fautifs.length)
		console.error(
			`\n✗ Mouvement hors de la charte (${fautifs.length}) :\n\n  ${fautifs.join('\n  ')}\n\n  → var(--duree-geste) pour ce qui répond à un appui ou un survol, var(--duree-apparition) var(--ease-out) pour ce qui entre ; transform et opacity plutôt qu'une dimension. Sinon, déclarer l'exception avec sa raison.\n`,
		);
	if (mortes.length)
		console.error(`\n✗ Exception qui ne sert plus : ${mortes.join(', ')} — la retirer.\n`);
	process.exit(1);
}
console.log(
	`✓ Mouvement : ${total} déclaration(s), toutes sur les jetons de la charte (${servies.size} exception(s) déclarée(s)).`,
);
