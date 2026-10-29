/**
 * Auto-test de `#lib/accordeon.ts` — un seul bloc déplié à la fois (30/09/2026).
 *
 * Demandé : « déplier une section replie les autres, sans exception ». Le module
 * porte les trois formes de la règle ; ce test éprouve les deux qui se testent
 * sans navigateur — l'état pur et les groupes —, et surtout les deux EXCEPTIONS
 * arbitrées, qu'une réécriture pressée effacerait :
 *   - une carte en correction reste ouverte quand une autre liste prend la main ;
 *   - un membre détruit rend la main (sinon un bloc ouvert sur une page quittée
 *     replierait, à la page suivante, le premier bloc qui s'ouvre).
 * La troisième forme — les `<details>` natifs — l'est par `e2e/accordeon.spec.ts`.
 *
 * Il REFUSE aussi un nouvel état d'ouverture tenu par un `Set` : c'est la forme
 * qui laisse plusieurs blocs ouverts, et c'est par elle que la règle fuyait
 * (archives par année, kanban, diagnostics — corrigés le 30/09/2026).
 *
 * Usage : node scripts/check-accordeon.mjs --selftest
 */
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, relative, sep } from 'node:path';

import { basculer, listeMembre, membre } from '../src/lib/accordeon.ts';

const echecs = [];
let cas = 0;
function verifier(nom, obtenu, attendu) {
	cas++;
	if (JSON.stringify(obtenu) !== JSON.stringify(attendu))
		echecs.push(`${nom} : obtenu ${JSON.stringify(obtenu)}, attendu ${JSON.stringify(attendu)}`);
}

// ── L'état pur ─────────────────────────────────────────────────────────────
verifier('ouvrir un bloc', basculer(null, 3), 3);
verifier('en ouvrir un autre remplace le premier', basculer(3, 5), 5);
verifier('recliquer le ferme', basculer(5, 5), null);

// ── Les groupes ────────────────────────────────────────────────────────────
let a = true;
let b;
const ma = membre('reponses', () => (a = false));
const mb = membre('reponses', () => (b = false));
ma.prendre();
b = true;
mb.prendre();
verifier('ouvrir B replie A', [a, b], [false, true]);
mb.liberer();
ma.liberer();
let c = true;
const mc = membre('reponses', () => (c = false));
verifier('un membre détruit a rendu la main', c, true);
mc.liberer();

// ── Les listes, et l'exception de la correction ────────────────────────────
let conseil = { ouvert: 2, edite: 2 };
let syndic = { ouvert: null, edite: null };
const lc = listeMembre(
	'annuaires',
	() => conseil,
	(e) => (conseil = e),
);
const ls = listeMembre(
	'annuaires',
	() => syndic,
	(e) => (syndic = e),
);
lc.ouvrir(conseil);
ls.ouvrir({ ouvert: 0, edite: null });
verifier('une carte en correction reste ouverte', conseil, { ouvert: 2, edite: 2 });
lc.ouvrir({ ouvert: 1, edite: null });
verifier('une carte lue se replie quand l’autre liste s’ouvre', syndic, {
	ouvert: null,
	edite: null,
});
lc.liberer();
ls.liberer();

// ── Aucun nouvel état d'ouverture en `Set` ─────────────────────────────────
//
//  Les deux existants sont des accordéons — le `Set` y est toujours remis à UN
//  élément —, mais sous une forme qui permettrait d'en mettre deux : déclarés
//  ici, ils ne se multiplient plus. La liste ne fait que baisser ; une entrée qui
//  ne sert plus fait échouer le contrôle. Suivi des deux restantes : #2317.
const EXCEPTIONS = new Set([
	'lib/components/ListeTickets.svelte:expandedIds',
	'lib/components/OngletDescriptifPages.svelte:expandedPages',
]);
const RE_SET_OUVERTURE =
	/(?:let|const)\s+(\w*(?:ouvert|Ouvert|deplie|Deplie|depli|Depli|expanded|Expanded)\w*)\s*(?::[^=;]+)?=\s*new Set(?![A-Za-z])/g;
const racine = new URL('../src', import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, '$1');
function fichiers(dir) {
	return readdirSync(dir).flatMap((n) => {
		const p = join(dir, n);
		if (statSync(p).isDirectory()) return fichiers(p);
		return /\.(svelte|ts)$/.test(n) ? [p] : [];
	});
}
const vus = new Set();
for (const f of fichiers(racine)) {
	const rel = relative(racine, f).split(sep).join('/');
	for (const m of readFileSync(f, 'utf-8').matchAll(RE_SET_OUVERTURE)) {
		const cle = `${rel}:${m[1]}`;
		cas++;
		if (EXCEPTIONS.has(cle)) vus.add(cle);
		else
			echecs.push(
				`${cle} : un état d'ouverture en \`Set\` laisse plusieurs blocs ouverts — un identifiant et \`basculer\` (\`#lib/accordeon\`).`,
			);
	}
}
for (const e of EXCEPTIONS)
	if (!vus.has(e)) echecs.push(`${e} : exception déclarée qui ne sert plus — la retirer.`);

if (echecs.length) {
	console.error(`✗ accordeon — ${echecs.length} cas en échec sur ${cas} :\n`);
	for (const e of echecs) console.error('  ' + e);
	process.exit(1);
}
if (cas === 0) {
	console.error('✗ Aucun cas exécuté — le module ne s’importe plus. INCONNU, pas OK.');
	process.exit(1);
}
console.log(
	`✓ accordeon : ${cas} cas vérifiés — un seul bloc ouvert, correction et libération comprises.`,
);
