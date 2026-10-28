<!--
  BanniereResidence.svelte — la photo de la résidence en tête de sa fiche, et
  son remplacement par le conseil syndical.

  Sortie de `residence/+page.svelte` (#779, 01/10/2026) : un bloc autonome —
  son image, son téléversement, son style — qui gardait l'écran au-dessus de
  500 lignes. Au passage, le bouton s'atteint au clavier et répond à l'appui.
-->
<script lang="ts">
	import Icon from '#lib/components/Icon.svelte';
	import { tenter } from '#lib/erreurs.ts';
	import { uploads as uploadsApi, type Copropriete } from '#lib/api/index.ts';

	/** La fiche lue ; sa `photo_url` est remplacée après un téléversement. */
	export let copropriete: Copropriete;
	export let peutModifier = false;

	let envoi = false;
	let champ: HTMLInputElement;

	async function remplacerPhoto() {
		const fichier = champ.files?.[0];
		if (!fichier) return;
		envoi = true;
		await tenter(
			async () => {
				const { url } = await uploadsApi.residence(fichier);
				copropriete = { ...copropriete, photo_url: url };
			},
			'Photo mise à jour',
			'Erreur upload',
		);
		envoi = false;
		champ.value = '';
	}
</script>

<figure class="photo-figure">
	<div class="photo-banner">
		{#if copropriete.photo_url}
			<img src={copropriete.photo_url} alt="La résidence" />
		{:else}
			<div class="photo-placeholder">
				<Icon name="building-2" size={48} />
				<span>Aucune photo</span>
			</div>
		{/if}
		{#if peutModifier}
			<!--  Un vrai BOUTON qui ouvre le sélecteur masqué : une étiquette autour d'un
			      champ en `display:none` ne s'atteignait qu'à la souris (#779). -->
			<button
				type="button"
				class="photo-change-btn"
				class:uploading={envoi}
				disabled={envoi}
				on:click={() => champ.click()}
			>
				{envoi ? '…' : '\u{1F4F8} Changer la photo'}
			</button>
			<input bind:this={champ} type="file" accept="image/*" on:change={remplacerPhoto} hidden />
		{/if}
	</div>
	<figcaption class="photo-caption">{copropriete.nom}</figcaption>
</figure>

<style>
	.photo-figure {
		margin: 0 auto 2rem;
		max-width: 800px;
		text-align: center;
	}
	.photo-caption {
		font-size: var(--fs-base);
		color: var(--color-text-muted);
		padding: 0.35rem 0;
		font-style: italic;
	}
	.photo-banner {
		position: relative;
		width: 100%;
		border-radius: var(--radius);
		overflow: hidden;
		background: var(--color-bg);
		border: 1px solid var(--color-border);
	}
	.photo-banner img {
		width: 100%;
		aspect-ratio: 16 / 5;
		object-fit: cover;
		display: block;
	}
	.photo-placeholder {
		width: 100%;
		aspect-ratio: 16 / 5;
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		gap: 0.5rem;
		color: var(--color-text-muted);
		background: var(--color-bg);
		font-size: var(--fs-base);
	}
	.photo-change-btn {
		position: absolute;
		bottom: 0.75rem;
		right: 0.75rem;
		background: rgba(0, 0, 0, 0.55);
		color: var(--color-sur-voile);
		border: none;
		border-radius: var(--radius);
		padding: 0.35rem 0.75rem;
		font-size: var(--fs-sm);
		cursor: pointer;
		backdrop-filter: blur(4px);
		transition:
			background var(--duree-geste),
			transform var(--duree-geste) var(--ease-out);
	}
	.photo-change-btn:focus-visible {
		outline: 2px solid var(--color-primary);
		outline-offset: 2px;
	}
	.photo-change-btn:active:not(:disabled) {
		transform: scale(0.97);
	}
	@media (hover: hover) and (pointer: fine) {
		.photo-change-btn:hover {
			background: rgba(0, 0, 0, 0.75);
		}
	}
	.photo-change-btn.uploading {
		opacity: 0.6;
		pointer-events: none;
	}
</style>
