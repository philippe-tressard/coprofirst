#!/usr/bin/env node
/*
 *  **Une liste qui annonce « Aucun » doit avoir REGARDÉ.**
 *
 *  Le motif refusé, en toutes lettres :
 *
 *      {#if chargement}          ← on attend
 *        <p>Chargement…</p>
 *      {:else if items.length === 0}
 *        <div class="empty-state"><h3>Aucun élément</h3></div>   ← on AFFIRME
 *      {:else}
 *        …
 *
 *  Il n'a que deux branches là où il en faut trois. Quand le chargement
 *  **échoue**, la liste reste à sa valeur initiale — `[]` — et l'écran rend
 *  exactement la même chose que s'il n'y avait rien.
 *
 *  ## Ce n'est pas une hypothèse : c'est arrivé
 *
 *  Le 19/08/2026, l'utilisateur signale : *« J'avais un sondage non terminé qui
 *  a disparu ! »* et *« Il y avait 3 annonces non vendues ! à récupérer »*.
 *  Rien n'était perdu — deux sondages et trois annonces dormaient en base
 *  pendant que l'écran affichait « Aucun sondage » et « Aucune annonce ». Au
 *  bout d'une telle méprise, il y a une demande de restauration, et le risque
 *  d'écraser des données saines.
 *
 *  🔴 **Une sortie vide n'est pas un constat** (`standards/04` §1). La règle
 *  était écrite pour les contrôles d'infrastructure ; elle vaut mot pour mot
 *  pour un écran.
 *
 *  ## Ce que ce contrôle ajoute à ceux qui existaient
 *
 *  `EtatListe.svelte` est né de cet incident, et `lint:catch-vide` interdit
 *  depuis le `.catch(() => [])` qui l'avait causé. Les deux étaient verts, et
 *  **le défaut était pourtant encore là onze fois** : un `try/catch` qui se
 *  contente d'un toast laisse la liste à `[]` tout aussi silencieusement, et le
 *  toast s'efface au bout de quelques secondes. Le composant existait ; rien
 *  n'obligeait à s'en servir.
 *
 *  C'est la leçon de `project_le_composant_existait_deja` : un composant qui
 *  porte une règle et que rien n'impose est un composant que les écrans
 *  suivants réécriront à la main, correctement ou non.
 *
 *  ## Comment il lit
 *
 *  Pour chaque `class="empty-state"`, il regarde la **chaîne de conditions**
 *  qui le précède. Si elle parle de chargement (`loading`, `chargement`) sans
 *  parler d'échec (`erreur`, `error`), c'est le motif à deux branches — donc un
 *  écran qui affirme une absence qu'il n'a pas constatée.
 *
 *  ⚠️ Il ne vise QUE ce motif. Un `.empty-state` qui rend une consigne
 *  (« renseignez le titre puis cliquez sur Aperçu »), ou le vide d'une valeur
 *  DÉRIVÉE de données déjà chargées (un filtre, une colonne de kanban), ne
 *  ment sur rien : il n'y a pas de chargement à échouer. Les refuser tous
 *  aurait produit vingt exceptions et un contrôle désarmé dans la semaine —
 *  c'est l'arbitrage que `lint:catch-vide` a déjà tranché, et pour la même
 *  raison.
 *
 *  Test : node front/scripts/check-etat-liste.mjs --selftest
 */
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join } from 'node:path';
import { neutraliserCommentaires } from './lib-commentaires.mjs';

const RACINE = 'src';

/**
 *  Les écrans qui portent encore le motif, chacun avec sa raison.
 *
 *  🔴 Ce sont des DETTES, pas des dérogations : chacune est un écran qui peut
 *  aujourd'hui annoncer « aucun » sans avoir regardé. Elles sont nominatives
 *  pour qu'on les compte, et une entrée qui ne sert plus fait échouer le
 *  contrôle — reconduite « au cas où », elle masquerait la prochaine.
 *
 *  Il n'en reste aucune (30/10/2026, clôture de la carte #1571) : la seule entrée
 *  est un faux positif déclaré. La conversion se fait au fil de l'eau : un écran
 *  repris est un écran converti, et sa ligne disparaît d'ici.
 */
