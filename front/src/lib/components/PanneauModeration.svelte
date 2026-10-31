<!--
  PanneauModeration.svelte — les signalements en attente, en tête de la Communauté.

  Sorti de l'écran le 05/09/2026 : le garde-fou de modularité a refusé que
  `PageCommunaute.svelte` dépasse 500 lignes, et c'est le bon refus — ce panneau
  n'a rien à voir avec les trois rubriques, il ne partage avec elles que sa place
  à l'écran. Il part avec **tout** son style : Svelte le scope au composant, et
  une règle laissée dans la page n'habillerait plus rien (v2.67.11).

  Il ne décide de rien : la page charge les signalements et applique la décision.
  Ce composant les montre et dit ce qu'on a cliqué.
-->
<script lang="ts">
	import { SEPARATEUR } from '#lib/separateurs.ts';
	import type { Signalement } from '#lib/api/index.ts';
	import { createEventDispatcher } from 'svelte';

	/** Les signalements en attente, tels que l'API les rend. */
	export let signalements: Signalement[] = [];

	const dispatch = createEventDispatcher<{
		resoudre: { id: number; decision: 'traite' | 'rejete' };
	}>();

	let showModeration = false;
</script>

<div class="moderation-panel">
	<button
		type="button"
		class="moderation-tete"
		on:click={() => (showModeration = !showModeration)}
		aria-expanded={showModeration}
	>
		🚩 {signalements.length} signalement{signalements.length > 1 ? 's' : ''} à modérer
		<span class="moderation-chevron">{showModeration ? '▲' : '▼'}</span>
	</button>
	{#if showModeration}
		<div class="moderation-liste">
			{#each signalements as sig (sig.id)}
				<div class="moderation-item">
					<div class="moderation-meta">
						<span class="badge badge-blue">{sig.cible_type_label}</span>
						<strong>« {sig.apercu}</strong>
						{#if sig.auteur_cible}<span class="muted">{SEPARATEUR.tiret}par {sig.auteur_cible}</span
							>{/if}
					</div>
					<div class="moderation-motif">
						Motif : {sig.motif}
						<span class="muted">(signalé par {sig.signale_par})</span>
					</div>
					<div class="moderation-actions">
						<button
							class="btn btn-sm btn-outline"
							on:click={() => dispatch('resoudre', { id: sig.id, decision: 'traite' })}
							>✓ Marquer traité</button
						>
						<button
							class="btn btn-sm btn-outline"
							on:click={() => dispatch('resoudre', { id: sig.id, decision: 'rejete' })}
							>Ignorer</button
						>
					</div>
				</div>
			{/each}
			<p class="moderation-aide">
				Pour retirer un contenu, utilisez le bouton 🗑️ sur le contenu concerné, puis marquez le
				signalement « traité ». Les récidives se gèrent via Admin{SEPARATEUR.fleche}bannissement
				Communauté.
			</p>
		</div>
	{/if}
</div>

<style>
	/* Les styles des réponses sont dans le composant partagé Reponses.svelte */
	/* Signalement + modération */
	.moderation-panel {
		border: 1px solid var(--color-warning);
		border-radius: var(--radius);
		background: var(--color-warning-fond);
		margin-bottom: 1.25rem;
		overflow: hidden;
	}
	.moderation-tete {
		width: 100%;
		text-align: left;
		background: none;
		border: none;
		padding: 0.7rem 1rem;
		font-weight: 600;
		font-size: var(--fs-base);
		cursor: pointer;
		color: var(--color-text);
		display: flex;
		align-items: center;
		gap: 0.5rem;
	}
	.moderation-chevron {
		margin-left: auto;
		font-size: var(--fs-xs);
	}
	.moderation-liste {
		padding: 0 1rem 1rem;
		display: flex;
		flex-direction: column;
		gap: 0.6rem;
	}
	.moderation-item {
		border: 1px solid var(--color-border);
		border-radius: var(--radius);
		padding: 0.6rem 0.8rem;
		background: var(--color-surface);
	}
	.moderation-meta {
		display: flex;
		flex-wrap: wrap;
		gap: 0.4rem;
		align-items: center;
		font-size: var(--fs-md);
		margin-bottom: 0.25rem;
	}
	.moderation-motif {
		font-size: var(--fs-md);
		margin-bottom: 0.4rem;
	}
	.moderation-actions {
		display: flex;
		gap: 0.5rem;
		flex-wrap: wrap;
	}
	.moderation-aide {
		font-size: var(--fs-xs);
		color: var(--color-text-muted);
		margin-top: 0.3rem;
	}
</style>
