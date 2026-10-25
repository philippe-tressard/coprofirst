<!--
  **Ce que le règlement dit d'un lot, et ce qu'il faut en savoir** (#2215) — la phrase qui
  explique la charge, les parts clé par clé, et les alertes du lot. Écrit ici UNE fois pour
  les endroits qui montrent un lot à son propriétaire : la fiche d'un lot, la carte d'un lot
  possédé, le lot d'un locataire qui en possède aussi.

  Tout vient du serveur et se montre tel quel : la phrase (`utils/lots_explication`), les
  parts (`quotes_parts`) et les alertes (`utils/alertes_lot`, rendues par le composant du
  patrimoine, `ConstatsLots`). Un lecteur sans droit aux tantièmes reçoit `null` : le tableau
  disparaît, et la phrase s'arrête à la desserte.
-->
<script lang="ts">
	import ChargesDuLot from '$lib/components/ChargesDuLot.svelte';
	import ConstatsLots from '$lib/components/ConstatsLots.svelte';
	import type { MonLot } from '$lib/api';

	export let lot: Pick<MonLot, 'quotes_parts' | 'explication' | 'alertes'>;

	$: lignes = (lot.quotes_parts ?? []).map((q) => ({
		...q,
		precision: q.nb_lots > 1 ? `${q.nb_lots} lots y contribuent` : undefined,
	}));
</script>

{#if lot.explication}<p class="aide explication">{lot.explication}</p>{/if}
<ChargesDuLot {lignes} />
{#if lot.alertes?.length}
	<div class="alertes">
		<ConstatsLots constats={lot.alertes} />
	</div>
{/if}

<style>
	.explication {
		margin: 0.75rem 0 0.5rem;
		max-width: 60ch;
	}
	.alertes {
		margin-top: 0.75rem;
	}
</style>
