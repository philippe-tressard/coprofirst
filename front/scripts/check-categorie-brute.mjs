#!/usr/bin/env node
/**
 *  Une catégorie, un statut, un type ou un rôle s'affiche par son LIBELLÉ —
 *  jamais sa valeur brute (26/09/2026, signalé à l'écran ; étendu aux statuts
 *  par #1345 : cinq écrans d'accès rendaient « actif », « perdu » tels quels ;
 *  étendu aux types et aux rôles, et aux valeurs avec repli, le 05/11/2026).
 *
 *  ## Pourquoi ce contrôle
 *
 *  L'infobulle de l'icône de catégorie, sur la liste des affaires, disait
 *  « etude_travaux » au lieu de « Étude & travaux ». Le libellé existait
 *  (aujourd’hui servi : `categorie_libelle`, #2511) ; rien n’obligeait à le
 *  prendre. La recherche en a trouvé deux autres : le tableau des reportings
 *  et la relance du syndic rendaient la même valeur brute.
 *
 *  🔴 Le 05/11/2026, Admin › Télémétrie montrait « copropriétaire_résident »
 *  dans la colonne Type des utilisateurs les plus actifs — `{u.statut ?? '—'}`.
 *  Ce contrôle existait et ne le voyait pas : le REPLI (`?? '—'`) suffisait à
 *  sortir du motif. Et « Commandes d'accès » rendait « vigik » (`{cmd.type}`),
 *  un champ qu'il ne regardait pas. Un slug avec un tiret bas est un nom
 *  interne, pas un mot de l'interface.
 *
 *  ## Ce qu'il refuse
 *
 *  Dans le balisage d'un `.svelte`, un `X.categorie`, `X.statut`, `X.type` ou
 *  `X.role` rendu TEL QUEL — avec ou sans repli `?? '—'` :
 *
 *    title={ticket.categorie}          aria-label={t.categorie}
 *    <td>{row.categorie}</td>          <span>{t.categorie}</span>
 *    <td>{u.statut ?? '—'}</td>        ({l.type})
 *
 *  La forme conforme : le libellé SERVI par l'API (`x.categorie_libelle`, #2511 ;
 *  `libelle_type`), ou pour un statut le libellé de SA table — `statutTicketLabel`,
 *  `statutAccesLabel`, `libelleStatut`, `typeAccesLabel`…
 *
 *  ⚠️ Il ne regarde pas une valeur passée à une fonction, comparée ou servant
 *  de clé — c'est son usage normal. Seul l'AFFICHAGE est en cause.
 *
 *  ## Les exceptions — déclarées, avec leur raison et leur compte
 *
 *  Un champ nommé `type` ou `statut` qui porte DÉJÀ un libellé (servi par
 *  l'API) se déclare dans `EXCEPTIONS`. Le contrôle échoue si une exception
 *  cesse de servir : une exception qui ne sert plus est un oubli qui ressemble
 *  à une décision.
 *
 *  Lancer : node scripts/check-categorie-brute.mjs [--selftest]
 */
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join, sep } from 'node:path';
import { neutraliserCommentaires } from './lib-commentaires.mjs';

