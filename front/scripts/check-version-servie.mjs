/**
 * La version RÉELLEMENT servie — l'extracteur de P3, et le garde-fou qui le
 * garde vivant.
 *
 * ## Pourquoi ce fichier existe (30/08/2026, MEP v3.20.0)
 *
 * P3 est le contrôle du post-check qui prouve qu'un déploiement a **eu lieu** :
 * il lit la version dans le bundle que le navigateur reçoit vraiment. Il vivait
 * dans un bloc de code de la skill `mep-precheck`, et son ancrage était
 *
 *     "hostachy-front",VAR="x.y.z"
 *
 * — le NOM du paquet suivi de sa version, au motif documenté que « le nom
 * survit à la minification, contrairement aux noms de variables ».
 *
 * 🔴 **Il ne survit plus.** Rollup élague désormais l'import JSON du layout
 * (`import pkg from '../../../package.json'`) : seule la clé lue subsiste, et le
 * bundle porte
 *
 *     const fn="3.20.0",hn={version:fn}
 *
 * P3 a donc rendu `INCONNU` à la MEP du 30/08, et la version a dû être
 * retrouvée à la main. Il a échoué du BON côté — jamais un faux vert, ce que la
 * skill exige — mais un contrôle qui ne mesure plus est un contrôle absent.
 *
 * ## Ce que ce fichier change, et c'est le point
 *
 * Le problème n'est pas l'ancrage : c'est qu'**aucun contrôle ne regardait si
 * l'ancrage marchait encore**. Le premier à l'apprendre était le post-check, en
 * production, une fois la MEP faite — trop tard pour que cela serve.
 *
 * L'extracteur vit donc ici, et **la CI l'exerce à chaque PR** sur le build
 * local : il doit y retrouver, exactement, la version de `package.json`. Le jour
 * où la chaîne d'outils change encore son émission, c'est la CI qui le dit,
 * avant la MEP, et non P3 qui devient muet après.
 *
 * C'est `standards/04` §2 appliqué au contrôle lui-même : *ce qui est critique
 * ne se vérifie pas seulement en MEP*. Et c'est la même règle que #498 énonce
 * pour l'aperçu des e-mails — **la fonction qui vérifie doit être celle qui
 * sert**, sinon les deux dérivent et personne ne le voit.
 *
 * ## Usage
 *
 *     node scripts/check-version-servie.mjs                     # CI : build local
 *     node scripts/check-version-servie.mjs --site https://…    # P3 : production
 *     node scripts/check-version-servie.mjs --client <dossier>  # le client d'une IMAGE publiée
 *
 * `--client` lit le dossier `client` d'un build adapter-node (`/app/build/client`
 * dans l'image du front) : le workflow `images.yml` vérifie ainsi que l'image
 * étiquetée `X.Y.Z` affiche bien X.Y.Z dans son pied de page (#1753).
 *     node scripts/check-version-servie.mjs --selftest
 *
 * Sortie du mode site : la version sur la sortie standard (code 0), ou
 * `INCONNU: <raison>` et **code 2**. Jamais une sortie vide — c'est la règle 1
 * de `mep-precheck` : *on ne déduit pas un vert d'une sortie vide*, et c'est ce
 * défaut-là qui avait rendu la commande d'origine inopérante en silence
 * (03/08/2026).
 */
import { readFileSync, existsSync, readdirSync } from 'node:fs';
import { join } from 'node:path';
import { pathToFileURL } from 'node:url';

const RACINE = new URL('..', import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, '$1');

/**
 * Les guillemets d'une chaîne émise par un bundler : `"`, `'` et l'accent grave.
 *
 * 🔴 Rollup écrivait `"3.20.0"` ; Rolldown (Vite 8) écrit `3.20.0` entre accents
 * graves. Un motif qui ne connaît que `["']` rend INCONNU sur le premier build
 * Vite 8 — le cas du 30/08/2026 une seconde fois, par une autre porte (#2205,
 * 24/10/2026).
 */
const G = '["\'`]';

/**
 * Les formes sous lesquelles la version du paquet peut survivre au bundle.
 *
 * ⚠️ Ancrées sur `{…version:…}`, la STRUCTURE que le code source produit
 * (`import pkg from package.json` → `pkg.version`), et non sur un nom de
 * variable ni sur le nom du paquet — les deux ancrages précédents ont été
 * élagués par la chaîne d'outils, chacun à son tour.
 *
 * Deux écritures de la const hissée : Rollup la déclare seule
 * (`const fn="3.20.0",hn={version:fn}`), Rolldown la range dans UN `var` avec les
 * clés voisines du paquet (`var e=<nom>,t=<version>,n={name:e,version:t,…`).
 */
