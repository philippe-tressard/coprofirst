<!--
  CorpsCarteTicket.svelte — le corps DÉPLIÉ d'une carte d'affaire : la fiche de
  lecture et son fil, ou l'un des trois panneaux (options, correction, Suite).

  ## Pourquoi un composant à part (12/10/2026, #1860)

  `CarteTicket` importait statiquement tout ce que seul le dépliage affiche —
  le fil (`RubriqueHistorique`), la synthèse d'une affaire close et ses six
  rubriques, les transferts de courriels, la fiche de lecture, le panneau
  d'options. La page Affaires les téléchargeait à l'ouverture, pour des cartes
  qu'on ouvre une à une. La carte le charge désormais au geste, par
  `ChargementDiffere`, et le PRÉCHARGE dès que la main s'en approche
  (`CarteListe onApprocher`) : le dépliage n'attend pas un aller-retour.

  La carte garde l'en-tête, l'aperçu et le conteneur `.carte-corps` (le fondu
  d'entrée, #1579) ; ce composant n'en rend que le CONTENU.

  🔴 Il parle à la page par `gestes`, comme `ActualiteEnListe` — jamais par
  `bind:this` depuis la carte : tant que le morceau n'est pas arrivé, la
  référence vaudrait `null` (règle de `ChargementDiffere`).
-->
<script lang="ts">
	import ChargementDiffere from '$lib/components/ChargementDiffere.svelte';
	import EtatListe from './EtatListe.svelte';
	import PanneauOptionsPublication from './PanneauOptionsPublication.svelte';
	import FicheLecture from './FicheLecture.svelte';
	import RubriqueHistorique from './RubriqueHistorique.svelte';
	import SyntheseFil from './SyntheseFil.svelte';
	import TransfertsVerses from './TransfertsVerses.svelte';
	import MentionFusion from './MentionFusion.svelte';
	import type { Ticket, TicketEvolution } from '$lib/api';
	import { currentUser, isAdmin } from '$lib/stores/auth';
	import { TICKET } from '$lib/entites/ticket';
	import {
		OPTIONS_TICKET,
		optionsDuTicket,
		optionsVersTicket,
		STATUT_TICKET_LABELS,
		estTicketClos,
		statutTicketLabel,
		type GestesTicket,
	} from '$lib/tickets';
	import { entreesDuFil } from '$lib/evolutions';
	import { fmtDate } from '$lib/date';
	import { equipLabel, intervenantAffiche } from '$lib/prestataires';

	export let ticket: Ticket;
	export let evolutions: TicketEvolution[] = [];
	/** Le fil n'a pas pu être chargé : on le DIT, au lieu d'un fil vide. */
	export let erreurSuivi = '';
	/** Ce que la page a ouvert sur cette carte — le contrat de `CarteTicket`. */
	export let mode: 'lecture' | 'edition' | 'evolution' | 'options' = 'lecture';
	export let optionsRapidesEnCours = false;
	export let evolutionEnCours = false;
	export let evolEnEdition: number | null = null;
	export let evolCorrectionEnCours = false;
	/** Le lecteur peut-il suivre cette affaire ? Calculé par la carte (`peutCommenter`). */
	export let peutSuivre = false;
	export let gestes: GestesTicket;

	//  Le brouillon du panneau rapide : on ne touche PAS au ticket affiché tant
	//  que le serveur n'a pas répondu — sinon l'écran montre un état enregistré
	//  qui ne l'est pas, et le laisse faux si la requête échoue.
	//  `confidentiel` : la clé que le panneau attend. La case 🔒 n'y est plus
	//  rendue (en tête du Périmètre, 25/09/2026), et elle ne repart pas.
	const optionsRapidesInitiales = () => ({ ...optionsDuTicket(ticket), confidentiel: false });
	let optionsRapides = optionsRapidesInitiales();
	$: if (mode === 'options') optionsRapides = optionsRapidesInitiales();

	//  « La suite · n » compte ce que le fil raconte — la même liste que lui.
	$: suites = entreesDuFil(evolutions);
	//  La clôture se lit dans le fil : la dernière transition vers un état clos.
	//  Le modèle n'en garde pas la date (pas de `statut_change_le` sur l'affaire).
	$: cloture = estTicketClos(ticket.statut)
		? suites
				.filter((e) => e.type === 'etat' && e.nouveau_statut === ticket.statut)
				.sort((a, b) => b.cree_le.localeCompare(a.cree_le))[0]
		: undefined;
</script>

{#if mode === 'options'}
	<div class="tk-formulaire">
		<PanneauOptionsPublication
			objet="ticket"
			optionsRendues={OPTIONS_TICKET}
			perimetreCible={ticket.perimetre_cible ?? []}
			dejaEpingle={ticket.epingle ?? false}
			enregistrement={optionsRapidesEnCours}
			bind:options={optionsRapides}
			on:enregistrer={() =>
				gestes.optionsEnregistrer(
					ticket,
					optionsVersTicket({
						epingle: optionsRapides.epingle,
						urgente: optionsRapides.urgente,
						brouillon: optionsRapides.brouillon,
						suiviKanban: optionsRapides.suiviKanban,
					}),
				)}
			on:annuler={() => gestes.annuler()}
		/>
	</div>
{:else if mode === 'edition'}
	<div class="tk-formulaire">
		<ChargementDiffere charger={() => import('$lib/components/FormulaireTicket.svelte')}>
			{#snippet contenu(FormulaireTicket)}
				<FormulaireTicket
					{ticket}
					on:modifie={(e) => gestes.modifie(e.detail)}
					on:annule={() => gestes.annuler()}
				/>
			{/snippet}
		</ChargementDiffere>
	</div>
{:else if mode === 'evolution'}
	<div class="tk-formulaire">
		<!--  Le MÊME montage que la fiche (`SuiteAffaire`, 01/10/2026). -->
		<ChargementDiffere charger={() => import('$lib/components/SuiteAffaire.svelte')}>
			{#snippet contenu(SuiteAffaire)}
				<SuiteAffaire
					{ticket}
					entrees={evolutions}
					{peutSuivre}
					saving={evolutionEnCours}
					on:submit={(e) => gestes.evoluer(ticket, e.detail)}
					on:cancel={() => gestes.annuler()}
				/>
			{/snippet}
		</ChargementDiffere>
	</div>
{:else}
	<!--  Trois rubriques titrées (maquette A, arbitrée le 15/10/2026) : la DEMANDE,
	      sa SYNTHÈSE quand l'affaire est close, la SUITE. L'ordre des sections de
	      la demande reste celui du cadre (R2, `FicheLecture`) : la maquette rangeait
	      intervenant et équipement dans un bloc « Autour » sous la description, ce
	      que l'ordre des sections ne permet pas. -->
	<h4 class="intertitre">La demande</h4>
	<FicheLecture
		entite={TICKET}
		description={ticket.description}
		intervenant={intervenantAffiche(ticket)}
		equipement={ticket.equipement ? equipLabel(ticket.equipement) : ''}
		photos={ticket.photos_urls ?? []}
		documents={ticket.fichiers_urls ?? []}
		affairesLiees={ticket.affaires_liees}
	/>
	<MentionFusion {ticket} />

	<!--  Défaire un transfert de courriel, comme sur la fiche (#1482) : la
	      carte n'ouvre pas la fiche, et c'était le seul endroit du geste. -->
	<TransfertsVerses
		ticketId={ticket.id}
		encadre={false}
		on:change={() => gestes.filChange(ticket)}
	/>
	<EtatListe compact erreur={erreurSuivi} />
	<!--  🧾 La synthèse d'une affaire close (#1643), en bloc — comme sur la fiche. -->
	<SyntheseFil {ticket} {evolutions} on:change={() => gestes.filChange(ticket)} />
	{#if suites.length > 0}
		<h4 class="intertitre">La suite · {suites.length}</h4>
		<!--  Le crayon par entrée : il existait dans la rubrique depuis #431,
		      et la fiche du ticket s'en servait — mais pas cette liste-ci.
		      Un même fil modifiable sur un écran et pas sur l'autre.
		      ⚠️ Les états ne sont PAS proposés en correction : corriger le
		      texte d'une entrée ne rejoue pas la transition qu'elle a
		      enregistrée (`test_correction_pas_transition.py`).
		      Trois entrées, puis « plus anciennes » : la carte se lit d'un regard. -->
		<RubriqueHistorique
			avecFiltre
			{evolutions}
			seuil={4}
			apercu={3}
			statutLabels={STATUT_TICKET_LABELS}
			peutModifier={peutSuivre}
			currentUserId={$currentUser?.id}
			estAdmin={$isAdmin}
			avecSuppression
			enEdition={evolEnEdition}
			on:modifier={(e) => gestes.evolModifier(e.detail)}
			on:supprimer={(e) => gestes.evolSupprimer({ ticket, evolId: e.detail })}
		>
			<svelte:fragment slot="edition" let:evol>
				{#key evolEnEdition}
					<ChargementDiffere charger={() => import('$lib/components/SuiteAffaire.svelte')}>
						{#snippet contenu(SuiteAffaire)}
							<SuiteAffaire
								{ticket}
								{evol}
								entrees={evolutions}
								{peutSuivre}
								saving={evolCorrectionEnCours}
								on:submit={(e) => gestes.evolCorriger(ticket, e.detail)}
								on:cancel={() => gestes.evolAnnuler()}
							/>
						{/snippet}
					</ChargementDiffere>
				{/key}
			</svelte:fragment>
		</RubriqueHistorique>
	{/if}
	<!--  Le NUMÉRO est dans l'en-tête : pas deux fois le même fait. -->
	<p class="tk-meta">
		Créée le {fmtDate(ticket.cree_le)}{cloture
			? ` · ${statutTicketLabel(ticket.statut)} le ${fmtDate(cloture.cree_le)}`
			: ''}
	</p>
{/if}

<style>
	.tk-formulaire {
		padding: 0.25rem 0;
	}
	.tk-meta {
		margin: 0.9rem 0 0;
		color: var(--color-text-muted);
		font-size: var(--fs-sm);
	}
</style>
