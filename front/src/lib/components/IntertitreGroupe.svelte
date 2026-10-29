<!--
  L'intertitre d'un groupe de cartes — « Ascenseur », « Maintenance &
  dépannage » — avec, s'il y en a un, son descriptif en italique.

  Extrait le 01/10/2026 (#779) : en découpant la page des prestataires en deux
  onglets, son balisage et son style auraient été recopiés dans chacun. Une
  classe partagée par deux composants n'a rien à faire dans le style scopé de
  l'un d'eux (`standards/02-factorisation.md`).
-->
<script lang="ts">
	export let libelle: string;
	export let descriptif = '';
</script>

<div class="intertitre-groupe">
	<span class="intertitre-libelle">{libelle}</span>
	{#if descriptif}<span class="intertitre-descriptif">{descriptif}</span>{/if}
</div>

<style>
	.intertitre-groupe {
		display: flex;
		align-items: baseline;
		gap: 0.5rem;
		margin: 1.25rem 0 0.5rem;
		padding-bottom: 0.3rem;
		border-bottom: 2px solid var(--color-border);
	}
	.intertitre-groupe:first-child {
		margin-top: 0;
	}
	.intertitre-libelle {
		font-size: var(--fs-xl);
		font-weight: 700;
	}
	.intertitre-descriptif {
		font-size: var(--fs-md);
		color: var(--color-text-muted);
		font-style: italic;
	}
</style>
