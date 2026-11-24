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

//  🔴 Le manuel servi vaut pour TOUTE installation (#2924, 23/11/2026). Il
//  décrivait l'infrastructure de la référence — ses deux Raspberry Pi, « Les deux
//  nœuds », un chemin du poste de l'exploitant (`C:\Backup\…`), « v2.118.1 · RPi1 »
//  — et ses bâtiments (« Bât. 1 (D) » à « Bât. 4 (A) »). Ce qui ne vaut que pour la
//  référence vit dans `docs/` (non servi) : `docs/redondance-rpi5.md`.
const REFERENCE =
	/Raspberry|\bRPi\s?\d?\b|\b[A-Z]:\\|Bât\.(?:&nbsp;|\s)*\d+(?:&nbsp;|\s)*\([A-Z]\)/;
const manuel = controler({
	racine: 'static',
	extensions: ['.html'],
	temoin: null,
	fautes: lignesPortant(REFERENCE),
	cas: [
		['les deux Raspberry&nbsp;Pi sont ensemble la référence', 1],
		['par exemple «&nbsp;v2.118.1 · RPi1&nbsp;»', 1],
		['les copie toutes dans <code>C:\\Backup\\archives-affaires</code>', 1],
		['«&nbsp;Bât.&nbsp;1&nbsp;(D)&nbsp;» à «&nbsp;Bât.&nbsp;4&nbsp;(A)&nbsp;»', 1],
		['entre parenthèses, «&nbsp;Bât.&nbsp;1 (D)&nbsp;»', 1],
		['«&nbsp;Bât.&nbsp;1 › Logement › Terrasses Balcons&nbsp;»', 0],
		['une ligne par tâche, détaillée serveur par serveur', 0],
	],
	ok: "Manuel servi : rien de propre à l'infrastructure ni aux bâtiments de la référence",
	ko: 'ligne(s) du manuel servi propres à la référence (Raspberry, RPi, C:\\, Bât. N (lettre))',
	conseil:
		'Le manuel est servi par chaque installation : un exemple neutre, et ce qui ne vaut ' +
		'que pour la référence dans `docs/` (non servi), par exemple `docs/redondance-rpi5.md`.',
});

process.exit(Math.max(code, livre, manuel));
