/**
 * Garde-fou : une couche superposée (modale, visionneuse…) emprunte le
 * défilement du document et la touche Échap par UNE seule porte —
 * `poserCouche` (`#lib/couche.ts`).
 *
 * ## Pourquoi ce contrôle existe (#1042, 24/09/2026)
 *
 * Le verrou de défilement du `<body>` était écrit DEUX fois, avec deux
 * sémantiques : un compteur partagé dans `Modale`, un booléen par instance dans
 * `Lightbox`. Une visionneuse ouverte DEPUIS une modale (les pièces jointes d'un
 * formulaire d'édition) rendait le défilement en se fermant : la modale restait
 * ouverte, et la page défilait derrière — le défaut exact que le commentaire de
 * `Modale` décrivait. Et chacune écoutait Échap sur `window` : une seule
 * pression fermait la visionneuse ET la modale sous elle, saisie comprise.
 *
 * C'est une mutation d'état global (`standards/11-interface-et-ux.md` §12) :
 * deux écritures d'un bien commun ne se coordonnent pas, elles se marchent
 * dessus.
 *
 * ## Ce qui est interdit hors de `#lib/couche.ts`
 *
 *   1. écrire `body.style.overflow` ;
 *   2. traiter `Escape` dans un écouteur de `<svelte:window>` — Échap ne ferme
 *      que la couche du DESSUS, et seule la pile du module la connaît. Une
 *      bulle qui ne fige pas la page y entre par `poserEchap` (`Infobulle`).
 *      Un `on:keydown` posé sur un champ (annuler une saisie) reste permis :
 *      il ne s'entend que là où l'on tape.
 *
 * Le contrôle s'auto-contrôle (`standards/04-fiabilite-des-controles.md` §2,
 * cas zéro) : module absent, fonction renommée, ou plus aucun appelant → échec.
 *
 * Usage : npm run lint:couches
 */
import { readFileSync, readdirSync, statSync, existsSync } from 'node:fs';
import { join, relative, sep } from 'node:path';
import { neutraliserCommentaires } from './lib-commentaires.mjs';

const RACINE = new URL('../src', import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, '$1');
const MODULE = join(RACINE, 'lib', 'couche.ts');
//  Les deux couches du site. Si l'une cesse d'appeler le module, elle a
//  retrouvé sa propre écriture — ou elle a disparu, et la liste doit le dire.
const APPELANTS_ATTENDUS = ['lib/components/Modale.svelte', 'lib/components/Lightbox.svelte'];

function fichiers(dir) {
	const sortie = [];
	for (const nom of readdirSync(dir)) {
		const chemin = join(dir, nom);
		if (statSync(chemin).isDirectory()) sortie.push(...fichiers(chemin));
		else if (/\.(svelte|ts|js)$/.test(nom)) sortie.push(chemin);
	}
	return sortie;
}

const rel = (f) => relative(RACINE, f).split(sep).join('/');

//  ── Auto-contrôle (cas zéro) ────────────────────────────────────────────────
if (!existsSync(MODULE)) {
	console.error(`✗ Cas zéro : ${MODULE} est introuvable — contrôle inopérant.`);
	process.exit(1);
}
if (!/export function poserCouche\b/.test(readFileSync(MODULE, 'utf8'))) {
	console.error(
		"✗ Cas zéro : `#lib/couche.ts` n'exporte plus `poserCouche` — le contrat a changé.",
	);
	process.exit(1);
}
const tous = fichiers(RACINE).filter((f) => f !== MODULE);
if (tous.length === 0) {
	console.error("✗ Cas zéro : aucun fichier analysé — l'arborescence a changé.");
	process.exit(1);
}

//  ── Recherche ───────────────────────────────────────────────────────────────
const ecarts = [];
const appelants = new Set();
for (const f of tous) {
	const source = neutraliserCommentaires(readFileSync(f, 'utf8'));
	if (/\bposerCouche\s*\(/.test(source)) appelants.add(rel(f));
	if (/body\.style\.overflow/.test(source)) {
		ecarts.push(`${rel(f)} : écrit \`body.style.overflow\` — passer par poserCouche()`);
	}
	//  La balise entière, jusqu'à `/>` : `[^>]*` s'arrêtait au `=>` du premier
	//  gestionnaire, et un `on:keydown` posé après lui passait (`PastilleLecture`,
	//  jusqu'au 15/10/2026).
	const fenetre = (source.match(/<svelte:window\b[\s\S]*?\/>/g) ?? []).join(' ');
	if (/on:keydown/.test(fenetre) && /['"`]Escape['"`]/.test(source)) {
		ecarts.push(
			`${rel(f)} : traite Échap sur <svelte:window> — passer par poserCouche(fermer), ` +
				'qui ne ferme que la couche du dessus',
		);
	}
}
for (const attendu of APPELANTS_ATTENDUS) {
	if (!appelants.has(attendu)) {
		ecarts.push(`${attendu} : n'appelle plus poserCouche() — couche qui gère seule le document`);
	}
}

if (ecarts.length) {
	console.error(`✗ ${ecarts.length} écart(s) — la couche passe par #lib/couche.ts :\n`);
	for (const e of ecarts) console.error(`  ${e}`);
	process.exit(1);
}
console.log(
	`✓ Couches : ${tous.length} fichiers, ${appelants.size} appelant(s) de poserCouche ` +
		`(${[...appelants].sort().join(', ')}), aucun verrou ni Échap global hors du module.`,
);
