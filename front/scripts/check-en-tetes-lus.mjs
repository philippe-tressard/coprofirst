#!/usr/bin/env node
/**
 *  Un en-tête que le front POSE doit être LU par une route de l'API (#1534,
 *  02/10/2026).
 *
 *  ## Le défaut qui l'a fait naître
 *
 *  « Agir pour… » : le client (`#lib/api/client.ts`) posait `X-Acting-As` sur
 *  chaque requête, le menu affichait « Vous agissez pour Mme X », et côté
 *  serveur seule `auth/deps.get_acting_user` lisait l'en-tête — une dépendance
 *  qu'AUCUNE route n'a jamais prise. L'aidant écrivait donc sous sa propre
 *  identité, pendant que l'écran et le manuel promettaient le contraire.
 *
 *  Arbitré le 02/10/2026 : la délégation devient « lecture seule » — la lecture
 *  passe par `utils/delegations_actives` et n'a besoin d'aucun en-tête — et le
 *  commutateur d'identité a été retiré.
 *
 *  ## Ce que le contrôle refuse
 *
 *  Un en-tête personnalisé (`X-…`) posé par le front sans qu'une route le lise :
 *  - lu **dans un routeur** (`alias="X-…"`, `request.headers.get("X-…")`) ;
 *  - ou lu par une dépendance de `app/auth/` **qu'une route prend**
 *    (`Depends(…)`, pas un import) — directement, ou par une autre dépendance
 *    qu'une route prend.
 *  Lire l'en-tête dans `deps.py` ne suffit donc pas : c'est exactement la forme
 *  du défaut de #1534. Côté API, `test_autorisation.py` refuse de son côté une
 *  dépendance d'autorisation qu'aucune route ne prend ; ce contrôle-ci garde
 *  l'autre bord — l'en-tête qui repart d'un écran sans destinataire.
 *
 *  ⚠️ Comparaison sans casse : HTTP ne distingue pas `X-Foo` de `x-foo`.
 *
 *  Lancer : node scripts/check-en-tetes-lus.mjs [--selftest]
 */