const FORMES = [
	//  Inlinée : `{version:"3.20.0"}`
	{ nom: 'inlinée', regex: new RegExp(`\\{\\s*version\\s*:\\s*${G}(\\d+\\.\\d+\\.\\d+)${G}`) },
	//  Par une const hissée, déclarée seule ou au milieu d'une liste de déclarations.
	{
		nom: 'const hissée',
		regex: new RegExp(
			`(?:(?:const|let|var)\\s+|,\\s*)(\\w+)\\s*=\\s*${G}(\\d+\\.\\d+\\.\\d+)${G}` +
				`[\\s\\S]{0,80}?\\{[^{}]{0,80}?\\bversion\\s*:\\s*\\1\\s*[,}]`,
		),
		version: (m) => m[2],
	},
];

/**
 * Extrait la version d'un chunk, ou `null`.
 *
 * 🔴 Rend `null` — et non la première chaîne trouvée — si deux formes donnent
 * des versions DIFFÉRENTES : `package.json` peut être élagué en partie et une
 * version de dépendance traîner dans le même chunk. Un contrôle qui tranche au
 * hasard entre deux candidates ment une fois sur deux.
 */
export function versionDansChunk(source) {
	const vues = new Set();
	for (const forme of FORMES) {
		const m = source.match(forme.regex);
		if (m) vues.add(forme.version ? forme.version(m) : m[1]);
	}
	if (vues.size === 1) return [...vues][0];
	return null;
}

/** Les chunks d'un build local, contenu compris. */
function chunksLocaux(client = join(RACINE, '.svelte-kit', 'output', 'client')) {
	const base = join(client, '_app', 'immutable');
	if (!existsSync(base)) return null;
	const sortie = [];
	const parcourir = (d) => {
		for (const nom of readdirSync(d, { withFileTypes: true })) {
			const p = join(d, nom.name);
			if (nom.isDirectory()) parcourir(p);
			else if (nom.name.endsWith('.js'))
				sortie.push({ nom: nom.name, contenu: readFileSync(p, 'utf8') });
		}
	};
	parcourir(base);
	return sortie;
}

/**
 * Un refus HTTP : le site a RÉPONDU, mais pas ce qu'on demandait.
 *
 * 🔴 Distinct de « injoignable » (aucune réponse) et de « pas de build »
 * (une page servie sans point d'entrée). Jusqu'au 25/09/2026 (#1283), `lire()`
 * changeait toute réponse non 2xx en texte vide : une 403 du proxy d'une
 * session cloud s'affichait « le site ne sert pas un build SvelteKit », et
 * envoyait chercher une panne du site qui n'existait pas — le site servait
 * bien 2.49.2. Le code HTTP était le seul renseignement utile, et il se perdait.
 */
export class RefusHttp extends Error {
	constructor(url, statut) {
		super(`${url} a répondu HTTP ${statut}`);
		this.url = url;
		this.statut = statut;
	}
}

/**
 * Les chunks servis par un site, atteints depuis son point d'entrée.
 *
 * `obtenir` est `fetch`, injectable pour l'autotest : c'est la seule façon
 * d'éprouver une 403 ou un chunk en 404 sans dépendre du réseau.
 */
export async function chunksDistants(site, obtenir = fetch) {
	const lire = async (url) => {
		const r = await obtenir(url, { redirect: 'follow' });
		if (!r.ok) throw new RefusHttp(url, r.status);
		return await r.text();
	};
	const racine = await lire(`${site}/`);
	const entree = racine.match(/\/_app\/immutable\/entry\/app\.[A-Za-z0-9_-]+\.js/)?.[0];
	if (!entree) return null;
	const listing = await lire(`${site}${entree}`);
	const refs = [...new Set(listing.match(/(?:nodes|chunks)\/[0-9A-Za-z_.-]+\.js/g) ?? [])];
	const sortie = [];
	for (const ref of refs) {
		sortie.push({ nom: ref, contenu: await lire(`${site}/_app/immutable/${ref}`) });
	}
	return sortie;
}

/** La version portée par un jeu de chunks — la première trouvée, ou `null`. */
export function versionDansChunks(chunks) {
	for (const c of chunks) {
		const v = versionDansChunk(c.contenu);
		if (v) return { version: v, chunk: c.nom };
	}
	return null;
}

//  ── Modes ───────────────────────────────────────────────────────────────────

/**
 * La mesure de P3 : la version servie, ou `INCONNU: <raison>`. PURE à `obtenir`
 * près — c'est elle que l'autotest éprouve, et `modeSite` ne fait que l'afficher.
 */