export const DETTES = {
	//  🔴 FAUX POSITIF ASSUMÉ, et déclaré comme tel (07/09/2026) :
	//  `ApercuDiffusion` reçoit ses canaux en PROP (`apercu?.canaux ?? []`) — ce
	//  n'est pas lui qui charge. « Aucun canal coché » y est un état légitime du
	//  formulaire, pas une absence non constatée : le ticket partira sans
	//  notification, et c'est exactement ce que la phrase dit.
	//
	//  ⚠️ Il reste dans cette table plutôt que dans une liste d'exclusions à part :
	//  une entrée qui cesse de servir fait échouer le contrôle, donc si ce
	//  composant se met un jour à charger lui-même, la ligne disparaîtra du
	//  relevé et forcera à trancher de nouveau.
	'lib/components/ApercuDiffusion.svelte':
		'FAUX POSITIF — les canaux viennent d’une prop, ce composant ne charge rien',
};

function fichiers(dir, acc = []) {
	for (const e of readdirSync(dir)) {
		const p = join(dir, e);
		if (statSync(p).isDirectory()) fichiers(p, acc);
		else if (e.endsWith('.svelte')) acc.push(p);
	}
	return acc;
}

/*  ⚠️ AUCUNE frontière de mot, d'aucun côté, et insensible à la casse : ces
    indicateurs se nomment d'après CE QU'ILS CHARGENT autant que d'après leur
    nature — `ahLoading`, `emailsLoading`, `santeLoading`, `erreurLots`,
    `erreurBaux`, `loadError`.

    🔴 Ce commentaire a été écrit DEUX fois, pour les deux moitiés du même
    défaut, et la seconde m'a repris en flagrant délit (08/09/2026) :

    1. le 07/09, `CHARGEMENT` exigeait une frontière des DEUX côtés — il a
       laissé passer six écrans que je venais de relever à la main, et le
       contrôle a répondu « dette périmée » sur des dettes bien vivantes ;
    2. le 08/09, j'ai corrigé la TÊTE de `CHARGEMENT` et laissé la QUEUE des
       deux motifs. `ECHEC` a donc refusé de reconnaître `{:else if
       erreurLots}` — la branche d'échec que je venais d'écrire — et le
       contrôle a accusé d'un défaut l'écran qui le corrigeait.

    La leçon est celle de #801 : un motif étroit ne rend pas un rouge prudent,
    il rend un verdict FAUX, dans le sens que le hasard décide. Ici les deux
    sens se sont produits en vingt-quatre heures. */
const CHARGEMENT = /(loading|chargement)/i;
const ECHEC = /(erreur|error)/i;

/**
 *  Les lignes fautives d'une source : un `.empty-state` dont la chaîne de
 *  conditions parle de chargement mais jamais d'échec.
 *
 *  ⚠️ Les commentaires sont neutralisés d'abord. Deux contrôles ont déjà été
 *  déclenchés par leur PROPRE prose le 06/09/2026 (`standards/04` §39) — un
 *  fichier qui explique le motif qu'il refuse ne doit pas se refuser lui-même.
 */
