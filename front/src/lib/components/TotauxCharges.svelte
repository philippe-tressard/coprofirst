<!--
  **Le total de mes charges, tous mes lots confondus** (#2215) — pour un copropriétaire de
  plusieurs lots : un logement, une cave, deux places contribuent chacun à des clés, et une
  même clé (« Ascenseur A ») pèse sur lui pour la SOMME de ses parts.

  Rien ne s'affiche en deçà de deux lots (le total serait la fiche du lot) ni sans tantièmes
  lisibles (un locataire).
-->
<script lang="ts">
	import ChargesDuLot from '$lib/components/ChargesDuLot.svelte';
	import { totauxParCle } from '$lib/charges-lots';
	import type { MonLot } from '$lib/api';

	export let lots: Pick<MonLot, 'quotes_parts'>[];

	$: lignes = totauxParCle(lots).map((t) => ({
		...t,
		precision: t.lots > 1 ? `${t.lots} de mes lots` : undefined,
	}));
</script>

{#if lots.length > 1 && lignes.length}
	<section class="card totaux" aria-labelledby="titre-totaux-charges">
		<h2 id="titre-totaux-charges" class="section-title">Mes charges, tous mes lots</h2>
		<p class="aide">
			Chaque clé de charges additionne les parts de ceux de vos lots qui y contribuent.
		</p>
		<ChargesDuLot {lignes} titre="Mes charges, tous mes lots" />
	</section>
{/if}

<style>
	.totaux {
		margin-bottom: 1rem;
	}
</style>
