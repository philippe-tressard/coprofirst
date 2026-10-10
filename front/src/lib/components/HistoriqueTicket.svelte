<!--
  HistoriqueTicket.svelte — le fil d'un ticket, et les gestes qui l'alimentent.

  ## Pourquoi ce composant (18/08/2026)

  Le fil d'un ticket était rendu à **deux endroits** : `CarteTicket` (la liste) et
  la fiche `/tickets/[id]`, chacun avec son propre câblage. Deux rendus de la même
  entité, donc deux jeux de branchements à tenir d'accord — et ils ne l'ont pas
  été, **deux fois, dans les deux sens** :

    • le CRAYON servait la fiche et manquait à la liste (#431) ;
    • la CORBEILLE, ajoutée à la liste, manquait à la fiche le jour même.

  Le second écart est celui qui a fait naître ce fichier : le garde-fou de
  modularité a refusé que la fiche grossisse pour recevoir le handler manquant, et
  il avait raison — ce n'était pas un problème de taille mais de **placement**. Un
  fil de ticket, avec son formulaire de commentaire, sa correction d'entrée et sa
  suppression, est une notion : elle s'écrit une fois.

  🔴 La carte dépliée de la LISTE (`CarteTicket`) ne passe PAS par ce composant :
  elle monte son propre fil. Tout ce qui s'ajoute au fil d'une affaire s'ajoute
  aux deux — la synthèse ne l'a été d'abord qu'ici (v2.99.0), d'où `SyntheseFil`,
  monté par les deux, et `test_chaque_fil_d_affaire_monte_la_synthese`.

  ⚠️ Ce composant ne remplace pas `RubriqueHistorique`, il l'**habille** : la
  rubrique reste le fil générique — actualités, événements, espace CS l'utilisent
  aussi — et celui-ci y ajoute ce qui est propre au TICKET.

  ## Ce qu'il décide, et ce qu'il ne décide pas

  Il porte les gestes et leurs appels d'API. La page garde ce qu'elle seule sait :
  quel ticket, et quoi faire après (recharger sa liste). D'où `on:change`, émis
  après chaque écriture — c'est le seul contrat.
-->
<script lang="ts">
	import ChargementDiffere from '$lib/components/ChargementDiffere.svelte';
	import { SUITE } from '$lib/gestes';
	import MentionFusion from './MentionFusion.svelte';
	import { createEventDispatcher } from 'svelte';
	import RubriqueHistorique from './RubriqueHistorique.svelte';
	import EtatListe from './EtatListe.svelte';
	import { TITRE_HISTORIQUE } from '$lib/archives';
	import SyntheseAffaire from './SyntheseAffaire.svelte';
	import SyntheseFil from './SyntheseFil.svelte';
	import type { EtatSynthese, Ticket } from '$lib/api';
	import { tickets as ticketsApi, type TicketEvolution } from '$lib/api';
	import { messageErreur } from '$lib/erreurs';
	import { toast } from './Toast.svelte';
	import { currentUser, isAdmin, isCS } from '$lib/stores/auth';
	import { STATUT_TICKET_LABELS } from '$lib/tickets';
	import { chargeCorrection, evolutionIcone, type ChargeUtileEvolution } from '$lib/evolutions';

	export let ticketId: number;
	/**  L'affaire : la Suite et sa correction en DÉRIVENT tout — état, périmètre,
	 *   options, assistant, motif WhatsApp (`SuiteAffaire`, 01/10/2026). La fiche
	 *   les calculait et les passait un à un, la liste les recalculait : deux
	 *   écritures de chaque, qui avaient divergé (l'adresse externe). */
	export let ticket: Ticket | null = null;
	export let evolutions: TicketEvolution[] = [];
	/** Le fil n'a pas pu être chargé : on le DIT, au lieu d'un fil vide. */
	export let erreurSuivi = '';

	/** Émis après toute écriture — la page recharge ce qu'elle affiche. */
	const dispatch = createEventDispatcher<{ change: void }>();

	let ouvert = false;
	let enEdition: number | null = null;
	let enregistre = false;
	let corrige = false;

	//  🧾 La synthèse d'une affaire close (#1643) : `SyntheseFil` la lit et offre
	//  « Produire » ; la Suite se rend ici, dans le créneau `synthese`.
	let etatSynthese: EtatSynthese | null = null;
	let filSynthese: SyntheseFil;

	async function ajouter(e: CustomEvent<ChargeUtileEvolution>) {
		enregistre = true;
		try {
			//  Les options voyagent AVEC l'entrée (`SuiteAffaire` les y a mises) :
			//  c'est le serveur qui les applique, pas un second appel qui pourrait
			//  réussir à moitié.
			await ticketsApi.addEvolution(ticketId, e.detail);
			ouvert = false;
			dispatch('change');
			toast('success', e.detail?.nouveau_statut ? 'Statut mis à jour' : 'Commentaire ajouté');
		} catch (err) {
			toast('error', messageErreur(err));
		} finally {
			enregistre = false;
		}
	}

	//  🔄 TOUTES les sections se corrigent, Suivi compris (01/10/2026) — la
	//  correction reste sur l'entrée, à sa date, sans ajouter d'étape au fil
	//  (`app/utils/suivi_fil.py`). La charge : `chargeCorrection`, seule écriture.
	async function corriger(e: CustomEvent<ChargeUtileEvolution>) {
		if (enEdition === null) return;
		corrige = true;
		try {
			await ticketsApi.updateEvolution(ticketId, enEdition, chargeCorrection(e.detail));
			enEdition = null;
			dispatch('change');
			toast('success', 'Entrée corrigée');
		} catch (err) {
			toast('error', messageErreur(err));
		} finally {
			corrige = false;
		}
	}

	//  Effacer — ADMIN seulement, et le serveur le revérifie (`require_admin`). Une
	//  transition d'état est refusée côté serveur (422) et n'affiche pas de
	//  corbeille côté écran : l'écran dit la même chose que le serveur.
	async function supprimer(e: CustomEvent<number>) {
		try {
			await ticketsApi.deleteEvolution(ticketId, e.detail);
			dispatch('change');
			toast('success', 'Entrée supprimée');
		} catch (err) {
			toast('error', messageErreur(err));
		}
	}
</script>

<div class="bloc-historique colonne-lecture">
	<EtatListe compact erreur={erreurSuivi} />
	<SyntheseFil
		bind:this={filSynthese}
		bind:etat={etatSynthese}
		{ticket}
		{evolutions}
		on:change={() => dispatch('change')}
	/>
	<RubriqueHistorique
		avecFiltre
		{evolutions}
		statutLabels={STATUT_TICKET_LABELS}
		titre={TITRE_HISTORIQUE}
		vide="Aucune évolution enregistrée."
		peutModifier={$isCS && !ticket?.fusionnee}
		currentUserId={$currentUser?.id}
		estAdmin={$isAdmin}
		avecSuppression
		{enEdition}
		on:modifier={(e) => (enEdition = e.detail)}
		on:supprimer={supprimer}
	>
		<svelte:fragment slot="action">
			{#if ticket?.fusionnee}
				<MentionFusion {ticket} />
			{:else if $isCS}
				<button class="btn btn-outline btn-sm" on:click={() => (ouvert = !ouvert)}>
					<!--  Le bouton et l'entrée qu'il produit lisent la MÊME table : c'est ce
					      qui les empêche de diverger, et c'est précisément par là que
					      l'écart est arrivé (19/08/2026). -->
					{ouvert ? '✕ Annuler' : `${evolutionIcone('commentaire')} ${SUITE.libelle}`}
				</button>
			{/if}
		</svelte:fragment>

		<svelte:fragment slot="synthese" let:evol>
			{#if etatSynthese?.synthese && etatSynthese.synthese.evolution_id === evol.id}
				<SyntheseAffaire
					synthese={etatSynthese.synthese}
					gestes={$isCS}
					on:change={() => filSynthese.recharger()}
				/>
			{/if}
		</svelte:fragment>

		<svelte:fragment slot="edition" let:evol>
			{#if ticket}
				{#key enEdition}
					<ChargementDiffere charger={() => import('$lib/components/SuiteAffaire.svelte')}>
						{#snippet contenu(SuiteAffaire)}
							<SuiteAffaire
								{ticket}
								{evol}
								entrees={evolutions}
								peutSuivre={$isCS}
								saving={corrige}
								on:submit={corriger}
								on:cancel={() => (enEdition = null)}
							/>
						{/snippet}
					</ChargementDiffere>
				{/key}
			{/if}
		</svelte:fragment>
	</RubriqueHistorique>

	{#if ouvert && ticket}
		<div class="evol-form card">
			{#key ouvert}
				<ChargementDiffere charger={() => import('$lib/components/SuiteAffaire.svelte')}>
					{#snippet contenu(SuiteAffaire)}
						<SuiteAffaire
							{ticket}
							entrees={evolutions}
							peutSuivre={$isCS}
							saving={enregistre}
							on:submit={ajouter}
							on:cancel={() => (ouvert = false)}
						/>
					{/snippet}
				</ChargementDiffere>
			{/key}
		</div>
	{/if}
</div>

<style>
	/*  Le balisage part avec ses styles : une classe posée ici et définie dans la
	    page ne serait pas atteinte (panne des pastilles nues, v2.67.11). */
	.bloc-historique {
		margin-top: 1.5rem;
	}
	.evol-form {
		margin-top: 1rem;
	}
</style>
