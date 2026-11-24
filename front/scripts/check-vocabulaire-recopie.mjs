#!/usr/bin/env node
/**
 *  Garde-fou — **un vocabulaire du front ne se recopie pas en liste d'options.**
 *
 *  ## Pourquoi (24/11/2026, #2947)
 *
 *  `check-tables-statuts.mjs` refuse deux `Record<…>` d'un MÊME fichier qui
 *  partagent leurs clés. Une liste `[{ value, label }]` écrite dans un AUTRE
 *  fichier lui échappait — et c'est la forme qu'avait prise la recopie :
 *
 *  | Où | Ce qu'elle recopiait |
 *  |---|---|
 *  | `auth/inscription/+page.svelte` | six statuts et leurs libellés, identiques à `ATTRIBUTS_STATUT` (`#lib/roles`) |
 *
 *  Les copies concordaient : rien de faux n'était visible. C'est l'état de toutes
 *  les tables recopiées avant leur premier écart (#415, #828) — un statut renommé
 *  dans `#lib/roles` serait resté l'ancien à l'inscription, sans que rien lève.
 *
 *  ## Ce qu'il refuse
 *
 *  Un objet littéral qui porte `value: '<clé>'` et un `label` (ou un `libelle`),
 *  quand `<clé>` est une clé d'un des VOCABULAIRES ci-dessous, hors des fichiers
 *  qui les déclarent. La réponse : dériver la liste de la table (l'ordre de
 *  l'écran dans une liste de clés, le libellé lu dans la table).
 *
 *  Il lit le code TypeScript par son arbre (le compilateur est déjà là pour
 *  `svelte-check`) : une entrée répartie sur plusieurs lignes par Prettier est
 *  vue comme une entrée d'une ligne, et un commentaire n'est pas du code.
 *
 *  Lancé par `npm run lint:tables-statuts` (CI), avec `check-tables-statuts.mjs`.
 *
 *  Lancer : node scripts/check-vocabulaire-recopie.mjs [--selftest]
 */
import { readFileSync } from 'node:fs';
import ts from 'typescript';
import { fichiersSources } from './lib-source-unique.mjs';

/**  Les vocabulaires : le fichier qui les déclare, et la constante. Un objet
 *   donne ses clés, une liste les `value` de ses entrées. */
const VOCABULAIRES = [
	['src/lib/roles.ts', 'ATTRIBUTS_STATUT'],
	['src/lib/roles.ts', 'ATTRIBUTS_ROLE'],
	['src/lib/tickets.ts', 'STATUTS_TICKET'],
	['src/lib/idees.ts', 'STATUTS_IDEE'],
	['src/lib/liens-lot.ts', 'TYPES_LIEN'],
	['src/lib/tickets-categories.ts', 'CATEGORIES_TICKET'],
];

/**  Écarts déclarés, avec leur raison. Une entrée qui ne sert plus fait échouer. */
const EXCEPTIONS = {};

const nomDe = (p) =>
	p.name && (ts.isIdentifier(p.name) || ts.isStringLiteral(p.name)) ? p.name.text : null;

/** Retire `as const`, `satisfies …`, les parenthèses : la valeur elle-même. */
function nu(e) {
	while (
		e &&
		(ts.isAsExpression(e) || ts.isSatisfiesExpression(e) || ts.isParenthesizedExpression(e))
	)
		e = e.expression;
	return e;
}

/** Les clés de la constante `nom` du texte TS, ou `null` si elle est introuvable. PURE. */
export function clesDe(texte, nom) {
	const arbre = ts.createSourceFile('v.ts', texte, ts.ScriptTarget.Latest, true);
	let cles = null;
	const visiter = (n) => {
		if (ts.isVariableDeclaration(n) && ts.isIdentifier(n.name) && n.name.text === nom) {
			const v = nu(n.initializer);
			if (v && ts.isObjectLiteralExpression(v)) {
				cles = v.properties.map(nomDe).filter(Boolean);
			} else if (v && ts.isArrayLiteralExpression(v)) {
				cles = v.elements
					.map(nu)
					.filter((e) => ts.isObjectLiteralExpression(e))
					.map((e) => e.properties.find((p) => nomDe(p) === 'value'))
					.filter((p) => p && ts.isPropertyAssignment(p) && ts.isStringLiteralLike(p.initializer))
					.map((p) => p.initializer.text);
			}
		}
		ts.forEachChild(n, visiter);
	};
	visiter(arbre);
	return cles;
}

/** Le code d'un fichier : un `.svelte` n'a de TypeScript que dans ses `<script>`. */
function codeDe(chemin, texte) {
	if (!chemin.endsWith('.svelte')) return texte;
	//  Les lignes hors script sont blanchies : les numéros de ligne restent justes.
	let code = '';
	let fin = 0;
	//  `i` : une balise s'écrit aussi `<SCRIPT>` ; `</script …>` aussi se ferme
	//  (CodeQL js/bad-tag-filter, #3075).
	for (const m of texte.matchAll(/<script\b[^>]*>([\s\S]*?)<\/script\b[^>]*>/gi)) {
		const debut = m.index + m[0].indexOf('>') + 1;
		code += texte.slice(fin, debut).replace(/[^\n]/g, ' ') + m[1];
		fin = debut + m[1].length;
	}
	return code;
}

