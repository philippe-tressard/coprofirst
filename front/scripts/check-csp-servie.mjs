#!/usr/bin/env node
// SPDX-FileCopyrightText: 2026 Philippe Tressard
// SPDX-License-Identifier: AGPL-3.0-or-later
/**
 * `script-src` doit rester BLOQUANT et porter un condensat — mesuré sur le serveur.
 *
 * ## Pourquoi ce contrôle
 *
 * #770 (06/09/2026) a mis `script-src` en mode bloquant sans écrire une ligne
 * dans le `Caddyfile` : c'est SvelteKit qui émet `script-src 'self' 'sha256-…'`,
 * parce que lui seul connaît le contenu de ses scripts d'hydratation. Cette
 * protection tient donc à **six lignes de `vite.config.ts`** que rien
 * n'obligeait à rester là.
 *
 * 🔴 Le précédent est connu et coûteux : la v2.24.0 a livré un bandeau de mise à
 * jour PWA « vérifié » sur l'artefact — bundle correct, image correcte, version
 * correcte — pendant que le service worker ne s'enregistrait plus du tout. Les
 * artefacts ne prouvent rien sur le comportement.
 *
 * D'où la mesure sur le **serveur réellement construit** : on démarre
 * `build/index.js`, on lit l'en-tête `content-security-policy` d'une vraie
 * réponse, et on exige que `script-src` y soit, avec au moins un condensat. Une
 * configuration lue dans un fichier n'aurait rien prouvé — c'est la règle
 * `standards/04` : vérifier le fait, pas le symptôme attendu.
 *
 * ⚠️ Ce contrôle mesure ce que SvelteKit émet. Ce que Caddy en fait ensuite est
 * l'autre moitié du sujet, et elle tient à un seul caractère : `+` devant
 * `Content-Security-Policy` dans le `Caddyfile`, sans quoi l'en-tête de
 * SvelteKit est ÉCRASÉ. C'est pourquoi le `Caddyfile` est vérifié ici aussi :
 * les deux moitiés sont inséparables, et aucune ne se voit depuis l'autre.
 *
 * Usage :  node scripts/check-csp-servie.mjs [--selftest]
 */