const RACINE = 'src';
//  Le champ, puis un repli facultatif : `?? '—'`, `?? "N/A"`, `?? autre.chose`.
const EXPRESSION = String.raw`[\w.?$]+\.(?:categorie|statut|type|role)(?:\s*\?\?\s*(?:'[^']*'|"[^"]*"|[\w.]+))?`;
const ATTRIBUT = new RegExp(String.raw`\b(?:title|aria-label|alt)=\{${EXPRESSION}\}`, 'g');
const TEXTE = new RegExp(String.raw`>\s*\{${EXPRESSION}\}\s*<`, 'g');
//  « … (appartement) » : la valeur entre parenthèses dans une phrase.
const PARENTHESE = new RegExp(String.raw`\(\{${EXPRESSION}\}\)`, 'g');
const EMPLOI =
	/(?:\.categorie_libelle\b|\.libelle_categorie\b|statut\w*Label\(|libelleStatut\(|typeAccesLabel\()/;

/**  Les écrans dont le champ porte DÉJÀ un libellé — nombre d'occurrences et raison. */
const EXCEPTIONS = new Map([
	[
		'lib/components/RetourComptes.svelte',
		{
			nombre: 1,
			raison: '`type` est le libellé du statut, servi par l’API (`retour_comptes.libelle_statut`)',
		},
	],
]);

/**  Les valeurs rendues brutes dans une source. PURE. */
export function categoriesBrutes(source) {
	const s = neutraliserCommentaires(source);
	return (
		(s.match(ATTRIBUT) ?? []).length +
		(s.match(TEXTE) ?? []).length +
		(s.match(PARENTHESE) ?? []).length
	);
}

if (process.argv.includes('--selftest')) {
	let ko = 0;
	const t = (libelle, attendu, src) => {
		const r = categoriesBrutes(src);
		console.log(`${r === attendu ? 'PASS' : 'FAIL'}  ${libelle} → ${r}`);
		if (r !== attendu) ko = 1;
	};
	//  🔴 Les trois formes trouvées le 26/09/2026.
	t('infobulle brute', 1, '<span class="tk-cat" title={ticket.categorie}>🏗️</span>');
	t('cellule brute', 1, '<tr><td>{row.categorie}</td><td>{row.total}</td></tr>');
	t('badge brut', 1, '<span class="badge badge-gray">{t.categorie}</span>');
	t('nom accessible brut', 1, '<span aria-label={t.categorie}>🏗️</span>');
	//  🔴 #1345 : le statut d'un accès, rendu brut dans un badge.
	t('statut brut', 1, '<span class="badge">{a.statut}</span>');
	t('statut conforme', 0, '<span class="badge">{statutAccesLabel(a.statut)}</span>');
	//  🔴 05/11/2026 : le repli cachait la valeur brute au contrôle.
	t('statut brut avec repli', 1, '<td class="text-muted-sm">{u.statut ?? \'—\'}</td>');
	t(
		'statut brut avec repli multiligne',
		1,
		'<span\n\tclass="badge"\n>\n\t{l.statut ?? "—"}\n</span>',
	);
	t('statut avec repli, conforme', 0, "<td>{u.statut ? libelleStatut(u.statut) : '—'}</td>");
	t('type brut', 1, '<td><span class="badge badge-blue">{cmd.type}</span></td>');
	t(
		'type conforme',
		0,
		'<td><span class="badge badge-blue">{typeAccesLabel(cmd.type)}</span></td>',
	);
	t('type brut entre parenthèses', 1, '<option>{l.numero} ({l.type})</option>');
	t('libellé servi entre parenthèses', 0, '<option>{l.numero} ({l.libelle_type})</option>');
	t('rôle brut', 1, '<li>{m.role}</li>');
	t('libellé conforme', 0, '<span title={ticket.categorie_libelle}>🏗️</span>');
	t('texte conforme', 0, '<td>{row.categorie_libelle}</td>');
	t(
		'clé, comparaison et propriété',
		0,
		"{#each l as r (r.categorie)}{#if r.categorie === 'bug'}<Badge type={r.type} />{/if}{/each}",
	);
	t('commentaire ignoré', 0, '<!-- <td>{row.categorie}</td> -->');
	console.log(ko ? '== ÉCHECS ==' : '== TOUS OK ==');
	process.exit(ko);
}

function fichiers(dir, acc = []) {
	for (const e of readdirSync(dir)) {
		const p = join(dir, e);
		if (statSync(p).isDirectory()) fichiers(p, acc);
		else if (e.endsWith('.svelte')) acc.push(p);
	}
	return acc;
}

const fautifs = [];
const perimees = [];
let emplois = 0;
for (const f of fichiers(RACINE)) {
	const rel = f
		.split(sep)
		.join('/')
		.replace(/^src\//, '');
	const source = readFileSync(f, 'utf8');
	if (EMPLOI.test(neutraliserCommentaires(source))) emplois++;
	const n = categoriesBrutes(source);
	const exception = EXCEPTIONS.get(rel);
	if (exception) {
		if (n !== exception.nombre)
			perimees.push(`${rel} : ${n} au lieu de ${exception.nombre} déclarée(s)`);
		continue;
	}
	if (n) fautifs.push(`${rel} (${n})`);
}

//  🔴 LE CAS ZÉRO (`standards/04` §2) : plus aucun écran n'emploie le libellé,
//  c'est que la règle a changé de forme — le contrôle ne mesure plus rien.
if (emplois === 0) {
	console.error(
		'\n✗ INCONNU : aucun écran n’appelle un libellé de catégorie ou de statut — mettre le contrôle à jour.\n',
	);
	process.exit(2);
}

if (perimees.length) {
	console.error(`\n✗ ${perimees.length} exception(s) de EXCEPTIONS ne décrivent plus l’écran :\n`);
	for (const p of perimees) console.error(`  ${p}`);
	console.error('\n  → mettre `nombre` à jour, ou retirer l’exception.\n');
	process.exit(1);
}

if (fautifs.length) {
	console.error(
		`\n✗ ${fautifs.length} fichier(s) affichent une catégorie, un statut, un type ou un rôle bruts :\n`,
	);
	for (const f of fautifs) console.error(`  ${f}`);
	console.error(
		'\n  → le libellé servi (`categorie_libelle`, `libelle_type`) ou celui de sa table : `statutTicketLabel`, `statutAccesLabel`, `libelleStatut`, `typeAccesLabel`…\n',
	);
	process.exit(1);
}
console.log(
	`✓ Catégories, statuts, types et rôles : ${emplois} écran(s) les affichent par leur libellé, aucun brut (${EXCEPTIONS.size} exception(s) déclarée(s)).`,
);
