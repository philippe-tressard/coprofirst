#!/usr/bin/env node
/**
 *  Une couleur tenue hors d'une feuille se dit par son JETON (mode sombre,
 *  #2174 — lot S2, 29/10/2026).
 *
 *  ## Pourquoi
 *
 *  Le bloc sombre de `socle.css` redéfinit les jetons en UN endroit. Une teinte
 *  écrite en `#rrggbb` dans un `.ts` ou dans le script d'un composant (la couleur
 *  d'un type du fil, d'un périmètre, d'une étape de kanban, d'une tuile
 *  d'import) lui échappe : au sombre, une pastille rouge foncé sur fond rose
 *  clair resterait telle quelle sur une page noire. `lint:charte-valeurs` ne la
 *  voyait pas non plus — il lit les `<style>`, pas les tables de données.
 *
 *  Le code désigne donc la teinte par son jeton — `'var(--fil-rouge)'` — et la
 *  valeur vit dans `socle.css`. Quand la teinte se CHOISIT par donnée (le rang
 *  d'un périmètre), le jeton est indexé : `--teinte-N`.
 *
 *  ## Ce qu'il refuse
 *
 *  Dans tout `.ts`, et dans le script ou le balisage d'un `.svelte` (le `<style>`
 *  est l'affaire de `lint:charte-valeurs`), commentaires retirés : un littéral
 *  hexadécimal (`#b91c1c`, `#fff`, `#00000080`) et les fonctions `rgb()`,
 *  `rgba()`, `hsl()`, `hsla()`, `hwb()`, `oklch()`.
 *
 *  ## Les exceptions (déclarées, et elles doivent servir)
 *
 *  Le manifeste de l'application installée : le navigateur le lit AVANT la
 *  feuille de style et ne résout aucune variable CSS. Sa valeur est donc écrite,
 *  et `parite` l'oblige à rester celle du jeton qu'elle imite — comme la balise
 *  `<meta name="theme-color">` de `app.html` (la doubler pour le sombre est S5).
 *
 *  Lancer : node scripts/check-couleurs-ts.mjs [--selftest]
 */
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { controler, lignesPortant } from './lib-source-unique.mjs';

const RACINE = join(dirname(fileURLToPath(import.meta.url)), '..');