import { existsSync, readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { neutraliserCommentaires } from './lib-commentaires.mjs';
import { controler, fichiersSources } from './lib-source-unique.mjs';

const ICI = dirname(fileURLToPath(import.meta.url));
const API = join(ICI, '..', '..', 'api', 'app');

/** `headers['X-Foo'] =`, `{ 'X-Foo': … }`, `headers.set('X-Foo', …)`. */
const POSE =
	/(?:\[\s*['"`](x-[\w-]+)['"`]\s*\]\s*=|['"`](x-[\w-]+)['"`]\s*:|\.(?:set|append)\(\s*['"`](x-[\w-]+)['"`])/gi;

/** `alias="X-Foo"`, `headers.get("X-Foo")`, `headers["X-Foo"]` côté Python. */
const LECTURE = /(?:alias\s*=\s*|headers\.get\(\s*|headers\[\s*)["'](x-[\w-]+)["']/gi;

/** `setHeaders({ … })` de SvelteKit : des en-têtes de RÉPONSE, que le serveur du
 *  front renvoie au navigateur — rien ne part vers l'API (`X-Robots-Tag` de la
 *  démo publique, #1906). Le contrôle ne vise que les requêtes. */
const REPONSE = /setHeaders\(\s*\{[^}]*\}\s*\)/g;

/** Les en-têtes posés par une source front, en minuscules. PURE. */
export function posesPar(texte) {
	const requetes = neutraliserCommentaires(texte).replace(REPONSE, '');
	return [...requetes.matchAll(POSE)].map((m) => (m[1] ?? m[2] ?? m[3]).toLowerCase());
}

/** Retire les commentaires `#` d'une source Python (assez pour ce relevé). */
const sansCommentairesPy = (t) => t.replace(/#[^\n]*/g, '');

/** `{ nom: corps }` des fonctions de premier niveau d'un module Python. */
function fonctionsPy(texte) {
	const fns = {};
	const blocs = sansCommentairesPy(texte).split(/^(?=def \w+\s*\()/m);
	for (const b of blocs) {
		const m = b.match(/^def (\w+)\s*\(/);
		if (m) fns[m[1]] = b;
	}
	return fns;
}

/**
 * Les en-têtes qu'une ROUTE lit, en minuscules. PURE.
 *
 * @param {Record<string,string>} routeurs  chemin → source des routeurs
 * @param {Record<string,string>} auth      chemin → source de `app/auth/`
 */
export function lusParLesRoutes(routeurs, auth) {
	const lus = new Set();
	const sourceRouteurs = Object.values(routeurs).map(sansCommentairesPy).join('\n');
	for (const m of sourceRouteurs.matchAll(LECTURE)) lus.add(m[1].toLowerCase());

	//  Les dépendances de `app/auth/` PRISES par une route — `Depends(nom…)`, pas
	//  un simple import —, de proche en proche : une dépendance prise par une
	//  dépendance prise l'est aussi.
	const deps = Object.assign({}, ...Object.values(auth).map(fonctionsPy));
	const prend = (source, nom) => new RegExp(`Depends\\(\\s*${nom}\\b`).test(source);
	const prises = new Set(Object.keys(deps).filter((n) => prend(sourceRouteurs, n)));
	let ajout = true;
	while (ajout) {
		ajout = false;
		for (const nom of Object.keys(deps)) {
			if (prises.has(nom) || ![...prises].some((p) => prend(deps[p], nom))) continue;
			prises.add(nom);
			ajout = true;
		}
	}
	for (const nom of prises) {
		for (const m of deps[nom].matchAll(LECTURE)) lus.add(m[1].toLowerCase());
	}
	return lus;
}

/** Les numéros des lignes qui posent un en-tête absent de `lus`. PURE. */
const fautesSelon = (lus) => (texte) =>
	neutraliserCommentaires(texte)
		.split('\n')
		.map((ligne, i) => [ligne, i + 1])
		.filter(([l]) => posesPar(l).some((h) => !lus.has(h)))
		.map(([, n]) => n);

function lire(racine) {
	const contenus = {};
	if (!existsSync(racine)) return contenus;
	for (const f of fichiersSources(racine, ['.py'])) contenus[f] = readFileSync(f, 'utf8');
	return contenus;
}

/** Les cas du relevé côté API — ceux que `controler` ne sait pas rejouer. */
function selftestApi() {
	const DEP = 'def lit(x = Header(default=None, alias="X-Lu")):\n    return x\n';
	const cas = [
		['lu dans un routeur', lusParLesRoutes({ r: 'a = Header(alias="X-Lu")' }, {}), ['x-lu']],
		['request.headers.get', lusParLesRoutes({ r: 'request.headers.get("x-lu")' }, {}), ['x-lu']],
		//  La forme exacte de #1534 : lu par une dépendance que personne ne prend.
		['lu par une dépendance orpheline', lusParLesRoutes({ r: 'Depends(autre)' }, { d: DEP }), []],
		['lu par une dépendance prise', lusParLesRoutes({ r: 'Depends(lit)' }, { d: DEP }), ['x-lu']],
		[
			'lu par une dépendance prise par une dépendance prise',
			lusParLesRoutes(
				{ r: 'Depends(porte)' },
				{ d: DEP + 'def porte(u = Depends(lit)):\n    return u\n' },
			),
			['x-lu'],
		],
		[
			'une dépendance importée sans être prise ne lit rien',
			lusParLesRoutes({ r: 'from app.auth.deps import lit' }, { d: DEP }),
			[],
		],
		['un commentaire Python ne lit rien', lusParLesRoutes({ r: '# alias="X-Lu"' }, {}), []],
	];
	let ko = 0;
	for (const [quoi, obtenu, attendu] of cas) {
		const ok = JSON.stringify([...obtenu]) === JSON.stringify(attendu);
		console.log(`${ok ? 'PASS' : 'FAIL'}  ${quoi}`);
		if (!ok) ko = 1;
	}
	return ko;
}

const selftest = process.argv.includes('--selftest');
let lus;
if (selftest) {
	if (selftestApi()) process.exit(1);
	lus = new Set(['x-lu']);
} else {
	const routeurs = lire(join(API, 'routers'));
	//  Cas zéro (standards/04 §2) : aucun routeur lu n'est pas « aucun en-tête lu ».
	if (!Object.keys(routeurs).length) {
		console.error(`✗ Aucun routeur lu sous ${API} : contrôle INCONNU.`);
		process.exit(1);
	}
	lus = lusParLesRoutes(routeurs, lire(join(API, 'auth')));
}

process.exit(
	controler({
		extensions: ['.ts', '.svelte', '.js'],
		fautes: fautesSelon(lus),
		cas: [
			//  La ligne retirée par #1534 : posée, lue par aucune route.
			["\tif (_actingAsId !== null) headers['X-Acting-As'] = String(_actingAsId);", 1],
			["\tconst h = { 'X-Acting-As': '12' };", 1],
			["\theaders.set('x-acting-as', '12');", 1],
			//  Un en-tête qu'une route lit — casse indifférente.
			["\theaders['X-Lu'] = '1';", 0],
			//  Un en-tête standard n'est pas personnalisé.
			["\tif (body) headers['Content-Type'] = 'application/json';", 0],
			//  Un commentaire qui cite l'en-tête retiré.
			["\t// on posait headers['X-Acting-As'] ici (#1534)", 0],
			//  Un en-tête de RÉPONSE posé par SvelteKit ne part pas vers l'API (#1906)…
			["\tif (demo) setHeaders({ 'x-robots-tag': 'noindex, nofollow' });", 0],
			//  …mais une requête posée sur la même ligne reste vue.
			["\tsetHeaders({ 'x-robots-tag': 'x' }); headers['X-Acting-As'] = '1';", 1],
		],
		ok: 'En-têtes personnalisés : chacun de ceux que pose le front est lu par une route',
		ko: 'en-tête(s) posé(s) par le front sans route qui le lise',
		conseil:
			'Une route doit lire l’en-tête (directement, ou par une dépendance de `app/auth/` ' +
			'qu’elle prend) — sinon ne pas le poser : l’écran promettrait un effet qui n’a pas lieu (#1534).',
	}),
);
