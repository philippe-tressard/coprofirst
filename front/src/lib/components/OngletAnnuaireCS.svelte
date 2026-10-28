<!--
  L'onglet ANNUAIRE de l'Espace CS — le lien vers les consignes, les consignes de
  la fiche arrivant, le conseil syndical et le syndic.

  Extrait de `espace-cs/+page.svelte` le 12/10/2026 (#1844) : l'onglet se charge
  au geste, en UN morceau, plutôt que trois composants différés côte à côte — la
  page repassait au-dessus de 500 lignes. La page garde la lecture des données
  de référence (#1843) : les deux annuaires les attendent (`referenceLue`), car
  « pas encore là » ne se lit pas « aucune correspondance » (#522).
-->
<script lang="ts">
	import type { SourcesRapprochement } from '#lib/annuaire-rapprochement.ts';
	import AnnuaireConseil from '#lib/components/AnnuaireConseil.svelte';
	import AnnuaireSyndic from '#lib/components/AnnuaireSyndic.svelte';
	import ConsignesArrivant from '#lib/components/ConsignesArrivant.svelte';
	import EtatListe from '#lib/components/EtatListe.svelte';
	import LienConsignes from '#lib/components/LienConsignes.svelte';

	export let referenceLue: boolean;
	export let sources: SourcesRapprochement;
</script>

<LienConsignes />

<!--  Ce que la fiche imprime sous « Consignes de la copropriété » (#1727). -->
<section class="annuaire-section">
	<div class="annuaire-section-header">
		<h2 class="section-title">Consignes de la fiche arrivant</h2>
	</div>
	<ConsignesArrivant />
</section>

<section class="annuaire-section">
	<div class="annuaire-section-header">
		<h2 class="section-title">Conseil Syndical</h2>
	</div>
	{#if referenceLue}
		<AnnuaireConseil {sources} />
	{:else}
		<EtatListe chargement />
	{/if}
</section>

<section class="annuaire-section">
	<div class="annuaire-section-header">
		<h2 class="section-title">Syndic</h2>
	</div>
	{#if referenceLue}
		<AnnuaireSyndic {sources} />
	{:else}
		<EtatListe chargement />
	{/if}
</section>

<style>
	/*  L'annuaire porte son style avec son balisage — `AnnuaireConseil`,
	    `AnnuaireSyndic`, et `CarteMembre` pour ce qui s'écrit dans ses
	    emplacements (#779, 29/09/2026). Ne restent ici que ses sections. */
	.annuaire-section {
		margin-bottom: 2.5rem;
		max-width: 780px;
	}
	.annuaire-section-header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		margin-bottom: 0.75rem;
	}
	.section-title {
		margin: 0;
	} /* la charte pose `margin-bottom` (#607) */
</style>