const HEX = /#[0-9a-fA-F]{6}(?:[0-9a-fA-F]{2})?\b/;
//  Trois chiffres : au moins une lettre, sinon `'#441'` (un ticket) serait une couleur.
const HEX_COURT = /['"`]#(?=[0-9]*[a-fA-F])[0-9a-fA-F]{3}['"`]/;
const FONCTION = /\b(?:rgba?|hsla?|hwb|oklch)\(/;
const COULEUR = new RegExp(`${HEX.source}|${HEX_COURT.source}|${FONCTION.source}`);

/** Le `.svelte` privé de ses blocs `<style>` : ils relèvent de `charte-valeurs`. */
const sansStyle = (texte) =>
	texte.replace(/<style[\s\S]*?<\/style>/g, (bloc) => bloc.replace(/[^\n]/g, ' '));

const ligneCouleur = lignesPortant(COULEUR);

/** Les numéros de ligne fautifs d'un source. PURE. */
export function fautes(texte) {
	return ligneCouleur(sansStyle(texte));
}

const MANIFESTE = 'src/routes/manifest.webmanifest/+server.ts';

/**
 *  Le manifeste et `app.html` portent la valeur de `--color-primary` (barre du
 *  navigateur) et de `--color-surface` (fond de lancement) : ce qu'une variable
 *  dirait, écrit faute de pouvoir la lire. PURE : rend les écarts.
 */
export function parite({ socle, manifeste, html }) {
	const jeton = (nom) =>
		socle.match(new RegExp(`${nom}\\s*:\\s*(#[0-9a-fA-F]{3,8})\\s*;`))?.[1]?.toLowerCase();
	const attendu = { theme: jeton('--color-primary'), fond: jeton('--color-surface') };
	const lu = (texte, motif) => texte.match(motif)?.[1]?.toLowerCase();
	const complet = (c) => (c?.length === 4 ? `#${[...c.slice(1)].map((x) => x + x).join('')}` : c);
	const trouve = [
		['theme_color du manifeste', lu(manifeste, /theme_color\s*:\s*'(#[0-9a-fA-F]{3,6})'/), 'theme'],
		[
			'background_color du manifeste',
			lu(manifeste, /background_color\s*:\s*'(#[0-9a-fA-F]{3,6})'/),
			'fond',
		],
		[
			'<meta name="theme-color"> de app.html',
			lu(html, /name="theme-color"\s+content="(#[0-9a-fA-F]{3,6})"/),
			'theme',
		],
	];
	const ecarts = [];
	for (const [quoi, valeur, cle] of trouve) {
		if (!attendu[cle])
			ecarts.push(`${quoi} : le jeton de référence est introuvable dans socle.css`);
		else if (!valeur) ecarts.push(`${quoi} : valeur introuvable`);
		else if (complet(valeur) !== attendu[cle])
			ecarts.push(`${quoi} : ${valeur} ≠ ${attendu[cle]} (le jeton)`);
	}
	return ecarts;
}

const lire = (rel) => readFileSync(join(RACINE, rel), 'utf8');

if (process.argv.includes('--selftest')) {
	let ko = 0;
	const cas = (quoi, obtenu, attendu) => {
		const ok = JSON.stringify(obtenu) === JSON.stringify(attendu);
		if (!ok) ko = 1;
		console.log(`${ok ? 'PASS' : 'FAIL'}  ${quoi} → ${JSON.stringify(obtenu)}`);
	};
	cas('hex à six chiffres', fautes("const c = '#B91C1C';"), [1]);
	cas('hex à huit chiffres (alpha)', fautes('const c = "#00000080";'), [1]);
	cas('hex court entre guillemets', fautes("const c = '#fff';"), [1]);
	cas('rgba() dans une chaîne', fautes("const c = 'rgba(0,0,0,.4)';"), [1]);
	cas('hsl() dans un attribut de balisage', fautes('<p style="color:hsl(10 50% 50%)">a</p>'), [1]);
	cas('un jeton ne compte pas', fautes("const c = 'var(--fil-rouge)';"), []);
	cas('un commentaire ne compte pas', fautes('// était #b91c1c\n/* rgb(1,2,3) */'), []);
	cas('le <style> relève de charte-valeurs', fautes('<style>\n.a{color:#b91c1c}\n</style>'), []);
	cas(
		'le balisage avant un <style> compte',
		fautes('<i style="color:#abcdef"></i>\n<style>\n</style>'),
		[1],
	);
	cas(
		'une ancre n’est pas une couleur',
		fautes("const h = '#section'; const n = '#2174'; t = '#441';"),
		[],
	);
	cas('les numéros de ligne restent justes', fautes("a;\n\nconst c = '#123abc';"), [3]);
	const jetons = ':root { --color-primary: #1E3A5F; --color-surface: #ffffff; }';
	const man = "theme_color: '#1E3A5F', background_color: '#ffffff'";
	const html = '<meta name="theme-color" content="#1E3A5F" />';
	cas('parité : tout est d’accord', parite({ socle: jetons, manifeste: man, html }), []);
	cas(
		'parité : un manifeste qui dérive est refusé',
		parite({ socle: jetons, manifeste: man.replace('1E3A5F', '000000'), html }).length,
		1,
	);
	cas(
		'parité : une balise absente est refusée (cas zéro)',
		parite({ socle: jetons, manifeste: man, html: '' }).length,
		1,
	);
	cas(
		'parité : un jeton de référence absent est refusé (cas zéro)',
		parite({ socle: '', manifeste: man, html }).length,
		3,
	);
	console.log(ko ? '== ÉCHECS ==' : '== TOUS OK ==');
	process.exitCode = ko;
} else {
	process.exitCode = controler({
		extensions: ['.ts', '.svelte'],
		exceptions: {
			[MANIFESTE]:
				'le navigateur lit le manifeste avant la feuille de style : aucune variable CSS ; `parite` tient la valeur',
		},
		fautes,
		cas: [],
		ok: 'Couleurs hors feuille : aucune, toutes par jeton',
		ko: 'couleur(s) écrite(s) en dur hors d’une feuille',
		conseil:
			'Désigner la teinte par un jeton de `socle.css` (`var(--fil-rouge)`, `--teinte-N`, `--kanban-…`) ; en créer un, nommé par l’usage, s’il manque.',
	});
	const ecarts = parite({
		socle: lire('src/styles/socle.css'),
		manifeste: lire(MANIFESTE),
		html: lire('src/app.html'),
	});
	if (ecarts.length) {
		console.error('\n✗ Couleurs du navigateur en désaccord avec la charte :');
		for (const e of ecarts) console.error(`   ${e}`);
		process.exitCode = 1;
	} else if (!process.exitCode)
		console.log('✓ Manifeste et app.html : valeurs des jetons de la charte.');
}
