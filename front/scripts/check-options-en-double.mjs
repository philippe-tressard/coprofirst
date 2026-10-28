#!/usr/bin/env node
/**
 *  Une option n'a qu'UN badge sur une carte (27/09/2026, signalé à l'écran).
 *
 *  ## Pourquoi
 *
 *  Une affaire en priorité haute portait DEUX badges sur sa carte :
 *  « ⚡ Urgente » (le badge de priorité, orange) et « 🚨 Urgente » (la rangée
 *  des options actives). La rangée filtrait déjà `brouillon`, que
 *  `PastilleLecture` dit à sa place — le filtre était écrit en ligne, pour une
 *  seule option, et la seconde option rendue ailleurs n'y a jamais été ajoutée.
 *  #TK-109008 et #TK-121048, et toute affaire urgente depuis le 05/09/2026.
 *
 *  ## Ce qu'il refuse
 *
 *  1. `optionsActives(` dans un écran, hors de `BoutonOptions` (le bouton du
 *     geste, qui montre TOUS les glyphes, et c'est son rôle). Une carte passe
 *     par `optionsEnBadge` (`#lib/tickets`), qui retire ce qu'un badge dédié dit.
 *  2. Un badge dédié rendu par une carte sans que son option figure dans
 *     `OPTIONS_RENDUES_AILLEURS` : c'est ce qui fait tenir la liste à jour.
 *  3. Le COMPORTEMENT, exécuté et non relu (`standards/04` §22) : une affaire
 *     urgente, épinglée et confidentielle ne rend que « Épinglée » dans sa
 *     rangée, et sa forme brève de priorité dit bien l'urgence.
 *
 *  Lancer : node scripts/check-options-en-double.mjs [--selftest]
 */
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join, sep } from 'node:path';
import { resolve } from 'node:path';
import { neutraliserCommentaires } from './lib-commentaires.mjs';
import { chargerModule } from './lib/charger-module.mjs';

const TICKETS = 'src/lib/tickets.ts';
const CARTE = 'src/lib/components/PastillesAffaire.svelte';

/** Le rendu dédié → l'option qu'il dit déjà. */
const RENDUS_DEDIES = {
	PRIORITE_BREVE: 'urgente',
	PastilleLecture: 'brouillon',
};

/** Seul écran autorisé à lister toutes les options actives. */
const EXCEPTIONS = {
	'src/lib/components/BoutonOptions.svelte': 'le bouton du geste montre tous les glyphes actifs',
};

/** Les clés de `OPTIONS_RENDUES_AILLEURS`. PURE. */
export function renduesAilleurs(source) {
	const m = source.match(/OPTIONS_RENDUES_AILLEURS[^=]*=\s*\{([\s\S]*?)\n\};/);
	return m ? [...m[1].matchAll(/^\s*(\w+)\s*:/gm)].map((x) => x[1]) : null;
}

/** Les options qu'une carte dit par un badge dédié. PURE. */
export function optionsDediees(source) {
	const s = neutraliserCommentaires(source);
	return Object.entries(RENDUS_DEDIES)
		.filter(([rendu]) => new RegExp(`\\b${rendu}\\b`).test(s))
		.map(([, cle]) => cle);
}

/** Un appel direct à `optionsActives(`. PURE. */
export function appelleOptionsActives(source) {
	return /\boptionsActives\(/.test(neutraliserCommentaires(source));
}

if (process.argv.includes('--selftest')) {
	let ko = 0;
	const t = (libelle, attendu, obtenu) => {
		const ok = JSON.stringify(attendu) === JSON.stringify(obtenu);
		console.log(`${ok ? 'PASS' : 'FAIL'}  ${libelle} → ${JSON.stringify(obtenu)}`);
		if (!ok) ko = 1;
	};
	//  🔴 La forme du 27/09/2026 : la rangée filtrait `brouillon` seul.
	t(
		'appel direct',
		true,
		appelleOptionsActives(
			'<script>x</script>{#each optionsActives(o).filter((o) => o.cle !== "brouillon") as opt}',
		),
	);
	t('appel commenté ignoré', false, appelleOptionsActives('<!-- optionsActives(o) -->'));
	t(
		'rendus dédiés',
		['urgente', 'brouillon'],
		optionsDediees('<script>import { PRIORITE_BREVE } from "x";</script><PastilleLecture />'),
	);
	t(
		'liste lue',
		['brouillon', 'urgente'],
		renduesAilleurs(
			"export const OPTIONS_RENDUES_AILLEURS: X = {\n\tbrouillon: 'a',\n\turgente: 'b',\n};",
		),
	);
	t('liste absente', null, renduesAilleurs('rien'));
	console.log(ko ? '== ÉCHECS ==' : '== TOUS OK ==');
	process.exit(ko);
}

function fichiers(dir, acc = []) {
	for (const e of readdirSync(dir)) {
		const p = join(dir, e);
		if (statSync(p).isDirectory()) fichiers(p, acc);
		else if (e.endsWith('.svelte')) acc.push(p.split(sep).join('/'));
	}
	return acc;
}

const erreurs = [];
const servies = new Set();
for (const f of fichiers('src')) {
	if (!appelleOptionsActives(readFileSync(f, 'utf8'))) continue;
	if (EXCEPTIONS[f]) servies.add(f);
	else
		erreurs.push(`${f} — optionsActives( dans un écran : passer par optionsEnBadge (#lib/tickets)`);
}
for (const f of Object.keys(EXCEPTIONS))
	if (!servies.has(f)) erreurs.push(`${f} — exception qui ne sert plus : la retirer`);

const liste = renduesAilleurs(readFileSync(TICKETS, 'utf8'));
if (liste === null) erreurs.push(`${TICKETS} — OPTIONS_RENDUES_AILLEURS introuvable : INCONNU`);
else
	for (const cle of optionsDediees(readFileSync(CARTE, 'utf8')))
		if (!liste.includes(cle))
			erreurs.push(`${CARTE} — un badge dédié dit « ${cle} », absent d'OPTIONS_RENDUES_AILLEURS`);

const echouer = (m) => {
	console.error(`
✗ ${m}
`);
	process.exit(1);
};
const { optionsEnBadge, PRIORITE_BREVE } = await chargerModule(resolve(TICKETS), echouer);
if (typeof optionsEnBadge !== 'function' || !PRIORITE_BREVE)
	erreurs.push(`${TICKETS} — optionsEnBadge ou PRIORITE_BREVE introuvable : INCONNU`);
else {
	const cas = { priorite: 'haute', epingle: true, confidentiel: true };
	const rangee = optionsEnBadge(cas).map((o) => o.cle);
	if (JSON.stringify(rangee) !== '["epingle"]')
		erreurs.push(
			`optionsEnBadge(affaire urgente, épinglée, confidentielle) → ${JSON.stringify(rangee)}, attendu ["epingle"]`,
		);
	if (!/Urgente/.test(PRIORITE_BREVE.haute ?? ''))
		erreurs.push(
			`PRIORITE_BREVE.haute = « ${PRIORITE_BREVE.haute} » : la carte ne dit plus l'urgence`,
		);
}

if (erreurs.length) {
	console.error(`\n✗ Une option rendue deux fois sur une carte :\n\n  ${erreurs.join('\n  ')}\n`);
	process.exit(1);
}
console.log(`✓ Options d'une carte : un seul badge chacune (${liste.length} rendue(s) ailleurs).`);
