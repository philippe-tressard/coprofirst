/**
 * **Les tables du site que l'app iOS génère, publiées comme le contrat** (#2634).
 *
 * ## Pourquoi il existe (11/11/2026)
 *
 * L'app iOS générait ses libellés, onglets et pastilles en LISANT les sources du
 * front à une version taguée — plus de soixante-dix chemins, dont des motifs
 * appliqués à des composants Svelte. Rien, côté serveur, ne savait que ces fichiers
 * étaient lus : déplacer une constante cassait la montée de l'app, vu à sa
 * concordance du lendemain. Le contrat d'API, lui, est protégé (`reference.json`,
 * `retraits.py`, #2456) ; ces tables ne l'étaient pas.
 *
 * ## Ce qu'il fait
 *
 * Il lit les tables DÉCLARÉES (`tables-clients.registre.mjs`) dans l'arbre syntaxique
 * de leur seul fichier — il n'exécute rien et n'ouvre aucun autre fichier —, et :
 *
 * - `--ecrire` : écrit `front/tables-clients.json`, la référence versionnée que la
 *   release joint (`scripts/ci/lib-contrat-version.sh`). La version suit celle du
 *   contrat : majeure sur un retrait (annoncé), mineure sur tout autre écart. Un
 *   retrait ou un changement de forme NON annoncé dans `RETRAITS` est refusé, et
 *   rien n'est écrit ;
 * - sans option (la CI, `npm run lint:tables-clients`) : échoue si la référence
 *   n'est pas celle que les sources produisent, si un retrait n'est pas annoncé, ou
 *   si une annonce ne sert plus ;
 * - `--selftest` : chaque refus sur son cas, et le cas zéro.
 *
 * Lancer : node scripts/tables-clients.mjs [--ecrire | --selftest]
 */
