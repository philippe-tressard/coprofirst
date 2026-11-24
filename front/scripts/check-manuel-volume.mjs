#!/usr/bin/env node
/**
 * Garde-fou : **le manuel ne grossit plus** (#3008, 24/11/2026).
 *
 * ## Pourquoi
 *
 * L'arbitrage du 07/09/2026 (#651) jugeait le manuel « beaucoup trop complexe et
 * trop long ; seule la partie Démarrer est suffisante ». Il comptait alors
 * 3 042 mots. Le 23/11/2026, il en comptait près de trente mille, et un seul « En
 * savoir plus » (Admin) en faisait huit mille : chaque lot qui touchait un écran y
 * ajoutait un paragraphe, et rien ne mesurait la somme. Une consigne de concision
 * ne tient pas seule, et personne ne relit trente mille mots pour voir lesquels
 * sont de trop.
 *
 * ## Ce qu'il vérifie
 *
 * Il compte les mots — après retrait du balisage, des styles et des scripts — du
 * manuel entier, de chaque section (`<section id>`) et de chaque carte d'écran
 * (`.ecran-card`, par son `data-page`), et les confronte aux plafonds de
 * `check-manuel-volume.regles.mjs` :
 *
 * 1. un compte AU-DESSUS de son plafond est refusé : le manuel ne grossit pas ;
 * 2. un plafond qui dépasse son compte de plus de `MARGE` mots est refusé aussi :
 *    un texte qui a maigri fait baisser son plafond, dans le même lot — sinon la
 *    place libérée se reprendrait en silence (le motif de `PLAFOND_CLONES`) ;
 * 3. une carte ou une section sans plafond déclaré est refusée, et un plafond
 *    qui ne désigne plus rien aussi.
 *
 * Une carte NEUVE se déclare à sa longueur, et la plus courte possible : le
 * détail d'un écran vit dans l'application (aides d'écran, FAQ), pas ici.
 *
 * Il lit `docs/` seulement : la copie de `front/static/` lui est identique, ce
 * que vérifie `api/tests/test_documentation.py`.
 *
 * Usage :
 *   node scripts/check-manuel-volume.mjs              (exit 1 au premier écart)
 *   node scripts/check-manuel-volume.mjs --mesurer    (les comptes du jour, sans juger)
 *   node scripts/check-manuel-volume.mjs --selftest
 */
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { MARGE, PLAFONDS } from './check-manuel-volume.regles.mjs';

const RACINE = join(dirname(fileURLToPath(import.meta.url)), '..', '..');
const MANUEL = 'docs/manuel-utilisateur.html';

