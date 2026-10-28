<!--
  **Ce qu'il faut savoir d'un lot selon le règlement** (#2215, #2251) — ses alertes, et le
  chemin vers sa part. Écrit ici UNE fois pour les endroits qui montrent un lot à son
  propriétaire : la fiche d'un lot, la carte d'un lot possédé, le lot d'un locataire qui en
  possède aussi.

  🔴 Les CHIFFRES n'y sont plus (#2251, maquette A du 25/10/2026) : la part de chaque lot se
  lit dans le tableau croisé « Mes charges selon le règlement » (`TableauCharges`), une
  colonne par lot. La carte ne les répète pas — ni tableau ni phrase de charges —, elle
  renvoie à la colonne du lot, que le tableau surligne un instant. La désignation (situé
  dans, desservi par) reste au-dessus, dans `CaracteristiquesLot`.

  Les alertes viennent du serveur (`utils/alertes_lot`) et se rendent par `ConstatsLots`.
-->
<script lang="ts">
	import ConstatsLots from '#lib/components/ConstatsLots.svelte';
	import { lotSurligne } from '#lib/charges-lots.ts';
	import type { MonLot } from '#lib/api/index.ts';

	export let lot: Pick<MonLot, 'id' | 'quotes_parts' | 'alertes'>;
</script>

{#if lot.quotes_parts?.length}
	<p class="vers-charges">
		<a href="#mes-charges" on:click={() => lotSurligne.set(lot.id)}
			>Voir sa colonne dans le tableau des charges ↑</a
		>
	</p>
{/if}
{#if lot.alertes?.length}
	<div class="alertes">
		<ConstatsLots constats={lot.alertes} />
	</div>
{/if}

<style>
	.vers-charges {
		margin: 0.6rem 0 0;
		font-size: var(--fs-sm);
	}
	.alertes {
		margin-top: 0.75rem;
	}
</style>
