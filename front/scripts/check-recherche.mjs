#!/usr/bin/env node
/**
 *  Un champ de RECHERCHE ne s'écrit que par `ChampRecherche` (#2308, 29/10/2026).
 *
 *  Demandé à l'écran : « standardisée sur tous les champs de saisie RECHERCHE ;
 *  l'objet doit être standard ». Le composant existait depuis le 28/09/2026 et
 *  servait sept écrans — deux autres écrivaient encore leur `<input>` à la main
 *  (l'audit des lots, la recherche d'un locataire), sans libellé, sans aide, et
 *  avec une règle qui butait sur les accents.
 *
 *  La FORME d'une copie : un `<input type="search">`, ou une saisie dont
 *  l'exemple commence par « Rechercher » / « Filtrer » / « Chercher » — celle
 *  de l'audit était un `type="text"`.
 *
 *  Lancer : node scripts/check-recherche.mjs [--selftest]
 */
import { controler, lignesPortant } from './lib-source-unique.mjs';

const COPIE =
	/type\s*=\s*["'{]\s*['"]?search\b|placeholder\s*=\s*["'](?:Rechercher|Filtrer|Chercher)\b/i;

process.exit(
	controler({
		temoin: 'src/lib/components/ChampRecherche.svelte',
		exceptions: {
			//  Un SÉLECTEUR, pas une recherche dans une liste : son libellé nomme ce
			//  qu'on choisit (« Affaire liée »), et la liste déroulante est le
			//  résultat. Le passer à « Recherche » ferait perdre ce qu'on y choisit.
			'src/lib/components/ChoixAffaire.svelte':
				'sélecteur d’affaire (combobox), libellé de ce qu’on choisit',
		},
		fautes: lignesPortant(COPIE),
		cas: [
			['\t\t\ttype="search"', 1],
			['\t<input type="search" bind:value={q} />', 1],
			['\t<input type="text" placeholder="Filtrer par nom, lot ou bâtiment…" />', 1],
			["\t<input placeholder='Rechercher un compte' />", 1],
			//  La forme voulue, jamais signalée.
			['\t<ChampRecherche id="x" bind:valeur={q} dans="nom" />', 0],
			//  Un exemple qui ne dit pas « chercher » : hors portée.
			['\t<input type="text" placeholder="Nom, prénom ou email…" />', 0],
			//  Un commentaire qui cite la forme refusée.
			['\t<!-- jadis un <input type="search"> ici -->', 0],
		],
		ok: 'Recherche : tous les champs passent par `ChampRecherche`',
		ko: 'champ(s) de recherche écrit(s) hors de `ChampRecherche`',
		conseil:
			'Employer `<ChampRecherche id bind:valeur placeholder dans="…" />` (`#lib/components/ChampRecherche.svelte`).',
	}),
);