import { spawn } from 'node:child_process';
import { existsSync, readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const ICI = dirname(fileURLToPath(import.meta.url));
const FRONT = resolve(ICI, '..');
const RACINE = resolve(FRONT, '..');
const PORT = 41999;

/** La décision, pure : cet en-tête protège-t-il les scripts ? */
export function verdictEntete(entete) {
	if (!entete) return { ok: false, motif: 'aucun en-tête `content-security-policy` servi' };
	const directive = entete
		.split(';')
		.map((d) => d.trim())
		.find((d) => d.startsWith('script-src'));
	if (!directive) return { ok: false, motif: "l'en-tête ne porte pas de `script-src`" };
	if (directive.includes("'unsafe-inline'"))
		return { ok: false, motif: "`script-src` porte `'unsafe-inline'` — il ne protège plus rien" };
	if (!/'sha(256|384|512)-[A-Za-z0-9+/=]+'/.test(directive) && !/'nonce-/.test(directive))
		return {
			ok: false,
			motif: `\`script-src\` sans condensat ni nonce : « ${directive} ». Les scripts inline de SvelteKit seraient bloqués et le site rendu blanc.`,
		};
	return { ok: true, motif: directive };
}

/** La décision, pure : le Caddyfile préserve-t-il l'en-tête du framework ? */
export function verdictCaddyfile(texte) {
	const lignes = texte
		.split(/\r?\n/)
		.map((l) => l.trim())
		.filter((l) => /^\+?Content-Security-Policy(-Report-Only)?\s/.test(l));
	if (lignes.length === 0) return { ok: false, motif: 'aucune directive CSP dans le Caddyfile' };
	const ecrasantes = lignes.filter((l) => !l.startsWith('+'));
	if (ecrasantes.length)
		return {
			ok: false,
			motif: `${ecrasantes.length} directive(s) CSP posée(s) sans \`+\` : Caddy REMPLACERAIT l'en-tête de SvelteKit, ses condensats seraient perdus et le site deviendrait blanc.`,
		};
	return { ok: true, motif: `${lignes.length} directive(s) CSP, toutes en ajout` };
}

const CAS = [
	['bloquant avec condensat', "script-src 'self' 'sha256-abc123='", true],
	['bloquant avec nonce', "script-src 'self' 'nonce-xyz'", true],
	['en-tête absent', '', false],
	['pas de script-src', "font-src 'self'; style-src 'self'", false],
	['script-src nu : casserait le site', "script-src 'self'", false],
	['unsafe-inline : ne protège plus', "script-src 'self' 'unsafe-inline'", false],
	['directive noyée au milieu', "font-src 'self'; script-src 'self' 'sha256-a='; img-src *", true],
];

const CAS_CADDY = [
	['tout en ajout', '+Content-Security-Policy "a"\n+Content-Security-Policy-Report-Only "b"', true],
	['une seule, en ajout', '+Content-Security-Policy "a"', true],
	['posée sans +, écrase', 'Content-Security-Policy "a"', false],
	[
		'mélange : une seule suffit à casser',
		'+Content-Security-Policy "a"\nContent-Security-Policy-Report-Only "b"',
		false,
	],
	['cas zéro : aucune directive', '# rien ici', false],
];

function selftest() {
	let echecs = 0;
	for (const [nom, entete, attendu] of CAS) {
		const { ok, motif } = verdictEntete(entete);
		const bon = ok === attendu;
		if (!bon) echecs++;
		console.log(`${bon ? 'PASS' : 'ÉCHEC'}  ${nom} → ${ok ? 'accepté' : `refusé (${motif})`}`);
	}
	for (const [nom, texte, attendu] of CAS_CADDY) {
		const { ok, motif } = verdictCaddyfile(texte);
		const bon = ok === attendu;
		if (!bon) echecs++;
		console.log(
			`${bon ? 'PASS' : 'ÉCHEC'}  Caddyfile : ${nom} → ${ok ? 'accepté' : `refusé (${motif})`}`,
		);
	}
	console.log(echecs ? `== ${echecs} ÉCHEC(S) ==` : '== TOUS OK ==');
	return echecs ? 1 : 0;
}

async function mesurer() {
	const entree = resolve(FRONT, 'build/index.js');
	if (!existsSync(entree)) {
		// INCONNU, jamais OK : sans build, ce contrôle n'a rien mesuré.
		console.error('INCONNU : `front/build/index.js` absent — lancer `npm run build` d’abord.');
		return 2;
	}
	const serveur = spawn(process.execPath, [entree], {
		env: { ...process.env, PORT: String(PORT), HOST: '127.0.0.1' },
		stdio: 'ignore',
	});
	try {
		let reponse = null;
		for (let essai = 0; essai < 40 && !reponse; essai++) {
			await new Promise((r) => setTimeout(r, 250));
			try {
				reponse = await fetch(`http://127.0.0.1:${PORT}/auth/connexion`, { redirect: 'manual' });
			} catch {
				/* le serveur n'écoute pas encore */
			}
		}
		if (!reponse) {
			console.error(`INCONNU : le serveur n’a pas répondu sur le port ${PORT} en 10 s.`);
			return 2;
		}
		const { ok, motif } = verdictEntete(reponse.headers.get('content-security-policy'));
		if (!ok) {
			console.error(`❌ CSP servie par SvelteKit : ${motif}`);
			console.error('   option `csp` (mode `hash`) de front/vite.config.ts — cf. #770.');
			return 1;
		}
		console.log(`✅ CSP servie par SvelteKit : ${motif}`);
		return 0;
	} finally {
		serveur.kill();
	}
}

async function main() {
	if (process.argv.includes('--selftest')) return selftest();
	const codeServeur = await mesurer();
	const caddyfile = resolve(RACINE, 'Caddyfile');
	if (!existsSync(caddyfile)) {
		console.error('INCONNU : `Caddyfile` introuvable — la moitié « proxy » n’a pas été mesurée.');
		return Math.max(codeServeur, 2);
	}
	const { ok, motif } = verdictCaddyfile(readFileSync(caddyfile, 'utf8'));
	console.log(`${ok ? '✅' : '❌'} Caddyfile : ${motif}`);
	return Math.max(codeServeur, ok ? 0 : 1);
}

process.exit(await main());
