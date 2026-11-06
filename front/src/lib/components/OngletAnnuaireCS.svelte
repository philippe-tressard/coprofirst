<!--
  L'onglet ANNUAIRE de l'Espace CS — le lien vers les consignes, les consignes de
  la fiche arrivant, le conseil syndical et le syndic.

  Extrait de `espace-cs/+page.svelte` le 12/10/2026 (#1844) : l'onglet se charge
  au geste, en UN morceau, plutôt que trois composants différés côte à côte — la
  page repassait au-dessus de 500 lignes.

  Il n'attend plus de données de référence (#2522) : le rapprochement d'un nom
  saisi se demande au serveur, fiche par fiche (`#lib/annuaire-rapprochement`).
-->
<script lang="ts">
	import AnnuaireConseil from '#lib/components/AnnuaireConseil.svelte';
	import AnnuaireSyndic from '#lib/components/AnnuaireSyndic.svelte';
	import ConsignesArrivant from '#lib/components/ConsignesArrivant.svelte';
	import LienConsignes from '#lib/components/LienConsignes.svelte';
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
	<AnnuaireConseil />
</section>

<section class="annuaire-section">
	<div class="annuaire-section-header">
		<h2 class="section-title">Syndic</h2>
	</div>
	<AnnuaireSyndic />
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
