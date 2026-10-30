#!/usr/bin/env node
/**
 *  Jamais de `:global(…)` dans une feuille GLOBALE (#2306, 30/10/2026).
 *
 *  `:global()` est une syntaxe de Svelte : elle ne vit que dans le `<style>`
 *  d'un composant, que Svelte réécrit. Une feuille de `src/styles/` (ou
 *  `app.css`) passe par Vite seul, qui la laisse telle quelle — et le
 *  navigateur abandonne toute règle dont un sélecteur lui est inconnu, la liste
 *  entière avec lui. La règle est donc MORTE, sans un mot : aucun rendu, aucun
 *  avertissement, aucune erreur de build.
 *
 *  Deux blocs l'étaient : les huit règles `.rich-content :global(p)`… de
 *  `socle.css`, recopie inerte de celles de `normes.css` (qui habillaient le
 *  contenu riche avec d'autres valeurs), et les règles d'impression du
 *  reporting dans `ecrans.css`, `:global(body.print-reporting …)` — la barre de
 *  navigation sortait donc sur le papier depuis leur montée dans la feuille
 *  globale. Dans une feuille globale, la règle EST globale : on écrit le
 *  sélecteur nu.
 *
 *  La liste des feuilles est celle de `lib-css-global.mjs` — jamais recopiée.
 *
 *  Lancer : node scripts/check-global-feuille-globale.mjs [--selftest]
 */
import { controler, lignesPortant } from './lib-source-unique.mjs';
import { fichiersCssGlobal } from './lib-css-global.mjs';

const RACINE = 'src';

process.exitCode = controler({
	racines: [],
	fichiers: fichiersCssGlobal(RACINE).map((f) => `${RACINE}/${f}`),
	fautes: lignesPortant(/:global\s*\(/),
	cas: [
		['.rich-content :global(p) {\n\tmargin: 0;\n}', 1],
		['@media print {\n\t:global(body.print-reporting .sidebar),\n\t:global(body .x) {}\n}', 2],
		['.rich-content p {\n\tmargin: 0;\n}', 0],
		['/* Les huit `:global(.custom-content …)` DISPARAISSENT. */', 0],
		['body.print-reporting .sidebar {\n\tdisplay: none;\n}', 0],
	],
	ok: 'Feuilles globales : aucun `:global()`, toutes leurs règles s’appliquent',
	ko: '`:global()` dans une feuille globale — la règle est abandonnée par le navigateur',
	conseil:
		'Écrire le sélecteur nu : dans `src/styles/` la règle est déjà globale. `:global()` ne sert que dans le `<style>` d’un composant.',
});
