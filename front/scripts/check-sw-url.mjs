#!/usr/bin/env node
/**
 * Garde-fou : le service worker doit s'enregistrer depuis une URL ABSOLUE.
 *
 * Le 26/07/2026 (v2.24.0), `vite-plugin-pwa` a hérité du `base` de Vite — vide sous
 * SvelteKit — et a généré `new Workbox('./sw.js', { scope: './' })`. Un chemin
 * relatif est résolu par rapport à la page courante : depuis `/auth/connexion`, le
 * navigateur demandait `/auth/sw.js`, recevait un 404 et abandonnait. Résultat en
 * production : PLUS AUCUN service worker enregistré sur les routes autres que la
 * racine — ni cache hors ligne, ni bandeau de mise à jour — sans la moindre trace,
 * l'erreur n'étant remontée qu'à un `onRegisterError` qu'on ne branchait pas.
 *
 * Ce contrôle porte sur le BUNDLE CONSTRUIT et non sur `vite.config.ts` : c'est
 * l'artefact livré qui compte, et la valeur fautive venait justement d'un défaut du
 * plugin, pas d'une ligne écrite à la main. Une option renommée, un changement de
 * défaut ou une régression amont seraient tous attrapés ici.
 *
 * Les points 1 à 6 du post-check MEP étaient au vert ce jour-là ; seule la
 * vérification du comportement réel (P7) a levé le lièvre. Ce script en automatise
 * la partie mécanique.
 *
 * Script Node sans dépendance, comme `check-dates.mjs`.
 *
 * ## Les trois guillemets (24/10/2026, #2205)
 *
 * Rollup écrivait les chaînes entre guillemets doubles ; Rolldown (Vite 8) les
 * écrit en GABARITS à accents graves : `new e(`/sw.js`,{scope:`/`})`. Un motif
 * qui ne connaît que `["']` conclut alors « l'enregistrement a disparu » (faux
 * négatif : il est là, en URL absolue) — c'est ce qui a fait croire, en
 * août, que Vite 8 perdait le service worker. Pire, le même aveuglement
 * laisserait passer un enregistrement RELATIF écrit en accents graves. Tous les
 * motifs de ce fichier admettent donc les trois guillemets, et `--selftest`
 * éprouve chaque forme (absolue OK, relative refusée, rien trouvé refusé).
 *
 * Ce que ce contrôle ne prouve PAS : que le navigateur enregistre bien le service
 * worker. Cela se mesure par un test de comportement (`e2e-build/`, étape CI
 * « Service worker enregistré »).
 *
 * Usage : npm run build && npm run lint:sw   (exit 1 si violation)
 *         node scripts/check-sw-url.mjs --selftest
 */
import { readFileSync, readdirSync, statSync, existsSync } from 'node:fs';
import { dirname, join, relative } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const RACINE = join(dirname(fileURLToPath(import.meta.url)), '..');
const CLIENT = join(RACINE, 'build', 'client');

//  Les trois guillemets d'une chaîne émise par un bundler : `"`, `'` et l'accent
//  grave de Rolldown. Écrits ICI, une fois : un motif qui recopierait `["']`
//  referait l'aveuglement du 24/10/2026.
const G = '["\'`]';

/** `new Workbox('./sw.js'…)`, `register('sw.js'…)`, `scope: './'` — tout ce qui est relatif. */
const MOTIFS_RELATIFS = [
	new RegExp(`new\\s+\\w+\\(\\s*${G}\\./sw\\.js${G}`),
	new RegExp(`new\\s+\\w+\\(\\s*${G}sw\\.js${G}`),
	new RegExp(`serviceWorker\\.register\\(\\s*${G}\\.?/?sw\\.js${G}`),
	new RegExp(`scope\\s*:\\s*${G}\\./${G}`),
];

/** L'URL ABSOLUE du service worker, sous n'importe lequel des trois guillemets. */
const MOTIF_ABSOLU = new RegExp(`${G}/sw\\.js${G}`);

