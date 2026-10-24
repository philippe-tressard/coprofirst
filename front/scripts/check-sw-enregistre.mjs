#!/usr/bin/env node
/**
 *  Le service worker est-il ENREGISTRÉ par le navigateur ? — le comportement,
 *  pas la chaîne.
 *
 *  ## Pourquoi (#2205, 24/10/2026)
 *
 *  `lint:sw` lit le BUNDLE : il y cherche `/sw.js` en URL absolue. C'est une
 *  mesure de forme, et elle s'est trompée deux fois en sens inverse :
 *
 *   - 26/07/2026 : un chemin relatif (`./sw.js`) — le bundle disait vrai, mais
 *     seul le navigateur, sur une route imbriquée, a vu le 404 ;
 *   - 24/10/2026 : Rolldown (Vite 8) écrit la chaîne entre accents graves, le
 *     motif ne connaissait que les guillemets, et `lint:sw` a conclu à la
 *     disparition d'un enregistrement qui était là — un faux négatif qui a
 *     bloqué la montée de Vite pendant près de trois mois.
 *
 *  Un contrôle qui lit la forme d'un artefact se casse à chaque changement de
 *  l'outil qui l'émet. Celui-ci lance l'application CONSTRUITE (`node build`,
 *  l'adaptateur de la production), l'ouvre dans Chromium sur une route
 *  IMBRIQUÉE, et exige que `navigator.serviceWorker.getRegistration('/')` rende
 *  un service worker ACTIVÉ, de portée `/`, servi depuis `/sw.js`.
 *
 *  ## Cas zéro
 *
 *  Une mesure qui ne sait pas dire non ne prouve rien (standards/04 §2). Dans le
 *  même passage, un second contexte bloque les service workers
 *  (`serviceWorkers: 'block'`) : l'enregistrement y est absent, et le verdict
 *  DOIT être un refus. Si ce contrôle-là rend « enregistré », c'est la mesure qui
 *  est cassée.
 *
 *  ## Ce que ce script respecte des e2e du projet
 *
 *  Son serveur est le sien, sur un port demandé au système (#2051), en
 *  `127.0.0.1` (#1732), jamais emprunté (#1150). Aucune API n'est requise : la
 *  page de connexion se rend sans elle.
 *
 *  Lancer APRÈS `npm run build` :
 *      node scripts/check-sw-enregistre.mjs [--selftest]
 */
import { execFileSync, spawn } from 'node:child_process';
import { existsSync } from 'node:fs';
import { fileURLToPath, pathToFileURL } from 'node:url';

const RACINE = fileURLToPath(new URL('..', import.meta.url));
const ROUTE = '/auth/connexion';
const DELAI_SERVEUR_MS = 30_000;
const DELAI_ENREGISTREMENT_MS = 30_000;

/**
 *  Le verdict, PUR : `info` est ce que le navigateur rend de
 *  `getRegistration('/')`, ou `null` s'il n'y a rien. Rend la liste des
 *  défauts — vide, c'est que le service worker est bien en place.
 */
export function defauts(info, base) {
	if (!info) return ["aucun service worker n'est enregistré pour « / »"];
	const fautes = [];
	if (info.scope !== `${base}/`) fautes.push(`portée « ${info.scope} » au lieu de « ${base}/ »`);
	if (info.script !== `${base}/sw.js`) {
		fautes.push(`script « ${info.script} » au lieu de « ${base}/sw.js »`);
	}
	if (info.etat !== 'activated') fautes.push(`état « ${info.etat} » au lieu de « activated »`);
	return fautes;
}

function portLibre() {
	const sonde =
		"const s = require('node:net').createServer();" +
		"s.listen(0, '127.0.0.1', () => { process.stdout.write(String(s.address().port)); s.close(); });";
	const port = Number(execFileSync(process.execPath, ['-e', sonde], { encoding: 'utf8' }).trim());
	if (!Number.isInteger(port) || port <= 0) throw new Error(`Port illisible : « ${port} ».`);
	return port;
}

async function attendreServeur(base, serveur) {
	const fin = Date.now() + DELAI_SERVEUR_MS;
	while (Date.now() < fin) {
		if (serveur.exitCode !== null)
			throw new Error(`le serveur s'est arrêté (code ${serveur.exitCode})`);
		try {
			const r = await fetch(`${base}${ROUTE}`);
			if (r.ok) return;
		} catch {
			/* pas encore à l'écoute */
		}
		await new Promise((resolve) => setTimeout(resolve, 250));
	}
	throw new Error(
		`le serveur ne répond pas sur ${base}${ROUTE} après ${DELAI_SERVEUR_MS / 1000} s`,
	);
}

/** Ce que le navigateur sait du service worker de « / » — `null` s'il n'y en a pas. */
const LIRE_ENREGISTREMENT = async () => {
	const r = await navigator.serviceWorker.getRegistration('/');
	if (!r) return null;
	const actif = r.active;
	return { scope: r.scope, script: actif?.scriptURL ?? null, etat: actif?.state ?? null };
};

