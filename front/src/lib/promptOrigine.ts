/**
 *  « Ce prompt est-il celui d'ORIGINE ? » — la question que l'écran
 *  d'administration pose à chaque usage de l'assistant IA (#994).
 *
 *  ## Pourquoi cette comparaison existe
 *
 *  L'écran disait « Prompt modifié » dès que la clé était non vide : il
 *  comparait au VIDE, pas au texte livré. Deux conséquences, et Philippe a buté
 *  sur la seconde le 17/09/2026 :
 *
 *  · un texte collé identique à l'origine s'annonçait « modifié » ;
 *  · rien ne disait qu'une version plus récente de l'origine était arrivée avec
 *    le déploiement, puisque l'écran ne regardait jamais l'origine.
 *
 *  ## 🔴 Ce module n'importe RIEN, et c'est sa raison d'être
 *
 *  Node le lit directement (`scripts/check-prompt-origine.mjs --selftest`, en
 *  CI) : le code éprouvé est donc CELUI QUE LE SITE EMBARQUE, pas une copie.
 *  Le premier jet vivait dans `#lib/assistant.ts`, qui importe `#lib/utils` —
 *  et un alias `#lib` ne se résout pas hors de Vite. Un module pur se teste, un
 *  module lié ne se teste qu'avec tout son graphe.
 */

/**
 *  Le texte enregistré est-il, au caractère près, le prompt d'origine livré ?
 *
 *  ⚠️ La comparaison NORMALISE les fins de ligne et les espaces de fin de ligne.
 *  Sans cela, un texte collé depuis un éditeur Windows différerait par ses seuls
 *  `\r\n` — et l'écran annoncerait une divergence que personne n'a écrite, ce
 *  qui est précisément le signal trompeur qu'on vient supprimer.
 *
 *  ⚠️ Et elle ne normalise QUE cela : un espace au milieu d'une ligne, une ligne
 *  vide de plus, un mot changé comptent. Une normalisation plus large tairait la
 *  version récente au lieu de la signaler.
 */
export function memePrompt(a: string | null | undefined, b: string | null | undefined): boolean {
	return normaliserPrompt(a) === normaliserPrompt(b);
}

function normaliserPrompt(texte: string | null | undefined): string {
	return (texte ?? '')
		.replace(/\r\n?/g, '\n')
		.split('\n')
		.map((ligne) => ligne.replace(/[ \t]+$/, ''))
		.join('\n')
		.trim();
}
