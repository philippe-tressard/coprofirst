#!/usr/bin/env node
/**
 *  La note d'un prestataire ne se rend qu'à UN endroit (08/09/2026).
 *
 *  🔴 Elle était rendue **cinq fois**, et les cinq ne disaient pas la même
 *  chose. La plus fausse : `VuePrestataires` colorait TOUTE note en orange —
 *  un prestataire noté **1/5 y paraissait comme un 3,5**. La teinte est censée
 *  dire d'un coup d'œil si l'on est content de quelqu'un ; là, elle mentait.
 *
 *  ⚠️ `starsDisplay` était DÉJÀ dans `#lib/utils` : la règle était factorisée,
 *  son **emploi** non — et c'est l'emploi qui porte les SEUILS (`< 3`, `< 4`,
 *  `>= 4`), donc le jugement. Même motif que la validation des téléversements
 *  (#825), où la règle vivait à un endroit et son geste dans trois routeurs.
 *
 *  ⚠️ Ce que le contrôle cherche : un appel à `starsDisplay` **hors du
 *  composant**. C'est le seul marqueur commun aux cinq écritures — les classes,
 *  les couleurs et les seuils, eux, divergeaient déjà.
 *
 *  Lancer : node scripts/check-note-etoiles.mjs [--selftest]
 */
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join, sep } from 'node:path';

const RACINE = 'src';
const SOURCE = 'src/lib/components/NoteEtoiles.svelte';

const APPEL = /\bstarsDisplay\s*\(/;

function fichiers(dir, acc = []) {
	for (const e of readdirSync(dir)) {
		const p = join(dir, e);
		if (statSync(p).isDirectory()) fichiers(p, acc);
		else if (e.endsWith('.svelte')) acc.push(p);
	}
	return acc;
}

function fautes(source) {
	return (
		source
			.split('\n')
			.map((l, i) => [l, i + 1])
			//  Les commentaires n'affichent rien — et celui qui explique ce contrôle
			//  cite justement le nom qu'il refuse.
			.filter(([l]) => !l.trim().startsWith('//') && !l.trim().startsWith('*'))
			.filter(([l]) => APPEL.test(l))
			.map(([, n]) => n)
	);
}

function selftest() {
	const cas = [
		['\t\t<td>{starsDisplay(n.note)} {n.note}/5</td>', 1],
		['\t\t<NoteEtoiles note={n.note} surCinq />', 0],
		['//  `starsDisplay` vit dans `#lib/utils` — ce commentaire ne rend rien', 0],
		['\t\t*  ⚠️ starsDisplay( est le marqueur cherché', 0],
	];
	let ko = 0;
	for (const [src, attendu] of cas) {
		const n = fautes(src).length;
		if (n !== attendu) {
			console.error(`  ✗ ${n} au lieu de ${attendu} : ${src.trim().slice(0, 56)}…`);
			ko++;
		}
	}
	if (ko) {
		console.error(`\n✗ Auto-test : ${ko} cas en échec.`);
		process.exit(1);
	}
	console.log('✓ Auto-test : le marqueur est reconnu, et lui seul.');
}

selftest();
if (process.argv.includes('--selftest')) process.exit(0);

const fautifs = [];
for (const p of fichiers(RACINE)) {
	const chemin = p.split(sep).join('/');
	if (chemin === SOURCE) continue;
	const lignes = fautes(readFileSync(p, 'utf8'));
	if (lignes.length) fautifs.push(`${chemin}:${lignes.join(',')}`);
}

if (fautifs.length) {
	console.error(`\n✗ ${fautifs.length} écran(s) rendent une note à la main :\n`);
	for (const f of fautifs) console.error(`  ${f}`);
	console.error(
		'\n  Elle était rendue CINQ fois, et l’une colorait un 1/5 comme un 3,5.\n' +
			'  Les seuils (< 3, < 4, >= 4) sont un JUGEMENT : recopiés, le même\n' +
			'  prestataire paraît « correct » sur un écran et « mécontent » sur l’autre.\n' +
			'  → employer `<NoteEtoiles note={…} nbAvis={…} surCinq />`.\n',
	);
	process.exit(1);
}
console.log('✓ Note : rendue au seul endroit qui porte les seuils.');