async function enregistrement(page, base) {
	await page.goto(`${base}${ROUTE}`);
	//  Le layout enregistre APRÈS l'ouverture (`apresOuverture`) : on attend, sans
	//  dormir à l'aveugle, que le service worker soit activé — ou que le délai passe.
	const fin = Date.now() + DELAI_ENREGISTREMENT_MS;
	let info = null;
	while (Date.now() < fin) {
		info = await page.evaluate(LIRE_ENREGISTREMENT);
		if (info?.etat === 'activated') return info;
		await page.waitForTimeout(250);
	}
	return info;
}

async function mesurer() {
	if (!existsSync(`${RACINE}build/index.js`)) {
		console.error(
			`\n✗ build/index.js est introuvable — lancer \`npm run build\` avant ce contrôle.` +
				`\n  Un contrôle qui ne peut pas s'exécuter renvoie INCONNU, jamais OK.\n`,
		);
		return 1;
	}
	let chromium;
	try {
		({ chromium } = await import('@playwright/test'));
	} catch (e) {
		console.error(`\n✗ INCONNU : Playwright est introuvable (${e.message}).\n`);
		return 1;
	}

	const port = portLibre();
	const base = `http://127.0.0.1:${port}`;
	const serveur = spawn(process.execPath, ['build'], {
		cwd: RACINE,
		env: { ...process.env, HOST: '127.0.0.1', PORT: String(port), NODE_ENV: 'production' },
		stdio: ['ignore', 'pipe', 'pipe'],
	});
	let journal = '';
	for (const flux of [serveur.stdout, serveur.stderr]) flux.on('data', (d) => (journal += d));

	let navigateur;
	try {
		await attendreServeur(base, serveur);
		try {
			navigateur = await chromium.launch();
		} catch (e) {
			console.error(
				`\n✗ INCONNU : Chromium ne se lance pas (${e.message.split('\n')[0]}).` +
					`\n  \`npx playwright install chromium\`, puis relancer.\n`,
			);
			return 1;
		}

		//  1. Le vrai passage : le service worker doit être en place.
		const contexte = await navigateur.newContext();
		const page = await contexte.newPage();
		const info = await enregistrement(page, base);
		const fautes = defauts(info, base);

		//  2. Le cas zéro : service workers BLOQUÉS — la mesure doit dire non.
		const bloque = await navigateur.newContext({ serviceWorkers: 'block' });
		const pageBloquee = await bloque.newPage();
		await pageBloquee.goto(`${base}${ROUTE}`);
		await pageBloquee.waitForTimeout(2000);
		const infoBloquee = await pageBloquee.evaluate(LIRE_ENREGISTREMENT).catch(() => null);
		if (defauts(infoBloquee, base).length === 0) {
			console.error(
				`\n✗ Cas zéro en échec : service workers bloqués, et la mesure rend « enregistré ».` +
					`\n  Un contrôle qui ne sait pas dire non ne prouve rien.\n`,
			);
			return 1;
		}

		if (fautes.length > 0) {
			console.error(
				`\n✗ Le service worker de l'application construite n'est pas en place sur ${ROUTE} :\n\n` +
					fautes.map((f) => `  - ${f}`).join('\n') +
					`\n\n  Sans lui, ni cache hors ligne ni bandeau de mise à jour — et rien ne le signalerait` +
					`\n  à l'exécution. \`npm run lint:sw\` lit le bundle ; ceci lit le navigateur.\n`,
			);
			return 1;
		}
		console.log(
			`✓ Service worker enregistré par Chromium sur ${ROUTE} : portée /, ${info.script.replace(base, '')}, ` +
				`${info.etat} — et refusé quand les service workers sont bloqués (cas zéro).`,
		);
		return 0;
	} catch (e) {
		console.error(
			`\n✗ INCONNU : ${e.message}\n\n--- journal du serveur ---\n${journal.slice(-1500)}\n`,
		);
		return 1;
	} finally {
		await navigateur?.close().catch(() => {});
		serveur.kill();
	}
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
	const B = 'http://127.0.0.1:4000';
	const bon = { scope: `${B}/`, script: `${B}/sw.js`, etat: 'activated' };
	t('en place : aucun défaut', defauts(bon, B), []);
	t('rien d’enregistré : refus', defauts(null, B).length, 1);
	t(
		'relatif, depuis la route imbriquée (26/07/2026) : refus',
		defauts({ ...bon, script: `${B}/auth/sw.js` }, B).length,
		1,
	);
	t(
		'portée de la route et non de la racine : refus',
		defauts({ ...bon, scope: `${B}/auth/` }, B).length,
		1,
	);
	t('en attente, jamais activé : refus', defauts({ ...bon, etat: 'installing' }, B).length, 1);
	t('pas de worker actif : refus', defauts({ ...bon, script: null, etat: null }, B).length, 2);
	t('un port libre est un entier', Number.isInteger(portLibre()), true);
	console.log(
		ko === 0 ? '\n✓ Autotest : le verdict nomme chaque défaut.' : '\n✗ Autotest en échec',
	);
	return ko;
}

const _lance = process.argv[1] ? pathToFileURL(process.argv[1]).href : '';
if (import.meta.url === _lance) {
	process.exit(process.argv.includes('--selftest') ? autotest() : await mesurer());
}
