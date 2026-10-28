#!/usr/bin/env node
/**
 * **Un paquet chargé par `import()` est déclaré à Vite** (#1956, 14/10/2026).
 *
 * ## Pourquoi
 *
 * Un paquet que le source charge à la demande (`import('marked')`) n'est
 * découvert par Vite qu'au premier écran qui l'appelle : il l'optimise alors, puis
 * RECHARGE toutes les pages ouvertes — les e2e en vol tombent (#1421). La règle :
 * le déclarer dans `optimizeDeps.include` (`vite.config.ts`). L'étape e2e de la CI
 * le détecte, mais seulement sur un cache de Vite NEUF : sur le poste de celui qui
 * vient d'ajouter le paquet, le cache le connaît déjà, et rien ne se recharge.
 * C'est ce qui est arrivé à `marked` (#1930) — rattrapé par la CI de la PR, pas
 * par le rejeu.
 *
 * Ce contrôle lit le SOURCE, pas un cache : il voit le paquet le jour où l'on
 * écrit son `import()`, sur n'importe quel poste.
 *
 * ## Ce qu'il ne voit pas
 *
 * Un import STATIQUE d'un écran que le pré-scan de Vite n'atteint qu'à la visite
 * (`qrcode-generator`, #779) : rien dans le source ne le distingue d'un import
 * ordinaire. L'étape e2e de la CI reste la seconde sonde.
 *
 * Usage : node scripts/check-optimize-deps.mjs [--selftest]
 */
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join } from 'node:path';
import { neutraliserCommentaires } from './lib-commentaires.mjs';

const SRC = new URL('../src', import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, '$1');
const VITE = new URL('../vite.config.ts', import.meta.url);

/** Les modules que fournit un PLUGIN, pas `node_modules` : Vite ne les optimise pas. */
const VIRTUELS = /^virtual:/;

/** `import('x')` d'un paquet — ni chemin relatif, ni alias `#lib`, ni absolu. */
export function paquetsImportesALaDemande(source) {
	const trouves = new Set();
	for (const m of neutraliserCommentaires(source).matchAll(/\bimport\(\s*['"]([^'"]+)['"]\s*\)/g)) {
		const spec = m[1];
		if (/^[./#]/.test(spec) || VIRTUELS.test(spec)) continue;
		trouves.add(spec);
	}
	return trouves;
}

/** Les entrées de `optimizeDeps.include`, lues dans le texte de `vite.config.ts`. */
export function declares(config) {
	const bloc = /optimizeDeps\s*:\s*\{[\s\S]*?include\s*:\s*\[([\s\S]*?)\]/.exec(
		neutraliserCommentaires(config),
	);
	if (!bloc) return null;
	return new Set([...bloc[1].matchAll(/['"]([^'"]+)['"]/g)].map((m) => m[1]));
}

export function oublis(importes, declaresVite) {
	return [...importes].filter((p) => !declaresVite.has(p)).sort();
}

function fichiers(dir, acc = []) {
	for (const e of readdirSync(dir)) {
		const p = join(dir, e);
		if (statSync(p).isDirectory()) fichiers(p, acc);
		else if (/\.(ts|js|svelte)$/.test(e)) acc.push(p);
	}
	return acc;
}

function selftest() {
	const cas = [
		[
			'un paquet chargé à la demande est relevé',
			paquetsImportesALaDemande("const m = await import('marked');").has('marked'),
		],
		[
			'un chemin, un alias, un module virtuel ne le sont pas',
			paquetsImportesALaDemande(
				"import('./a.svelte'); import('#lib/x'); import('virtual:pwa-register');",
			).size === 0,
		],
		[
			'un import() en commentaire ne compte pas',
			paquetsImportesALaDemande("// import('marked')").size === 0,
		],
		[
			'la liste de Vite se lit, commentaires écartés',
			[
				...(declares(
					"optimizeDeps: {\n include: [\n 'dompurify', // à la demande\n // 'oublie',\n 'marked',\n ],\n}",
				) ?? []),
			].join() === 'dompurify,marked',
		],
		[
			'un paquet non déclaré est un oubli',
			oublis(new Set(['marked', 'dompurify']), new Set(['dompurify'])).join() === 'marked',
		],
		['sans bloc optimizeDeps : INCONNU, pas vert', declares('export default {}') === null],
	];
	let ko = 0;
	for (const [nom, vrai] of cas) {
		console.log(`${vrai ? '✓' : '✗'} ${nom}`);
		if (!vrai) ko++;
	}
	if (ko) process.exit(1);
}

if (process.argv.includes('--selftest')) {
	selftest();
} else {
	const vite = declares(readFileSync(VITE, 'utf8'));
	if (!vite) {
		console.error('✗ INCONNU — `optimizeDeps.include` introuvable dans vite.config.ts.');
		process.exit(2);
	}
	const importes = new Set();
	for (const f of fichiers(SRC)) {
		for (const p of paquetsImportesALaDemande(readFileSync(f, 'utf8'))) importes.add(p);
	}
	//  Cas zéro : le source charge des paquets à la demande (l'éditeur riche,
	//  l'assainisseur). N'en trouver aucun, c'est un motif qui ne mord plus.
	if (importes.size === 0) {
		console.error('✗ Cas zéro : aucun import() de paquet trouvé — le relevé ne mord plus.');
		process.exit(1);
	}
	const manquants = oublis(importes, vite);
	if (manquants.length) {
		console.error(
			`✗ Chargé(s) par import() mais absent(s) de optimizeDeps.include (vite.config.ts) : ${manquants.join(', ')}\n` +
				'  Vite les découvrirait au premier écran qui les appelle, et rechargerait la page (#1421).',
		);
		process.exit(1);
	}
	console.log(
		`✓ Paquets chargés à la demande, tous déclarés à Vite : ${[...importes].sort().join(', ')}`,
	);
}
