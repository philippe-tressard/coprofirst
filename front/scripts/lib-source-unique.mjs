/**
 * **Une notion, une source** — le squelette des contrôles qui refusent la
 * copie d'une notion hors du fichier qui la porte (#779, 01/10/2026).
 *
 * ## Le défaut que ce module retire
 *
 * Chaque factorisation de #779 livrait son garde-fou, et chaque garde-fou
 * recopiait le même squelette : parcourir `src/`, sauter la source, relever les
 * lignes qui portent la forme d'une copie, rejouer des cas, dire le compte. Il
 * en existait quatre (`identite-copropriete`, `type-lot`, `nombre-saisi`,
 * `lien-consignes`) quand le lot suivant s'apprêtait à en écrire deux de plus.
 *
 * 🔴 Et les copies avaient déjà divergé là où ça compte :
 *
 * | | cas zéro | commentaires | exception qui doit servir |
 * |---|---|---|---|
 * | `identite-copropriete` | oui | comptés | — |
 * | `type-lot` | **non** — 0 fichier lu rendait ✓ | ignorés | — |
 * | `nombre-saisi` | oui | ignorés | oui |
 * | `lien-consignes` | oui | comptés | la source |
 *
 * Un contrôle qui lit 0 fichier et conclut « aucune copie » est le faux vert
 * de `standards/04` §2 : il l'était pour `type-lot`.
 *
 * ## Ce que le module garantit à chacun
 *
 * - le **cas zéro** : aucun fichier lu rend un échec, jamais un ✓ ;
 * - les **commentaires** ne comptent pas (`lib-commentaires`) : un en-tête qui
 *   cite la forme refusée n'est pas une copie ;
 * - le **témoin** : la source qui porte la notion doit encore la porter, sinon
 *   le contrôle resterait vert sur une notion disparue ;
 * - les **exceptions** déclarées, avec leur raison, doivent servir.
 *
 * Ce qui reste à chaque contrôle : son en-tête (pourquoi), sa forme fautive,
 * ses cas, ses messages.
 *
 * Lancer : node scripts/lib-source-unique.mjs --selftest
 */
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join, sep } from 'node:path';
import { fileURLToPath } from 'node:url';
import { neutraliserCommentaires } from './lib-commentaires.mjs';

/** Les fichiers de `racine` dont l'extension est retenue, chemins en `/`. */
export function fichiersSources(racine, extensions) {
	const acc = [];
	const parcourir = (dir) => {
		for (const e of readdirSync(dir)) {
			const p = join(dir, e);
			if (statSync(p).isDirectory()) parcourir(p);
			else if (extensions.some((x) => e.endsWith(x))) acc.push(p.split(sep).join('/'));
		}
	};
	parcourir(racine);
	return acc;
}

/**
 * Les numéros des lignes qui portent `motif`, hors commentaires. PURE.
 *
 * Les commentaires sont blanchis par `lib-commentaires` — un en-tête qui cite
 * la forme refusée n'est pas une copie, y compris sur plusieurs lignes
 * (`<!-- … -->` d'un composant). Les numéros de ligne restent justes.
 */
export function lignesPortant(motif) {
	return (texte) =>
		neutraliserCommentaires(texte)
			.split('\n')
			.map((ligne, i) => [ligne, i + 1])
			.filter(([l]) => motif.test(l))
			.map(([, n]) => n);
}

/** Rejoue `[source, attendu]` contre `fautes`. Rend 0 si tous passent. */
export function rejouerCas(cas, fautes) {
	let ko = 0;
	for (const [source, attendu] of cas) {
		const obtenu = fautes(source).length;
		console.log(`${obtenu === attendu ? 'PASS' : 'FAIL'}  ${source.trim().split('\n')[0]}`);
		if (obtenu !== attendu) ko = 1;
	}
	console.log(ko ? '== ÉCHECS ==' : '== TOUS OK ==');
	return ko;
}

/**
 * Le relevé, sans entrée ni sortie : ce que `controler` dit, et ce que
 * l'auto-test éprouve. PURE.
 *
 * @param {Record<string, string>} contenus  chemin → texte
 */
export function releve(contenus, { sources = [], temoin = null, exceptions = {}, fautes }) {
	const copies = [];
	const servies = new Set();
	let temoinSert = temoin === null;
	for (const [rel, texte] of Object.entries(contenus)) {
		//  Le chemin suit le texte : un contrôle qui déclare un écart plus fin que
		//  le fichier (un champ dans un fichier, `check-nombres-bruts`) le lit.
		const n = fautes(texte, rel);
		if (rel === temoin) {
			temoinSert = n.length > 0;
			continue;
		}
		if (sources.includes(rel)) continue;
		if (rel in exceptions) {
			if (n.length) servies.add(rel);
			continue;
		}
		for (const l of n) copies.push(`${rel}:${l}`);
	}
	return {
		lus: Object.keys(contenus).length,
		copies,
		temoinSert,
		mortes: Object.keys(exceptions).filter((r) => !servies.has(r)),
	};
}

