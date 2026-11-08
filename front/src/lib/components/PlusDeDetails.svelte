<!--
  PlusDeDetails.svelte — le groupe plié où la saisie ESSENTIELLE range les
  sections qu'elle ne montre pas (#2595, arbitré le 08/11/2026).

  Ce n'est pas une section du cadre : il n'a ni rang ni déclaration, il ENVELOPPE
  des sections qui gardent les leurs. Et ce n'est pas l'arbitrage n° 51 (une section
  sans objet pour la nature reste à son rang, grisée) : ici les sections ont un
  objet, la saisie choisit seulement de ne pas les montrer d'emblée.

  🔴 Le contenu reste MONTÉ quand le groupe est plié (`hidden`, pas `{#if}`) : une
  section de Diffusion porte l'aperçu avant envoi (`bind:this`), et une valeur déjà
  saisie vit dans ses composants. Plié, rien ne se perd — et rien ne part
  autrement que par la charge utile habituelle.
-->
<script lang="ts">
	/** Le nombre de sections rangées, dit dans l'intitulé. */
	export let nombre = 0;
	/** Ouvert ? Lié : l'appelant l'ouvre quand une valeur autre que le défaut s'y trouve. */
	export let ouvert = false;
	/** Préfixe des `id` — deux formulaires peuvent coexister à l'écran. */
	export let idPrefixe = 'plus-de-details';

	$: intitule = `Plus de détails (${nombre} ${nombre > 1 ? 'sections' : 'section'})`;
</script>

<div class="plus-de-details">
	<button
		type="button"
		class="plus-de-details-bouton"
		aria-expanded={ouvert}
		aria-controls="{idPrefixe}-corps"
		on:click={() => (ouvert = !ouvert)}
	>
		<span>{intitule}</span>
		<span class="chevron" class:open={ouvert} aria-hidden="true">›</span>
	</button>
	<div id="{idPrefixe}-corps" class="plus-de-details-corps" hidden={!ouvert}>
		<slot />
	</div>
</div>

<style>
	.plus-de-details {
		margin-top: 1.5rem;
		border-top: 1px solid var(--color-border);
	}
	.plus-de-details-bouton {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 0.5rem;
		width: 100%;
		min-height: 44px;
		padding: 0.5rem 0;
		background: none;
		border: 0;
		font: inherit;
		font-size: var(--fs-base);
		font-weight: 600;
		color: var(--color-primary);
		cursor: pointer;
		text-align: left;
	}
	.plus-de-details-corps[hidden] {
		display: none;
	}
</style>
