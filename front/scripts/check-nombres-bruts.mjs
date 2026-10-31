#!/usr/bin/env node
/**
 *  Un nombre ou un mois que l'API envoie ne s'affiche pas tel quel (#2358,
 *  30/10/2026) : il passe par `fmtNombre` (`#lib/utils`) ou `fmtMonthYear`
 *  (`#lib/date`).
 *
 *  🔴 La télémétrie affichait « 27054 », « 3864.9 » et « Record mois — 2026-05 »
 *  — vu à l'écran pendant le contrôle visuel de #2313, par l'utilisateur. Les
 *  contrôles voisins ne pouvaient pas le voir : `check-formats` refuse un format
 *  ÉCRIT à la main (`toFixed(`, `toLocaleString`), et ici il n'y avait aucun
 *  format du tout — la valeur du serveur, rendue brute.
 *
 *  ## Ce que le contrôle lit
 *
 *  - les **champs du client d'API** (`src/lib/api/*.ts`) : ceux typés `number`
 *    (avec ou sans `null`) sont des nombres, ceux typés `MoisIso`
 *    (`api/valeurs.ts`) des clés `AAAA-MM` ;
 *  - le **gabarit** de chaque composant (AST de `svelte/compiler`) : le texte et
 *    les attributs qui se LISENT (`title`, `aria-label`, `alt`, `placeholder`),
 *    gabarits `${…}` et branches d'une condition compris.
 *
 *  Il refuse `{x.champ}` (ou `{x.champ ?? 0}`) quand `champ` est l'un d'eux.
 *  `{fmtNombre(x.champ)}` est un appel : il passe.
 *
 *  ## Ce qu'il ne voit pas — et c'est dit
 *
 *  Le nom seul : un champ du client se reconnaît à son NOM, pas au type de
 *  l'objet qui le porte (le contrôle ne fait pas tourner TypeScript sur le
 *  gabarit). D'où deux listes déclarées : `NON_QUANTITES` — un nombre qui n'est
 *  pas une quantité, et que `fmtNombre` abîmerait (« 2 026 ») — et `HOMONYMES`
 *  — un champ d'un fichier où le nom désigne un TEXTE (`note` d'un relevé,
 *  `refus` d'un service). Toutes deux doivent servir. Il ne voit pas non plus une
 *  variable locale (`{moyenne}`), un `.length`, ni une clé `AAAA-MM` déclarée
 *  `string` : la légende du graphe de télémétrie, dont la clé change avec la
 *  vue, est tenue par `e2e/telemetrie-nombres-fr.spec.ts`.
 *
 *  Câblé dans `npm run lint:dates` : la notion est la même — « un format ne se
 *  réimplémente pas, et ne s'oublie pas non plus ».
 *
 *  Lancer : node scripts/check-nombres-bruts.mjs [--selftest]
 */
import { readFileSync } from 'node:fs';
import ts from 'typescript';
import { parse } from 'svelte/compiler';
import { controler, fichiersSources } from './lib-source-unique.mjs';

/**
 *  Les nombres qui ne sont PAS des quantités : les grouper les fausserait.
 *  Chaque nom doit être un nombre du client ET être rendu brut quelque part —
 *  une déclaration qui ne sert plus fait échouer.
 */
const NON_QUANTITES = {
	id: 'un identifiant (n° de compte, de ligne) : « 1 204 » ne désigne rien',
	user_id: 'un identifiant de compte',
	lot_id: 'un identifiant de lot',
	batiment_id: 'un identifiant de bâtiment, affiché en repli de son nom',
	conditions_acceptees: 'la version des conditions acceptées (« Contrat v3 »)',
	code: 'un code (statut HTTP, code d’accès) : il se recopie, il ne se compte pas',
	version: 'un numéro de version',
	revision: 'un numéro de révision d’un compte rendu',
	annee: 'une année : « 2 026 » serait faux',
	exercice: 'une année d’exercice comptable',
	ag_annee: 'l’année d’une assemblée générale',
};

/**
 *  Un champ d'un fichier dont le NOM est celui d'un nombre du client, et qui
 *  désigne un texte : `fichier → { champ: raison }`. Chaque paire doit servir.
 */
