#!/usr/bin/env node
/**
 *  Une carte de liste se rend par **`CarteListe`, et par lui seul** — son
 *  conteneur, sa gouttière, son geste de dépliage et ses états (10/10/2026).
 *
 *  ## Pourquoi ce contrôle
 *
 *  Demandé à l'écran : « standardise-la dans un objet, pour avoir toujours le
 *  même comportement quelle que soit son occurrence ». Quatorze cartes
 *  recopiaient le conteneur `class="carte-liste a-gouttiere"`, son
 *  `role="presentation"`, le clic qui déplie une carte repliée et
 *  `<Gouttiere>` en premier enfant. Une gouttière sortait par le bas d'une
 *  carte courte : le correctif a dû passer par chaque copie (#1819).
 *
 *  🔴 Et l'état « archivé » avait CINQ rendus — `.attenue` sous trois
 *  variantes, `.item-inactive` (FAQ, 0,55), `.history-item` (affaire, sans le
 *  filet de la carte). Aucun contrôle ne le voyait : chaque copie était
 *  cohérente avec elle-même.
 *
 *  ## Ce qui est refusé hors de `CarteListe.svelte`
 *
 *  - le conteneur écrit à la main : `class="… carte-liste …"`, `class:carte-liste` ;
 *  - la prise de la colonne : `a-gouttiere` ;
 *  - l'ancienne carte d'archive : `history-item` ;
 *  - la gouttière rendue ou importée par une carte : `<Gouttiere`, `import Gouttiere`.
 *
 *  `lint:entete-carte` vérifie, lui, ce que chaque carte rend DANS ce
 *  conteneur (`EnteteCarte`, `carte-corps`).
 *
 *  Lancer : node scripts/check-carte-liste.mjs [--selftest]
 */
import { controler, lignesPortant } from './lib-source-unique.mjs';

const CLASSES = '(?:carte-liste|a-gouttiere|history-item)';
/**  Une classe de conteneur écrite (statique ou `class:`), ou la gouttière
 *   rendue par une carte. */
const COPIE = new RegExp(
	`class="[^"]*(?<![\\w-])${CLASSES}(?![\\w-])|class:${CLASSES}(?![\\w-])|<Gouttiere\\b|import\\s+Gouttiere\\s+from`,
);

process.exit(
	controler({
		temoin: 'src/lib/components/CarteListe.svelte',
		fautes: lignesPortant(COPIE),
		cas: [
			['<div class="carte-liste a-gouttiere" id="x">', 1],
			['<div class="idee-card carte-liste" id="x">', 1],
			['\tclass:carte-liste={!archive}', 1],
			['\tclass:history-item={archive}', 1],
			['\tclass="a-gouttiere"', 1],
			['\t<Gouttiere quand={x.cree_le} />', 1],
			["\timport Gouttiere from './Gouttiere.svelte';", 1],
			//  La forme voulue, jamais signalée.
			['<CarteListe class="idee-card" quand={x.cree_le} {expanded}>', 0],
			["\timport CarteListe from '#lib/components/CarteListe.svelte';", 0],
			//  Un voisin de nom ne vaut pas la classe ; un sélecteur CSS non plus.
			['<div class="carte-liste-titre">', 0],
			['\t.carte-liste .carte-corps { opacity: 1; }', 0],
			["\timport type { ClasseGouttiere } from '#lib/gouttiere.ts';", 0],
		],
		ok: 'Carte de liste : conteneur et gouttière rendus par CarteListe seul',
		ko: 'conteneur(s) de carte ou gouttière(s) écrits hors de CarteListe',
		conseil:
			'Employer `<CarteListe id quand classe expanded urgent archive onDeplier>` ; ' +
			'ce qui lui manque s’y ajoute en prop, jamais dans la carte.',
	}),
);
