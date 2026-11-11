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
 * de leur fichier et des modules de `src/lib` qu'elles importent — il n'exécute rien
 * et n'ouvre aucun autre fichier (`tables-clients.lecture.mjs`) —, et :
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
import {
	Refus,
	SOURCE,
	constanteExportee,
	lecteur,
	moduleImporte,
} from './tables-clients.lecture.mjs';
import { SOURCE_CSS, valeurCss } from './tables-clients.css.mjs';
import { RETRAITS, TABLES } from './tables-clients.registre.mjs';

const FRONT = fileURLToPath(new URL('../', import.meta.url));
const REFERENCE = `${FRONT}tables-clients.json`;
const FORMAT = 1;
/** Une source déclarée : `src/lib/<module>.ts#EXPORT`, une règle CSS
 *  (`src/styles/<feuille>.css@<sélecteur>`, `src/lib/…/X.svelte@<sélecteur>`), ou un
 *  objet de sources. PURE. */
function sourcesDe(nom, source) {
	const liste = typeof source === 'string' ? [source] : Object.values(source ?? {});
	if (!liste.length || liste.some((s) => !SOURCE.test(s ?? '') && !SOURCE_CSS.test(s ?? '')))
		throw new Refus(
			`${nom} : source « ${JSON.stringify(source)} » ni src/lib/<module>.ts#EXPORT ni <feuille>@<sélecteur>`,
		);
	return liste;
}

/** Les tables du registre, lues par `lire(chemin)` — seuls les fichiers de `src/lib`
 *  qu'elles nomment ou importent sont ouverts. PURE. */
