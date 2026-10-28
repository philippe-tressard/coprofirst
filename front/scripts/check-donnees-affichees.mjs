#!/usr/bin/env node
/**
 *  Chaque écran de premier niveau déclare ses données affichées (#1846).
 *
 *  ## Pourquoi ce contrôle
 *
 *  La télémétrie mesurait l'ouverture d'un écran jusqu'à l'hydratation : la
 *  moitié de l'attente — Affaires à chaud, 430 ms hydratée, 861 ms affichée.
 *  `marquerDonneesAffichees()` (`#lib/telemetry`) mesure l'autre moitié, mais
 *  seul l'écran sait quand ses données principales sont posées : l'appel est
 *  explicite. Un écran qui l'oublie ne produit RIEN — et un écran qui ne se
 *  mesure pas passe pour rapide.
 *
 *  ## Ce qu'il exige
 *
 *  Chaque écran de premier niveau appelle `marquerDonneesAffichees(`. La liste
 *  se LIT : les `href` de `#lib/pages.ts` (le menu), plus `ECRANS_HORS_MENU`.
 *  Un écran qui confie son chargement à un composant se déclare dans `DELEGUES`.
 *  Une entrée qui ne sert plus — l'écran a disparu, ou n'appelle plus son
 *  composant — fait échouer.
 *
 *  Lancer : node scripts/check-donnees-affichees.mjs [--selftest]
 */
import { existsSync, readFileSync } from 'node:fs';
import { neutraliserCommentaires } from './lib-commentaires.mjs';

const PAGES = 'src/lib/pages.ts';
const APPEL = /\bmarquerDonneesAffichees\s*\(/;

/** Les écrans de premier niveau que le menu ne porte pas — réservés à un rôle. */
const ECRANS_HORS_MENU = ['/espace-cs', '/admin'];

/** L'écran → le composant qui charge ses données à sa place. */
const DELEGUES = {
	'/sondages': 'src/lib/components/PageCommunaute.svelte',
};

/** Les `href` d'une table des pages. PURE. */
export function hrefsDuMenu(source) {
	return [...neutraliserCommentaires(source).matchAll(/\bhref:\s*'(\/[^']*)'/g)].map((m) => m[1]);
}

/** Le fichier appelle-t-il la mesure ? PURE. */
export function appelle(source) {
	return APPEL.test(neutraliserCommentaires(source));
}

const fichierDe = (ecran) => `src/routes/(app)${ecran}/+page.svelte`;

if (process.argv.includes('--selftest')) {
	let ko = 0;
	const t = (libelle, attendu, obtenu) => {
		const ok = JSON.stringify(attendu) === JSON.stringify(obtenu);
		if (!ok) ko++;
		console.log(`${ok ? '✓' : '✗'} ${libelle}`);
	};
	t('appel reconnu', true, appelle('\tmarquerDonneesAffichees();'));
	t('import seul ≠ appel', false, appelle("import { marquerDonneesAffichees } from 'x';"));
	t('appel en commentaire ignoré', false, appelle('// marquerDonneesAffichees()'));
	t('les href de la table', ['/a', '/b'], hrefsDuMenu("{ href: '/a' }, { href: '/b' }"));
	t('cas zéro : table vide', [], hrefsDuMenu('export const PAGES = [];'));
	process.exit(ko ? 1 : 0);
}

const menu = hrefsDuMenu(readFileSync(PAGES, 'utf8'));
//  Cas zéro : une table illisible rendrait un contrôle vert sans rien regarder.
if (menu.length < 5) {
	console.error(`✗ ${PAGES} : ${menu.length} écran(s) lu(s) — la lecture du menu est cassée.`);
	process.exit(1);
}

const fautes = [];
for (const ecran of [...menu, ...ECRANS_HORS_MENU]) {
	const page = fichierDe(ecran);
	if (!existsSync(page)) {
		fautes.push(`${ecran} : ${page} introuvable`);
		continue;
	}
	const delegue = DELEGUES[ecran];
	if (delegue) {
		const nom = delegue.split('/').pop().replace('.svelte', '');
		if (!readFileSync(page, 'utf8').includes(`<${nom}`))
			fautes.push(`${ecran} : DELEGUES dit ${nom}, que la page ne rend plus`);
		else if (!appelle(readFileSync(delegue, 'utf8')))
			fautes.push(`${ecran} : ${delegue} n'appelle pas marquerDonneesAffichees()`);
	} else if (!appelle(readFileSync(page, 'utf8'))) {
		fautes.push(`${ecran} : ${page} n'appelle pas marquerDonneesAffichees()`);
	}
}
for (const ecran of Object.keys(DELEGUES))
	if (![...menu, ...ECRANS_HORS_MENU].includes(ecran))
		fautes.push(`DELEGUES : ${ecran} n'est plus un écran de premier niveau`);

if (fautes.length) {
	console.error('✗ Écrans de premier niveau sans mesure des données affichées (#1846) :');
	for (const f of fautes) console.error(`  - ${f}`);
	process.exit(1);
}
console.log(`✓ ${menu.length + ECRANS_HORS_MENU.length} écrans déclarent leurs données affichées.`);