function collecter(dir, acc = []) {
	for (const e of readdirSync(dir)) {
		const p = join(dir, e);
		if (statSync(p).isDirectory()) collecter(p, acc);
		else if (e.endsWith('.js')) acc.push(p);
	}
	return acc;
}

/**
 * Le bundle CLIENT : où le service worker est-il enregistré, et sous quelle forme ?
 * PURE — `fichiers` est `[{ nom, contenu }]` —, c'est ce que l'autotest éprouve.
 */
export function analyserClient(fichiers) {
	const fautifs = [];
	let absoluTrouve = false;
	for (const { nom, contenu } of fichiers) {
		if (!contenu.includes('sw.js')) continue;
		if (MOTIF_ABSOLU.test(contenu)) absoluTrouve = true;
		for (const motif of MOTIFS_RELATIFS) {
			const m = contenu.match(motif);
			if (m) fautifs.push(`  ${nom}\n      ${m[0]}`);
		}
	}
	return { fautifs, absoluTrouve };
}

const echapper = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

/**
 * Le service worker CONSTRUIT : les erreurs qu'il porte, dans l'ordre où elles
 * se lisent — chacune est `{ message }`, la première arrête le contrôle.
 * PURE, comme `analyserClient`.
 */
export function analyserSw(sw, nomSw = 'sw.js') {
	// ── Repli de navigation vers un fichier qui n'existe pas ──────────────────
	//
	// `vite-plugin-pwa` suppose une SPA et pose par défaut `navigateFallback:
	// 'index.html'` : le service worker répond alors à CHAQUE navigation en servant
	// cet `index.html` depuis son precache. SvelteKit en `adapter-node` rend les
	// pages côté serveur et n'en produit aucun — workbox lève donc
	// `non-precached-url :: [{"url":"index.html"}]`, la navigation cliente échoue et
	// l'hydratation ne se termine pas.
	//
	// Constaté en production le 14/08/2026, signalé par l'utilisateur : sur /profil
	// rechargée directement, prénom, nom et e-mail restaient VIDES — et « Enregistrer »
	// aurait écrasé les vraies valeurs par du vide. Le défaut est intermittent (il
	// dépend de l'état du cache et du chemin d'arrivée), ce qui explique qu'il ait
	// traversé tous les post-checks : ils regardaient la racine, où le repli tombe
	// juste. Il n'a été trouvé que par la console du navigateur, sur la page fautive.
	//
	// Le contrôle porte, comme celui du dessus, sur l'ARTEFACT construit : la valeur
	// fautive vient d'un défaut du plugin, pas d'une ligne écrite à la main.
	const repli = sw.match(new RegExp(`createHandlerBoundToURL\\(\\s*${G}([^"'\`]+)${G}\\s*\\)`));
	if (repli) {
		const cible = echapper(repli[1]);
		//  Le repli n'est acceptable que si sa cible est RÉELLEMENT précachée.
		const precachee =
			new RegExp(`${G}url${G}\\s*:\\s*${G}${cible}${G}`).test(sw) ||
			new RegExp(`${G}${cible}${G}\\s*,\\s*${G}revision${G}`).test(sw) ||
			//  Rolldown/terser écrivent la clé sans guillemets : `{url:"index.html"}`.
			new RegExp(`\\burl\\s*:\\s*${G}${cible}${G}`).test(sw);
		if (!precachee) {
			return {
				message:
					`\n✗ Le service worker replie les navigations sur « ${repli[1]} », qui n'est PAS` +
					`\n  dans son precache. Workbox lèvera \`non-precached-url\` à chaque` +
					`\n  navigation : la page se charge, l'hydratation échoue, et les formulaires` +
					`\n  restent vides sans le moindre message côté serveur.` +
					`\n\n  SvelteKit rend les pages côté serveur : poser \`navigateFallback: null\`` +
					`\n  dans les options \`workbox\` de VitePWA (front/vite.config.ts).\n`,
			};
		}
	}

	// ── Mise en cache d'une réponse d'API authentifiée ────────────────────────
	//
	// Le service worker servait `/api/lots` et `/api/publications` en
	// `StaleWhileRevalidate` pendant une heure. Les deux exigent `get_current_user`
	// et leur contenu est filtré par utilisateur et par périmètre : ce cache
	// contenait donc des réponses authentifiées et personnalisées.
	//
	// `StaleWhileRevalidate` rend le cache D'ABORD et revalide après, en arrière-plan.
	// Une session expirée continuait d'afficher du contenu applicatif complet, et
	// c'est la revalidation — après le rendu — qui prenait le 401 : l'écran affirmait
	// une session qui n'existait plus (#379, signalé le 16/08/2026). Rien ne purgeait
	// ce cache à la déconnexion ni à l'expiration, si bien que le piège se réarmait
	// tout seul à chaque fois.
	//
	// Le contrôle porte sur le SW CONSTRUIT et non sur `vite.config.ts` : c'est
	// l'artefact livré qui compte, et `runtimeCaching` peut revenir d'un défaut de
	// plugin ou d'un changement de défaut amont autant que d'une ligne écrite à la
	// main — exactement comme le repli de navigation ci-dessus.
	//
	// Ce qui reste légitime : le precache des ressources STATIQUES (js, css, icônes,
	// polices), qui ne porte aucune donnée d'utilisateur.
	const MOTIFS_CACHE_API = [
		{ motif: new RegExp(`${G}api-cache${G}`), quoi: `le cache nommé « api-cache »` },
		{ motif: /\\?\/api\\?\/[a-z]/i, quoi: `une route /api/ référencée par le service worker` },
	];
	const cacheApi = MOTIFS_CACHE_API.map(({ motif, quoi }) => {
		const m = sw.match(motif);
		return m ? `  ${quoi}\n      ${m[0]}` : null;
	}).filter(Boolean);
	if (cacheApi.length > 0) {
		return {
			message:
				`\n✗ Le service worker met en cache des réponses d'API :\n\n` +
				cacheApi.join('\n') +
				`\n\n  /api/lots et /api/publications exigent une session et sont filtrés par` +
				`\n  utilisateur : les mettre en cache fait afficher du contenu applicatif à` +
				`\n  une session expirée, la revalidation ne prenant le 401 qu'APRÈS le rendu.` +
				`\n  Rien ne purge ce cache à la déconnexion — le piège se réarme seul.` +
				`\n\n  Retirer l'entrée \`runtimeCaching\` des options \`workbox\` de VitePWA` +
				`\n  (front/vite.config.ts). Le precache des ressources statiques n'est pas` +
				`\n  concerné.\n`,
		};
	}

	// ── Un document HTML dans le precache ─────────────────────────────────────
	//
	// Le precache sert ses entrées D'ABORD, sans consulter le serveur, jusqu'à ce
	// qu'un nouveau service worker soit ACTIVÉ. Le manuel (`static/manuel-
	// utilisateur.html`) y figurait : le 09/10/2026, un navigateur dont le service
	// worker n'avait pas été remplacé affichait le manuel v2.38 quand le serveur
	// servait la v2.58, même par un `fetch(…, { cache: 'no-store' })`. Caddy le sert
	// en `no-cache` précisément pour qu'il ne soit jamais périmé.
	//
	// Un document se lit à jour ; seules les ressources STATIQUES versionnées (js,
	// css, icônes, polices) se précachent. Cas zéro : un precache sans aucune entrée
	// lue ne prouverait rien — le motif aurait cessé de lire le fichier.
	const entrees = [...sw.matchAll(new RegExp(`url\\s*:\\s*${G}([^"'\`]+)${G}`, 'g'))].map(
		(m) => m[1],
	);
	if (entrees.length === 0) {
		return {
			message:
				`\n✗ Aucune entrée lue dans le precache de ${nomSw} : le motif ne lit` +
				`\n  plus le fichier. Un contrôle qui ne mesure rien renvoie INCONNU, jamais OK.\n`,
		};
	}
	const documents = entrees.filter((u) => /\.html?$/i.test(u));
	if (documents.length > 0) {
		return {
			message:
				`\n✗ Le precache du service worker contient ${documents.length} document(s) HTML :\n\n` +
				documents.map((u) => `  ${u}`).join('\n') +
				`\n\n  Le precache les sert sans consulter le serveur : un service worker non` +
				`\n  remplacé fait lire une version périmée (manuel v2.38 servi pour v2.58).` +
				`\n  Retirer \`html\` de \`globPatterns\` (front/vite.config.ts).\n`,
		};
	}
	return { entrees: entrees.length };
}

