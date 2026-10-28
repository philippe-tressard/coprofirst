<!--
  Vignette carrée réutilisable (aperçu d'un contenu dans une liste).
  Pattern d'origine : cartes de la Communauté (petites annonces) — factorisé ici
  pour être partagé avec les Annonces Hall.

  Props :
    - src         : URL de l'image (null → placeholder)
    - alt         : texte alternatif de l'image
    - placeholder : emoji ou texte affiché faute d'image (encoder les non-BMP)
    - count       : badge « +N » en bas à droite (0 = masqué)
    - size        : côté de la vignette en px
    - title       : infobulle
  Slot : contenu superposé (bouton de suppression, badge…)
-->
<script lang="ts">
	export let src: string | null = null;
	export let alt = '';
	export let placeholder = '';
	export let count = 0;
	export let size = 80;
	export let title = '';
</script>

<div class="vignette" class:vignette-empty={!src} style="--vignette-size:{size}px" {title}>
	{#if src}
		<img {src} {alt} />
	{:else}
		<span class="vignette-placeholder">{placeholder}</span>
	{/if}
	{#if count > 0}<span class="vignette-count">+{count}</span>{/if}
	<slot />
</div>

<style>
	.vignette {
		position: relative;
		width: var(--vignette-size);
		height: var(--vignette-size);
		flex-shrink: 0;
		border-radius: var(--radius);
		overflow: hidden;
		border: 1px solid var(--color-border);
		background: var(--color-neutre-fond);
	}
	.vignette img {
		width: 100%;
		height: 100%;
		object-fit: cover;
	}
	.vignette-empty {
		display: flex;
		align-items: center;
		justify-content: center;
	}
	.vignette-placeholder {
		font-size: var(--fs-chiffre);
	}
	.vignette-count {
		position: absolute;
		bottom: 2px;
		right: 4px;
		font-size: var(--fs-2xs);
		background: rgba(0, 0, 0, 0.55);
		color: var(--color-sur-voile);
		border-radius: 4px;
		padding: 0 4px;
	}
</style>