export function fautes(source) {
	const src = neutraliserCommentaires(source);
	const lignes = src.split('\n');
	const trouves = [];
	for (let i = 0; i < lignes.length; i++) {
		if (!/class="empty-state"/.test(lignes[i])) continue;
		//  La chaîne de conditions qui mène ici : les branches ouvertes juste avant.
		const fenetre = lignes.slice(Math.max(0, i - 8), i).join('\n');
		const conditions = fenetre.match(/\{[#:]\s*(?:else\s+)?if[^}]*\}/g)?.join(' ') ?? '';
		if (CHARGEMENT.test(conditions) && !ECHEC.test(conditions)) trouves.push(i + 1);
	}
	return trouves;
}

//  ── Cas zéro ────────────────────────────────────────────────────────────────
function selftest() {
	const cas = [
		//  🔴 Le motif à deux branches : chargement, puis vide. C'est #519.
		[
			'{#if loading}\n<p>…</p>\n{:else if items.length === 0}\n<div class="empty-state">a</div>\n{/if}',
			1,
		],
		//  Trois branches : l'échec est distingué, et il passe AVANT le vide.
		[
			'{#if loading}\n<p>…</p>\n{:else if erreur}\n<p>{erreur}</p>\n{:else if items.length === 0}\n<div class="empty-state">a</div>\n{/if}',
			0,
		],
		//  Une valeur DÉRIVÉE de données déjà chargées : aucun chargement à échouer.
		['{#if col.items.length === 0}\n<div class="empty-state">a</div>\n{/if}', 0],
		//  Une consigne, pas l'état d'une liste.
		['{:else}\n<div class="empty-state">Cliquez sur Aperçu</div>\n{/if}', 0],
		//  🔴 Le contrôle ne doit pas se déclencher sur sa PROPRE prose.
		['<!-- {#if loading} puis <div class="empty-state"> : le motif refusé -->', 0],
		//  🔴 Les deux moitiés du défaut de motif, une fois chacune (08/09/2026).
		//  Sans ces deux cas, la correction du 07/09 se déferait en silence :
		//  l'indicateur porte le nom de CE QU'IL charge, pas seulement sa nature.
		[
			'{#if lotsLoading}\n<p>…</p>\n{:else if items.length === 0}\n<div class="empty-state">a</div>\n{/if}',
			1,
		],
		[
			'{#if loading}\n<p>…</p>\n{:else if erreurLots}\n<p>{erreurLots}</p>\n{:else if items.length === 0}\n<div class="empty-state">a</div>\n{/if}',
			0,
		],
	];
	let ko = 0;
	for (const [src, attendu] of cas) {
		const n = fautes(src).length;
		if (n !== attendu) {
			console.error(`  ✗ ${n} faute(s) au lieu de ${attendu} : ${src.slice(0, 60)}…`);
			ko++;
		}
	}
	if (ko) {
		console.error(`\n✗ Auto-test : ${ko} cas en échec.`);
		process.exit(1);
	}
	console.log('✓ Auto-test : le motif est reconnu, et lui seul.');
}

selftest();

const nouveaux = [];
const dettesVues = new Set();

for (const p of fichiers(RACINE)) {
	const chemin = p
		.split('\\')
		.join('/')
		.replace(/^src\//, '');
	const lignes = fautes(readFileSync(p, 'utf8'));
	if (lignes.length === 0) continue;
	if (chemin in DETTES) dettesVues.add(chemin);
	else nouveaux.push(`${chemin}:${lignes.join(',')}`);
}

let echec = false;

if (nouveaux.length) {
	echec = true;
	console.error(`\n✗ ${nouveaux.length} écran(s) annoncent « aucun » sans avoir regardé :\n`);
	for (const e of nouveaux) console.error(`  ${e}`);
	console.error(
		'\n  Le motif `{#if chargement}…{:else if liste.length === 0}` n’a que deux\n' +
			'  branches : quand le chargement ÉCHOUE, la liste reste à `[]` et l’écran\n' +
			'  affirme une absence qu’il n’a pas constatée. C’est #519 — deux sondages\n' +
			'  et trois annonces crus détruits.\n' +
			'  → passer par `EtatListe` (`chargement`, `erreur`, `vide`), qui impose de\n' +
			'    fournir `erreur` et rend l’échec AVANT le vide.\n',
	);
}

const perimees = Object.keys(DETTES).filter((c) => !dettesVues.has(c));
if (perimees.length) {
	echec = true;
	console.error(`\n✗ ${perimees.length} dette(s) déclarée(s) qui ne servent plus :\n`);
	for (const e of perimees) console.error(`  ${e}`);
	console.error(
		'\n  Le fichier a disparu, ou l’écran est passé à `EtatListe`. Retirer la ligne :\n' +
			'  reconduite « au cas où », elle masquerait la prochaine.\n',
	);
}

if (echec) process.exit(1);

console.log(
	`✓ Aucun écran neuf n’annonce « aucun » sans avoir regardé — ${dettesVues.size} entrée(s) déclarée(s), chacune avec sa raison.`,
);