function autotest() {
	let ko = 0;
	const t = (libelle, obtenu, attendu) => {
		const ok = JSON.stringify(obtenu) === JSON.stringify(attendu);
		console.log(
			`${ok ? 'PASS' : 'FAIL'}  ${libelle}${ok ? '' : ` — obtenu ${JSON.stringify(obtenu)}`}`,
		);
		if (!ok) ko = 1;
	};
	const client = (contenu) => {
		const { fautifs, absoluTrouve } = analyserClient([{ nom: 'a.js', contenu }]);
		return { fautifs: fautifs.length, absoluTrouve };
	};

	//  ── Le bundle client : l'enregistrement, sous les trois guillemets ───────
	t('absolu, guillemets doubles', client('new Workbox("/sw.js",{scope:"/"})'), {
		fautifs: 0,
		absoluTrouve: true,
	});
	t('absolu, guillemets simples', client("new Workbox('/sw.js',{scope:'/'})"), {
		fautifs: 0,
		absoluTrouve: true,
	});
	//  🔴 La forme réelle de Rolldown (Vite 8) : celle que l'ancien motif ne voyait pas.
	t('absolu, accents graves (Rolldown)', client('new e(`/sw.js`,{scope:`/`,type:`classic`})'), {
		fautifs: 0,
		absoluTrouve: true,
	});
	//  🔴 L'envers : le défaut du 26/07/2026 écrit en accents graves ne doit pas passer.
	t(
		'relatif `./sw.js`, accents graves → refusé',
		client('new e(`./sw.js`,{scope:`./`})').fautifs,
		2,
	);
	t('relatif `sw.js` nu, accents graves → refusé', client('new e(`sw.js`,{scope:`/`})').fautifs, 1);
	t(
		'relatif, guillemets doubles → refusé',
		client('new Workbox("./sw.js",{scope:"./"})').fautifs,
		2,
	);
	t(
		'register relatif, accents graves → refusé',
		client('navigator.serviceWorker.register(`sw.js`)').fautifs,
		1,
	);
	//  Cas zéro : un bundle sans aucune référence n'est PAS un succès.
	t('aucune référence → absoluTrouve faux', client('const a=1;'), {
		fautifs: 0,
		absoluTrouve: false,
	});
	t('`/sw.js` dans un commentaire sans guillemets → non trouvé', client('// voir /sw.js ici'), {
		fautifs: 0,
		absoluTrouve: false,
	});

	//  ── Le service worker construit ────────────────────────────────────────
	const ok = (sw) => analyserSw(sw).message === undefined;
	const PRE = 'precacheAndRoute([{url:"a.js",revision:null},{url:"b.css",revision:null}]);';
	t('precache lu, rien de fautif', ok(PRE), true);
	t(
		'precache en accents graves lu aussi',
		ok('precacheAndRoute([{url:`a.js`,revision:null}]);'),
		true,
	);
	t('aucune entrée lue → refus (cas zéro)', ok('const a=1;'), false);
	t(
		'document HTML précaché → refus',
		ok('precacheAndRoute([{url:"manuel-utilisateur.html"}]);'),
		false,
	);
	t(
		'document HTML précaché, accents graves → refus',
		ok('precacheAndRoute([{url:`manuel-utilisateur.html`}]);'),
		false,
	);
	t(
		'repli sur une cible non précachée → refus',
		ok(`${PRE}createHandlerBoundToURL("index.html");`),
		false,
	);
	t(
		'repli sur une cible non précachée, accents graves → refus',
		ok(`${PRE}createHandlerBoundToURL(\`index.html\`);`),
		false,
	);
	t('repli sur une cible précachée → admis', ok(`${PRE}createHandlerBoundToURL("a.js");`), true);
	t('cache d’API nommé → refus', ok(`${PRE}new X({cacheName:"api-cache"});`), false);
	t(
		'cache d’API nommé, accents graves → refus',
		ok(`${PRE}new X({cacheName:\`api-cache\`});`),
		false,
	);
	t('route /api/ référencée → refus', ok(`${PRE}registerRoute(/\\/api\\/lots/);`), false);

	console.log(ko === 0 ? '\n✓ Autotest : les trois guillemets sont lus.' : '\n✗ Autotest en échec');
	return ko;
}