const HOMONYMES = {
	'src/lib/components/Gouttiere.svelte': {
		mois: '`date.mois` est le morceau TEXTE de `partiesDate` (« avr. »)',
	},
	'src/lib/components/RaccourcisRapides.svelte': {
		mois: '`jour.mois` est le morceau TEXTE de `partiesDate` (« nov. »)',
	},
	'src/lib/components/ChampFrequence.svelte': {
		nombre: '`unite.nombre` est le LIBELLÉ du champ (« Tous les N mois »)',
	},
	'src/lib/components/OngletServices.svelte': {
		refus: '`s.refus` est la phrase qui dit ce qu’on perd en coupant le service',
	},
	'src/lib/components/OngletUtilisateurs.svelte': {
		ok: '`t.ok` est le texte d’aide d’une étiquette de compte',
	},
	'src/lib/components/OngletConsommations.svelte': {
		note: '`r.note` est la note TEXTE d’un relevé de compteur',
	},
	'src/lib/components/ConciliationFusion.svelte': {
		destinataires: '`o.resultat.destinataires` est la PHRASE qui dit qui lira l’affaire fusionnée',
	},
	'src/lib/components/TableauCharges.svelte': {
		note: '`l.note` est la note TEXTE d’une ligne de charges',
	},
};

/** Les attributs que l'on LIT à l'écran (au survol, au lecteur d'écran). */
const ATTRIBUTS_LUS = new Set(['title', 'aria-label', 'alt', 'placeholder']);

/** Le type d'un champ est-il `number` (éventuellement `| null | undefined`) ? */
function estNombre(t) {
	if (!t) return false;
	if (t.kind === ts.SyntaxKind.NumberKeyword) return true;
	if (!ts.isUnionTypeNode(t)) return false;
	const vide = (x) =>
		x.kind === ts.SyntaxKind.UndefinedKeyword ||
		(ts.isLiteralTypeNode(x) && x.literal.kind === ts.SyntaxKind.NullKeyword);
	return (
		t.types.some((x) => x.kind === ts.SyntaxKind.NumberKeyword) &&
		t.types.every((x) => x.kind === ts.SyntaxKind.NumberKeyword || vide(x))
	);
}

/** Le type d'un champ est-il `MoisIso` (ou `MoisIso[]`, avec ou sans `null`) ? */
function estMoisIso(t) {
	if (!t) return false;
	if (ts.isArrayTypeNode(t)) return estMoisIso(t.elementType);
	if (ts.isUnionTypeNode(t)) return t.types.some(estMoisIso);
	return ts.isTypeReferenceNode(t) && t.typeName.getText() === 'MoisIso';
}

/** Les noms des champs numériques et des clés de mois, lus dans des sources TS. PURE. */
export function champsDuClient(sources) {
	const nombres = new Set();
	const mois = new Set();
	for (const [nom, texte] of Object.entries(sources)) {
		const sf = ts.createSourceFile(nom, texte, ts.ScriptTarget.Latest, true);
		const visiter = (n) => {
			if ((ts.isPropertySignature(n) || ts.isPropertyDeclaration(n)) && n.type) {
				const champ = n.name.getText(sf);
				if (estNombre(n.type)) nombres.add(champ);
				if (estMoisIso(n.type)) mois.add(champ);
			}
			ts.forEachChild(n, visiter);
		};
		visiter(sf);
	}
	return { nombres, mois };
}

/**
 *  Les rendus bruts d'un gabarit : `[{ ligne, champ, sorte }]`. PURE.
 *  `ecartes` reçoit les champs passés parce que déclarés : ceux de
 *  `NON_QUANTITES`, et les `homonymes` du fichier.
 */
export function rendusBruts(source, { nombres, mois }, homonymes = {}, ecartes = new Set()) {
	let ast;
	try {
		ast = parse(source, { modern: true });
	} catch {
		//  Un fragment qui ne se lit pas n'est pas « sans faute » : il se signale.
		return [{ ligne: 1, champ: '(gabarit illisible)', sorte: 'illisible' }];
	}
	const trouves = [];
	const ligneDe = (pos) => source.slice(0, pos).split('\n').length;
	const examiner = (e) => {
		if (!e) return;
		switch (e.type) {
			case 'TemplateLiteral':
				return e.expressions.forEach(examiner);
			case 'ConditionalExpression':
				examiner(e.consequent);
				return examiner(e.alternate);
			case 'LogicalExpression':
				examiner(e.left);
				return examiner(e.right);
			case 'ChainExpression':
				return examiner(e.expression);
			case 'MemberExpression': {
				if (e.computed || e.property.type !== 'Identifier') return;
				const champ = e.property.name;
				const sorte = mois.has(champ) ? 'mois' : nombres.has(champ) ? 'nombre' : null;
				if (!sorte) return;
				if (sorte === 'nombre' && champ in NON_QUANTITES) return void ecartes.add(champ);
				if (champ in homonymes) return void ecartes.add(champ);
				trouves.push({ ligne: ligneDe(e.start), champ, sorte });
			}
		}
	};
	const parcourir = (n) => {
		if (!n || typeof n !== 'object') return;
		if (Array.isArray(n)) return n.forEach(parcourir);
		if (n.type === 'ExpressionTag') return examiner(n.expression);
		if (n.type === 'Attribute') {
			if (!ATTRIBUTS_LUS.has(n.name)) return;
			const valeurs = Array.isArray(n.value) ? n.value : [n.value];
			return valeurs.forEach(parcourir);
		}
		//  Ce qui ne s'affiche pas : directives, attributs étalés, et les
		//  expressions des blocs (`{#if …}`, `{#each …}`) — seuls leurs corps.
		if (/Directive$|^SpreadAttribute$/.test(n.type)) return;
		for (const [cle, v] of Object.entries(n)) {
			if (['expression', 'test', 'context', 'key', 'index', 'metadata'].includes(cle)) continue;
			parcourir(v);
		}
	};
	parcourir(ast.fragment);
	return trouves;
}

