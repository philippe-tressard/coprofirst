<!--
  FilActualiteEnListe.svelte — le fil d'une actualité DÉPLIÉE dans la liste des affaires.

  ## Pourquoi il vit à part (13/10/2026, #1861)

  `ActualiteEnListe` l'importait en tête : `RubriqueHistorique` entrait donc dans
  l'OUVERTURE de la page Affaires, alors que seul le dépliage d'une actualité
  l'affiche — le reste de #1860, qui avait fait de même pour `CorpsCarteTicket`.
  Il se charge par `ChargementDiffere`, avec le chargeur NOMMÉ que la carte
  appelle aussi à l'approche de la main (`CarteListe onApprocher`).

  Le parent ne lui parle que par props et `gestes` : aucune méthode, aucun
  `bind:this` (`ChargementDiffere`, la référence vaut `null` avant l'arrivée).
-->
<script lang="ts">
	import ChargementDiffere from '#lib/components/ChargementDiffere.svelte';
	import type { Ticket, TicketEvolution } from '#lib/api/index.ts';
	import { currentUser, isCS } from '#lib/stores/auth.ts';
	import type { GestesTicket } from '#lib/tickets.ts';
	import RubriqueHistorique from './RubriqueHistorique.svelte';

	export let ticket: Ticket;
	export let evolutions: TicketEvolution[];
	export let peutAdministrer = false;
	export let evolEnEdition: number | null = null;
	export let evolCorrectionEnCours = false;
	export let gestes: GestesTicket;
</script>

<div class="actu-fil">
	<RubriqueHistorique
		{evolutions}
		peutModifier={$isCS}
		currentUserId={$currentUser?.id}
		estAdmin={peutAdministrer}
		avecSuppression
		enEdition={evolEnEdition}
		on:modifier={(e) => gestes.evolModifier(e.detail)}
		on:supprimer={(e) => gestes.evolSupprimer({ ticket, evolId: e.detail })}
	>
		<svelte:fragment slot="edition" let:evol>
			<!--  Sa correction rouvre ses sections, comme celle d'une affaire. -->
			<ChargementDiffere charger={() => import('#lib/components/SuiteAffaire.svelte')}>
				{#snippet contenu(SuiteAffaire)}
					<SuiteAffaire
						{ticket}
						{evol}
						entrees={evolutions}
						peutSuivre
						saving={evolCorrectionEnCours}
						on:submit={(e) => gestes.evolCorriger(ticket, e.detail)}
						on:cancel={gestes.evolAnnuler}
					/>
				{/snippet}
			</ChargementDiffere>
		</svelte:fragment>
	</RubriqueHistorique>
</div>

<style>
	/*  La marge qui sépare le fil de ce qu'il suit — le parent seul sait ce
	    qu'il y a au-dessus. */
	.actu-fil {
		margin-top: 0.9rem;
	}
</style>