function mesurer() {
	if (!existsSync(CLIENT)) {
		console.error(
			`\n✗ ${relative(RACINE, CLIENT)} est introuvable — lancer \`npm run build\` avant ce contrôle.` +
				`\n  Un contrôle qui ne peut pas s'exécuter renvoie INCONNU, jamais OK.\n`,
		);
		return 1;
	}

	const chemins = collecter(CLIENT);
	const fichiers = chemins.map((p) => ({
		nom: relative(RACINE, p).replace(/\\/g, '/'),
		contenu: readFileSync(p, 'utf-8'),
	}));
	const { fautifs, absoluTrouve } = analyserClient(fichiers);

	if (fautifs.length > 0) {
		console.error(
			`\n✗ ${fautifs.length} enregistrement(s) de service worker en chemin relatif :\n\n` +
				fautifs.join('\n') +
				`\n\n  Un chemin relatif est résolu depuis la page courante : l'enregistrement` +
				`\n  échoue en 404 sur toute route imbriquée (/auth/sw.js, /tickets/sw.js…).` +
				`\n  Corriger via les options \`base: '/'\` et \`scope: '/'\` de VitePWA.\n`,
		);
		return 1;
	}

	if (!absoluTrouve) {
		console.error(
			`\n✗ Aucune référence à '/sw.js' dans le bundle : l'enregistrement du service` +
				`\n  worker a disparu du build. Sans lui, ni cache hors ligne ni bandeau de` +
				`\n  mise à jour — et rien ne le signalerait à l'exécution.\n`,
		);
		return 1;
	}

	const SW = join(CLIENT, 'sw.js');
	if (!existsSync(SW)) {
		console.error(
			`\n✗ ${relative(RACINE, SW)} est introuvable — le service worker n'a pas été généré.` +
				`\n  Un contrôle qui ne peut pas s'exécuter renvoie INCONNU, jamais OK.\n`,
		);
		return 1;
	}

	const resultat = analyserSw(readFileSync(SW, 'utf-8'), relative(RACINE, SW));
	if (resultat.message) {
		console.error(resultat.message);
		return 1;
	}

	console.log(
		`✓ ${fichiers.length} fichiers du bundle analysés — service worker en URL absolue, ` +
			`sans repli de navigation orphelin, sans cache de réponse d'API, ` +
			`${resultat.entrees} entrées précachées dont aucun document HTML.`,
	);
	return 0;
}

const _lance = process.argv[1] ? pathToFileURL(process.argv[1]).href : '';
if (import.meta.url === _lance) {
	process.exit(process.argv.includes('--selftest') ? autotest() : mesurer());
}
