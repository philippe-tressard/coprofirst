#!/usr/bin/env node
/**
 * Garde-fou : la nature d'une pièce jointe et son nom d'affichage ne se
 * redécident pas dans une page.
 *
 * Le 03/08/2026, l'ajout des pièces jointes documentaires aux tickets et aux
 * affaires a mis au jour quinze copies de trois règles minuscules :
 *
 *   1. `/\.(jpe?g|png|webp)$/i` — « est-ce une image ? », écrit huit fois. Aucune
 *      des huit ne connaissait `.gif`, pourtant accepté par le serveur : un GIF
 *      téléversé s'affichait en pastille de document, sans vignette.
 *   2. `url.split('/').pop()` — le nom affiché, écrit sept fois. Depuis que le
 *      serveur conserve le nom d'origine (`{uuid}_{nom}.pdf`), il faut aussi
 *      retirer le préfixe technique : sept endroits à corriger au lieu d'un.
 *   3. La liste `accept` du sélecteur de fichiers, écrite trois fois, déjà
 *      divergente entre les pages.
 *
 * `#lib/fichiers.ts` porte les trois (`estImage`, `nomFichier`,
 * `ACCEPT_PHOTOS` / `ACCEPT_DOCUMENTS` / `ACCEPT_FICHIERS`) et
 * `api/tests/test_pieces_jointes.py` vérifie qu'elles restent alignées sur la
 * liste blanche du serveur — qui, elle, fait autorité.
 *
 * Script Node sans dépendance, même parti pris que `check-dates.mjs` : le projet
 * n'a pas de lanceur de tests front.
 *
 * Usage : npm run lint:fichiers   (exit 1 si violation)
 */
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { dirname, join, relative } from 'node:path';
import { fileURLToPath } from 'node:url';
import { neutraliserCommentaires } from './lib-commentaires.mjs';

const RACINE = join(dirname(fileURLToPath(import.meta.url)), '..');

/** Porte légitimement ces règles : c'est la source de vérité. */
const EXEMPTS = new Set(['src/lib/fichiers.ts']);

