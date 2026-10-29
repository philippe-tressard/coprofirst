#!/usr/bin/env node
/*
 *  Auto-test de `memePrompt` (`#lib/assistant.ts`) — « ce texte est-il le prompt
 *  d'origine ? », la question que l'écran d'administration pose à chaque usage
 *  de l'assistant IA (#994).
 *
 *  ## Pourquoi un contrôle pour trois lignes
 *
 *  Ce n'est pas la comparaison qui est fragile, c'est sa NORMALISATION. Un
 *  prompt collé depuis un éditeur Windows ne diffère de l'original que par ses
 *  `\r\n` : sans normalisation, l'écran annonce « Prompt modifié » à quelqu'un
 *  qui n'a rien modifié — exactement le signal trompeur que #994 vient
 *  supprimer. Et une normalisation trop large ferait l'inverse : deux prompts
 *  réellement différents déclarés identiques, donc une version plus récente
 *  jamais signalée.
 *
 *  Le pattern est celui des scripts d'infra — fonction PURE + `--selftest` — et
 *  Node lit le module TypeScript directement : le code éprouvé est CELUI QUE LE
 *  SITE EMBARQUE, pas une copie.
 *
 *  Usage : node scripts/check-prompt-origine.mjs --selftest
 */
import { memePrompt } from '../src/lib/promptOrigine.ts';

const ORIGINE = 'Tu rédiges la synthèse.\n\n- une règle\n- une autre\n';

const CAS = [
	['un texte identique est reconnu', ORIGINE, ORIGINE, true],
	['la clé vide n’est pas l’origine', '', ORIGINE, false],
	['null n’est pas l’origine', null, ORIGINE, false],
	['deux vides sont égaux', '', null, true],
	//  🔴 Le cas qui motive le contrôle : un copier-coller depuis Windows.
	['les fins de ligne CRLF ne comptent pas', ORIGINE.replace(/\n/g, '\r\n'), ORIGINE, true],
	['un CR seul ne compte pas', ORIGINE.replace(/\n/g, '\r'), ORIGINE, true],
	['les espaces de fin de ligne ne comptent pas', ORIGINE.replace(/\n/g, '   \n'), ORIGINE, true],
	['les blancs autour ne comptent pas', `\n\n  ${ORIGINE}  \n`, ORIGINE, true],
	//  Et ce qu'il ne doit PAS avaler : une différence de fond, aussi petite
	//  qu'elle soit. Une normalisation trop large tairait la version récente.
	['un mot changé compte', ORIGINE.replace('une autre', 'une troisième'), ORIGINE, false],
	['une règle ajoutée compte', `${ORIGINE}- une de plus\n`, ORIGINE, false],
	[
		'une ligne vide EN PLUS au milieu compte',
		ORIGINE.replace('- une règle', '\n- une règle'),
		ORIGINE,
		false,
	],
	[
		'un espace AU MILIEU d’une ligne compte',
		ORIGINE.replace('une  règle', 'une règle').replace('une règle', 'une  règle'),
		ORIGINE,
		false,
	],
];

const echecs = [];
for (const [nom, a, b, attendu] of CAS) {
	const obtenu = memePrompt(a, b);
	if (obtenu !== attendu) echecs.push(`${nom} — attendu ${attendu}, obtenu ${obtenu}`);
	//  La comparaison est SYMÉTRIQUE : l'écran l'appelle dans un sens, rien ne
	//  garantit que le suivant fera de même.
	if (memePrompt(b, a) !== attendu) echecs.push(`${nom} — asymétrique`);
}

if (echecs.length) {
	console.error(`\n✗ check-prompt-origine : ${echecs.length} cas en échec\n`);
	for (const e of echecs) console.error(`   • ${e}`);
	process.exit(1);
}
console.log(
	`✓ check-prompt-origine — ${CAS.length} cas : fins de ligne, espaces de fin, ` +
		`blancs autour, et les différences de fond qui doivent RESTER visibles.`,
);
