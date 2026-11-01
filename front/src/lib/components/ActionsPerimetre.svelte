<!--
  **Les gestes d'un nœud de l'arborescence** — la rangée d'icônes de son corps.

  Sortie d'`OngletPerimetres` le 01/11/2026, quand les flèches de niveau et la
  copie sous d'autres périmètres l'ont fait passer au-delà de 500 lignes
  (`standards/02` §6). Elle ne décide rien : chaque icône émet son geste, l'écran
  ouvre la boîte ou appelle le serveur.

  **Les quatre flèches** (01/11/2026) : ↑ ↓ changent le rang parmi les frères,
  ← sort le nœud de son parent, → le range sous le périmètre qui le précède. Une
  flèche que le serveur refuserait est GRISÉE, lue sur `deplacements` — la règle
  (`utils/perimetres/deplacement.py`) ne se recopie pas ici.
-->
<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import IconeAction from '#lib/components/IconeAction.svelte';
	import type { Perimetre, SensDeplacement } from '#lib/perimetres/index.ts';

	export let noeud: Perimetre;

	const dispatch = createEventDispatcher<{
		editer: void;
		creer: void;
		dupliquer: void;
		copier: void;
		deplacer: SensDeplacement;
		supprimer: void;
	}>();

	const FLECHES: { sens: SensDeplacement; icone: string; libelle: string }[] = [
		{ sens: 'haut', icone: 'arrow-up', libelle: 'Monter' },
		{ sens: 'bas', icone: 'arrow-down', libelle: 'Descendre' },
		{ sens: 'gauche', icone: 'arrow-left', libelle: 'Remonter d’un niveau, hors de son parent' },
		{
			sens: 'droite',
			icone: 'arrow-right',
			libelle: 'Descendre d’un niveau, sous le périmètre au-dessus',
		},
	];
</script>

<div class="ref-actions">
	<button
		class="btn-icon-edit"
		aria-label="Modifier"
		title="Modifier"
		on:click={() => dispatch('editer')}><IconeAction icone="pencil" /></button
	>
	<button
		class="btn-icon"
		aria-label="Ajouter un sous-périmètre"
		title="Ajouter un sous-périmètre"
		on:click={() => dispatch('creer')}><IconeAction icone="plus" /></button
	>
	{#if noeud.dupliquable}
		<button
			class="btn-icon"
			aria-label="Dupliquer avec ses sous-périmètres"
			title="Dupliquer avec ses sous-périmètres"
			on:click={() => dispatch('dupliquer')}><IconeAction icone="copy" /></button
		>
	{/if}
	{#if noeud.copiable}
		<button
			class="btn-icon"
			aria-label="Copier sous d’autres périmètres"
			title="Copier sous d’autres périmètres"
			on:click={() => dispatch('copier')}><IconeAction icone="copy-plus" /></button
		>
	{/if}
	{#each FLECHES as f (f.sens)}
		<button
			class="btn-icon"
			aria-label={f.libelle}
			title={f.libelle}
			disabled={!noeud.deplacements.includes(f.sens)}
			on:click={() => dispatch('deplacer', f.sens)}><IconeAction icone={f.icone} /></button
		>
	{/each}
	<button
		class="btn-icon-danger"
		aria-label="Supprimer"
		title="Supprimer"
		on:click={() => dispatch('supprimer')}><IconeAction icone="trash-2" /></button
	>
</div>

<style>
	.ref-actions {
		display: flex;
		flex-wrap: wrap;
		gap: 0.3rem;
	}
</style>
