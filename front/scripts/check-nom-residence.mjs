#!/usr/bin/env node
/**
 *  Le nom de CETTE résidence ne s'écrit pas dans le code du site (#1725).
 *
 *  🔴 « 5Hostachy » était écrit dans le repli du nom du site (`siteNomStore`),
 *  l'état initial du formulaire d'administration, le titre d'une fiche de
 *  sondage, la mention du responsable de traitement à l'inscription, une
 *  catégorie d'affaire, le lien vers le code source et le manifeste de
 *  l'application installée. Le produit doit servir une autre copropriété
 *  (`specs/architecture/multi-coproprietes.md`) : chacune de ces lignes
 *  affichait le nom de celle-ci chez une autre.
 *
 *  Deux noms, deux sources — jamais un littéral :
 *    - la RÉSIDENCE : `siteNomStore` (`#lib/stores/pageConfig`), repli neutre
 *      `NOM_SITE_PAR_DEFAUT` (`#lib/configSite`) ;
 *    - la PLATEFORME : `#lib/plateforme` — le logiciel s'appelle CoproFirst
 *      (D9), et ce module porte aussi l'adresse du dépôt et la licence en
 *      vigueur.
 *
 *  Le dépôt portait le nom de la résidence jusqu'au 09/10/2026 : l'adresse
 *  du code source était alors la SEULE ligne admise, et `plateforme.ts` le
 *  témoin qui devait la porter. Renommé en `coprofirst` (#1772), il n'y a
 *  plus de témoin — aucune ligne de `src/` n'a le droit d'écrire « hostachy ».
 *
 *  Le pendant serveur est `api/tests/test_nom_site.py`.
 *
 *  🔴 `static/` aussi (#1755, 08/10/2026) : ce dossier part tel quel dans l'image
 *  du front, donc chez TOUTES les installations. Le manuel utilisateur y nommait
 *  le produit « 5Hostachy » huit fois ; il nomme la plateforme, CoproFirst
 *  (arbitrage du 08/10/2026). Ce que `src/` ne voyait pas.
 *
 *  Lancer : node scripts/check-nom-residence.mjs [--selftest]
 */
import { controler, lignesPortant } from './lib-source-unique.mjs';

const MOTIF = /hostachy/i;

const code = controler({
	extensions: ['.svelte', '.ts', '.js', '.css'],
	temoin: null,
	exceptions: {
		'src/lib/stores/locale.ts':
			'`hostachy_locale` : la clé de stockage de la langue choisie. La renommer ' +
			'ferait perdre leur réglage aux navigateurs déjà configurés, et elle ne ' +
			"s'affiche nulle part.",
	},
	fautes: lignesPortant(MOTIF),
	cas: [
		["export const siteNomStore = derived(configStore, ($c) => $c['site_nom'] ?? '5Hostachy');", 1],
		['<title>{sondage.question} — 5Hostachy</title>', 1],
		['\t\thref="https://github.com/philippe-tressard/5hostachy"', 1],
		['\t\t\tplaceholder="— Envoyé depuis 5hostachy.fr"', 1],
		//  Les commentaires racontent l'histoire et peuvent la nommer.
		['// « 5Hostachy » était écrit ici', 0],
		['/*  5Hostachy — Styles globaux */', 0],
		['<!-- 5Hostachy › Communauté -->', 0],
		['<title>{titre} — {$siteNomStore}</title>', 0],
	],
	ok: 'Nom de la résidence : jamais écrit dans le code du site',
	ko: 'ligne(s) qui écrivent « hostachy »',
	conseil:
		'La résidence : `$siteNomStore` (`#lib/stores/pageConfig`) ; la plateforme : ' +
		'`#lib/plateforme`. Une exception se déclare dans ce contrôle, avec sa raison.',
});

//  Le contenu livré tel quel : le manuel, le manifeste, les icônes.
const livre = controler({
	racine: 'static',
	extensions: ['.html', '.txt', '.json', '.webmanifest', '.svg'],
	temoin: null,
	fautes: lignesPortant(MOTIF),
	cas: [
		['  <title>Manuel utilisateur · 5Hostachy</title>', 1],
		['  <title>Manuel utilisateur · CoproFirst</title>', 0],
	],
	ok: 'Nom de la résidence : absent du contenu livré tel quel (static/)',
	ko: 'ligne(s) du contenu livré qui écrivent « hostachy »',
	conseil:
		'Le manuel décrit la plateforme : « CoproFirst ». Une maquette d’écran montre ' +
		'« Ma résidence », jamais le nom de celle-ci.',
});

process.exit(Math.max(code, livre));
