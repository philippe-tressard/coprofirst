#!/usr/bin/env node
/**
 * Garde-fou : une case de Diffusion LIÉE doit être ENVOYÉE.
 *
 * ## 🔴 Le piège, rencontré deux fois le 31/08/2026
 *
 * Le matin, `demanderApercu` a été fourni à deux écrans sans que l'interception
 * le soit : tout avait l'air branché, et le message partait sans aperçu.
 * L'utilisateur l'a découvert **en recevant le mail**.
 *
 * La quatrième case de la Diffusion — « M'envoyer une copie » — a exactement la
 * même forme : un écran peut la lier (`bind:auteur={…}`) et ne jamais mettre
 * `envoyer_auteur` dans ce qu'il envoie. La case s'affiche, se coche, et ne fait
 * rien. Aucun contrôle existant ne le voit : `svelte-check` est vert, l'API est
 * correcte, et le seul symptôme est une copie qui n'arrive pas — c'est-à-dire
 * une absence, qui ne se remarque pas.
 *
 * ## Ce qui est vérifié
 *
 * Tout fichier qui lie `auteur` doit citer `envoyer_auteur` — dans sa charge
 * utile, ou en le passant à un composant qui l'enverra.
 *
 * ⚠️ **L'inverse n'est PAS vérifié.** Un écran peut légitimement envoyer
 * `envoyer_auteur` sans lier la case : c'est le cas d'un relais qui reçoit la
 * valeur en propriété. Exiger les deux ferait crier sur du légitime, et un
 * contrôle qui crie sur du légitime finit désarmé (leçon de C16).
 *
 * Usage : npm run lint:diffusion-auteur
 */
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { dirname, join, relative, sep } from 'node:path';
import { fileURLToPath } from 'node:url';

import { neutraliserCommentaires as sansCommentaires } from './lib-commentaires.mjs';

const RACINE = join(dirname(fileURLToPath(import.meta.url)), '..');
const SOURCE = join(RACINE, 'src');

/**
 * Les composants qui PORTENT la case ou la relaient sans rien envoyer.
 *
 * `CanauxNotification` la déclare ; `SectionDiffusion` et `ChampsCommuns` la
 * transmettent. Aucun des trois ne compose de charge utile — c'est l'écran qui
 * sait ce qu'il envoie, et à qui.
 */
const RELAIS = [
	'lib/components/CanauxNotification.svelte',
	'lib/components/SectionDiffusion.svelte',
	'lib/components/ChampsCommuns.svelte',
	//  Ajouté le 01/09/2026 (#480) : ce formulaire pose la Diffusion, et c'est
	//  l'onglet qui l'héberge qui compose la charge utile. Même structure que les
	//  trois autres — et le contrôle suit désormais le SECOND saut, voir plus bas.
	'lib/components/FormulaireAnnonceHall.svelte',
];

function fichiers(dir) {
	const sortie = [];
	for (const nom of readdirSync(dir)) {
		const chemin = join(dir, nom);
		if (statSync(chemin).isDirectory()) sortie.push(...fichiers(chemin));
		else if (nom.endsWith('.svelte')) sortie.push(chemin);
	}
	return sortie;
}

const tous = fichiers(SOURCE);
//  Cas zéro : sans fichiers lus, « aucun écart » ne veut rien dire.
if (tous.length < 50) {
	console.error(
		`\n✗ Cas zéro : ${tous.length} fichier(s) analysé(s), au moins 50 attendus —\n` +
			'  le parcours ne correspond plus à `src/`.\n',
	);
	process.exit(1);
}

