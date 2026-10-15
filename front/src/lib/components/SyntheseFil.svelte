<!--
  SyntheseFil.svelte — la synthèse d'une affaire close, côté FIL (#1643).

  Ce que le fil d'une affaire close demande au serveur — la synthèse lisible,
  et si l'on peut en produire une —, puis ce qu'il en montre au-dessus de
  l'Historique : le bouton « 🧾 Produire la synthèse » (le conseil, affaire du
  carnet close sans synthèse) ou la mention qu'elle est en préparation.

  🔴 Il est monté par les DEUX rendus du fil, la fiche (`HistoriqueTicket`) et la
  carte dépliée de la liste (`CarteTicket`), qui ne partagent pas leur câblage.
  Livré d'abord dans la seule fiche (v2.99.0), le bouton manquait à la liste et
  la Suite y paraissait vide — trouvé à l'écran par l'utilisateur, pas par un
  contrôle.

  🧾 Il rend AUSSI la synthèse elle-même, en bloc au-dessus du fil (15/10/2026,
  maquette A de la carte dépliée). Elle se rendait dans le créneau `synthese` de
  `RubriqueHistorique`, à la date de sa Suite — câblé deux fois, à l'identique,
  par la carte et par la fiche. Le fil ne raconte plus cette Suite sans texte
  (`entreesDuFil`) : elle est la conclusion de l'affaire, pas une étape.
-->
<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import { syntheses, type EtatSynthese, type Ticket } from '$lib/api';
	import { messageErreur } from '$lib/erreurs';
	import { isCS } from '$lib/stores/auth';
	import { estTicketClos } from '$lib/tickets';
	import EtatListe from './EtatListe.svelte';
	import SyntheseAffaire from './SyntheseAffaire.svelte';
	import { toast } from './Toast.svelte';

	export let ticket: Pick<Ticket, 'id' | 'statut'> | null;
	/** Le fil : relu à chaque écriture, il fait relire la synthèse avec lui. */
	export let evolutions: unknown[] = [];
	/** L'état lu : la synthèse lisible, et ce que le conseil peut en faire. */
	let etat: EtatSynthese | null = null;

	const dispatch = createEventDispatcher<{ change: void }>();

	let erreur = '';
	let enCours = false;
	$: cle = ticket && estTicketClos(ticket.statut) ? `${ticket.id}:${evolutions.length}` : null;
	$: if (cle) recharger();
	$: if (!cle) etat = null;

	async function recharger() {
		if (!ticket) return;
		erreur = '';
		try {
			etat = await syntheses.lire(ticket.id);
		} catch (e) {
			etat = null;
			erreur = messageErreur(e);
		}
	}

	async function produire() {
		if (!ticket) return;
		enCours = true;
		try {
			await syntheses.produire(ticket.id);
			dispatch('change');
			toast('success', 'Synthèse produite — à relire, puis valider');
		} catch (e) {
			toast('error', messageErreur(e));
		} finally {
			enCours = false;
		}
	}
</script>

<EtatListe compact {erreur} />
{#if $isCS && etat?.produisible}
	<div class="synthese-fil">
		<button class="btn btn-outline btn-sm" disabled={enCours} on:click={produire}
			>{enCours ? 'Rédaction…' : '🧾 Produire la synthèse'}</button
		>
	</div>
{:else if $isCS && etat?.en_attente}
	<p class="aide">
		🧾 La synthèse de l’affaire est en préparation : elle paraîtra ici sous quarante minutes.
	</p>
{/if}
{#if etat?.synthese}
	<SyntheseAffaire synthese={etat.synthese} gestes={$isCS} on:change={recharger} />
{/if}

<style>
	.synthese-fil {
		display: flex;
		justify-content: flex-end;
		margin-bottom: 0.5rem;
	}
</style>
