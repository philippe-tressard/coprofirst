#!/usr/bin/env node
/**
 *  Un geste qui LANCE l'assistant IA se dessine par `IconeIA` : ✨ au repos, ⏳
 *  qui clignote pendant l'appel (17/10/2026).
 *
 *  ## Pourquoi
 *
 *  Demandé par l'utilisateur : « cet icone ✨ qui se transforme en ⏳ quand le
 *  traitement est en cours ; standardise partout le principe ». Huit gestes
 *  lançaient l'assistant, et l'attente s'y disait de cinq façons : ✨ émoji
 *  devenu ⏳ émoji (tarif d'un modèle), étincelle au trait devenue sablier au
 *  trait (synthèse d'un contrat), étincelle émoji qui pulsait (barre de
 *  l'éditeur), étincelle fixe (résumé des affaires), ou rien du tout — synthèse
 *  d'une affaire, question au règlement. Et un ✨ décorait un bouton qui n'appelle
 *  AUCUNE IA (« Préselection recommandée » des accès d'un bail) : ✨ ne veut plus
 *  rien dire s'il se dit d'autre chose.
 *
 *  ## Ce qu'il refuse
 *
 *  1. le nom `sparkles` ou `hourglass` écrit hors d'`IconeIA` — le dessin de
 *     l'IA ne se recompose pas dans un écran ;
 *  2. un ✨ dans le contenu d'un `<button>` : le geste IA passe par `IconeIA`,
 *     et un bouton qui n'appelle pas l'assistant ne prend pas sa marque ;
 *  3. un `<button>` qui porte `<IconeIA` sans `aria-busy` : le sablier se voit,
 *     l'attente doit aussi s'ENTENDRE au lecteur d'écran.
 *
 *  Ce qu'il ne juge pas : ✨ hors bouton — la MARQUE « rédigé avec l'assistant »
 *  (`MarqueIA`, une pastille, un résumé signalé), qui ne clignote jamais.
 *
 *  Lancer : node scripts/check-geste-ia.mjs [--selftest]
 */
import { controler } from './lib-source-unique.mjs';
import { neutraliserCommentaires } from './lib-commentaires.mjs';
import { balisageSeul } from './lib-analyse-styles.mjs';
import { balisesOuvrantes, contenuDe, ligneDe } from './lib-balises.mjs';

const SOURCE = 'src/lib/components/IconeIA.svelte';

/**  Les exceptions, NOMMÉES avec leur raison — et qui doivent servir. */
const EXCEPTIONS = {
	'src/lib/components/OngletUtilisateurs.svelte':
		'le sablier y dit un bannissement TEMPORAIRE de la communauté, pas une attente de l’assistant',
};

const NOM_DESSIN = /['"](sparkles|hourglass)['"]/;

/** Les lignes fautives d'une source. PURE. */
export function fautes(texte) {
	const lignes = new Set();
	neutraliserCommentaires(texte)
		.split('\n')
		.forEach((l, i) => NOM_DESSIN.test(l) && lignes.add(i + 1));
	const nu = balisageSeul(texte);
	for (const ouvrante of balisesOuvrantes(nu, 'button')) {
		const contenu = contenuDe(nu, 'button', ouvrante);
		const texteVu = contenu.replace(/\{[^}]*\}/g, ' ');
		if (texteVu.includes('✨')) lignes.add(ligneDe(nu, ouvrante.index));
		if (/<IconeIA\b/.test(contenu) && !/\baria-busy\b/.test(ouvrante.balise))
			lignes.add(ligneDe(nu, ouvrante.index));
	}
	return [...lignes].sort((a, b) => a - b);
}

process.exit(
	controler({
		extensions: ['.svelte', '.ts'],
		temoin: SOURCE,
		exceptions: EXCEPTIONS,
		fautes,
		cas: [
			//  🔴 Le dessin recomposé dans un écran.
			[`<IconeAction icone={x ? 'hourglass' : 'sparkles'} />`, 1],
			//  ✨ émoji dans un bouton — qu'il parle ou non.
			['<button aria-label="Tarif">✨</button>', 1],
			['<button class="btn">✨ Relancer</button>', 1],
			//  Un bouton qui porte IconeIA sans dire qu'il travaille.
			['<button class="btn"><IconeIA enCours={x} /> Relancer</button>', 1],
			//  La forme attendue.
			['<button aria-busy={x}><IconeIA enCours={x} /> Relancer</button>', 0],
			//  La marque hors bouton n'est pas un geste.
			['<span class="marque-ia" role="img" aria-label="IA">✨</span>', 0],
			//  Un commentaire qui cite la forme refusée n'est pas une copie.
			[`<!-- l'icône ✨ et 'sparkles' -->`, 0],
			//  Un ✨ dans un script (un toast) n'est pas un bouton.
			["<script>toast('success', `✨ ${n} affaires`);</script>", 0],
		],
		ok: 'Gestes IA : ✨ puis ⏳ qui clignote, par IconeIA seul',
		ko: 'geste(s) IA dessiné(s) hors d’IconeIA',
		conseil:
			'→ <button aria-busy={enCours} …><IconeIA {enCours} /> …</button> ; ' +
			'un bouton qui n’appelle pas l’assistant ne porte pas ✨.',
	}),
);