//  Le module qui compose la charge utile d'une affaire : un écran qui l'appelle envoie ce
//  qu'il cite. Lu ici, et exigé — un module qui ne citerait plus `envoyer_auteur` ferait
//  échouer l'écran qui s'y fie, au lieu de le laisser passer sur la foi d'un nom.
const DELEGUE = /\bchargeUtileAffaire\(/;
const chargeAffaireEnvoie = /envoyer_auteur/.test(
	sansCommentaires(readFileSync(join(SOURCE, 'lib/formulaire-affaire.ts'), 'utf8')),
);
const lient = [];
const fautifs = [];
//  🔴 LE TROU QUE CE CONTRÔLE N'A PAS VU (31/08/2026).
//
//  Il ne regardait QUE les écrans qui lient `bind:auteur`, et il écartait les
//  relais. Or c'est le relais qui AFFICHE la case : un écran pouvait employer
//  `ChampsCommuns avecDiffusion` sans jamais lier `auteur`, et la case
//  s'affichait alors, se cochait, et n'allait nulle part — ni dans la charge
//  utile, ni dans un champ du serveur.
//
//  C'était vrai de CINQ écrans — actualité, sondage, événement… — pendant que ce
//  contrôle annonçait « 6 écrans lient la case, et tous l'envoient ». Il disait
//  vrai, et il mesurait la mauvaise chose : *un contrôle qui ne regarde que ce
//  qui est branché ne voit jamais ce qui ne l'est pas.*
//
//  Deux vérifications désormais : qui LIE la case l'envoie, et qui l'AFFICHE la lie.
const orphelins = [];
for (const chemin of tous) {
	const rel = relative(SOURCE, chemin).split(sep).join('/');
	const source = sansCommentaires(readFileSync(chemin, 'utf8'));
	if (RELAIS.includes(rel)) continue;
	//  ⚠️ La case n'apparaît QUE si les canaux sont rendus. `ChampsCommuns` les
	//  rend par défaut (`avecCanaux = true`), et un écran peut les couper
	//  explicitement — c'est le cas de l'annonce, dont la Diffusion ne porte
	//  que l'affiche de hall. La couper est une décision légitime ; ne pas lier
	//  la case tout en la montrant ne l'est pas.
	//
	//  🔴 Sans cette nuance le contrôle criait sur du légitime — et un contrôle
	//  qui crie sur du légitime finit désarmé (leçon de C16).
	const montreLesCanaux =
		/\bavecDiffusion\b|<SectionDiffusion|<CanauxNotification/.test(source) &&
		!/avecCanaux={false}/.test(source);
	if (montreLesCanaux && !/bind:auteur\b/.test(source)) {
		orphelins.push(rel);
	}
	//  🔴 LE SECOND SAUT. Un écran ne lie pas toujours `auteur` directement : il
	//  peut lier la prop d'un relais (`bind:envoyerAuteur={…}`), et c'est LUI qui
	//  compose la charge utile. Sans cette ligne, le relais serait exempté et son
	//  hôte invisible — la case reviendrait à ne rien faire, par un chemin de plus.
	if (!/bind:auteur\b|bind:envoyerAuteur\b/.test(source)) continue;
	lient.push(rel);
	//  Citer `envoyer_auteur` dans sa charge utile, OU composer celle-ci par
	//  `chargeUtileAffaire` — qui l'écrit (#2595 : le formulaire d'affaire ne la compose plus).
	if (!/envoyer_auteur/.test(source) && !(DELEGUE.test(source) && chargeAffaireEnvoie)) {
		fautifs.push(rel);
	}
}

//  🔴 Le relevé légitime est VIDE : il ne peut pas distinguer « rien trouvé » de
//  « rien lu ». Le témoin est le nombre d'écrans qui lient réellement la case.
if (lient.length === 0) {
	console.error(
		'\n✗ Cas zéro : aucun écran ne lie `bind:auteur`. Soit la propriété a été\n' +
			'  renommée, soit plus personne n’offre la copie — ne pas lire ceci comme\n' +
			'  un succès.\n',
	);
	process.exit(1);
}

if (orphelins.length) {
	console.error('\n✗ Écran(s) qui AFFICHENT la case sans jamais la lire :\n');
	for (const f of orphelins) console.error(`   ${f}`);
	console.error(
		'\n  🔴 La case s’affiche, se coche, et ne va nulle part. C’est le défaut' +
			'\n  du 31/08/2026 : cinq écrans dans cet état, et ce contrôle vert.' +
			'\n\n  Lier `bind:auteur={…}`, passer `auteurNom`, mettre `envoyer_auteur`' +
			'\n  dans la charge utile — et vérifier que le SERVEUR le consomme.\n',
	);
	process.exit(1);
}

if (fautifs.length) {
	console.error('\n✗ Case « M’envoyer une copie » liée mais JAMAIS envoyée :\n');
	for (const f of fautifs) console.error(`   ${f}`);
	console.error(
		'\n  🔴 La case s’affiche, se coche, et ne fait rien. Aucun autre contrôle ne' +
			'\n  le voit : svelte-check est vert, l’API est correcte, et le seul symptôme' +
			'\n  est une copie qui n’arrive pas — une absence, qui ne se remarque pas.' +
			'\n\n  Ajouter `envoyer_auteur` à la charge utile de cet écran.\n',
	);
	process.exit(1);
}

console.log(
	`✓ Diffusion : ${lient.length} écran(s) lient « Envoyer une copie à … », tous ` +
		`l’envoient, et aucun ne l’affiche sans la lire (${tous.length} composants vérifiés).`,
);
