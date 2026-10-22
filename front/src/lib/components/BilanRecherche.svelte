<!--
  BilanRecherche.svelte — la ligne qui suit une RECHERCHE : ce qu'elle a trouvé
  (le contenu, à l'appelant), et « Effacer la recherche » à droite.

  ## Pourquoi (#2173, 23/10/2026)

  Sortie de `FiltresAffaires` le jour où les trois tableaux d'import ont reçu
  leur recherche : ils avaient besoin de la même ligne — un bilan annoncé
  (`role="status"`), un bouton qui vide le champ —, et la recopier aurait fait
  la deuxième écriture d'un même objet (`standards/02`). Le BILAN reste à qui
  le connaît : la page Affaires dit ses Archives et ses erreurs de serveur,
  un import compte ses lignes.

  ⚠️ L'appelant décide QUAND la ligne paraît (une recherche posée) : un bilan
  « 240 lignes » sans recherche ne dirait rien que le compteur ne dise.
-->
<script lang="ts">
	/** La saisie de la recherche — liée : « Effacer » la vide. */
	export let recherche = '';
</script>

<p class="bilan-recherche" role="status">
	<slot />
	<button type="button" class="btn btn-outline btn-sm effacer" on:click={() => (recherche = '')}
		>Effacer la recherche</button
	>
</p>

<style>
	.bilan-recherche {
		display: flex;
		flex-wrap: wrap;
		gap: 0.35rem;
		align-items: baseline;
		margin: -0.5rem 0 1rem;
		font-size: var(--fs-base);
		color: var(--color-text-muted);
	}
	.bilan-recherche :global(strong) {
		color: var(--color-text);
	}
	.effacer {
		margin-left: auto;
	}
</style>
