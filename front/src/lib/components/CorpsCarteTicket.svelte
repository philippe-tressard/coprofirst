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
	import RubriqueEtape from './RubriqueEtape.svelte';
	import ComptesRendusAffaire from './ComptesRendusAffaire.svelte';
	import RubriqueHistorique from './RubriqueHistorique.svelte';
	import SyntheseFil from './SyntheseFil.svelte';
	import TransfertsVerses from './TransfertsVerses.svelte';
	import MentionFusion from './MentionFusion.svelte';
	import MentionConservation from './MentionConservation.svelte';
	import type { Ticket, TicketEvolution } from '$lib/api';
	import { currentUser, isAdmin, isCS } from '$lib/stores/auth';
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
	import { basculer } from '$lib/accordeon';
	import { entreesDuFil } from '$lib/evolutions';
	import { fmtDate } from '$lib/date';
	import { stripHtml } from '$lib/utils';
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
	/**  L'étape dépliée À L'OUVERTURE : « La demande » dans la liste Affaires,
	 *   « La suite » au fil d'activité (arbitrage n° 66, 18/10/2026) — le fil
	 *   montre d'abord ce qui vient d'arriver. Une affaire sans suite n'a que sa
	 *   demande : elle reste dépliée, c'est elle la nouvelle. */
	export let ouverteParDefaut: 'demande' | 'suite' = 'demande';

	//  Le brouillon du panneau rapide : on ne touche PAS au ticket affiché tant
	//  que le serveur n'a pas répondu — sinon l'écran montre un état enregistré
	//  qui ne l'est pas, et le laisse faux si la requête échoue.
	//  `confidentiel` : la clé que le panneau attend. La case 🔒 n'y est plus
	//  rendue (en tête du Périmètre, 25/09/2026), et elle ne repart pas.
	const optionsRapidesInitiales = () => ({ ...optionsDuTicket(ticket), confidentiel: false });
	let optionsRapides = optionsRapidesInitiales();
	$: if (mode === 'options') optionsRapides = optionsRapidesInitiales();

	//  « La suite · n entrées » compte ce que le fil raconte — la même liste que lui.
	$: suites = entreesDuFil(evolutions);

	//  🔴 L'accordéon des trois rubriques (`$lib/accordeon`) : une ouverte, la
	//  demande d'abord. Un identifiant, jamais un `Set`.
	let ouverte: 'demande' | 'suite' | 'comptes-rendus' | 'synthese' | null =
		ouverteParDefaut === 'suite' && entreesDuFil(evolutions).length === 0
			? 'demande'
			: ouverteParDefaut;

	//  Ce que dit une rubrique PLIÉE, sur une ligne. La demande : quand, et pour
	//  qui quand le conseil l'a saisie (lui seul le lit, comme la mention dépliée).
	$: resumeDemande = [
		fmtDate(ticket.cree_le),
		$isCS && ticket.saisi_pour_affichage ? `saisie pour ${ticket.saisi_pour_affichage}` : '',
	]
		.filter(Boolean)
		.join(' · ');
	//  La suite : la DERNIÈRE entrée — c'est elle qui dit « Résolu le 15 oct. ».
	$: derniere = [...suites].sort((a, b) => b.cree_le.localeCompare(a.cree_le))[0];
	$: resumeSuite = derniere ? resumeEntree(derniere) : '';

	/** PURE. Une entrée du fil en une ligne : son état et sa date, puis son texte. */
	function resumeEntree(e: TicketEvolution): string {
		const texte = e.contenu ? stripHtml(e.contenu) : '';
		const tete =
			e.type === 'etat' && e.nouveau_statut
				? `${statutTicketLabel(e.nouveau_statut)} le ${fmtDate(e.cree_le)}`
				: fmtDate(e.cree_le);
		return texte ? `${tete} — ${texte}` : tete;
	}
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
	<!--  Trois rubriques en ÉTAPES (maquette G, arbitrée le 16/10/2026, après la
	      maquette A du 15/10) : la DEMANDE, la SUITE, puis la SYNTHÈSE quand
	      l'affaire est close — la conclusion se lit en dernier. Chacune dans son
	      encart teinté, reliées par le rail ; une seule dépliée à la fois, la
	      demande d'abord (la suite au fil d'activité : `ouverteParDefaut`), les autres pliées sur une ligne qui dit l'essentiel.
	      L'ordre des sections de la demande reste celui du cadre (R2,
	      `FicheLecture`). -->
	<!--  Défaire un transfert de courriel, comme sur la fiche (#1482) : la carte
	      n'ouvre pas la fiche, et c'était le seul endroit du geste. AU-DESSUS des
	      étapes, jamais dans une étape pliée : c'est un geste en ATTENTE, qui ne
	      doit pas se cacher derrière un clic (16/10/2026). Vide, il ne rend rien. -->
	<TransfertsVerses
		ticketId={ticket.id}
		encadre={false}
		on:change={() => gestes.filChange(ticket)}
	/>
	<MentionConservation {ticket} />
	<RubriqueEtape
		titre="La demande"
		icone="inbox"
		resume={resumeDemande}
		ouverte={ouverte === 'demande'}
		onBasculer={() => (ouverte = basculer(ouverte, 'demande'))}
	>
		<FicheLecture
			entite={TICKET}
			description={ticket.description}
			intervenant={intervenantAffiche(ticket)}
			equipement={ticket.equipement ? equipLabel(ticket.equipement) : ''}
			photos={ticket.photos_urls ?? []}
			documents={ticket.fichiers_urls ?? []}
			affairesLiees={ticket.affaires_liees}
		>
			<!--  Qui l'a saisie POUR qui — le conseil seul le lit, avec l'adresse d'une
		      personne sans compte. La seule phrase du site qui nomme les deux rôles :
		      y substituer le propriétaire dirait « saisi par lui-même ». Elle ne
		      vivait que sur la fiche du lien direct, que la carte remplace
		      (15/10/2026). -->
			<svelte:fragment slot="specifiques">
				{#if ticket.saisi_pour_affichage && $isCS}
					<p class="tk-saisi-pour">
						👤 Saisi par <strong>{ticket.auteur_nom ?? 'inconnu'}</strong> pour
						<strong>{ticket.saisi_pour_affichage}</strong>
						{#if ticket.saisi_pour_email}
							· <a href="mailto:{ticket.saisi_pour_email}">{ticket.saisi_pour_email}</a>
						{/if}
					</p>
				{/if}
			</svelte:fragment>
			<svelte:fragment slot="pied">
				{#if ticket.destinataire_syndic}
					<p class="tk-envoi">📧 Envoyé au syndic</p>
				{/if}
			</svelte:fragment>
		</FicheLecture>
		<MentionFusion {ticket} />
	</RubriqueEtape>

	<EtatListe compact erreur={erreurSuivi} />
	{#if suites.length > 0}
		<RubriqueEtape
			titre="La suite"
			icone="clock"
			ton="info"
			compte={suites.length}
			resume={resumeSuite}
			ouverte={ouverte === 'suite'}
			onBasculer={() => (ouverte = basculer(ouverte, 'suite'))}
		>
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
		</RubriqueEtape>
	{/if}
	<!--  Les comptes rendus VALIDÉS des points CS / Syndic (#2042, maquette B4) :
	      entre la suite et la synthèse, et seulement s'il y en a. -->
	<ComptesRendusAffaire
		ticketId={ticket.id}
		ouverte={ouverte === 'comptes-rendus'}
		onBasculer={() => (ouverte = basculer(ouverte, 'comptes-rendus'))}
	/>
	<!--  🧾 La synthèse d'une affaire close (#1643) — la dernière étape. -->
	<SyntheseFil
		{ticket}
		{evolutions}
		ouverte={ouverte === 'synthese'}
		onBasculer={() => (ouverte = basculer(ouverte, 'synthese'))}
		on:change={() => gestes.filChange(ticket)}
	/>
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
	.tk-saisi-pour {
		font-size: var(--fs-md);
		color: var(--color-text-muted);
		margin: 0.5rem 0;
		padding: 0.5rem 0.75rem;
		background: var(--color-bg-muted, #f5f5f5);
		border-radius: var(--radius);
	}
	.tk-envoi {
		font-size: var(--fs-sm);
		color: var(--color-text-muted);
		margin-top: 0.5rem;
	}
	.tk-meta {
		margin: 0.9rem 0 0;
		color: var(--color-text-muted);
		font-size: var(--fs-sm);
	}
</style>