/** Le nombre de mots d'un fragment HTML : lettres et chiffres, apostrophes et traits d'union internes compris. */
export function compterMots(fragment) {
	const texte = fragment
		.replace(/<(style|script)\b[^>]*>[\s\S]*?<\/\1>/gi, ' ')
		.replace(/<[^>]+>/g, ' ')
		.replace(/&[#a-z0-9]+;/gi, ' ');
	return (texte.match(/[\p{L}\p{N}]+(?:['’-][\p{L}\p{N}]+)*/gu) ?? []).length;
}

/** L'élément ouvert à `debut`, jusqu'à sa balise fermante (les `<balise>` imbriqués comptés). */
function element(html, debut, balise) {
	const motif = new RegExp(`<(/?)${balise}\\b`, 'gi');
	motif.lastIndex = debut;
	let profondeur = 0;
	for (let m; (m = motif.exec(html));) {
		profondeur += m[1] ? -1 : 1;
		if (profondeur === 0) return html.slice(debut, html.indexOf('>', m.index) + 1);
	}
	return html.slice(debut);
}

/** `{ total, sections: {id: mots}, cartes: {data-page: mots} }` d'un manuel. */
export function mesurer(html) {
	const propre = html.replace(/<(style|script)\b[^>]*>[\s\S]*?<\/\1>/gi, ' ');
	const sections = {};
	for (const m of propre.matchAll(/<section\b[^>]*\bid="([^"]+)"/g)) {
		sections[m[1]] = compterMots(element(propre, m.index, 'section'));
	}
	const cartes = {};
	for (const m of propre.matchAll(/<div\b[^>]*class="[^"]*\becran-card\b[^"]*"[^>]*>/g)) {
		const page =
			m[0].match(/\bdata-page="([^"]+)"/)?.[1] ?? `(sans data-page, position ${m.index})`;
		cartes[page] = compterMots(element(propre, m.index, 'div'));
	}
	return { total: compterMots(propre), sections, cartes };
}

/** Les écarts entre une mesure et des plafonds — une ligne par écart, vide si tout tient. */
export function juger(mesure, plafonds, marge = MARGE) {
	const ecarts = [];
	const comparer = (quoi, compte, plafond) => {
		if (plafond === undefined) {
			ecarts.push(
				`${quoi} : ${compte} mots, sans plafond déclaré — le déclarer à sa longueur, la plus courte possible`,
			);
		} else if (compte > plafond) {
			ecarts.push(
				`${quoi} : ${compte} mots pour un plafond de ${plafond} — le manuel ne grossit pas (arbitrage du 07/09/2026, #3008)`,
			);
		} else if (plafond - compte > marge) {
			ecarts.push(
				`${quoi} : ${compte} mots, plafond ${plafond} — le texte a maigri, baisser le plafond à ${compte}`,
			);
		}
	};
	comparer('manuel entier', mesure.total, plafonds.total);
	for (const famille of ['sections', 'cartes']) {
		const declares = plafonds[famille] ?? {};
		for (const [cle, compte] of Object.entries(mesure[famille])) {
			comparer(`${famille === 'sections' ? 'section' : 'carte'} « ${cle} »`, compte, declares[cle]);
		}
		for (const cle of Object.keys(declares)) {
			if (!(cle in mesure[famille]))
				ecarts.push(`plafond de « ${cle} » (${famille}) : plus rien ne porte ce nom — le retirer`);
		}
	}
	return ecarts;
}

function autotest() {
	const html =
		'<style>.x{}</style><section id="a"><h2>Deux mots</h2>' +
		'<div class="ecran-card" data-page="/p"><div>l’état d’un lot&nbsp;: trois</div></div></section>';
	const m = mesurer(html);
	const attendu = { total: 6, sections: { a: 6 }, cartes: { '/p': 4 } };
	const fautes = [];
	if (JSON.stringify(m) !== JSON.stringify(attendu))
		fautes.push(`mesure ${JSON.stringify(m)} ≠ ${JSON.stringify(attendu)}`);
	const cas = [
		['juste', attendu, 0],
		['grossi', { total: 5, sections: { a: 6 }, cartes: { '/p': 4 } }, 1],
		['maigri sans baisser', { total: 6, sections: { a: 6 }, cartes: { '/p': 9 } }, 1],
		['carte sans plafond', { total: 6, sections: { a: 6 }, cartes: {} }, 1],
		['plafond orphelin', { total: 6, sections: { a: 6, b: 3 }, cartes: { '/p': 4 } }, 1],
	];
	for (const [nom, plafonds, nb] of cas) {
		const n = juger(m, plafonds, 2).length;
		if (n !== nb) fautes.push(`cas « ${nom} » : ${n} écart(s), ${nb} attendu(s)`);
	}
	if (fautes.length) {
		console.error('✗ Autotest de check-manuel-volume :\n  ' + fautes.join('\n  '));
		process.exit(1);
	}
	console.log(
		`✓ Autotest de check-manuel-volume : la mesure et ${cas.length} cas de jugement tiennent.`,
	);
}

const args = process.argv.slice(2);
if (args.includes('--selftest')) {
	autotest();
} else {
	const mesure = mesurer(readFileSync(join(RACINE, MANUEL), 'utf8'));
	if (args.includes('--mesurer')) {
		console.log(JSON.stringify(mesure, null, '\t'));
	} else {
		const ecarts = juger(mesure, PLAFONDS);
		if (ecarts.length) {
			console.error(`✗ Volume du manuel (${MANUEL}) :\n  • ${ecarts.join('\n  • ')}`);
			console.error(
				'\n  Les plafonds : scripts/check-manuel-volume.regles.mjs ; les comptes du jour : --mesurer.',
			);
			process.exit(1);
		}
		const n = Object.keys(mesure.cartes).length;
		console.log(
			`✓ Volume du manuel : ${mesure.total} mots, ${n} cartes d'écran, chacune sous son plafond.`,
		);
	}
}