/** Les objets `{ value: '<clé du vocabulaire>', label|libelle }` du code. PURE. */
export function recopies(code, cles) {
	const arbre = ts.createSourceFile('f.ts', code, ts.ScriptTarget.Latest, true);
	const trouvees = [];
	const visiter = (n) => {
		if (ts.isObjectLiteralExpression(n)) {
			const props = new Map(n.properties.map((p) => [nomDe(p), p]));
			const v = props.get('value');
			if (
				v &&
				ts.isPropertyAssignment(v) &&
				ts.isStringLiteralLike(v.initializer) &&
				cles.has(v.initializer.text) &&
				(props.has('label') || props.has('libelle'))
			) {
				const ligne = arbre.getLineAndCharacterOfPosition(n.getStart()).line + 1;
				trouvees.push([ligne, v.initializer.text]);
			}
		}
		ts.forEachChild(n, visiter);
	};
	visiter(arbre);
	return trouvees;
}

function selftest() {
	const cles = new Set(['locataire', 'syndic', 'ouvert']);
	const cas = [
		//  🔴 La forme de l'inscription, sur une ligne.
		[
			"const s = [{ value: 'locataire', label: 'Locataire' }, { value: 'syndic', label: 'Syndic' }];",
			2,
		],
		//  🔴 Répartie par Prettier sur plusieurs lignes, et `libelle` au lieu de `label`.
		["const s = [\n\t{\n\t\tvalue: 'ouvert',\n\t\tlibelle: 'Ouvert',\n\t},\n];", 1],
		//  ✅ La forme dérivée : la clé passe par une variable.
		['const s = STATUTS.map((value) => ({ value, label: LIBELLES_STATUT[value] }));', 0],
		//  ✅ Une valeur hors du vocabulaire.
		["const s = [{ value: 'tous', label: 'Tous' }];", 0],
		//  ✅ Une clé du vocabulaire sans libellé : ce n'est pas une option recopiée.
		["const f = { value: 'syndic', actif: true };", 0],
		//  ✅ Un commentaire.
		["// [{ value: 'syndic', label: 'Syndic' }]", 0],
	];
	let ko = 0;
	for (const [src, attendu] of cas) {
		const n = recopies(src, cles).length;
		console.log(`${n === attendu ? 'PASS' : 'FAIL'}  ${src.split('\n')[0]}`);
		if (n !== attendu) ko = 1;
	}
	//  La lecture des tables : un objet et une liste se lisent tous deux.
	const objet = clesDe(
		"export const T = {\n\ta: { libelle: 'A' },\n\t'b': { libelle: 'B' },\n};",
		'T',
	);
	const liste = clesDe("export const L = [{ value: 'x', libelle: 'X' }] as const;", 'L');
	const lus = JSON.stringify(objet) === '["a","b"]' && JSON.stringify(liste) === '["x"]';
	console.log(`${lus ? 'PASS' : 'FAIL'}  lecture des clés d'un objet et d'une liste`);
	if (!lus) ko = 1;
	console.log(ko ? '== ÉCHECS ==' : '== TOUS OK ==');
	return ko;
}

function controle() {
	const sources = new Set(VOCABULAIRES.map(([f]) => f));
	const parCle = new Map();
	for (const [fichier, nom] of VOCABULAIRES) {
		const cles = clesDe(readFileSync(fichier, 'utf8'), nom);
		//  Cas zéro (standards/04 §2) : une table introuvable ne vaut pas « aucune copie ».
		if (!cles?.length) {
			console.error(`✗ ${nom} introuvable ou vide dans ${fichier} : contrôle INCONNU.`);
			return 1;
		}
		for (const c of cles) parCle.set(c, [...(parCle.get(c) ?? []), `${nom} (${fichier})`]);
	}
	const cles = new Set(parCle.keys());
	const fichiers = fichiersSources('src', ['.ts', '.svelte']);
	if (!fichiers.length) {
		console.error('✗ Aucun fichier lu sous src : contrôle INCONNU.');
		return 1;
	}
	const copies = [];
	const servies = new Set();
	for (const f of fichiers) {
		if (sources.has(f)) continue;
		const trouvees = recopies(codeDe(f, readFileSync(f, 'utf8')), cles);
		if (f in EXCEPTIONS) {
			if (trouvees.length) servies.add(f);
			continue;
		}
		for (const [ligne, cle] of trouvees) {
			copies.push(`${f}:${ligne} — '${cle}', de ${parCle.get(cle).join(' ou ')}`);
		}
	}
	let ko = 0;
	const mortes = Object.keys(EXCEPTIONS).filter((f) => !servies.has(f));
	if (mortes.length) {
		console.error(`✗ Exception(s) qui ne servent plus — les retirer : ${mortes.join(', ')}`);
		ko = 1;
	}
	if (copies.length) {
		console.error(`\n✗ ${copies.length} option(s) recopiée(s) d'un vocabulaire du front :`);
		for (const c of copies) console.error(`   ${c}`);
		console.error(
			'\n  Dériver la liste de la table : une liste de clés dans le module qui la déclare\n' +
				'  (l’ordre de l’écran), le libellé lu dans la table. Un écart légitime se déclare\n' +
				'  dans EXCEPTIONS de scripts/check-vocabulaire-recopie.mjs, avec sa raison.\n',
		);
		ko = 1;
	}
	if (!ko) {
		console.log(
			`✓ Vocabulaires : aucune option recopiée hors de sa table (${VOCABULAIRES.length} tables, ` +
				`${fichiers.length} fichiers lus).`,
		);
	}
	return ko;
}

process.exit(process.argv.includes('--selftest') ? selftest() : controle());