/**
 * Le contrôle complet : `--selftest` rejoue les cas, sinon relève `src/`.
 * Rend le code de sortie.
 *
 * @param {object} o
 * @param {string} [o.racine]          'src'
 * @param {string[]} [o.racines]       plusieurs racines à la place de `racine`
 * @param {string[]} [o.fichiers]       fichiers isolés lus en plus des racines
 * @param {string[]} [o.extensions]    ['.svelte']
 * @param {string[]} [o.sources]       fichiers qui portent la notion : non relevés
 * @param {string|null} [o.temoin]     fichier qui DOIT porter la forme (la source elle-même)
 * @param {Record<string,string>} [o.exceptions]  chemin → raison ; doivent servir
 * @param {(texte: string, chemin?: string) => number[]} o.fautes
 * @param {[string, number][]} o.cas
 * @param {string} o.ok       « Identité de la copropriété : saisie par … seul »
 * @param {string} o.ko       « champ(s) d'identité lié(s) à la main »
 * @param {string} o.conseil  la forme à employer
 */
export function controler(o) {
	if (process.argv.includes('--selftest')) return rejouerCas(o.cas, o.fautes);
	const racines = o.racines ?? [o.racine ?? 'src'];
	const racine = racines.join(', ');
	const contenus = {};
	for (const r of racines) {
		for (const f of fichiersSources(r, o.extensions ?? ['.svelte'])) {
			contenus[f] = readFileSync(f, 'utf8');
		}
	}
	for (const f of o.fichiers ?? []) contenus[f] = readFileSync(f, 'utf8');
	const r = releve(contenus, o);
	//  Cas zéro (standards/04 §2) : aucun fichier lu n'est pas « aucune copie ».
	if (!r.lus) {
		console.error(`✗ Aucun fichier lu sous ${racine} : contrôle INCONNU.`);
		return 1;
	}
	let ko = 0;
	if (!r.temoinSert) {
		console.error(`✗ ${o.temoin} ne porte plus la forme : la source unique manque.`);
		ko = 1;
	}
	if (r.mortes.length) {
		console.error(`✗ Exception(s) qui ne servent plus — les retirer : ${r.mortes.join(', ')}`);
		ko = 1;
	}
	if (r.copies.length) {
		console.error(`\n✗ ${r.copies.length} ${o.ko} :`);
		for (const c of r.copies) console.error(`   ${c}`);
		console.error(`\n  ${o.conseil}\n`);
		ko = 1;
	}
	if (!ko) console.log(`✓ ${o.ok} (${r.lus} fichiers lus).`);
	return ko;
}

/** Auto-test du squelette lui-même : cas zéro, témoin, exceptions, commentaires. */
function selftest() {
	const fautes = lignesPortant(/COPIE/);
	const cas = [
		[
			'un commentaire ne compte pas, même sur plusieurs lignes',
			fautes('// COPIE\n/* COPIE\n COPIE */\n<!--\n  COPIE\n-->').length,
			0,
		],
		['une ligne de code compte', fautes('const x = COPIE;').length, 1],
		[
			'la copie est relevée, la source non',
			releve({ 'a.svelte': 'COPIE', 's.ts': 'COPIE' }, { sources: ['s.ts'], fautes }).copies,
			['a.svelte:1'],
		],
		[
			'un témoin qui ne porte plus la forme se signale',
			releve({ 't.ts': 'rien' }, { temoin: 't.ts', fautes }).temoinSert,
			false,
		],
		[
			'une exception qui ne sert plus se signale',
			releve({ 'e.ts': 'rien' }, { exceptions: { 'e.ts': 'raison' }, fautes }).mortes,
			['e.ts'],
		],
		['aucun fichier lu se compte zéro', releve({}, { fautes }).lus, 0],
	];
	let ko = 0;
	for (const [quoi, obtenu, attendu] of cas) {
		const ok = JSON.stringify(obtenu) === JSON.stringify(attendu);
		console.log(`${ok ? 'PASS' : 'FAIL'}  ${quoi}`);
		if (!ok) ko = 1;
	}
	console.log(ko ? '== ÉCHECS ==' : '== TOUS OK ==');
	return ko;
}

if (process.argv[1] === fileURLToPath(import.meta.url) && process.argv.includes('--selftest')) {
	process.exit(selftest());
}
