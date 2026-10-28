<!--
  ChampIcone.svelte — choisir l'icône d'une page, DANS le catalogue du site.

  ## Pourquoi (05/09/2026)

  Le champ était une zone de texte libre, doublée d'un lien vers `lucide.dev` :
  *« Parcourir lucide.dev → »*. Deux défauts, et le second est le vrai.

  1. **C'était le seul lien externe du produit.** L'utilisateur a demandé de les
     supprimer : une icône se prend dans le catalogue local
     (`#lib/icones-svg.json`), pas sur un site tiers.
  2. **Le catalogue ne contient que 58 des 1 500 icônes de Lucide.** Parcourir
     lucide.dev, c'était donc choisir dans une bibliothèque dont le produit ne
     sert qu'un vingtième — et `Icon` retombe **en silence** sur `help-circle`
     pour un nom absent (`ux-patterns` §13). L'administrateur voyait un point
     d'interrogation sans jamais savoir pourquoi, et le lien qu'on lui donnait
     était précisément ce qui l'y menait.

  Une liste fermée règle les deux : on ne peut plus nommer une icône qui n'existe
  pas ici, et l'aperçu montre ce qu'on vient de choisir.

  ⚠️ Une valeur enregistrée AVANT cette liste peut n'y pas figurer. Elle est
  ajoutée en tête, marquée « (absente du catalogue) » : sans cela, ouvrir l'écran
  changerait la valeur sans que personne ne l'ait demandé — et la page perdrait
  son icône au premier enregistrement.
-->
<script lang="ts">
	import Icon from '#lib/components/Icon.svelte';
	import icones from '#lib/icones-svg.json';

	/** Le nom de l'icône, lié à l'appelant. */
	export let valeur: string;
	/** Identifiant du `<select>`, pour que le libellé le désigne. */
	export let id: string;

	const NOMS = Object.keys(icones as Record<string, string>).sort();
	$: inconnue = valeur && !NOMS.includes(valeur) ? valeur : null;
</script>

<div class="field">
	<label for={id}>Icône</label>
	<div class="champ-icone">
		<select {id} bind:value={valeur}>
			{#if inconnue}
				<option value={inconnue}>{inconnue} (absente du catalogue)</option>
			{/if}
			{#each NOMS as nom (nom)}
				<option value={nom}>{nom}</option>
			{/each}
		</select>
		<span class="apercu"><Icon name={valeur || 'help-circle'} size={20} /></span>
	</div>
	<span class="aide">
		Affichée dans le menu <strong>et</strong> avant le titre en haut de la page (c'est la même). Les
		{NOMS.length} icônes proposées sont celles que le site embarque : elles fonctionnent aussi dans les
		documents imprimés, qui partagent le même catalogue.
	</span>
</div>

<style>
	.champ-icone {
		display: flex;
		align-items: center;
		gap: 0.5rem;
	}
	.champ-icone select {
		flex: 1;
	}
	.apercu {
		color: var(--color-text-muted);
		flex-shrink: 0;
		display: flex;
		align-items: center;
	}
</style>
