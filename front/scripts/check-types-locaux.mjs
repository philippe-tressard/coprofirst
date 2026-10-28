#!/usr/bin/env node
/**
 *  Un type d'ENTITÉ se déclare là où le client le rend, jamais dans un écran (#1044).
 *
 *  ## Pourquoi ce contrôle
 *
 *  L'audit du 19/09/2026 a trouvé la seconde source de types du front : les
 *  écrans. Le client rendait `any`, et chaque écran retypait l'entité de son
 *  côté — `Bail` dans `mon-lot`, l'accès d'un bail dans `ModaleAccesBail`,
 *  les membres du CS dans `annuaire`… C'est `standards/02` §4 quater : deux
 *  écrans qui affichent la même entité la décrivent chacun, et le premier champ
 *  ajouté côté serveur n'arrive que dans l'un des deux. Le `Bail` de `mon-lot`
 *  omettait déjà trois champs du contrat.
 *
 *  ## Ce qu'il refuse
 *
 *  Dans `src/routes/**` et `src/lib/components/**`, une `interface` — ou un
 *  `type` littéral — portant un champ `id` à son premier niveau. Le champ `id`
 *  est le signe d'une entité : c'est la clé que le serveur lui donne.
 *
 *  Le type va dans `#lib/api/types.ts` ou dans le module du domaine
 *  (`#lib/api/bailleur.ts` pour un bail), et le CLIENT le rend.
 *
 *  ## Ce qui est déclaré
 *
 *  - `LEGITIMES` : un `id` qui n'est pas celui d'une entité rendue par l'API —
 *    un objet d'interface, un état de formulaire. Chacun dit pourquoi, et une
 *    entrée qui ne sert plus fait échouer le contrôle.
 *
 *  Il n'y a plus de dette : la liste `DETTE` (#1044) est tombée à zéro le
 *  06/10/2026 (#1571), et un plafond à zéro ne compte plus rien — il ne ferait
 *  que laisser la place d'en réintroduire un. Un type d'entité neuf dans un
 *  écran est refusé, sans échappatoire autre que `LEGITIMES`.
 *
 *  ⚠️ Le relevé lit l'ARBRE syntaxique (parseur TypeScript), pas le texte : un
 *  `id` imbriqué (`options: { id: number }[]`) n'est pas le champ du type, et
 *  une regex l'aurait confondu.
 *
 *  ## Le client lui-même : aucun `any` (#1572)
 *
 *  Le client rendait `any` et chaque écran retypait l'entité. Il en est à zéro
 *  depuis v2.105.0 : c'est ESLint qui le tient (`no-explicit-any` en ERREUR sur
 *  `src/lib/api/`, `eslint.config.js`) — le plafond par module qui le suivait
 *  jusque-là n'a plus rien à compter, et un compteur à zéro serait muet.
 *
 *  Lancer : node scripts/check-types-locaux.mjs [--selftest]
 */
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, sep } from 'node:path';
import ts from 'typescript';

const RACINES = ['src/routes', 'src/lib/components'];

/** Un `id` qui n'est pas celui d'une entité de l'API. */
const LEGITIMES = {
	'lib/components/Toast.svelte::ToastMessage':
		"l'identifiant d'un toast à l'écran, attribué par le store — aucune entité serveur",
	'lib/components/FormulaireEditionDocument.svelte::CorrectionDocument':
		"l'état d'une correction en cours : `id: null` signifie « aucune », le document vient d'un autre type",
	'lib/components/FormulaireSondage.svelte::OptionForm':
		"une ligne du formulaire : `id` absent pour une réponse neuve, c'est la charge utile d'un PATCH",
};

/** Les blocs de code d'un fichier : le fichier entier pour `.ts`, les `<script>` pour `.svelte`. */
function blocs(source, chemin) {
	if (chemin.endsWith('.ts')) return [source];
	return [...source.matchAll(/<script[^>]*>([\s\S]*?)<\/script>/g)].map((m) => m[1]);
}

