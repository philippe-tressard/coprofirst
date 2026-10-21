#!/usr/bin/env node
/**
 *  Les tests de navigateur lancent LEUR serveur, et ne l'empruntent jamais (#1150).
 *
 *  ## Pourquoi ce contrôle
 *
 *  `playwright.config.ts` portait le port de `npm run dev` (5173) et
 *  `reuseExistingServer: true`. Un rejeu qui trouvait un serveur sur ce port
 *  s'y branchait sans un mot — celui du poste, ou celui d'une autre session,
 *  dans un autre worktree. Mesuré le 25/09/2026 :
 *
 *   - quand ce serveur s'arrêtait, les tests tombaient en
 *     `ERR_CONNECTION_REFUSED`, un différent à chaque fois — l'intermittence
 *     du ticket, prise pendant trois jours pour une affaire de charge ;
 *   - et tant qu'il tournait, les tests lisaient le code de QUI L'AVAIT LANCÉ :
 *     `rejouer-ci.sh` pouvait dire vert sur un autre arbre que le sien.
 *
 *  Remettre `true` accélère un lancement local de deux secondes. C'est
 *  précisément le geste qu'on fait sans y penser — d'où ce contrôle.
 *
 *  ## Ce qu'il refuse, dans la config (commentaires neutralisés)
 *
 *   1. `reuseExistingServer` autre que `false` ;
 *   2. une commande de serveur sans `--strictPort` — Vite se replierait en
 *      silence sur un port voisin, pendant que Playwright interroge le premier ;
 *   3. le port de développement écrit en dur ;
 *   4. `localhost`, et un serveur sans `--host 127.0.0.1` (#1732, 08/10/2026).
 *      Vite écoutait sur `localhost` résolu en `::1` SEUL, et les tests
 *      visaient `localhost`, que le navigateur tente aussi en `127.0.0.1` :
 *      des connexions refusées par intermittence — `ERR_CONNECTION_REFUSED`
 *      au `goto`, ou « Failed to fetch dynamically imported module …/app.js »
 *      —, un spec DIFFÉRENT à chaque passage, une suite complète sur deux sur
 *      le poste. Une adresse, explicite, la même des deux côtés : six suites
 *      complètes de suite au vert.
 *   5. un port DÉDUIT (du pid, d'une plage) au lieu d'un port demandé au
 *      système (#2051, 17/10/2026). `5300 + pid % 600` couvrait 5432, le port
 *      du PostgreSQL que la suite exige sur le poste : une relance tombée sur
 *      lui a rendu un faux rouge (« Port 5432 is already in use »). Écarter
 *      5432 ne protégerait que de lui ; le système, lui, ne rend jamais un
 *      port tenu.
 *
 *  Lancer : node scripts/check-e2e-serveur.mjs [--selftest]
 */
import { readFileSync } from 'node:fs';
import { neutraliserCommentaires } from './lib-commentaires.mjs';

const CONFIG = 'playwright.config.ts';

/**  Les fautes d'une config, PURES. @returns {string[]} */
export function fautes(source) {
	const code = neutraliserCommentaires(source);
	const f = [];
	const reuse = code.match(/reuseExistingServer\s*:\s*([^,\n}]+)/);
	if (!reuse || reuse[1].trim() !== 'false')
		f.push('reuseExistingServer doit valoir `false` : un serveur emprunté sert le code d’un autre');
	if (!/--strictPort\b/.test(code))
		f.push(
			'la commande du serveur doit porter `--strictPort` : sinon Vite change de port en silence',
		);
	if (/\b5173\b/.test(code))
		f.push('le port 5173 est celui de `npm run dev` : un port partagé est un serveur partagé');
	if (/\blocalhost\b/.test(code))
		f.push(
			'`localhost` se résout en ::1 OU 127.0.0.1 : le navigateur et Vite peuvent ne pas viser la même adresse (#1732)',
		);
	if (!/--host\s+127\.0\.0\.1\b/.test(code))
		f.push(
			'la commande du serveur doit porter `--host 127.0.0.1` : sans elle, Vite écoute sur ::1 seul (#1732)',
		);
	if (/E2E_PORT\s*=[^;\n]*\bprocess\.pid\b/.test(code))
		f.push(
			'un port déduit du pid peut tomber sur un port tenu — 5432, le PostgreSQL du poste (#2051) : le demander au système',
		);
	if (!/\.listen\(\s*0\s*[,)]/.test(code))
		f.push('le port du serveur se demande au système (`listen(0)`), jamais dans une plage (#2051)');
	return f;
}

if (process.argv.includes('--selftest')) {
	let ko = 0;
	const t = (libelle, attendu, src) => {
		const n = fautes(src).length;
		console.log(`${n === attendu ? 'PASS' : 'FAIL'}  ${libelle} → ${n} faute(s)`);
		if (n !== attendu) ko = 1;
	};
	const CONFORME =
		'const PORT = Number(process.env.E2E_PORT);\n' +
		"const sonde = createServer().listen(0, '127.0.0.1');\n" +
		'process.env.E2E_PORT = portLibre();\n' +
		'const BASE = `http://127.0.0.1:${PORT}`;\n' +
		'webServer: { command: `npm run dev -- --host 127.0.0.1 --port ${PORT} --strictPort`, reuseExistingServer: false }';
	//  🔴 L'état exact d'avant le 25/09/2026 : ses trois fautes, l'adresse et le port.
	t(
		'la config d’avant #1150',
		5,
		"const PORT = 5173;\nwebServer: { command: 'npm run dev -- --port ' + PORT, reuseExistingServer: true }",
	);
	//  🔴 L'état exact d'avant le 08/10/2026 : `localhost`, et Vite sur ::1 seul.
	t(
		'la config d’avant #1732',
		2,
		CONFORME.replace('127.0.0.1:${PORT}', 'localhost:${PORT}').replace('--host 127.0.0.1 ', ''),
	);
	//  🔴 L'état exact d'avant le 21/10/2026 : un port tiré dans 5300–5899.
	t(
		'la config d’avant #2051',
		2,
		CONFORME.replace("const sonde = createServer().listen(0, '127.0.0.1');\n", '').replace(
			'process.env.E2E_PORT = portLibre();',
			'process.env.E2E_PORT = String(5300 + (process.pid % 600));',
		),
	);
	t('la config conforme', 0, CONFORME);
	t('`localhost` cité en commentaire seulement', 0, CONFORME + '\n// jadis localhost');
	t(
		'réutilisation remise',
		1,
		CONFORME.replace('reuseExistingServer: false', 'reuseExistingServer: true'),
	);
	t('réutilisation laissée au défaut', 1, CONFORME.replace(', reuseExistingServer: false', ''));
	t('réutilisation conditionnelle', 1, CONFORME.replace('false }', '!process.env.CI }'));
	t('port de développement cité en commentaire seulement', 0, CONFORME + '\n// jadis 5173');
	process.exit(ko);
}

const trouvees = fautes(readFileSync(CONFIG, 'utf8'));
if (trouvees.length) {
	console.error(`✗ ${CONFIG} :`);
	for (const f of trouvees) console.error(`  • ${f}`);
	console.error('\n  Voir le commentaire d’en-tête de la config, et #1150.');
	process.exit(1);
}
console.log('✓ Tests de navigateur : un serveur à eux, sur un port à eux, jamais emprunté.');