export function lireTables(tables, lire) {
	const noms = Object.keys(tables).sort();
	if (noms.length === 0) throw new Refus('aucune table déclarée : le registre est vide');
	const valeur = lecteur(lire);
	const une = (s, sans = null) => {
		if (SOURCE_CSS.test(s)) {
			if (sans) throw new Refus(`${s} : « sans » ne vaut que pour une constante TypeScript`);
			const arobase = s.indexOf('@');
			return valeurCss(lire(s.slice(0, arobase)), s.slice(0, arobase), s.slice(arobase + 1));
		}
		const [chemin, exportee] = s.split('#');
		return valeur(chemin, exportee, true, sans);
	};
	const sortie = {};
	for (const nom of noms) {
		const { source, sans } = tables[nom];
		sourcesDe(nom, source);
		if (sans !== undefined && (typeof source !== 'string' || !Array.isArray(sans) || !sans.length))
			throw new Refus(`${nom} : « sans » se déclare en liste non vide, sur une source unique`);
		sortie[nom] =
			typeof source === 'string'
				? { source: `front/${source}`, valeur: une(source, sans ?? null) }
				: {
						source: Object.fromEntries(Object.entries(source).map(([c, s]) => [c, `front/${s}`])),
						valeur: Object.fromEntries(Object.entries(source).map(([c, s]) => [c, une(s)])),
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
		'étalement d’un objet lu',
		JSON.stringify(constanteExportee(src, 'S', 'm.ts')) ===
			JSON.stringify(constanteExportee(src, 'T', 'm.ts')),
	);
	//  ── Le lecteur : identifiants, imports, gabarits, exclusions (lot B) ──────
	const modules = {
		'src/lib/a.ts':
			"import { NOM, LISTE } from '#lib/b.ts';\nimport { AILLEURS } from 'svelte/store';\n" +
			"const LOCAL = 'loc';\nexport const R = { nom: NOM, gabarit: `${NOM} v${2}`, plus: 'a' + LOCAL, " +
			'liste: [...LISTE, 3], LOCAL };\n' +
			'export const H = { x: AILLEURS };\nexport const C1 = { y: C2 };\nexport const C2 = { z: C1 };\n' +
			"export const P = [{ code: 'a', lien: { cible: () => '/', aide: 'x' } }];\n" +
			'export const U = { v: undefined };\nexport const N = { n: NON_EXPORTE };\n',
		'src/lib/b.ts':
			"export const NOM = 'Copro';\nexport const LISTE = [1, 2];\nconst NON_EXPORTE = 1;\n",
	};
	const lire = (c) => {
		if (!(c in modules)) throw new Error(`non déclaré : ${c}`);
		return modules[c];
	};
	const val = (nom, sans) => lecteur(lire)('src/lib/a.ts', nom, true, sans);
	cas(
		'identifiant, import de #lib, gabarit, concaténation, étalement, propriété abrégée',
		JSON.stringify(val('R')) ===
			'{"nom":"Copro","gabarit":"Copro v2","plus":"aloc","liste":[1,2,3],"LOCAL":"loc"}',
	);
	cas(
		'import hors de src/lib refusé',
		leve(() => val('H')),
	);
	cas(
		'définition circulaire refusée',
		leve(() => val('C1')),
	);
	cas(
		'fonction refusée sans exclusion',
		leve(() => val('P')),
	);
	cas(
		'exclusion déclarée : la fonction sautée, le reste lu',
		JSON.stringify(val('P', ['[].lien.cible'])) === '[{"code":"a","lien":{"aide":"x"}}]',
	);
	cas(
		'exclusion qui ne sert plus refusée',
		leve(() => val('P', ['[].lien.cible', '[].autre'])),
	);
	cas(
		'« undefined » refusé',
		leve(() => val('U')),
	);
	cas(
		'identifiant inconnu refusé',
		leve(() => val('N')),
	);
	cas(
		'module importé : chemin borné à src/lib',
		moduleImporte('#lib/b.ts', 'src/lib/a.ts') === 'src/lib/b.ts' &&
			moduleImporte('./pages-roles', 'src/lib/pages.ts') === 'src/lib/pages-roles.ts' &&
			moduleImporte('../../x', 'src/lib/a.ts') === null &&
			moduleImporte('svelte', 'src/lib/a.ts') === null,
	);
	cas(
		'source en objet de sources lue',
		JSON.stringify(
			lireTables({ t: { source: { a: 'src/lib/b.ts#NOM', b: 'src/lib/b.ts#LISTE' } } }, lire).t
				.valeur,
		) === '{"a":"Copro","b":[1,2]}',
	);
	//  ── Les règles CSS (lot C) ─────────────────────────────────────────────
	const css = {
		'src/styles/f.css':
			"/* :root { --x: faux; } */\n:root,\n.ilot { --a: #fff; --b: var(--a); content: 'x;y'; }\n" +
			"@media screen { :root[data-p='un'] { --a: #000; } }\n:root[data-p='deux'], .z { --a: #111; }\n" +
			':root[data-p="un"] .ilot { --a: #222; }\n.d { --a: 1; }\n.d { --a: 2; }\n',
		'src/lib/C.svelte':
			"<div></div>\n<style>\n\t[data-t='s1'] { background: var(--s-1); }\n</style>\n",
	};
	const lireCss = (c) => css[c];
	const t = (source, sans) => lireTables({ t: { source, sans } }, lireCss).t.valeur;
	cas(
		'règle CSS lue : sélecteur dans une liste, commentaire sauté, « ; » dans une chaîne',
		JSON.stringify(t('src/styles/f.css@:root')) ===
			'{"--a":"#fff","--b":"var(--a)","content":"\'x;y\'"}',
	);
	cas(
		'famille : un code par règle, @media traversé, guillemets indifférents',
		JSON.stringify(t("src/styles/f.css@:root[data-p='*']")) ===
			'{"un":{"--a":"#000"},"deux":{"--a":"#111"}}',
	);
	cas(
		'<style> d’un composant lu',
		JSON.stringify(t("src/lib/C.svelte@[data-t='*']")) === '{"s1":{"background":"var(--s-1)"}}',
	);
	cas(
		'deux règles pour un sélecteur refusées',
		leve(() => t('src/styles/f.css@.d')),
	);
	cas(
		'sélecteur absent refusé',
		leve(() => t('src/styles/f.css@.absente')),
	);
	cas(
		'« sans » sur une règle CSS refusé',
		leve(() => t('src/styles/f.css@:root', ['.x'])),
	);
	cas(
		'feuille hors de src/styles refusée',
		leve(() => t('src/autre/f.css@:root')),
	);
	cas(
		'« sans » sur un objet de sources refusé',
		leve(() => lireTables({ t: { source: { a: 'src/lib/b.ts#NOM' }, sans: ['.x'] } }, lire)),
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
