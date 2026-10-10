<!--
  ActualiteEnListe.svelte — une actualité dans la liste des AFFAIRES.

  ## Pourquoi (23/09/2026, #1091 lot 4 et #1092)

  Arbitré à l'écran : *« la notion d'actualité n'existe plus ; c'est une affaire
  (tout est centralisé dans cette vue) »*. La page Actualités disparaît, et ses
  cartes paraissent dans la liste des affaires, sous le filtre « Actualité ».

  Une actualité y garde son ALLURE — `CarteActualite`, sans numéro ni état de
  suivi — parce que c'est ce qui la distingue d'un dossier à traiter. Ses
  GESTES, eux, sont ceux de toute affaire : ce composant reçoit le même objet
  `gestes` que `CarteTicket`, et n'écrit aucun appel à l'API de son côté — une
  seconde écriture divergerait au premier écart. `ListeTickets` choisit entre
  les deux cartes ; la page n'en sait rien.

  Ce qui vivait dans `routes/(app)/actualites/+page.svelte` et vit ici :

  | Geste | Relais |
  |---|---|
  | ↩️ Suite (commentaire, ciblage, mise en avant) | `gestes.evoluer` |
  | ✏️ correction — `FormulaireTicket`, dans la carte, comme une affaire | `gestes.modifie` |
  | ⚙️ Options rapides — épinglage, urgence | `gestes.optionsEnregistrer` |
  | 🎯 En faire une affaire suivie (#1094) | `promouvoirActualite` → `gestes.modifie` |
  | 🗑️ Supprimer (admin) | `gestes.supprimer` |
-->
<script lang="ts">
	import ChargementDiffere from '$lib/components/ChargementDiffere.svelte';
	import {
		documents as docsApi,
		type CorrespondanceAffaire,
		type Document,
		type Ticket,
		type TicketEvolution,
	} from '$lib/api';
	import { supprimerDocument } from '$lib/gestes-document';
	import { promouvoirActualite } from '$lib/gestes-actualite';
	import { currentUser, isCS } from '$lib/stores/auth';
	import { OPTIONS_TICKET, ticketUrgent, type GestesTicket } from '$lib/tickets';
	import ActionsActualite from './ActionsActualite.svelte';
	import CarteActualite from './CarteActualite.svelte';
	import PanneauOptionsPublication from './PanneauOptionsPublication.svelte';
	import RubriqueHistorique from './RubriqueHistorique.svelte';
	import EtatListe from './EtatListe.svelte';
	import { essayer, messagePartiel } from '$lib/chargement';

	export let ticket: Ticket;
	export let evolutions: TicketEvolution[] = [];
	/** Le fil n'a pas pu être chargé : on le DIT, au lieu d'un fil vide. */
	export let erreurSuivi = '';
	export let expanded = false;
	/** Allure d'archive — atténuée, sans épingle ni « New ». */
	export let archive = false;
	/** Ce que la page a ouvert sur CETTE carte — le même contrat que `CarteTicket`. */
	export let mode: 'lecture' | 'edition' | 'evolution' | 'options' = 'lecture';
	export let optionsRapidesEnCours = false;
	export let evolutionEnCours = false;
	export let evolEnEdition: number | null = null;
	export let evolCorrectionEnCours = false;
	export let peutAdministrer = false;
	export let gestes: GestesTicket;
	export let correspondance: CorrespondanceAffaire | null = null;

	//  Mise en avant d'une actualité : épinglage et urgence (#1096) — les options
	//  d'une affaire, `OPTIONS_TICKET` (elles y étaient recopiées). Copie de
	//  travail — on n'écrit dans l'affaire qu'après la réponse du serveur.
	const optionsInitiales = () => ({
		epingle: ticket.epingle ?? false,
		urgente: ticketUrgent(ticket),
		brouillon: false,
		confidentiel: false,
	});
	let options = optionsInitiales();
	//  Reprise à chaque ouverture : un panneau abandonné ne laisse rien derrière.
	$: if (mode === 'options' || mode === 'evolution') options = optionsInitiales();

	//  Les `Document` des ANCIENNES publications, chargés au premier dépliage.
	//  Une actualité récente n'en a aucun : ses pièces sont en URLs.
	let documents: Document[] = [];
	let documentsCharges = false;
	//  La carte se lit sans eux, mais ne les dit pas absents s'ils n'ont pas été lus (#1459).
	let erreurDocuments = '';
	$: if (expanded && !documentsCharges) chargerDocuments();
	async function chargerDocuments() {
		documentsCharges = true;
		[documents, erreurDocuments] = await essayer(docsApi.listByTicket(ticket.id), []);
	}

	//  🔴 Les retirer (#1178) : ils ne passent pas par le formulaire, qui ne
	//  connaît que `fichiers_urls`. Écart DÉCLARÉ, et voulu — les migrer en URLs
	//  les ferait passer de `uploads/prive/` (contrôle `document_visible`) à
	//  `uploads/fichiers/`, lisible de toute session : la sécurité tranche (#390).
	const retirerDocument = (doc: { id: number }) =>
		supprimerDocument(
			doc.id,
			'Ce document',
			(id) => (documents = documents.filter((d) => d.id !== id)),
		);

	const idSi = (m: typeof mode) => (mode === m ? ticket.id : null);
</script>

<CarteActualite
	pub={ticket}
	{expanded}
	variante={archive ? 'historique' : 'fil'}
	{documents}
	onRetirerDocument={$isCS && !archive ? retirerDocument : null}
	formulaireOuvert={mode === 'evolution' || mode === 'options' || mode === 'edition'}
	{correspondance}
	on:toggle={() => gestes.basculer(ticket)}
>
	<svelte:fragment slot="actions">
		<!--  Aux Archives aussi : c'est là, et là seulement, que l'administrateur
		      supprime (24/09/2026) — la rangée n'y montre que 🗑️. -->
		<ActionsActualite
			pub={ticket}
			{archive}
			onArchiver={gestes.archiver}
			commentaireOuvertId={idSi('evolution')}
			editionOuverteId={idSi('edition')}
			optionsOuvertesId={idSi('options')}
			onCommenter={gestes.evoluerOuvrir}
			onModifier={gestes.modifier}
			onOptions={gestes.optionsOuvrir}
			onPromouvoir={(p) => promouvoirActualite(p, gestes.modifie)}
			onSupprimer={gestes.supprimer}
		/>
	</svelte:fragment>

	<svelte:fragment slot="formulaire">
		<!--  Correction — LE formulaire des affaires (23/09/2026) : une actualité
		      s'y corrige comme toute affaire, et sa catégorie avec elle. Il était
		      rendu en modale par `FormulaireActualite`, disparu dans celui-ci ;
		      le corps de la carte ne se replie pas pendant la saisie (#640). -->
		{#if mode === 'edition'}
			{#key ticket.id}
				<ChargementDiffere charger={() => import('$lib/components/FormulaireTicket.svelte')}>
					{#snippet contenu(FormulaireTicket)}
						<FormulaireTicket
							{ticket}
							on:modifie={(e) => gestes.modifie(e.detail)}
							on:annule={gestes.annuler}
						/>
					{/snippet}
				</ChargementDiffere>
			{/key}
		{:else if mode === 'options'}
			<PanneauOptionsPublication
				optionsRendues={OPTIONS_TICKET}
				perimetreCible={ticket.perimetre_cible ?? []}
				dejaEpingle={ticket.epingle ?? false}
				bind:options
				enregistrement={optionsRapidesEnCours}
				on:enregistrer={() =>
					gestes.optionsEnregistrer(ticket, { epingle: options.epingle, urgente: options.urgente })}
				on:annuler={gestes.annuler}
			/>
		{:else if mode === 'evolution'}
			<!--  `role="presentation"` : ce conteneur n'est qu'un relais qui arrête la
			      propagation, pour que saisir ne referme pas la carte. -->
			<div
				class="evol-form"
				role="presentation"
				on:click|stopPropagation
				on:keydown|stopPropagation
			>
				<!--  Le montage de TOUTE Suite d'affaire (`SuiteAffaire`) : il sait qu'une
				      actualité n'a pas de suivi (#1091). -->
				<ChargementDiffere charger={() => import('$lib/components/SuiteAffaire.svelte')}>
					{#snippet contenu(SuiteAffaire)}
						<SuiteAffaire
							{ticket}
							entrees={evolutions}
							peutSuivre
							saving={evolutionEnCours}
							on:submit={(e) => gestes.evoluer(ticket, e.detail)}
							on:cancel={gestes.annuler}
						/>
					{/snippet}
				</ChargementDiffere>
			</div>
		{/if}
	</svelte:fragment>

	<svelte:fragment slot="apres-corps">
		<EtatListe compact erreur={messagePartiel(erreurSuivi, erreurDocuments)} />
		{#if evolutions.length}
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
						<ChargementDiffere charger={() => import('$lib/components/SuiteAffaire.svelte')}>
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
		{/if}
	</svelte:fragment>
</CarteActualite>

<style>
	/*  La marge qui sépare le fil de ce qu'il suit — le parent seul sait ce
	    qu'il y a au-dessus. */
	.actu-fil {
		margin-top: 0.9rem;
	}
	.evol-form {
		padding: 0.5rem 0;
	}
</style>