const MOTIFS = [
	{
		regex: /jpe\?g/,
		message: "test d'extension d'image réécrit — utiliser estImage() de #lib/fichiers",
	},
	{
		regex: /\.split\(\s*['"]\/['"]\s*\)\s*\.pop\(\)/,
		message: "nom de fichier dérivé d'une URL — utiliser nomFichier() de #lib/fichiers",
	},
	{
		// Volontairement restreint à la forme MIME `application/pdf` : c'est
		// celle que produisent les sélecteurs branchés sur POST /uploads/fichier,
		// donc ceux qui recopient la liste blanche du serveur. Les sélecteurs par
		// extension des écrans d'import (`.xlsx` pour les lots, les Vigik, les
		// télécommandes) visent d'autres endpoints, avec leurs propres formats :
		// les inclure ferait échouer le contrôle sur du code parfaitement sain,
		// et un contrôle qui crie à tort finit par être ignoré.
		regex: /accept\s*=\s*["'][^"']*application\/pdf[^"']*["']/,
		message: 'liste accept en dur — utiliser ACCEPT_DOCUMENTS / ACCEPT_FICHIERS',
	},
	{
		//  🔴 Le champ qui NOMME un document déposé, signalé à l'écran le
		//  11/09/2026 : les contrats en portaient un, écrit à la main juste avant
		//  leur bouton d'ajout ; les tickets n'en avaient aucun. Deux gestes pour
		//  une même chose, dont un seul existait.
		//
		//  Il vit désormais dans `FichiersUpload` (`avecLibelle`), comme le reste
		//  du dépôt de fichier. Ce motif attrape la tentation de le réécrire à
		//  côté : un champ de titre collé au composant de dépôt.
		//
		//  ⚠️ Il vise le LIBELLÉ du fichier, pas tout champ nommé « titre » : la
		//  condition est la proximité d'un `aria-label`/`placeholder` de titre de
		//  document. Un titre d'actualité ou de ticket n'est pas concerné.
		regex: /(?:placeholder|aria-label)\s*=\s*["'][^"']*[Tt]itre du document[^"']*["']/,
		message: 'champ de libellé de document réécrit — employer `avecLibelle` sur FichiersUpload',
	},
];

const estCommentaire = (l) => {
	const t = l.trim();
	return t.startsWith('//') || t.startsWith('*') || t.startsWith('/*') || t.startsWith('<!--');
};

function collecter(dir, acc = []) {
	for (const e of readdirSync(dir)) {
		if (e === 'node_modules' || e === '.svelte-kit' || e === 'build') continue;
		const p = join(dir, e);
		if (statSync(p).isDirectory()) collecter(p, acc);
		else if (/\.(ts|js|mjs|svelte)$/.test(e)) acc.push(p);
	}
	return acc;
}

/**
 * Règle multi-lignes : une galerie de lecture ne se conditionne pas à l'identité.
 *
 * Le bloc des petites annonces a privé de galerie **deux publics successifs** :
 * d'abord le lecteur d'une annonce à une seule photo (`> 1 || est_auteur`), puis
 * son auteur (`&& !est_auteur`) — corrigé le 14/08/2026 (#338). Le défaut a
 * changé de victime sans disparaître, et rien ne le signalait : il ne se voit
 * qu'en ouvrant une annonce depuis le compte qui l'a déposée.
 *
 * `format="grand"` est le rendu du contenu DÉPLIÉ : à ce moment l'utilisateur a
 * demandé à voir, et qui il est ne change pas ce qu'on lui montre. Ce qui dépend
 * de l'identité, ce sont les actions — modifier, retirer —, pas l'affichage.
 */
function galerieConditionneeALIdentite(texte) {
	const lignes = texte.split('\n');
	const trouves = [];
	lignes.forEach((ligne, i) => {
		if (!/<PiecesJointes/.test(ligne) || !/format\s*=\s*["']grand["']/.test(ligne)) return;
		//  Les trois lignes qui précèdent, commentaires exclus : une condition
		//  d'identité y serait le `{#if}` qui gouverne cette galerie.
		for (let j = Math.max(0, i - 3); j < i; j++) {
			if (estCommentaire(lignes[j])) continue;
			if (/\{#if\b/.test(lignes[j]) && /est_auteur|estAuteur|isAuteur/.test(lignes[j])) {
				trouves.push({ ligne: i + 1, condition: lignes[j].trim() });
				break;
			}
		}
	});
	return trouves;
}

/**
 *  🔴 Le SÉLECTEUR de fichiers est `FichiersUpload`, et il n'y en a pas d'autre
 *  (27/09/2026, #1329). `FormulaireDocument` — plans, règlement, CR d'AG,
 *  diagnostics — gardait un `<input type="file">` nu : le bouton du navigateur,
 *  « Parcourir… aucun fichier sélectionné », à côté du bouton 📎 et des
 *  pastilles de tous les autres dépôts. Deux rendus pour une notion.
 *
 *  Les exceptions sont des GESTES différents, déclarés avec leur raison ; une
 *  exception qui ne sert plus fait échouer le contrôle.
 */
const SELECTEURS_NATIFS = {
	'src/lib/components/FichiersUpload.svelte': 'le composant lui-même',
	'src/lib/components/ImageUpload.svelte': 'une image unique, remplacée sur place (avatar, logo)',
	'src/lib/components/BarreImport.svelte': "l'import d'un tableur, qui n'est pas une pièce jointe",
	'src/lib/components/BanniereResidence.svelte':
		'« Changer la photo » posé SUR la bannière : la photo se remplace là où on la voit',
};
const SELECTEUR_NATIF = /type\s*=\s*["']file["']/;
const servis = new Set();

const cibles = collecter(join(RACINE, 'src'));
const fautifs = [];

for (const p of cibles) {
	const rel = relative(RACINE, p).replace(/\\/g, '/');
	if (EXEMPTS.has(rel)) continue;
	const contenu = readFileSync(p, 'utf-8');
	//  Longueurs conservées : la ligne i du texte neutralisé est la ligne i du fichier.
	const neutre = neutraliserCommentaires(contenu).split('\n');

	for (const { ligne, condition } of galerieConditionneeALIdentite(contenu)) {
		fautifs.push(
			`  ${rel}:${ligne} — galerie de lecture conditionnée à l'identité : ` +
				`déplier montre les photos à tout le monde, l'identité ne gouverne que les actions\n      ${condition}`,
		);
	}

	contenu.split('\n').forEach((ligne, i) => {
		if (estCommentaire(ligne)) return;
		if (rel.endsWith('.svelte') && SELECTEUR_NATIF.test(neutre[i] ?? '')) {
			if (SELECTEURS_NATIFS[rel]) servis.add(rel);
			else
				fautifs.push(
					`  ${rel}:${i + 1} — sélecteur de fichiers natif : employer FichiersUpload (\`differe\` si l'objet n'existe pas encore)\n      ${ligne.trim()}`,
				);
		}
		for (const { regex, message } of MOTIFS) {
			if (regex.test(ligne)) fautifs.push(`  ${rel}:${i + 1} — ${message}\n      ${ligne.trim()}`);
		}
	});
}

for (const f of Object.keys(SELECTEURS_NATIFS))
	if (!servis.has(f))
		fautifs.push(`  ${f} — exception de sélecteur natif qui ne sert plus : la retirer`);

if (fautifs.length > 0) {
	console.error(
		`\n✗ ${fautifs.length} règle(s) de pièce jointe réécrite(s) hors de #lib/fichiers.ts :\n\n` +
			fautifs.join('\n') +
			`\n\n  Une règle recopiée diverge : c'est ainsi que .gif s'est retrouvé classé` +
			`\n  « document » dans les huit copies du test d'image.\n`,
	);
	process.exit(1);
}

console.log(`✓ ${cibles.length} fichiers analysés — aucune règle de pièce jointe réécrite.`);
