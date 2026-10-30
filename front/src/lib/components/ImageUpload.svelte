<!--
  Composant réutilisable de téléchargement d'image.
  Props :
    - currentUrl   : URL de l'image actuelle (optionnel)
    - placeholder  : emoji ou texte affiché si pas d'image
    - label        : libellé du bouton
    - accept       : types MIME acceptés (défaut JPEG/PNG/WebP)
    - shape        : "circle" | "rect" (défaut "rect")
    - uploading    : état de chargement géré par le parent
  Events :
    - change(detail: File) — émis quand l'utilisateur sélectionne un fichier
-->
<script lang="ts">
	import { createEventDispatcher } from 'svelte';

	/** Posé sur le champ fichier, pour qu'un `<label for=…>` extérieur le désigne
	 *  réellement — sans lui, l'étiquette ne pointait sur rien. */
	export let id: string | undefined = undefined;
	export let currentUrl: string | undefined = undefined;
	export let placeholder = '\u{1F4F7}';
	export let label = 'Changer la photo';
	export let accept = 'image/jpeg,image/png,image/webp';
	export let shape: 'circle' | 'rect' = 'rect';
	export let uploading = false;
	export let previewSize = '120px';

	const dispatch = createEventDispatcher<{ change: File }>();

	let input: HTMLInputElement;
	let localPreview: string | undefined;

	$: displayUrl = localPreview ?? currentUrl;

	function handleChange(e: Event) {
		const file = (e.target as HTMLInputElement).files?.[0];
		if (!file) return;
		// Prévisualisation locale immédiate
		localPreview = URL.createObjectURL(file);
		dispatch('change', file);
	}
</script>

<div class="img-upload-wrap" style="--preview-size: {previewSize}">
	<div
		class="preview"
		class:circle={shape === 'circle'}
		role="button"
		tabindex="0"
		on:click={() => input.click()}
		on:keydown={(e) => e.key === 'Enter' && input.click()}
		title={label}
	>
		{#if displayUrl}
			<img src={displayUrl} alt="Aperçu" />
		{:else}
			<span class="placeholder">{placeholder}</span>
		{/if}

		<!--  Visible PENDANT l'envoi, survol ou non : le spinner y vit, et au doigt
		      il n'y a pas de survol pour le montrer (26/09/2026). -->
		<div class="overlay" class:en-cours={uploading}>
			{#if uploading}
				<span class="spinner"></span>
			{:else}
				<span class="overlay-label">&#x1F4F7;</span>
			{/if}
		</div>
	</div>

	<button type="button" class="btn-link" on:click={() => input.click()} disabled={uploading}>
		{uploading ? 'Chargement…' : label}
	</button>

	<input bind:this={input} {id} type="file" {accept} class="champ-cache" on:change={handleChange} />
</div>

<style>
	.img-upload-wrap {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 0.5rem;
	}

	.preview {
		position: relative;
		width: var(--preview-size);
		height: var(--preview-size);
		border-radius: 8px;
		border: 2px dashed var(--color-border);
		overflow: hidden;
		cursor: pointer;
		background: var(--color-neutre-fond);
		display: flex;
		align-items: center;
		justify-content: center;
		transition: border-color var(--duree-geste);
	}

	@media (hover: hover) and (pointer: fine) {
		.preview:hover {
			border-color: var(--color-primary);
		}
	}
	.preview.circle {
		border-radius: 50%;
	}

	.preview img {
		width: 100%;
		height: 100%;
		object-fit: cover;
	}

	.placeholder {
		font-size: var(--fs-picto-lg);
		opacity: 0.4;
	}

	.overlay {
		position: absolute;
		top: 0;
		right: 0;
		bottom: 0;
		left: 0;
		background: rgba(0, 0, 0, 0.35);
		display: flex;
		align-items: center;
		justify-content: center;
		opacity: 0;
		transition: opacity var(--duree-apparition) var(--ease-out);
	}

	@media (hover: hover) and (pointer: fine) {
		.preview:hover .overlay {
			opacity: 1;
		}
	}
	/*  Le focus au clavier n'est pas un survol : il reste hors du média souris. */
	.overlay.en-cours,
	.preview:focus-visible .overlay {
		opacity: 1;
	}

	.overlay-label {
		font-size: var(--fs-picto);
	}

	/* Base commune dans `app.css` : forme, rotation et durée viennent de là. Ne
	   restent ici que les deux vraies différences — la taille fixe et le blanc
	   du survol photo, `currentColor` n'ayant pas de sens sur cet aplat sombre. */
	.spinner {
		width: 24px;
		height: 24px;
		border-width: 3px;
		border-color: rgba(255, 255, 255, 0.4);
		/*  Le blanc d'un voile noir : `--color-sur-voile`, pas la surface, qui
		    s'assombrit au thème sombre (#2174, S4b). */
		border-top-color: var(--color-sur-voile);
	}

	.btn-link {
		background: none;
		border: none;
		color: var(--color-primary);
		font-size: var(--fs-sm);
		cursor: pointer;
		padding: 0;
		text-decoration: underline;
	}

	.btn-link:disabled {
		opacity: 0.5;
		cursor: default;
	}
	.champ-cache {
		display: none;
	}
</style>
