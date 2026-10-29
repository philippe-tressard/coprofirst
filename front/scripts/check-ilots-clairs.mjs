#!/usr/bin/env node
/**
 *  Un APERÇU de support imprimé ou envoyé reste CLAIR sous le thème sombre
 *  (#2174, lot S4d, 29/10/2026).
 *
 *  L'affiche du hall et le courriel sortent de l'application tels que le
 *  serveur les compose, sur papier ou dans une messagerie : leur aperçu se
 *  regarde POUR valider ce rendu. Au thème sombre, un aperçu qui suivrait le
 *  thème montrerait ce qui ne partira pas — le corps d'un modèle de courriel
 *  s'affichait en texte clair sur bleu nuit. La classe `.ilot-clair`
 *  (`styles/ilots-clairs.css`) lui rend les jetons du thème clair.
 *
 *  Ce qu'il exige :
 *
 *  1. tout `<iframe>` d'un composant porte `ilot-clair`, lui ou l'élément qui
 *     l'enveloppe — un cadre ne sert ici qu'à montrer un document rendu par le
 *     serveur (courriel, affiche), et c'est le cas qui se perd : son canevas
 *     paraît blanc par accident, le schéma du cadre différant de celui du
 *     document embarqué ;
 *  2. chaque support rendu SANS cadre, déclaré ci-dessous avec sa raison,
 *     porte la classe — la déclaration échoue si son élément disparaît ;
 *  3. la classe existe : partagée avec la règle `:root` de `socle.css`, et
 *     posant `color-scheme: light` dans `ilots-clairs.css`.
 *
 *  Lancer : node scripts/check-ilots-clairs.mjs [--selftest]
 */
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { neutraliserCommentaires } from './lib-commentaires.mjs';
import { fichiersSources } from './lib-source-unique.mjs';

const ICI = fileURLToPath(new URL('..', import.meta.url));
export const CLASSE = 'ilot-clair';

/**
 *  Les supports rendus SANS `<iframe>` : fichier → classe de l'élément qui les
 *  montre, et pourquoi il est un support.
 */
export const SUPPORTS = {
	'src/lib/components/OngletModelesEmail.svelte': {
		classe: 'apercu-email',
		raison: 'le corps d’un modèle de courriel, tel que le destinataire le lira',
	},
};

const VIDES = new Set([
	'area',
	'base',
	'br',
	'col',
	'embed',
	'hr',
	'img',
	'input',
	'link',
	'meta',
	'source',
	'track',
	'wbr',
]);

/** Les balises HTML d'une source, dans l'ordre — guillemets et accolades suivis. PURE. */
export function balisesDe(source) {
	const balises = [];
	const ouverture = /<(\/?)([a-zA-Z][\w:.-]*)/g;
	let m;
	while ((m = ouverture.exec(source))) {
		let i = m.index + m[0].length;
		let guillemet = '';
		let accolades = 0;
		while (i < source.length) {
			const c = source[i];
			if (guillemet) {
				if (c === guillemet) guillemet = '';
			} else if (c === '"' || c === "'" || c === '`') guillemet = c;
			else if (c === '{') accolades += 1;
			else if (c === '}') accolades = Math.max(0, accolades - 1);
			else if (c === '>' && accolades === 0) break;
			i += 1;
		}
		const texte = source.slice(m.index, i + 1);
		balises.push({
			nom: m[2],
			fermante: m[1] === '/',
			autoFermante: texte.endsWith('/>') || VIDES.has(m[2].toLowerCase()),
			texte,
			index: m.index,
		});
		ouverture.lastIndex = i + 1;
	}
	return balises;
}