const CLIENT = Object.fromEntries(
	fichiersSources('src/lib/api', ['.ts']).map((f) => [f, readFileSync(f, 'utf8')]),
);
const champs = champsDuClient(CLIENT);
//  Ce que les déclarations ont écarté : `champ` (NON_QUANTITES), `chemin:champ` (HOMONYMES).
const servis = new Set();

const fautes = (texte, chemin) => {
	const propres = HOMONYMES[chemin] ?? {};
	const ecartes = new Set();
	const lignes = rendusBruts(texte, champs, propres, ecartes).map((r) => r.ligne);
	for (const champ of ecartes) servis.add(champ in propres ? `${chemin}:${champ}` : champ);
	return lignes;
};

const selftest = process.argv.includes('--selftest');

//  Cas zéro (standards/04 §2) : un client sans nombre ni `MoisIso` ne serait pas
//  « aucune faute », ce serait un contrôle qui ne lit plus rien.
if (!champs.nombres.size || !champs.mois.size) {
	console.error(
		`✗ ${champs.nombres.size} champ(s) numérique(s) et ${champs.mois.size} clé(s) MoisIso ` +
			'lus dans src/lib/api : contrôle INCONNU.',
	);
	process.exit(1);
}

let ko = controler({
	extensions: ['.svelte'],
	fautes,
	cas: [
		//  Les formes du constat (#2358).
		['<div class="tl-kpi-value">{kpi.vues ?? 0}</div>', 1],
		['<div class="tl-kpi-value">{kpi.moy_vues_jour}</div>', 1],
		['<div>🏆 Record mois — {kpi.record_mois.mois}</div>', 1],
		['<td class="num-fort">{p.total}</td>', 1],
		['<div title="{b.d.label} — {b.d.total} vues"></div>', 1],
		['<span>{x ? r.uniques : "—"}</span>', 1],
		['<span>{`${r?.uniques} uniques`}</span>', 1],
		//  Les formes voulues, jamais signalées.
		['<div class="tl-kpi-value">{fmtNombre(kpi.vues)}</div>', 0],
		['<div>🏆 Record mois — {fmtMonthYear(kpi.record_mois.mois)}</div>', 0],
		//  Un nombre qui n'est pas une quantité (déclaré) ; un champ texte.
		['<td>{l.annee}</td><td>{u.id}</td><td>{u.nom}</td>', 0],
		//  Ce qui ne s'affiche pas : le style, une prop, le test d'un bloc.
		['<div style="height:{d.total}%" class:x={d.total > 1}></div>', 0],
		['<Jauge valeur={d.total} />', 0],
		['{#if d.total}<p>…</p>{/if}', 0],
		//  Un commentaire qui cite la forme refusée.
		['<!-- on écrivait {kpi.vues} -->', 0],
	],
	ok: 'Nombres et mois de l’API : rendus par fmtNombre / fmtMonthYear',
	ko: 'nombre(s) ou mois de l’API rendu(s) brut(s)',
	conseil:
		'Un nombre : `fmtNombre(x)` (`#lib/utils`) ; une clé AAAA-MM : `fmtMonthYear(x)` ' +
		'(`#lib/date`). Un nombre qui n’est pas une quantité se déclare dans NON_QUANTITES de ' +
		'scripts/check-nombres-bruts.mjs, un champ qui désigne un texte dans HOMONYMES.',
});

if (!selftest) {
	for (const [nom] of Object.entries(NON_QUANTITES)) {
		if (!champs.nombres.has(nom)) {
			console.error(`✗ NON_QUANTITES : « ${nom} » n'est plus un nombre du client — le retirer.`);
			ko = 1;
		} else if (!servis.has(nom)) {
			console.error(`✗ NON_QUANTITES : « ${nom} » n'est plus rendu brut — le retirer.`);
			ko = 1;
		}
	}
	for (const [chemin, propres] of Object.entries(HOMONYMES)) {
		for (const champ of Object.keys(propres)) {
			if (!servis.has(`${chemin}:${champ}`)) {
				console.error(`✗ HOMONYMES : « ${champ} » n'est plus rendu dans ${chemin} — le retirer.`);
				ko = 1;
			}
		}
	}
}
process.exit(ko);
