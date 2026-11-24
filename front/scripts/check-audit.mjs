#!/usr/bin/env node
/**
 * Garde-fou : aucune vulnérabilité connue dans l'arbre de dépendances du front,
 * sauf exception écrite, motivée et datée.
 *
 * Le 17/08/2026 (#411), `npm audit` en local relevait QUATRE vulnérabilités dont
 * une haute, quand le bandeau GitHub n'en annonçait qu'une basse : Dependabot suit
 * ses propres avis sur la branche par défaut, `npm audit` interroge le registre sur
 * l'arbre RÉELLEMENT installé. Ni l'un ni l'autre n'était un contrôle de CI — les
 * quatre jobs requis étaient verts, et leur silence ressemblait à du calme.
 *
 * Deux décisions structurent ce script, toutes deux prises dans ce ticket :
 *
 * 1. **Le seuil est `low`, le plus strict.** Un seuil haut laisserait passer
 *    exactement la vulnérabilité qui atteignait les résidents ce jour-là (`cookie`,
 *    sévérité basse, embarquée dans le serveur SSR), tout en échouant sur une haute
 *    confinée à la chaîne de construction. La sévérité annoncée par le registre ne
 *    dit rien de l'atteignabilité ici : c'est l'instruction, pas le seuil, qui
 *    tranche.
 *
 * 2. **L'échappatoire est nominative, pas globale.** Un contrôle sans porte de
 *    sortie finit désactivé la semaine où une vulnérabilité non corrigeable en
 *    amont bloque toutes les PR — même raisonnement que pour le plafond de
 *    modularité, volontairement relatif. Chaque exception nomme son avis, son
 *    motif, sa condition de levée et une date de revue ; elle expire, et une
 *    exception devenue inutile FAIT ÉCHOUER le contrôle pour forcer son retrait.
 *    C'est la même mécanique que les règles `ignore` de `.github/dependabot.yml`,
 *    dont chacune porte une condition de levée vérifiable par une commande.
 *
 * ⚠️ L'audit porte sur TOUT l'arbre, `devDependencies` comprises. Ici ce n'est pas
 * un excès de zèle : `@sveltejs/kit` et `@sveltejs/adapter-node` sont déclarés en
 * `devDependencies` et sont pourtant le serveur qui SERT le site en production.
 * `npm audit --omit=dev` produirait donc un vert sur la seule des quatre
 * vulnérabilités qui atteignait les résidents.
 *
 * Un audit qui ne peut pas s'exécuter (registre injoignable, sortie illisible) rend
 * INCONNU et sort en 2 — jamais OK (socle 04). Relancer le job.
 *
 * Script Node sans dépendance, comme `check-sw-url.mjs`.
 *
 * Usage : npm run lint:audit                         (le front)
 *         node front/scripts/check-audit.mjs --dossier whatsapp-bridge   (#2962)
 *   Le dossier porte son `package-lock.json` et, s'il en a, son `audit-exceptions.json`.
 *   exit 0 = aucune vulnérabilité hors exception
 *   exit 1 = vulnérabilité non couverte, ou exception périmée/inutile
 *   exit 2 = INCONNU (l'audit n'a pas pu être mesuré)
 */

import { spawnSync } from 'node:child_process';
import { existsSync, readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join, resolve } from 'node:path';

//  Le dossier audité : le front par défaut, ou `--dossier <chemin>` — le bridge
//  WhatsApp n'avait que Trivy, la nuit, aux seuils CRITICAL et HIGH (#2962). Même
//  seuil, même mécanique d'exceptions nominatives, un fichier par dossier.
const iDossier = process.argv.indexOf('--dossier');
const RACINE =
	iDossier > 0
		? resolve(process.argv[iDossier + 1] ?? '/dossier-absent')
		: join(dirname(fileURLToPath(import.meta.url)), '..');
const FICHIER_EXCEPTIONS = join(RACINE, 'audit-exceptions.json');
if (!existsSync(join(RACINE, 'package-lock.json'))) {
	//  Un dossier mal nommé (ou `--dossier` sans valeur) n'est pas un arbre sain.
	console.error(`\n⚠️  INCONNU — aucun package-lock.json dans ${RACINE} : rien n'a été audité.\n`);
	process.exit(2);
}

/** Rend INCONNU : le contrôle n'a pas pu mesurer, ce qui n'est pas un succès. */
function inconnu(raison, detail) {
	console.error(`\n⚠️  INCONNU — ${raison}`);
	if (detail) console.error(`   ${String(detail).trim().split('\n').slice(0, 5).join('\n   ')}`);
	console.error(
		"   L'audit n'a PAS été mesuré : ce n'est ni un succès ni un échec. Relancer le job.\n",
	);
	process.exit(2);
}

