<!--
  FluxAffaireEtapes.svelte — le corps d'une AFFAIRE dépliée au fil d'activité :
  les trois étapes de la liste Affaires, ouvertes sur « La suite ».

  ## Pourquoi (arbitrage n° 66, 18/10/2026, #2078)

  Une même affaire dépliée avait deux rendus : la brique des trois étapes dans la
  liste (`RubriqueEtape`, maquette G), trois encarts A dans le fil
  (`FluxRubriquesAffaire`, retiré). Le fil montre désormais la MÊME brique, par le
  même composant (`CorpsCarteTicket`) ; seule l'étape dépliée change — « La suite »,
  parce que le fil répond à « quoi de neuf ».

  ## Pourquoi on charge à l'ouverture, et pas dans la réponse du fil

  Le fil ne porte que la DERNIÈRE suite (`meta.evol_*`) ; la brique montre jusqu'à
  trois entrées, leurs pièces, la synthèse. Les envoyer pour chaque carte alourdirait
  une réponse que l'accueil lit entière. La carte de la liste fait déjà l'inverse —
  la fiche et le fil se chargent au dépliage — : ici de même, et le corps (`CorpsCarteTicket`)
  est différé comme là-bas (#1860), préchargé quand la main s'approche (`FluxCard`).

  Lecture seule : le fil informe, il ne sert pas à corriger. Les gestes d'édition
  restent sur la page Affaires (`peutSuivre` faux, gestes inertes) ; seul `filChange`
  agit — un transfert défait ou une synthèse produite se relisent ici.
-->
<script lang="ts">
	import { onMount } from 'svelte';
	import ChargementDiffere from '$lib/components/ChargementDiffere.svelte';
	import EtatListe from './EtatListe.svelte';
	import { tickets, type FluxItem, type Ticket, type TicketEvolution } from '$lib/api';
	import { messageErreur } from '$lib/erreurs';
	import type { GestesTicket } from '$lib/tickets';
	import { chargerCorpsAffaire } from '$lib/affaire-au-fil';

	export let item: FluxItem;

	let ticket: Ticket | null = null;
	let evolutions: TicketEvolution[] = [];
	let erreur = '';

	$: ticketId = item.meta?.ticket_id as number | undefined;

	async function charger() {
		if (ticketId === undefined) return;
		try {
			[ticket, evolutions] = await Promise.all([
				tickets.get(ticketId),
				tickets.evolutions(ticketId),
			]);
			erreur = '';
		} catch (e) {
			//  Dit, jamais avalé : un fil vide se lirait comme une affaire sans suite.
			erreur = messageErreur(e);
		}
	}
	onMount(charger);

	const inerte = () => {};
	const gestes: GestesTicket = {
		basculer: inerte,
		evoluerOuvrir: inerte,
		modifier: inerte,
		optionsOuvrir: inerte,
		optionsEnregistrer: inerte,
		supprimer: inerte,
		archiver: inerte,
		evoluer: inerte,
		evolModifier: inerte,
		evolCorriger: inerte,
		evolSupprimer: inerte,
		evolAnnuler: inerte,
		modifie: inerte,
		annuler: inerte,
		filChange: charger,
	};
</script>

{#if ticket}
	<!--  Constante : le rétrécissement de `ticket` ne traverse pas le snippet. -->
	{@const affaire = ticket}
	<ChargementDiffere charger={chargerCorpsAffaire}>
		{#snippet contenu(CorpsCarteTicket)}
			<CorpsCarteTicket ticket={affaire} {evolutions} {gestes} ouverteParDefaut="suite" />
		{/snippet}
	</ChargementDiffere>
{:else}
	<EtatListe compact chargement={!erreur} {erreur} messageChargement="Chargement de l'affaire…" />
{/if}