import { readFileSync, writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import ts from 'typescript';
import { RETRAITS, TABLES } from './tables-clients.registre.mjs';

const FRONT = fileURLToPath(new URL('../', import.meta.url));
const REFERENCE = `${FRONT}tables-clients.json`;
const FORMAT = 1;
const SOURCE = /^src\/lib\/[\w/-]+\.ts#[A-Z][A-Z0-9_]*$/;

/** Une erreur qui se dit sans pile : c'est une faute de déclaration, pas un bogue. */
class Refus extends Error {}

/** La valeur JSON d'un initialiseur LITTÉRAL ; tout autre nœud est refusé. PURE. */
export function litteral(noeud, ou) {
	while (
		ts.isAsExpression(noeud) ||
		ts.isSatisfiesExpression(noeud) ||
		ts.isParenthesizedExpression(noeud)
	)
		noeud = noeud.expression;
	if (ts.isStringLiteral(noeud) || ts.isNoSubstitutionTemplateLiteral(noeud)) return noeud.text;
	if (ts.isNumericLiteral(noeud)) return Number(noeud.text);
	if (
		ts.isPrefixUnaryExpression(noeud) &&
		noeud.operator === ts.SyntaxKind.MinusToken &&
		ts.isNumericLiteral(noeud.operand)
	)
		return -Number(noeud.operand.text);
	if (noeud.kind === ts.SyntaxKind.TrueKeyword) return true;
	if (noeud.kind === ts.SyntaxKind.FalseKeyword) return false;
	if (noeud.kind === ts.SyntaxKind.NullKeyword) return null;
	if (ts.isArrayLiteralExpression(noeud)) return noeud.elements.map((e) => litteral(e, ou));
	if (ts.isObjectLiteralExpression(noeud)) {
		const objet = {};
		for (const p of noeud.properties) {
			const nom =
				p.name && (ts.isIdentifier(p.name) || ts.isStringLiteral(p.name)) ? p.name.text : null;
			if (!ts.isPropertyAssignment(p) || nom === null)
				throw new Refus(`${ou} : propriété non littérale (« ${p.getText()} »)`);
			objet[nom] = litteral(p.initializer, ou);
		}
		return objet;
	}
	throw new Refus(`${ou} : valeur non littérale (« ${noeud.getText().slice(0, 60)} »)`);
}

/** La valeur de la constante EXPORTÉE `nom` du texte TypeScript `texte`. PURE. */
export function constanteExportee(texte, nom, ou) {
	const fichier = ts.createSourceFile(ou, texte, ts.ScriptTarget.Latest, true, ts.ScriptKind.TS);
	for (const instr of fichier.statements) {
		if (!ts.isVariableStatement(instr)) continue;
		const exportee = instr.modifiers?.some((m) => m.kind === ts.SyntaxKind.ExportKeyword);
		const constante = (instr.declarationList.flags & ts.NodeFlags.Const) !== 0;
		for (const d of instr.declarationList.declarations) {
			if (!ts.isIdentifier(d.name) || d.name.text !== nom) continue;
			if (!exportee || !constante || !d.initializer)
				throw new Refus(`${ou}#${nom} : pas une constante exportée initialisée`);
			return litteral(d.initializer, `${ou}#${nom}`);
		}
	}
	throw new Refus(`${ou}#${nom} : introuvable`);
}

/** Les tables du registre, lues par `lire(chemin)` — rien d'autre n'est ouvert. PURE. */
export function lireTables(tables, lire) {
	const noms = Object.keys(tables).sort();
	if (noms.length === 0) throw new Refus('aucune table déclarée : le registre est vide');
	const sortie = {};
	for (const nom of noms) {
		const { source } = tables[nom];
		if (!SOURCE.test(source ?? ''))
			throw new Refus(`${nom} : source « ${source} » hors de src/lib/<module>.ts#EXPORT`);
		const [chemin, exportee] = source.split('#');
		sortie[nom] = {
			source: `front/${source}`,
			valeur: constanteExportee(lire(chemin), exportee, chemin),
		};
	}
	return sortie;
}

/** La FORME d'une valeur : chemin → type. Les clés d'un objet en font partie, les
 *  éléments d'une liste non (une option ajoutée ou retirée est une valeur). PURE. */
export function forme(valeur, chemin = '$', sortie = {}) {
	if (Array.isArray(valeur)) {
		sortie[chemin] = 'liste';
		for (const e of valeur) forme(e, `${chemin}[]`, sortie);
	} else if (valeur !== null && typeof valeur === 'object') {
		sortie[chemin] = 'objet';
		for (const [c, v] of Object.entries(valeur)) forme(v, `${chemin}.${c}`, sortie);
	} else {
		const type = valeur === null ? 'null' : typeof valeur;
		const deja = sortie[chemin];
		sortie[chemin] = deja && deja !== type ? [deja, type].sort().join('|') : type;
	}
	return sortie;
}

/** Les tables RETIRÉES ou dont la forme a reculé, de `ancien` à `nouveau`. PURE. */
export function retraits(ancien, nouveau) {
	const sortie = {};
	for (const [nom, table] of Object.entries(ancien)) {
		if (!(nom in nouveau)) {
			sortie[nom] = ['table retirée'];
			continue;
		}
		const avant = forme(table.valeur);
		const apres = forme(nouveau[nom].valeur);
		const perdus = Object.entries(avant)
			.filter(([c, t]) => apres[c] !== t)
			.map(([c, t]) => (c in apres ? `${c} : ${t} → ${apres[c]}` : `${c} retiré`));
		if (perdus.length) sortie[nom] = perdus;
	}
	return sortie;
}

/** Les refus : un retrait non annoncé, une annonce qui ne sert pas. PURE. */
export function refus(ecarts, annonces, ancien) {
	const messages = [];
	for (const [nom, quoi] of Object.entries(ecarts))
		if (!annonces[nom]) messages.push(`${nom} : ${quoi.join(' ; ')} — sans annonce dans RETRAITS`);
	for (const [nom, annonce] of Object.entries(annonces)) {
		if (!annonce?.ticket || !annonce?.raison)
			messages.push(`RETRAITS.${nom} : ticket et raison obligatoires`);
		if (!(nom in ecarts) && nom in ancien)
			messages.push(
				`RETRAITS.${nom} : la table est publiée sous la même forme — l'annonce ne sert plus`,
			);
	}
	return messages;
}

/** La version suivante, comme celle du contrat (`inventaire.version_suivante`). PURE. */
export function versionSuivante(version, ancien, nouveau, ecarts) {
	const [majeure, mineure] = version.split('.').map(Number);
	if (Object.keys(ecarts).length) return `${majeure + 1}.0.0`;
	if (JSON.stringify(ancien) !== JSON.stringify(nouveau)) return `${majeure}.${mineure + 1}.0`;
	return version;
}

/** Le texte de la référence — trié par table, deux espaces, une fin de ligne. PURE. */
export function texteReference(version, tables) {
	return `${JSON.stringify({ format: FORMAT, version, tables }, null, 2)}\n`;
}

/** La référence versionnée, ou `null` si elle n'existe pas encore. */
function lireReference() {
	try {
		return JSON.parse(readFileSync(REFERENCE, 'utf8'));
	} catch {
		return null;
	}
}

/** Le contrôle et l'écriture : rend les messages d'échec (vide = conforme). */
export function juger({ ecrire = false, tables = TABLES, annonces = RETRAITS } = {}) {
	const lue = lireReference();
	if (!lue && !ecrire)
		return [
			'front/tables-clients.json est absente ou illisible : `node scripts/tables-clients.mjs --ecrire`',
		];
	//  La première publication part de 1.0.0, comme le contrat.
	const reference = lue ?? { format: FORMAT, version: '1.0.0', tables: {} };
	const courant = lireTables(tables, (chemin) => readFileSync(`${FRONT}${chemin}`, 'utf8'));
	const ecarts = retraits(reference.tables, courant);
	const messages = refus(ecarts, annonces, reference.tables);
	if (messages.length) return messages;
	const version = lue ? versionSuivante(lue.version, lue.tables, courant, ecarts) : '1.0.0';
	const texte = texteReference(version, courant);
	if (ecrire) {
		writeFileSync(REFERENCE, texte);
		console.log(
			`Tables publiées ${reference.version} → ${version} (${Object.keys(courant).length} tables).`,
		);
		return [];
	}
	if (readFileSync(REFERENCE, 'utf8') !== texte)
		return [
			'front/tables-clients.json n’est pas ce que les sources produisent : `node scripts/tables-clients.mjs --ecrire`',
		];
	return [];
}

function selftest() {
	let echecs = 0;
	const cas = (nom, ok) => {
		console.log(`${ok ? 'PASS' : 'FAIL'}  ${nom}`);
		if (!ok) echecs++;
	};
	const leve = (f) => {
		try {
			f();
			return false;
		} catch (e) {
			return e instanceof Refus;
		}
	};
	const src = `import { x } from './y';\nexport const T = { a: { libelle: 'A', n: -1 }, b: { libelle: 'B', n: 2 } } as const;\nexport const L: string[] = ['x', 'y'];\nconst P = 1;\nexport const F = calcul();\nexport const S = { ...T };`;
	cas(
		'objet littéral lu, ordre gardé',
		JSON.stringify(constanteExportee(src, 'T', 'm.ts')) ===
			'{"a":{"libelle":"A","n":-1},"b":{"libelle":"B","n":2}}',
	);
	cas('liste annotée lue', JSON.stringify(constanteExportee(src, 'L', 'm.ts')) === '["x","y"]');
	cas(
		'constante non exportée refusée',
		leve(() => constanteExportee(src, 'P', 'm.ts')),
	);
	cas(
		'appel de fonction refusé (rien ne s’exécute)',
		leve(() => constanteExportee(src, 'F', 'm.ts')),
	);
	cas(
		'décomposition refusée',
		leve(() => constanteExportee(src, 'S', 'm.ts')),
	);
	cas(
		'export introuvable refusé',
		leve(() => constanteExportee(src, 'Z', 'm.ts')),
	);
	cas(
		'cas zéro : registre vide refusé',
		leve(() => lireTables({}, () => src)),
	);
	cas(
		'source hors de src/lib refusée',
		leve(() => lireTables({ t: { source: '../api/x.ts#T' } }, () => src)),
	);
	const lus = [];
	lireTables({ t: { source: 'src/lib/m.ts#T' } }, (c) => (lus.push(c), src));
	cas('seul le fichier déclaré est lu', JSON.stringify(lus) === '["src/lib/m.ts"]');
	const ancien = { t: { valeur: { a: { libelle: 'A' } } }, u: { valeur: [1] } };
	cas(
		'clé ajoutée : pas un retrait',
		Object.keys(
			retraits(ancien, { ...ancien, t: { valeur: { a: { libelle: 'A' }, b: { libelle: 'B' } } } }),
		).length === 0,
	);
	cas(
		'option retirée d’une liste : pas un retrait',
		Object.keys(retraits({ u: { valeur: [1, 2] } }, { u: { valeur: [1] } })).length === 0,
	);
	const sansA = retraits(ancien, { ...ancien, t: { valeur: {} } });
	cas(
		'clé retirée : retrait',
		sansA.t?.some((m) => m.includes('$.a')),
	);
	const typeChange = retraits(ancien, { ...ancien, t: { valeur: { a: { libelle: 3 } } } });
	cas('type changé : retrait', typeChange.t?.[0]?.includes('string → number'));
	const sansU = retraits(ancien, { t: ancien.t });
	cas('table retirée : retrait', sansU.u?.[0] === 'table retirée');
	cas('retrait non annoncé refusé', refus(sansU, {}, ancien).length === 1);
	cas(
		'retrait annoncé admis',
		refus(sansU, { u: { ticket: '#1', raison: 'r' } }, ancien).length === 0,
	);
	cas('annonce sans raison refusée', refus(sansU, { u: { ticket: '#1' } }, ancien).length === 1);
	cas(
		'annonce qui ne sert plus refusée',
		refus({}, { t: { ticket: '#1', raison: 'r' } }, ancien).length === 1,
	);
	cas('version : retrait → majeure', versionSuivante('1.4.2', ancien, {}, sansU) === '2.0.0');
	cas('version : ajout → mineure', versionSuivante('1.4.2', {}, ancien, {}) === '1.5.0');
	cas('version : rien → inchangée', versionSuivante('1.4.2', ancien, ancien, {}) === '1.4.2');
	console.log(echecs ? `== ${echecs} ÉCHEC(S) ==` : '== TOUS OK ==');
	return echecs === 0;
}

const MODE = process.argv[2];
if (MODE === '--selftest') process.exit(selftest() ? 0 : 1);
try {
	const messages = juger({ ecrire: MODE === '--ecrire' });
	if (messages.length) {
		for (const m of messages) console.error(`✗ ${m}`);
		process.exit(1);
	}
	if (MODE !== '--ecrire')
		console.log(
			`✓ Tables publiées aux clients : ${Object.keys(TABLES).length} table(s), référence à jour.`,
		);
} catch (e) {
	if (!(e instanceof Refus)) throw e;
	console.error(`✗ ${e.message}`);
	process.exit(1);
}
