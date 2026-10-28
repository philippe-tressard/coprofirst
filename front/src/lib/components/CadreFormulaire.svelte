<!--
  **Le cadre d'un formulaire** — la boîte dans la page, pour les DEUX gestes.

  ## 🔴 REVIREMENT — l'utilisateur a tranché le 06/09/2026

  > « la boîte d'édition n'est pas standard à l'UX, elle apparaît dans une fenêtre
  > indépendante au lieu de la fenêtre principale […] comme le reste du site, avec
  > un UX standard, pas de spécifique »

  Ce fichier portait la règle inverse, posée le 30/08 (#640, `ux-patterns` §14 bis) :
  *créer → la boîte dans la page · éditer → la fenêtre*. Elle avait sa logique —
  isoler le geste de correction sans décaler la liste — et elle a été **écartée
  au vu de l'écran** : une boîte qui flotte par-dessus la page est un paradigme de
  plus, et le produit en avait déjà eu trois pour la seule création (#367).

  ⚠️ Ce n'est donc PAS le rendu de la fenêtre qui était en cause (#787 la disait
  décentrée, sans voile) : c'est la fenêtre elle-même. Corriger son affichage
  aurait rendu correct un cadre dont personne ne voulait.

  **Créer et corriger emploient désormais la même boîte**, à la même place, avec
  le même comportement — y compris l'auto-défilement de `FormulaireCreation`,
  dont l'édition a le plus besoin : le geste part d'une carte, souvent loin du
  formulaire.

  ## Pourquoi ce composant existe (02/09/2026)

  Le choix du cadre s'écrivait **cinq fois** :

      FormulaireActualite · FormulaireBail · FormulaireDocument
      FormulaireEvenement (supprimé avec #1092) · FormulaireFaq

  Chacune portait son `<svelte:component this={…}>`, ses deux imports et un
  commentaire expliquant la même chose dans des mots différents.
  `FormulaireAnnonce` allait être la sixième.

  ⚠️ **Elles avaient déjà divergé**, et c'est la forme la plus trompeuse de la
  duplication — celle où chaque copie a l'air juste. `classeBoite` valait `modal`,
  `modal-box` ou `modal-box card` selon l'écran, et `FormulaireAnnonce` n'avait ni
  l'une ni l'autre : ses bandes de section sortaient à fleur de fenêtre.

  🔴 **Ce paragraphe est conservé alors que la fenêtre a disparu**, et pas par
  nostalgie : il dit pourquoi ce composant doit rester le SEUL endroit où le cadre
  se choisit. Le jour où le produit voudra un troisième cadre, la question se
  posera ici, une fois — pas dans huit formulaires.

  ## Ce que ce composant NE fait pas

  Il ne pose **aucun bouton** et ne connaît ni l'enregistrement ni ce qu'annuler
  veut dire — comme `FormulaireCreation`, dont il hérite la retenue. Il relaie
  `on:fermer`, et c'est tout.

  Il ne décide pas non plus du **contenu** du formulaire selon le geste : les
  sections viennent du cadre #430 (`#lib/entites/*` + `sectionPresente`), et
  `npm run lint:etats` refuse qu'on remette une condition en dur.

  🔒 `edition` reste une prop, alors qu'elle ne change plus le cadre : elle
  distingue toujours les deux gestes pour le titre et pour la déclaration d'état,
  et `npm run lint:cadre-geste` vérifie qu'un formulaire qui connaît son geste ne
  se rend pas lui-même dans une `Modale`.
-->
<script lang="ts">
	import FormulaireCreation from './FormulaireCreation.svelte';

	/**  Le geste. `false` = création (boîte dans la page), `true` = correction
	 *   d'un objet existant (fenêtre).
	 *
	 *   ⚠️ **Une déclaration, pas une commodité** — même contrat que `Modale.edition`,
	 *   qu'il transmet. C'est lui qui distingue « créer » de « corriger », et rien
	 *   dans le balisage ne permettrait de le deviner. */
	export let edition = false;

	/** Le titre du cadre — en-tête de la boîte, ou titre annoncé de la fenêtre. */
	export let titre: string;

	//  🔴 `classeBoite` et `styleBoite` ONT DISPARU le 06/09/2026 : elles ne
	//  décrivaient que la fenêtre flottante, qui n'existe plus ici. Trois
	//  formulaires les passaient (Bail, Document, FAQ) ; leur retrait fait partie
	//  du même lot, sans quoi elles auraient survécu à leur objet.

	/**  Le cadre visible de la boîte. `false` quand le
	 *   formulaire s'ouvre déjà DANS une carte : deux bordures imbriquées pour un
	 *   seul objet, c'est « la carte dans la carte » (#425). */
	export let encadre = true;
	/**  Ce qui identifie l'objet en cours — et c'est l'ÉDITION qui en a le plus
	 *   besoin : cliquer « Modifier » sur une seconde carte alors que le
	 *   formulaire est déjà ouvert plus haut ne remonterait rien, et le geste
	 *   redeviendrait muet. Il change, et
	 *   `FormulaireCreation` ramène le formulaire à l'écran. */
	export let cle: unknown = undefined;
</script>

<FormulaireCreation {titre} {encadre} {cle} on:fermer>
	<slot />
</FormulaireCreation>
