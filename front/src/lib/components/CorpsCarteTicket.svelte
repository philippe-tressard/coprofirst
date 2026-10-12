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
	import SyntheseAffaire from './SyntheseAffaire.svelte';
	import SyntheseFil from './SyntheseFil.svelte';
	import TransfertsVerses from './TransfertsVerses.svelte';
	import MentionFusion from './MentionFusion.svelte';
	import type { EtatSynthese, Ticket, TicketEvolution } from '$lib/api';
	import { currentUser, isAdmin, isCS } from '$lib/stores/auth';
	import { TICKET } from '$lib/entites/ticket';
	import {
		OPTIONS_TICKET,
		optionsDuTicket,
		optionsVersTicket,
		STATUT_TICKET_LABELS,
		type GestesTicket,
	} from '$lib/tickets';
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

	//  🧾 La synthèse d'une affaire close (#1643) : lue par `SyntheseFil`.
	let etatSynthese: EtatSynthese | null = null;
	let filSynthese: SyntheseFil;
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
	<FicheLecture
		entite={TICKET}
		description={ticket.description}
		intervenant={intervenantAffiche(ticket)}
		equipement={ticket.equipement ? equipLabel(ticket.equipement) : ''}
		photos={ticket.photos_urls ?? []}
		documents={ticket.fichiers_urls ?? []}
		affairesLiees={ticket.affaires_liees}
	>
		<svelte:fragment slot="pied">
			<!--  Le NUMÉRO est dans l'en-tête : pas deux fois le même fait. -->
			<small class="tk-meta">Créé le {fmtDate(ticket.cree_le)}</small>
		</svelte:fragment>
	</FicheLecture>
	<MentionFusion {ticket} />

	<!--  Défaire un transfert de courriel, comme sur la fiche (#1482) : la
	      carte n'ouvre pas la fiche, et c'était le seul endroit du geste. -->
	<TransfertsVerses
		ticketId={ticket.id}
		encadre={false}
		on:change={() => gestes.filChange(ticket)}
	/>
	<EtatListe compact erreur={erreurSuivi} />
	<!--  🧾 La synthèse d'une affaire close (#1643), comme sur la fiche. -->
	<SyntheseFil
		bind:this={filSynthese}
		bind:etat={etatSynthese}
		{ticket}
		{evolutions}
		on:change={() => gestes.filChange(ticket)}
	/>
	{#if evolutions.length > 0}
		<div class="tk-fil">
			<!--  Le crayon par entrée : il existait dans la rubrique depuis #431,
			      et la fiche du ticket s'en servait — mais pas cette liste-ci.
			      Un même fil modifiable sur un écran et pas sur l'autre.
			      ⚠️ Les états ne sont PAS proposés en correction : corriger le
			      texte d'une entrée ne rejoue pas la transition qu'elle a
			      enregistrée (`test_correction_pas_transition.py`). -->
			<RubriqueHistorique
				avecFiltre
				{evolutions}
				statutLabels={STATUT_TICKET_LABELS}
				peutModifier={peutSuivre}
				currentUserId={$currentUser?.id}
				estAdmin={$isAdmin}
				avecSuppression
				enEdition={evolEnEdition}
				on:modifier={(e) => gestes.evolModifier(e.detail)}
				on:supprimer={(e) => gestes.evolSupprimer({ ticket, evolId: e.detail })}
			>
				<svelte:fragment slot="synthese" let:evol>
					{#if etatSynthese?.synthese?.evolution_id === evol.id}
						<SyntheseAffaire
							synthese={etatSynthese.synthese}
							gestes={$isCS}
							on:change={() => filSynthese.recharger()}
						/>
					{/if}
				</svelte:fragment>
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
		</div>
	{/if}
{/if}

<style>
	.tk-formulaire {
		padding: 0.25rem 0;
	}
	.tk-meta {
		color: var(--color-text-muted);
		font-size: var(--fs-sm);
	}
	/*  La marge haute du fil appartient à son hôte : la rubrique ne sait pas ce
	    qu'elle suit. C'est cette marge que la fiche du ticket avait perdue. */
	.tk-fil {
		margin-top: 0.9rem;
	}
</style>