export async function mesurerSite(site, obtenir = fetch) {
	let chunks;
	try {
		chunks = await chunksDistants(site, obtenir);
	} catch (e) {
		if (e instanceof RefusHttp) return { code: 2, ligne: `INCONNU: ${e.message}` };
		return { code: 2, ligne: `INCONNU: ${site} injoignable (${e.message})` };
	}
	if (chunks === null) {
		return {
			code: 2,
			ligne: "INCONNU: point d'entrée introuvable — le site ne sert pas un build SvelteKit",
		};
	}
	const trouve = versionDansChunks(chunks);
	if (!trouve) {
		return { code: 2, ligne: `INCONNU: version absente des ${chunks.length} chunk(s) servi(s)` };
	}
	return { code: 0, ligne: trouve.version };
}

async function modeSite(site) {
	const { code, ligne } = await mesurerSite(site);
	console.log(ligne);
	return code;
}

function modeCI(client) {
	const attendue = JSON.parse(readFileSync(join(RACINE, 'package.json'), 'utf8')).version;
	const chunks = chunksLocaux(client);

	//  Cas zéro : sans build, ce contrôle ne mesure rien — et le dire est le seul
	//  comportement honnête. Le job `build-frontend` bâtit avant de l'appeler.
	if (chunks === null || chunks.length === 0) {
		console.error(
			`✗ Cas zéro : aucun build dans \`${client ?? '.svelte-kit/output/client'}\` — lancer \`npm run build\` avant.\n` +
				"  Ne pas lire ceci comme un succès : l'extracteur de P3 n'a pas été éprouvé.",
		);
		return 1;
	}

	const trouve = versionDansChunks(chunks);
	if (!trouve) {
		console.error(
			`✗ L'extracteur de P3 ne trouve AUCUNE version dans les ${chunks.length} chunks du build.\n` +
				`  La chaîne d'outils a changé son émission de \`{version:…}\` — mettre à jour FORMES ici.\n` +
				'  🔴 Sans cette correction, P3 rendra INCONNU après la MEP, et plus rien ne prouvera\n' +
				"     qu'un déploiement a eu lieu. C'est exactement le cas du 30/08/2026.",
		);
		return 1;
	}
	if (trouve.version !== attendue) {
		console.error(
			`✗ L'extracteur lit ${trouve.version} (dans ${trouve.chunk}) là où package.json dit ${attendue}.\n` +
				"  Il capture autre chose que la version du paquet — la version d'une dépendance, sans doute.",
		);
		return 1;
	}
	console.log(
		`✓ Version servie : l'extracteur de P3 retrouve ${trouve.version} dans ${trouve.chunk} ` +
			`(${chunks.length} chunk(s) analysés) — il mesurera en production.`,
	);
	return 0;
}

