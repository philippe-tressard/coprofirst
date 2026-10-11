<!--
  ReglagesListe.svelte — la grille des RÉGLAGES d'une liste à gouttière : la
  recherche en tête, les rangées de filtres dessous, chaque libellé dans une
  colonne de la largeur de la gouttière des cartes.

  ## Pourquoi (10/10/2026, maquette B « Gouttière »)

  Sur la page Affaires, les libellés des filtres tiennent dans une colonne de la
  largeur de la gouttière, et les champs commencent là où commence le contenu
  d'une carte : une seule grille du haut au bas de la page. Cette grille vivait
  dans `FiltresAffaires` ; la page Affaires étant devenue le standard du site le
  soir même, elle en sort — une deuxième page qui la recopierait ferait la
  deuxième écriture du même objet (`standards/02`).

  Ce composant ne filtre rien et ne connaît aucun objet : il pose la grille, et
  l'appelant y range `ChampRecherche`, `ChoixPastilles libelleDevant`,
  `FiltrePerimetre libelleDevant`… Leur balisage et leur accessibilité ne
  changent pas — ils s'y fondent (`display: contents`).

  🔢 Le compteur est celui de chaque rangée (`compte`, ux-patterns §5) : la
  grille ne le porte pas.
-->
<div class="filtres-gouttiere">
	<slot />
</div>

<style>
	/*  La colonne des libellés : la gouttière ET le liseré gauche de la carte
	    (4 px, `.carte-liste`), pour que les champs partent du même bord que le
	    contenu des cartes. Au-dessous de 768 px, une colonne : libellé au-dessus. */
	.filtres-gouttiere {
		display: grid;
		grid-template-columns: calc(var(--largeur-gouttiere) + 4px) minmax(0, 1fr);
		align-items: center;
		gap: 0.6rem 0;
		margin-bottom: 1.25rem;
	}
	.filtres-gouttiere > :global(.champ-recherche),
	.filtres-gouttiere > :global(.choix-libelle-devant) {
		display: contents;
	}
	/*  Plus petits que les libellés de formulaire, et c'est voulu : ils tiennent
	    dans la gouttière (« RECHERCHE » est le plus long), et ils nomment des
	    réglages, pas des champs à remplir. `e2e/gouttiere-nature` mesure qu'ils
	    y tiennent. */
	.filtres-gouttiere :global(.libelle-devant) {
		margin: 0;
		padding-right: 0.5rem;
		font-size: var(--fs-2xs);
		font-weight: 600;
		letter-spacing: 0.06em;
		color: var(--color-text-muted);
	}
	.filtres-gouttiere :global(.recherche-saisie) {
		max-width: 52rem;
	}
	.filtres-gouttiere :global(.aide) {
		grid-column: 2;
		margin: -0.3rem 0 0.2rem;
	}
	@media (max-width: 767px) {
		.filtres-gouttiere {
			grid-template-columns: minmax(0, 1fr);
			gap: 0.3rem 0;
		}
		.filtres-gouttiere :global(.aide) {
			grid-column: 1;
		}
		.filtres-gouttiere :global(.libelle-devant) {
			margin-top: 0.5rem;
		}
	}
</style>