/** La balise porte-t-elle la classe ? `class="… ilot-clair …"` ou `class:ilot-clair`. PURE. */
export function porteLaClasse(texte, classe = CLASSE) {
	const attribut = texte.match(/\sclass\s*=\s*(["'])([\s\S]*?)\1/);
	if (attribut && attribut[2].split(/\s+/).includes(classe)) return true;
	return new RegExp(`\\sclass:${classe}(?=[\\s=/>])`).test(texte);
}

/** La ligne (1-based) d'un index. PURE. */
const ligne = (source, index) => source.slice(0, index).split('\n').length;

/** Les balises du BALISAGE : hors commentaires, hors `<script>` et `<style>`. PURE. */
export function balisesDuBalisage(source) {
	const sortie = [];
	let dans = '';
	for (const b of balisesDe(neutraliserCommentaires(source))) {
		const nom = b.nom.toLowerCase();
		if (dans) {
			if (b.fermante && nom === dans) dans = '';
			continue;
		}
		if ((nom === 'script' || nom === 'style') && !b.fermante) {
			if (!b.autoFermante) dans = nom;
			continue;
		}
		sortie.push(b);
	}
	return sortie;
}

/** Les `<iframe>` hors îlot d'une source : `[ligne]`. PURE. */
export function cadresHorsIlot(source) {
	const fautes = [];
	const pile = [];
	for (const b of balisesDuBalisage(source)) {
		if (b.nom.toLowerCase() === 'iframe' && !b.fermante) {
			const parent = pile[pile.length - 1];
			if (!porteLaClasse(b.texte) && !(parent && porteLaClasse(parent.texte)))
				fautes.push(ligne(source, b.index));
		}
		if (b.fermante) {
			const k = pile.map((p) => p.nom).lastIndexOf(b.nom);
			if (k >= 0) pile.length = k;
		} else if (!b.autoFermante) pile.push(b);
	}
	return fautes;
}

/** Combien d'`<iframe>` dans le balisage d'une source. PURE. */
export const compteCadres = (source) =>
	balisesDuBalisage(source).filter((b) => b.nom.toLowerCase() === 'iframe' && !b.fermante).length;

/** L'élément de classe `classe` porte-t-il l'îlot ? `null` s'il n'existe plus. PURE. */
export function supportEnIlot(source, classe) {
	const b = balisesDuBalisage(source).find((x) => !x.fermante && porteLaClasse(x.texte, classe));
	return b ? porteLaClasse(b.texte) : null;
}

/** Les fautes de la définition de la classe. PURE. */
export function fautesDefinition(socle, feuille) {
	const fautes = [];
	const sans = (css) => css.replace(/\/\*[\s\S]*?\*\//g, '');
	if (!/^:root\s*,\s*\.ilot-clair\s*\{/m.test(sans(socle)))
		fautes.push(
			'socle.css : la règle `:root` ne porte plus `.ilot-clair` — l’îlot perd les jetons clairs',
		);
	const regle = sans(feuille).match(/^\.ilot-clair\s*\{([^}]*)\}/m);
	if (!regle || !/color-scheme\s*:\s*light\s*;/.test(regle[1]))
		fautes.push('ilots-clairs.css : `.ilot-clair` ne pose pas `color-scheme: light`');
	return fautes;
}

if (process.argv.includes('--selftest')) {
	let ko = 0;
	const cas = (nom, obtenu, attendu) => {
		const ok = JSON.stringify(obtenu) === JSON.stringify(attendu);
		if (!ok) ko = 1;
		console.log(`${ok ? '✓' : '✗'} ${nom}${ok ? '' : ` — obtenu ${JSON.stringify(obtenu)}`}`);
	};
	cas('un cadre nu est refusé', cadresHorsIlot('<div>\n<iframe srcdoc={x}></iframe>\n</div>'), [2]);
	cas(
		'un cadre en îlot passe',
		cadresHorsIlot('<iframe class="a ilot-clair" title="t"></iframe>'),
		[],
	);
	cas(
		'un cadre dont l’enveloppe est l’îlot passe, attribut à flèche compris',
		cadresHorsIlot(
			'<div class="cadre ilot-clair" on:click={() => a > b}>\n\t<iframe srcdoc={h}></iframe>\n</div>',
		),
		[],
	);
	cas(
		'l’îlot d’un grand-parent ne suffit pas',
		cadresHorsIlot('<div class="ilot-clair"><section><iframe></iframe></section></div>'),
		[1],
	);
	cas(
		'`ilot-claire` n’est pas `ilot-clair`',
		cadresHorsIlot('<iframe class="ilot-claire"></iframe>'),
		[1],
	);
	cas('`class:ilot-clair` passe', cadresHorsIlot('<iframe class:ilot-clair={vrai}></iframe>'), []);
	cas('un cadre en commentaire ne compte pas', compteCadres('<!-- <iframe></iframe> -->'), 0);
	cas(
		'un cadre cité dans le script ne compte pas',
		compteCadres('<script>const s = "<iframe>";</script><p></p>'),
		0,
	);
	cas(
		'un support déclaré sans îlot est refusé',
		supportEnIlot('<div class="apercu-email">x</div>', 'apercu-email'),
		false,
	);
	cas(
		'un support déclaré en îlot passe',
		supportEnIlot('<div class="apercu-email ilot-clair">x</div>', 'apercu-email'),
		true,
	);
	cas(
		'un support disparu se signale',
		supportEnIlot('<div class="autre">x</div>', 'apercu-email'),
		null,
	);
	cas(
		'la définition est lue',
		fautesDefinition(':root,\n.ilot-clair {\n}', '.ilot-clair {\n\tcolor-scheme: light;\n}').length,
		0,
	);
	cas(
		'une définition amputée est refusée deux fois',
		fautesDefinition(':root {\n}', '.ilot-clair {\n\tbackground: x;\n}').length,
		2,
	);
	console.log(ko ? '== ÉCHECS ==' : '== TOUS OK ==');
	process.exit(ko);
}

const lire = (chemin) => readFileSync(join(ICI, chemin), 'utf8');
const fautes = fautesDefinition(lire('src/styles/socle.css'), lire('src/styles/ilots-clairs.css'));
let cadres = 0;
for (const chemin of fichiersSources(join(ICI, 'src'), ['.svelte'])) {
	const rel = chemin.slice(chemin.indexOf('/src/') + 1);
	const source = readFileSync(chemin, 'utf8');
	cadres += compteCadres(source);
	for (const n of cadresHorsIlot(source))
		fautes.push(`${rel}:${n} : <iframe> hors d’un îlot clair`);
}
for (const [chemin, { classe }] of Object.entries(SUPPORTS)) {
	const verdict = supportEnIlot(lire(chemin), classe);
	if (verdict === null)
		fautes.push(`${chemin} : plus d’élément .${classe} — retirer la déclaration de SUPPORTS`);
	else if (!verdict) fautes.push(`${chemin} : .${classe} montre un support hors d’un îlot clair`);
}
//  Cas zéro (`standards/04` §2) : sans aucun cadre lu, la règle 1 ne mesure rien.
if (cadres === 0) {
	console.error('\n✗ Aucun <iframe> lu dans src/ : lecteur cassé, contrôle inopérant (INCONNU).\n');
	process.exit(2);
}
if (fautes.length) {
	console.error(`\n✗ ${fautes.length} aperçu(s) de support hors d’un îlot clair :\n`);
	for (const f of fautes) console.error(`  ${f}`);
	console.error(
		'\n  Poser `class="… ilot-clair"` sur le cadre ou sur son enveloppe ; un support rendu sans cadre se déclare dans SUPPORTS.\n',
	);
	process.exit(1);
}
console.log(
	`✓ Îlots clairs : ${cadres} cadre(s) et ${Object.keys(SUPPORTS).length} support(s) déclaré(s), tous en îlot`,
);
