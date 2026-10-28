<!--
  Le CONTENU d'un badge qui porte des icônes : les icônes, le libellé, et une
  icône de fin (le cadenas de la pastille de lecture).

  Écrit une fois pour deux porteurs (lot 1 de la pastille de lecture,
  25/09/2026) : la pastille de la CARTE (`PastilleLecture`) et le badge d'état
  de la SECTION (`SectionFormulaire`). Arbitré : *« la même icône aux deux
  endroits »* — deux écritures l'auraient laissée diverger au premier ajout.

  ⚠️ Il ne porte ni la couleur ni la forme : c'est le badge qui l'entoure qui
  les décide. Sans icône, il rend le libellé seul — le badge d'avant.
-->
<script lang="ts">
	import Icon from '#lib/components/Icon.svelte';

	export let icones: string[] = [];
	export let texte = '';
	/** L'icône APRÈS le libellé — vide : aucune. Nommée `icone`, comme tout
	    relais vers `<Icon>` : c'est ce que `lint:icones` sait vérifier. */
	export let icone = '';
	export let taille = 13;
</script>

{#if icones.length || icone}
	<span class="contenu-badge"
		>{#each icones as nom, i (i)}<Icon name={nom} size={taille} />{/each}<span>{texte}</span
		>{#if icone}<Icon name={icone} size={taille - 1} />{/if}</span
	>
{:else}{texte}{/if}

<style>
	/*  Les icônes s'alignent sur le texte, serrées : c'est UNE étiquette. */
	.contenu-badge {
		display: inline-flex;
		align-items: center;
		gap: 0.2rem;
		min-width: 0;
	}
	.contenu-badge > span {
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		margin-left: 0.1rem;
	}
</style>
