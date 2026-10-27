<!--
  SelecteurMode.svelte — basculer un écran entre deux ou trois MODES d'une même
  liste, en un bouton segmenté (« Suivre | Relancer le syndic »).

  ## Pourquoi pas `ChoixPastilles` (#2035, 16/10/2026)

  `ChoixPastilles` CHOISIT une valeur — un filtre, un champ : la liste reste la
  même, on en garde une partie. Ici, le mode change ce que l'écran PERMET de
  faire sur la même liste : lire, ou composer une relance. Choisi sur maquette
  (3b) : deux segments soudés, l'un plein, l'autre au trait — on lit d'un coup
  d'œil dans quel mode on est, ce qu'une rangée de pastilles ne disait pas.

  Un bouton par mode, `aria-pressed` sur celui qui est actif, le groupe nommé
  par `libelle` (lu par un lecteur d'écran, jamais affiché).

  UTILISATION :
    <SelecteurMode libelle="Mode du suivi" options={MODES} bind:valeur={mode} />
-->
<script lang="ts">
	/** Les modes, dans l'ordre d'affichage. */
	export let options: { valeur: string; libelle: string }[];
	/** Le mode actif — lié. */
	export let valeur: string;
	/** Le nom du groupe, pour un lecteur d'écran. */
	export let libelle: string;
</script>

<div class="selecteur-mode" role="group" aria-label={libelle}>
	{#each options as o (o.valeur)}
		<button
			type="button"
			class="segment"
			class:actif={o.valeur === valeur}
			aria-pressed={o.valeur === valeur}
			on:click={() => (valeur = o.valeur)}
		>
			{o.libelle}
		</button>
	{/each}
</div>

<style>
	.selecteur-mode {
		display: inline-flex;
		border: 1px solid var(--color-primary);
		border-radius: 999px;
		overflow: hidden;
		background: var(--color-surface);
	}
	.segment {
		border: 0;
		background: transparent;
		color: var(--color-primary);
		font: inherit;
		font-size: var(--fs-base);
		font-weight: 600;
		padding: 0.5rem 1.1rem;
		min-height: 2.75rem;
		cursor: pointer;
		transition:
			background-color var(--duree-geste),
			color var(--duree-geste);
	}
	.segment.actif {
		background: var(--color-primary-plein);
		color: var(--color-sur-plein);
	}
	.segment:focus-visible {
		outline: 2px solid currentColor;
		outline-offset: -4px;
	}
	@media (hover: hover) and (pointer: fine) {
		.segment:not(.actif):hover {
			background: var(--color-primary-light);
		}
	}
</style>