/**  Les types d'une source qui portent un `id` à leur premier niveau. PUR. */
export function typesAvecId(source, chemin = 'x.svelte') {
	const trouves = [];
	for (const code of blocs(source, chemin)) {
		const sf = ts.createSourceFile('x.ts', code, ts.ScriptTarget.Latest, true);
		const visiter = (n) => {
			let membres = null;
			if (ts.isInterfaceDeclaration(n)) membres = n.members;
			else if (ts.isTypeAliasDeclaration(n) && ts.isTypeLiteralNode(n.type))
				membres = n.type.members;
			if (membres && membres.some((m) => m.name && m.name.getText(sf) === 'id'))
				trouves.push(n.name.text);
			ts.forEachChild(n, visiter);
		};
		visiter(sf);
	}
	return trouves;
}

if (process.argv.includes('--selftest')) {
	let ko = 0;
	const t = (libelle, attendu, src, chemin) => {
		const r = typesAvecId(src, chemin).join(',');
		console.log(`${r === attendu ? 'PASS' : 'FAIL'}  ${libelle} → [${r}]`);
		if (r !== attendu) ko = 1;
	};
	//  🔴 L'état exact de `mon-lot` avant le 25/09/2026.
	t(
		'interface d’entité dans un écran',
		'Bail',
		'<script lang="ts">\n\tinterface Bail {\n\t\tid: number;\n\t\tlot_id: number;\n\t}\n</script>',
	);
	t(
		'alias de type littéral',
		'Compte',
		'<script>type Compte = { id: number; nom: string };</script>',
	);
	t('id optionnel', 'Ligne', '<script>type Ligne = { id?: number; libelle: string };</script>');
	t(
		'id IMBRIQUÉ seulement : pas une entité',
		'',
		'<script>interface Saisie { question: string; options: { id: number }[] }</script>',
	);
	t('type sans id', '', '<script>interface Medaillon { nom: string; photo: string }</script>');
	t(
		'script de module ET d’instance',
		'A,B',
		'<script context="module">interface A { id: number }</script>\n<script>interface B { id: number }</script>',
	);
	t('fichier .ts', 'C', 'export interface C { id: number }', 'x.ts');
	process.exit(ko);
}

function fichiers(dir) {
	const sortie = [];
	for (const nom of readdirSync(dir)) {
		const chemin = join(dir, nom);
		if (statSync(chemin).isDirectory()) sortie.push(...fichiers(chemin));
		else if (/\.(svelte|ts)$/.test(nom)) sortie.push(chemin);
	}
	return sortie;
}

const tous = RACINES.flatMap(fichiers);
//  Cas zéro : l'arborescence a changé, le contrôle ne mesure plus rien.
if (tous.length < 100) {
	console.error(`✗ Cas zéro : ${tous.length} fichier(s), au moins 100 attendus.`);
	process.exit(1);
}

const vus = new Set();
const nouveaux = [];
for (const chemin of tous) {
	const rel = chemin
		.split(sep)
		.join('/')
		.replace(/^src\//, '');
	for (const nom of typesAvecId(readFileSync(chemin, 'utf8'), chemin)) {
		const cle = `${rel}::${nom}`;
		vus.add(cle);
		if (!(cle in LEGITIMES)) nouveaux.push(cle);
	}
}

const perimees = Object.keys(LEGITIMES).filter((c) => !vus.has(c));

if (nouveaux.length) {
	console.error(`\n✗ ${nouveaux.length} type(s) d'entité déclaré(s) dans un écran :\n`);
	for (const c of nouveaux) console.error(`   ${c}`);
	console.error(
		'\n  Le déclarer dans `#lib/api/types.ts` ou le module de son domaine, et que le' +
			'\n  CLIENT le rende — sinon chaque écran retype la même entité, et diverge.' +
			"\n  Si ce `id` n'est pas celui d'une entité de l'API, le déclarer dans" +
			'\n  `LEGITIMES`, avec sa raison.\n',
	);
	process.exit(1);
}
if (perimees.length) {
	console.error(`\n✗ ${perimees.length} déclaration(s) qui ne servent plus :\n`);
	for (const c of perimees) console.error(`   ${c}`);
	console.error(
		'\n  Le type a quitté l’écran (ou a été renommé) : retirer la ligne. Une liste' +
			'\n  qui garde ses entrées mortes laisse la place d’en réintroduire.\n',
	);
	process.exit(1);
}

console.log(
	`✓ Types locaux : aucun type d'entité nouveau dans les écrans — ` +
		`${Object.keys(LEGITIMES).length} légitimes.`,
);