// ── 1. Mesure ──────────────────────────────────────────────────────────────────
// `npm audit` sort en 1 dès qu'il trouve quelque chose : le code de sortie ne
// distingue pas « vulnérabilités trouvées » de « audit impossible ». C'est la
// sortie JSON qui fait foi, et son absence qui vaut INCONNU.
// Commande passée EN UN SEUL MORCEAU au shell, sans tableau d'arguments : c'est la
// seule forme portable. Sous Windows, `npm` est un `.cmd` que Node ≥ 20 refuse de
// lancer sans shell (EINVAL) ; avec `shell: true` et un tableau d'arguments, Node
// avertit qu'il les concatène sans échappement (DEP0190). Ici la commande est
// littérale et ne reçoit aucune entrée : il n'y a rien à échapper.
const audit = spawnSync('npm audit --json', {
	cwd: RACINE,
	encoding: 'utf8',
	shell: true,
	maxBuffer: 32 * 1024 * 1024,
});

if (audit.error) inconnu("`npm audit` n'a pas pu être lancé", audit.error.message);

let rapport;
try {
	rapport = JSON.parse(audit.stdout);
} catch {
	inconnu('sortie de `npm audit` illisible (registre injoignable ?)', audit.stderr || audit.stdout);
}

if (rapport.error) inconnu('`npm audit` a renvoyé une erreur', JSON.stringify(rapport.error));
if (!rapport.vulnerabilities) inconnu('sortie de `npm audit` sans section `vulnerabilities`');

// ── 2. Exceptions ──────────────────────────────────────────────────────────────
let exceptions = {};
try {
	exceptions = JSON.parse(readFileSync(FICHIER_EXCEPTIONS, 'utf8')).exceptions ?? {};
} catch (e) {
	if (e.code !== 'ENOENT') inconnu(`${FICHIER_EXCEPTIONS} illisible`, e.message);
}

const CHAMPS_REQUIS = ['motif', 'leveeSi', 'revoirLe'];
const aujourdhui = new Date().toISOString().slice(0, 10);

// ── 3. Confrontation ───────────────────────────────────────────────────────────
/** Identifiants d'avis (GHSA-…) rencontrés, par paquet. */
const avisTrouves = new Map();

for (const [paquet, v] of Object.entries(rapport.vulnerabilities)) {
	for (const via of v.via) {
		// `via` est soit un nom de paquet (vulnérabilité héritée d'une dépendance,
		// déjà comptée sur ELLE), soit l'avis lui-même. Seul le second cas est une
		// mesure : compter les deux ferait échouer sur un avis déjà couvert.
		if (typeof via === 'string') continue;
		const id = (via.url || '').split('/').pop() || `sans-avis:${paquet}`;
		if (!avisTrouves.has(id))
			avisTrouves.set(id, { titre: via.title, severite: via.severity, paquets: new Set() });
		avisTrouves.get(id).paquets.add(paquet);
	}
}

const echecs = [];
const tolerees = [];

for (const [id, info] of avisTrouves) {
	const exc = exceptions[id];
	const paquets = [...info.paquets].join(', ');
	if (!exc) {
		echecs.push(
			`${info.severite.toUpperCase()} — ${id} : ${info.titre}\n` +
				`      paquets : ${paquets}\n` +
				`      → corriger (npm audit fix, override, montée de version) ou écrire une exception motivée dans audit-exceptions.json`,
		);
		continue;
	}
	const manquants = CHAMPS_REQUIS.filter((c) => !exc[c]);
	if (manquants.length) {
		echecs.push(`${id} : exception incomplète — champ(s) manquant(s) : ${manquants.join(', ')}`);
		continue;
	}
	if (exc.revoirLe < aujourdhui) {
		echecs.push(
			`${id} : exception PÉRIMÉE (à revoir le ${exc.revoirLe}) — ${info.titre}\n` +
				`      levée si : ${exc.leveeSi}\n` +
				`      → vérifier si la condition de levée est remplie, puis corriger ou repousser la date en le disant`,
		);
		continue;
	}
	tolerees.push(`${id} (${info.severite}) — ${exc.motif} · revue le ${exc.revoirLe}`);
}

// Une exception qui ne correspond à plus rien est un mensonge en attente : elle
// laisserait passer une vulnérabilité réapparue sous le même avis sans que
// personne ne l'ait décidé aujourd'hui.
for (const id of Object.keys(exceptions)) {
	if (!avisTrouves.has(id))
		echecs.push(
			`${id} : exception INUTILE — cet avis n'apparaît plus dans l'arbre\n` +
				`      → la retirer de audit-exceptions.json`,
		);
}

// ── 4. Verdict ─────────────────────────────────────────────────────────────────
if (tolerees.length) {
	console.log('Vulnérabilités tolérées par exception écrite :');
	for (const l of tolerees) console.log(`  · ${l}`);
}

if (echecs.length) {
	console.error('\n❌ Audit des dépendances — ' + echecs.length + ' point(s) bloquant(s) :\n');
	for (const l of echecs) console.error(`   ${l}\n`);
	console.error(
		"Rappel : l'audit porte sur tout l'arbre, devDependencies comprises — `@sveltejs/kit`\n" +
			'et `@sveltejs/adapter-node` y sont déclarés et servent pourtant le site en production.\n',
	);
	process.exit(1);
}

const total = Object.keys(rapport.vulnerabilities).length;
console.log(
	`✓ Aucune vulnérabilité connue hors exception (${total} paquet(s) signalé(s), ${tolerees.length} exception(s) en cours).`,
);
