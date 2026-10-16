#!/usr/bin/env node
/**
 * Garde-fou : un aperçu de diffusion FOURNI doit être OUVERT (#498).
 *
 * ## 🔴 Le défaut, et il a coûté un envoi réel (31/08/2026)
 *
 * Brancher l'aperçu sur un écran demande **deux** gestes, et non un :
 *
 *   1. fournir la fonction   → `demanderApercu={…}`
 *   2. s'intercaler dans la soumission → `if (ref?.ouvrirSiDiffusion(…)) return;`
 *
 * Le lot du 31/08 a fait le premier sur les actualités et le calendrier, et
 * **oublié le second**. Tout avait l'air branché : l'endpoint répondait, la
 * fonction était passée, la modale savait s'ouvrir — et personne ne l'ouvrait.
 *
 * L'utilisateur l'a découvert **en recevant le mail** :
 *
 * > « Non, ça n'a pas marché, j'ai envoyé un mail !!! sans possibilité d'annuler »
 *
 * ⚠️ Rien ne pouvait le signaler. `svelte-check` est vert : les deux moitiés
 * compilent séparément. Les tests du serveur sont verts : l'endpoint est correct.
 * Le seul symptôme est un message parti — c'est-à-dire le dommage lui-même.
 *
 * ## Pourquoi ce contrôle et pas un test
 *
 * Le défaut est une **absence** dans le chemin de soumission, et une absence ne
 * se teste pas à l'exécution sans piloter un navigateur. Ici, la forme suffit et
 * elle est décidable : `demanderApercu` sans `ouvrirSiDiffusion` dans le même
 * fichier est **toujours** un oubli — il n'existe aucune raison de fournir un
 * aperçu qu'on n'ouvre jamais.
 *
 * ⚠️ L'inverse est vérifié aussi : `ouvrirSiDiffusion` sans `demanderApercu`
 * ouvrirait une modale que rien ne remplit.
 *
 * Usage : node scripts/check-apercu-branche.mjs
 */
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { dirname, join, relative, sep } from 'node:path';
import { fileURLToPath } from 'node:url';

import { neutraliserCommentaires as sansCommentaires } from './lib-commentaires.mjs';

const RACINE = join(dirname(fileURLToPath(import.meta.url)), '..');
const SOURCE = join(RACINE, 'src');

/**
 * L'objet qui PORTE l'aperçu : il déclare les deux moitiés, il ne les emploie
 * pas. Le contrôle ne le lit donc pas — sans quoi il s'accuserait lui-même.
 */
const PORTEUR = 'lib/components/SectionDiffusion.svelte';

/**
 * Le RELAIS : il transmet `demanderApercu` et `refDiffusion` à l'objet, sans
 * décider de la soumission. C'est l'écran qui l'emploie qui doit intercepter.
 */
const RELAIS = 'lib/components/ChampsCommuns.svelte';

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
//  Cas zéro : sans fichiers lus, « aucun écart » ne veut rien dire
//  (`standards/04` §27).
if (tous.length < 50) {
	console.error(
		`✗ Cas zéro : ${tous.length} fichier(s) analysé(s), au moins 50 attendus — ` +
			'le parcours ne correspond plus à `src/`.',
	);
	process.exit(1);
}

/**
 * Les composants qui interceptent eux-mêmes, indexés par leur nom de balise.
 *
 * 🔴 SANS CELA, LE CONTRÔLE ACCUSE LES RELAIS. `CarteTicket` et
 * `HistoriqueTicket` (retiré le 15/10/2026) passaient `demanderApercu` à `EvolForm`, qui porte le
 * formulaire ET l'interception : ils ont raison de ne pas intercepter
 * eux-mêmes, et le contrôle les refusait.
 *
 * ⚠️ La liste est **calculée**, jamais tenue à la main — une liste recopiée
 * diverge au premier composant ajouté, et c'est justement celui-là qui échappe.
 */
function composantsQuiInterceptent(fichiers) {
	const noms = new Set();
	for (const chemin of fichiers) {
		const source = sansCommentaires(readFileSync(chemin, 'utf8'));
		if (/ouvrirSiDiffusion\s*\(/.test(source)) {
			noms.add(
				chemin
					.split(sep)
					.pop()
					.replace(/\.svelte$/, ''),
			);
		}
	}
	return noms;
}

const INTERCEPTEURS = composantsQuiInterceptent(tous);

const fournissent = [];
const fautifs = [];
for (const chemin of tous) {
	const rel = relative(SOURCE, chemin).split(sep).join('/');
	if (rel === PORTEUR || rel === RELAIS) continue;
	const source = sansCommentaires(readFileSync(chemin, 'utf8'));
	const fournit = /demanderApercu\s*=\s*\{/.test(source);
	const ouvre = /ouvrirSiDiffusion\s*\(/.test(source);
	//  Un RELAIS confie la prop à un composant qui, lui, intercepte. Il n'a donc
	//  pas à le faire — c'est même ce qu'on veut : une seule interception par
	//  formulaire, chez celui qui porte le geste.
	const relaye = [...INTERCEPTEURS].some(
		(n) =>
			n !==
				chemin
					.split(sep)
					.pop()
					.replace(/\.svelte$/, '') && new RegExp(`<${n}\\b`).test(source),
	);
	if (fournit) fournissent.push(rel);
	if (fournit && !ouvre && !relaye) {
		fautifs.push({
			rel,
			quoi: "fournit `demanderApercu` mais n'appelle jamais `ouvrirSiDiffusion`",
			remede: 'dans le geste de soumission : `if (refDiffusion?.ouvrirSiDiffusion()) return;`',
		});
	}
	if (ouvre && !fournit) {
		fautifs.push({
			rel,
			quoi: 'appelle `ouvrirSiDiffusion` sans fournir `demanderApercu`',
			remede: 'la modale s’ouvrirait vide — passer `demanderApercu={…}` à la section',
		});
	}
}

//  🔴 Le relevé légitime de ce contrôle est VIDE : il ne peut donc pas
//  distinguer « rien trouvé » de « rien lu ». Le témoin est le nombre d'écrans
//  qui fournissent réellement un aperçu — s'il tombe à zéro, ce n'est pas que
//  tout est conforme, c'est que le motif ne mord plus.
if (fournissent.length === 0) {
	console.error(
		'✗ Cas zéro : aucun écran ne fournit `demanderApercu`. Soit la prop a été ' +
			'renommée, soit plus personne n’a d’aperçu — ne pas lire ceci comme un succès.',
	);
	process.exit(1);
}

if (fautifs.length > 0) {
	console.error('✗ Aperçu de diffusion à moitié branché :\n');
	for (const f of fautifs) {
		console.error(`   ${f.rel}`);
		console.error(`       ${f.quoi}`);
		console.error(`       → ${f.remede}`);
	}
	console.error(
		'\n  🔴 Brancher l’aperçu demande DEUX gestes : fournir la fonction, et' +
			'\n  s’intercaler dans la soumission. Le premier seul donne un écran qui a' +
			'\n  l’air branché — endpoint correct, modale prête — et qui envoie sans' +
			'\n  jamais rien montrer. C’est arrivé le 31/08/2026, et le seul symptôme' +
			'\n  a été un mail reçu par ses destinataires.\n',
	);
	process.exit(1);
}

console.log(
	`✓ Aperçu de diffusion : ${fournissent.length} écran(s) le fournissent, et tous ` +
		`l’ouvrent (${tous.length} composants vérifiés).`,
);