async function selftest() {
	let ko = 0;
	const t = (libelle, source, attendu) => {
		const obtenu = versionDansChunk(source);
		if (obtenu === attendu) console.log(`PASS  ${libelle}`);
		else {
			console.log(
				`FAIL  ${libelle} — obtenu ${JSON.stringify(obtenu)}, attendu ${JSON.stringify(attendu)}`,
			);
			ko = 1;
		}
	};

	t('forme inlinée', 'var x={version:"3.20.0"};', '3.20.0');
	//  🔴 La forme réelle du 30/08/2026, celle qui a fait rendre INCONNU.
	t('const hissée', 'const fn="3.20.0",hn={version:fn};var gn=1;', '3.20.0');
	t('guillemets simples', "const a='1.2.3',b={version:a};", '1.2.3');
	//  🔴 Les formes de Rolldown (Vite 8) : accents graves, et la const rangée dans
	//  un seul `var` avec le nom du paquet — celle que `lint:version-servie` a
	//  refusée au premier essai de la montée (24/10/2026).
	t('accents graves, inlinée', 'var x={version:`3.20.0`};', '3.20.0');
	t(
		'accents graves, const au milieu d’un var (Rolldown)',
		'var e=`hostachy-front`,t=`3.13.9`,n={name:e,version:t,private:!0};',
		'3.13.9',
	);
	t('accents graves, const hissée', 'const fn=`3.20.0`,hn={version:fn};', '3.20.0');
	t('un var d’une autre chose, sans {version:} → null', 'var e=`x`,t=`3.13.9`,n={name:e};', null);

	//  ⚠️ Un `{version:…}` qui ne se rapporte pas à la const trouvée ne compte
	//  pas : sans le renvoi arrière, n'importe quelle chaîne du chunk passerait.
	t('const sans renvoi vers {version:}', 'const fn="3.20.0";var hn={autre:fn};', null);
	t('aucune version', 'const a=1;var b={};', null);

	//  🔴 Le cas qui protège du pire : deux formes en désaccord. Rendre l'une des
	//  deux au hasard, c'est mentir une fois sur deux — mieux vaut ne rien rendre,
	//  P3 dira INCONNU et quelqu'un regardera.
	t('deux formes en désaccord', 'const fn="3.20.0",hn={version:fn};var z={version:"9.9.9"};', null);

	//  ── Le mode site : chaque cause d'INCONNU dit la sienne (#1283) ──────────
	//  Un faux site, servi par un `fetch` simulé : aucune requête réseau.
	const SITE = 'https://exemple.test';
	const ENTREE = '/_app/immutable/entry/app.Abc123.js';
	const faux = (pages) => async (url) => {
		const p = pages[url];
		if (p instanceof Error) throw p;
		if (p === undefined) return { ok: false, status: 404, text: async () => '' };
		const [statut, corps] = typeof p === 'string' ? [200, p] : p;
		return { ok: statut >= 200 && statut < 300, status: statut, text: async () => corps };
	};
	const m = async (libelle, pages, attendu) => {
		const { ligne } = await mesurerSite(SITE, faux(pages));
		if (ligne === attendu) console.log(`PASS  ${libelle}`);
		else {
			console.log(`FAIL  ${libelle} — obtenu « ${ligne} », attendu « ${attendu} »`);
			ko = 1;
		}
	};
	const sain = {
		[`${SITE}/`]: `<script src="${ENTREE}"></script>`,
		[`${SITE}${ENTREE}`]: 'import("./nodes/0.Xyz.js")',
		[`${SITE}/_app/immutable/nodes/0.Xyz.js`]: 'const fn="2.49.2",hn={version:fn};',
	};
	await m('site sain → la version', sain, '2.49.2');
	await m(
		'site sain en accents graves (Rolldown) → la version',
		{
			...sain,
			[`${SITE}/_app/immutable/nodes/0.Xyz.js`]:
				'var e=`hostachy-front`,t=`2.49.2`,n={name:e,version:t};',
		},
		'2.49.2',
	);
	//  Cas zéro : des chunks sans aucune version rendent INCONNU, jamais un vert.
	await m(
		'chunks sans version → INCONNU nommé',
		{ ...sain, [`${SITE}/_app/immutable/nodes/0.Xyz.js`]: 'const a=1;' },
		'INCONNU: version absente des 1 chunk(s) servi(s)',
	);
	//  🔴 Le cas du 25/09/2026 : le proxy d'une session cloud refuse le domaine.
	//  Avant #1283 : « le site ne sert pas un build SvelteKit ».
	await m(
		'racine en 403 → le refus est nommé, pas le build',
		{ [`${SITE}/`]: [403, 'Forbidden'] },
		`INCONNU: ${SITE}/ a répondu HTTP 403`,
	);
	await m(
		'chunk en 404 → le refus est nommé, pas une absence de version',
		{ ...sain, [`${SITE}/_app/immutable/nodes/0.Xyz.js`]: [404, ''] },
		`INCONNU: ${SITE}/_app/immutable/nodes/0.Xyz.js a répondu HTTP 404`,
	);
	await m(
		'racine servie sans point d’entrée → le message du build manquant',
		{ [`${SITE}/`]: '<html>maintenance</html>' },
		"INCONNU: point d'entrée introuvable — le site ne sert pas un build SvelteKit",
	);
	await m(
		'aucune réponse → injoignable',
		{ [`${SITE}/`]: new Error('ECONNREFUSED') },
		`INCONNU: ${SITE} injoignable (ECONNREFUSED)`,
	);

	//  Le cas zéro du mode CI : sans build, il refuse au lieu de conclure au vert.
	//  Éprouvé ici parce que c'est la propriété qui rend ce contrôle utile.
	console.log(
		ko === 0
			? '\n✓ Autotest : les deux formes de bundle sont lues, les cas ambigus rendent null, ' +
					'et chaque cause d’INCONNU du mode site dit la sienne.'
			: '\n✗ Autotest en échec',
	);
	return ko;
}

const _lance = process.argv[1] ? pathToFileURL(process.argv[1]).href : '';
if (import.meta.url === _lance) {
	const args = process.argv.slice(2);
	const iSite = args.indexOf('--site');
	const iClient = args.indexOf('--client');
	if (args.includes('--selftest')) process.exit(await selftest());
	else if (iSite !== -1) process.exit(await modeSite(args[iSite + 1]?.replace(/\/$/, '') ?? ''));
	else process.exit(modeCI(iClient !== -1 ? args[iClient + 1] : undefined));
}
