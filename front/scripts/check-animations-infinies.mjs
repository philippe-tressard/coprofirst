#!/usr/bin/env node
/**
 *  Une animation SANS FIN ne dit qu'une chose : « ça travaille » (26/09/2026).
 *
 *  `emil-design-eng` : ce qu'on voit plusieurs fois par jour ne s'anime pas. Le
 *  26/09/2026, trois pulsations décoratives tournaient sans fin sur les écrans
 *  les plus vus — le badge NEW et le point « nouveau » du fil, la carte des
 *  Consignes à chaque visite d'un locataire. Elles fatiguaient sans rien
 *  apprendre, et sont devenues fixes.
 *
 *  Ce qu'il refuse : un `infinite` dans un style, hors des ATTENTES déclarées
 *  ci-dessous — chacune avec sa raison. Une exception qui ne sert plus fait
 *  échouer le contrôle : sinon la liste devient une liste de passe-droits.
 *
 *  Lancer : node scripts/check-animations-infinies.mjs [--selftest]
 */
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join, sep } from 'node:path';

/** Fichier → animation(s) permise(s), et pourquoi : une ATTENTE en cours — ou un décor voulu. */
const ATTENTES = {
	'styles/composants.css': ['spin', 'le spinner : un chargement en cours'],
	'routes/(app)/tableau-de-bord/+page.svelte': ['shimmer', 'le squelette pendant le chargement'],
	'lib/components/IconeIA.svelte': [
		'clignote-ia',
		'l’assistant IA travaille : le ⏳ d’un appel de plusieurs secondes (17/10/2026)',
	],
	'styles/decor-fete.css': [
		[
			'decor-fete-balance',
			'decor-fete-scintille',
			'decor-fete-glisse',
			'decor-fete-parcourt',
			'decor-fete-monte',
			'decor-fete-tombe',
		],
		'le décor des jours de fête (#2312) : un ornement lent et voulu, désactivable par l’administration, arrêté sous prefers-reduced-motion',
	],
};

/** Les noms qu'une exception admet : un seul, ou plusieurs pour un même décor. */
const admis = (rel) => [ATTENTES[rel]?.[0] ?? []].flat();

/** Les animations `infinite` d'une source (nom de l'animation). PURE. */
export function infinies(source) {
	const s = source.replace(/\/\*[\s\S]*?\*\//g, '').replace(/\/\/[^\n]*/g, '');
	return [...s.matchAll(/animation\s*:\s*([\w-]+)[^;]*\binfinite\b/g)].map((m) => m[1]);
}

if (process.argv.includes('--selftest')) {
	let ko = 0;
	const t = (libelle, attendu, src) => {
		const r = JSON.stringify(infinies(src));
		const ok = r === JSON.stringify(attendu);
		console.log(`${ok ? 'PASS' : 'FAIL'}  ${libelle} → ${r}`);
		if (!ok) ko = 1;
	};
	t('pulsation sans fin', ['new-pulse'], '.x { animation: new-pulse 2s ease-in-out infinite; }');
	t('animation finie', [], '.x { animation: entree 200ms ease-out; }');
	t('commentaire ignoré', [], '/* animation: pulse 1s infinite; */');
	console.log(ko ? '== ÉCHECS ==' : '== TOUS OK ==');
	process.exit(ko);
}

function fichiers(dir, acc = []) {
	for (const e of readdirSync(dir)) {
		const p = join(dir, e);
		if (statSync(p).isDirectory()) fichiers(p, acc);
		else if (e.endsWith('.svelte') || e.endsWith('.css')) acc.push(p);
	}
	return acc;
}

const fautifs = [];
const servies = new Set();
for (const f of fichiers('src')) {
	const rel = f
		.split(sep)
		.join('/')
		.replace(/^src\//, '');
	for (const nom of infinies(readFileSync(f, 'utf8'))) {
		if (admis(rel).includes(nom)) servies.add(`${rel} — ${nom}`);
		else fautifs.push(`${rel} — ${nom}`);
	}
}
//  Chaque nom déclaré doit servir : une animation retirée retire son exception.
const mortes = Object.keys(ATTENTES).flatMap((f) =>
	admis(f)
		.map((nom) => `${f} — ${nom}`)
		.filter((cle) => !servies.has(cle)),
);
if (fautifs.length || mortes.length) {
	if (fautifs.length)
		console.error(
			`\n✗ Animation sans fin hors d'une attente :\n\n  ${fautifs.join('\n  ')}\n\n  → la rendre fixe, ou la déclarer dans ATTENTES avec sa raison.\n`,
		);
	if (mortes.length)
		console.error(`\n✗ Exception qui ne sert plus : ${mortes.join(', ')} — la retirer.\n`);
	process.exit(1);
}
console.log(`✓ Animations sans fin : ${servies.size} attente(s) déclarée(s), aucune décorative.`);
