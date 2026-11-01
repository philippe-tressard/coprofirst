<!--
  Le choix d'une ICÔNE au trait dans une liste courte — une grille de boutons.

  Sorti de `ChampsPerimetre` le 01/11/2026 (#2442) : l'administration des
  équipements en avait besoin à son tour, et la recopier aurait fait deux
  grilles, deux tailles de cible et deux allures du bouton retenu. L'appelant
  donne la liste (`ICONES_PERIMETRE`, `ICONES_EQUIPEMENT`) et le libellé du
  champ ; le composant porte le geste, l'état retenu et l'accessibilité.

  ⚠️ Au doigt, une cible de 2 rem était trop petite (`standards/11` §10) : elle
  passe à 2,75 rem sous `pointer: coarse`.
-->
<script lang="ts">
	import Icon from '#lib/components/Icon.svelte';

	/** Les icônes proposées — un nom du catalogue et ce qu'il évoque. */
	export let icones: readonly { nom: string; libelle: string }[];
	/** Le nom retenu, lié ; `''` = aucune. */
	export let valeur = '';
	/** Propose « — » (aucune icône) en tête. */
	export let aucune = false;
	/** Le nom accessible du groupe — le libellé du champ qui le porte. */
	export let libelle: string;
</script>

<div class="icones" role="group" aria-label={libelle}>
	{#if aucune}
		<button
			type="button"
			class="icone"
			class:icone-active={!valeur}
			aria-pressed={!valeur}
			title="Aucune icône"
			aria-label="Aucune icône"
			on:click={() => (valeur = '')}>—</button
		>
	{/if}
	{#each icones as ic (ic.nom)}
		<button
			type="button"
			class="icone"
			class:icone-active={valeur === ic.nom}
			aria-pressed={valeur === ic.nom}
			title={ic.libelle}
			aria-label={ic.libelle}
			on:click={() => (valeur = ic.nom)}
		>
			<Icon name={ic.nom} size={18} />
		</button>
	{/each}
</div>

<style>
	.icones {
		display: flex;
		flex-wrap: wrap;
		gap: 0.3rem;
		margin-top: 0.3rem;
	}
	.icone {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		width: 2rem;
		height: 2rem;
		border: 1px solid var(--color-border);
		border-radius: var(--radius);
		background: var(--color-surface);
		cursor: pointer;
		color: var(--color-text-muted);
		font-size: var(--fs-sm);
		transition:
			background var(--duree-geste),
			border-color var(--duree-geste),
			color var(--duree-geste),
			transform var(--duree-geste) var(--ease-out);
	}
	/*  Le retour vient à l'APPUI, pas au relâcher — comme tout bouton du site
	    (`ux-patterns` §17) ; pas sur l'icône déjà retenue. */
	.icone:active:not([aria-pressed='true']) {
		transform: scale(0.97);
	}
	@media (pointer: coarse) {
		.icone {
			width: 2.75rem;
			height: 2.75rem;
		}
	}
	@media (hover: hover) and (pointer: fine) {
		.icone:hover {
			border-color: var(--color-primary);
			color: var(--color-text);
		}
	}
	.icone-active {
		background: var(--color-primary-plein);
		color: var(--color-sur-plein);
		border-color: var(--color-primary-plein);
	}
</style>
