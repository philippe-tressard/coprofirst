<!--
  CarteTicket.svelte — la carte d'un ticket dans une liste, dépliable, et ses
  trois modes : lecture, correction (édition), nouvelle entrée (évolution).

  ## Pourquoi ce composant (17/08/2026, #431)

  `tickets/+page.svelte` rendait cette carte DEUX FOIS — une fois pour la liste
  active, une fois pour la section des tickets clos —, soit **115 lignes
  recopiées**, fil de suivi compris. Les deux copies avaient déjà divergé de trois
  façons, toutes invisibles à la relecture :

    • le badge NEW n'existait que sur la première ;
    • le bouton ✏️ *Modifier* n'existait que sur la première, sans que rien ne
      dise pourquoi un administrateur le perdrait au bout de sept jours ;
    • le fil de suivi y était réécrit intégralement, deux fois.

  Une carte, un fichier. La seule différence retenue est l'**allure d'archive**
  (`archive`), qui se voit : filet à gauche, fond atténué. Elle est portée ici, en
  prop — une classe posée par la page sur le balisage d'un composant enfant ne
  serait **pas atteinte** par le `<style>` de la page (panne des pastilles nues,
  v2.67.11).

  ## Les formulaires vivent ICI, et pas dans un slot

  Première écriture, la carte exposait un slot `formulaire` et la page y branchait
  `FormulaireTicket` et `EvolForm`. Ce câblage-là aurait été recopié deux fois —
  la duplication supprimée d'un côté serait revenue de l'autre, en plus discret.
  La carte porte donc ses trois modes ; la page ne garde que la décision (*quel
  ticket, quel mode*) et les appels d'API.

  ## L'affichage passe par le squelette de lecture

  Le corps déplié n'écrit plus l'ordre de ses notions : `FicheLecture` le lit dans
  la déclaration `TICKET` (`$lib/entites/ticket`). La carte affichait
  *description → photos → périmètre* ; les deux formulaires demandent
  *périmètre → description → photos → documents*. C'est R2, et elle vaut aussi
  pour l'affichage.
-->
<script lang="ts">
	import ChargementDiffere from '$lib/components/ChargementDiffere.svelte';
	import BadgeNouveau from '$lib/components/BadgeNouveau.svelte';
	import { createEventDispatcher } from 'svelte';
	import ApercuTicket from './ApercuTicket.svelte';
	import ExtraitRecherche from './ExtraitRecherche.svelte';
	import EnteteCarte from './EnteteCarte.svelte';
	import GouttiereAffaire from './GouttiereAffaire.svelte';
	import EtatListe from './EtatListe.svelte';
	import PastillesAffaire from './PastillesAffaire.svelte';
	import ActionsTicket from './ActionsTicket.svelte';
	import PanneauOptionsPublication from './PanneauOptionsPublication.svelte';
	import FicheLecture from './FicheLecture.svelte';
	import RubriqueHistorique from './RubriqueHistorique.svelte';
	import SyntheseAffaire from './SyntheseAffaire.svelte';
	import SyntheseFil from './SyntheseFil.svelte';
	import type { EtatSynthese } from '$lib/api';
	import TransfertsVerses from './TransfertsVerses.svelte';
	import { currentUser, isAdmin, isCS } from '$lib/stores/auth';
	import { peutCommenter as peutCommenterCe, peutEditer } from '$lib/droits';
	import MentionFusion from './MentionFusion.svelte';
	import { TICKET } from '$lib/entites/ticket';
	import {
		OPTIONS_TICKET,
		optionsDuTicket,
		optionsVersTicket,
		ticketUrgent,
		attributsNature,
		STATUT_TICKET_LABELS,
	} from '$lib/tickets';
	import { fmtDate } from '$lib/date';
	import { type CorrespondanceAffaire, type Ticket, type TicketEvolution } from '$lib/api';
	import { nomProprietaire } from '$lib/saisi-pour';
	import { equipLabel, intervenantAffiche } from '$lib/prestataires';

	export let ticket: Ticket;
	//  À QUI l'affaire appartient — le « Saisi pour » s'il existe, l'auteur
	//  sinon. Réactif : la carte se rafraîchit quand le ticket change.
	$: proprietaireNom = nomProprietaire(ticket);
	export let evolutions: TicketEvolution[] = [];
	/** Le fil n'a pas pu être chargé : on le DIT, au lieu d'un fil vide. */
	export let erreurSuivi = '';
	/** Ce qui l'a fait trouver, quand la liste est une recherche (27/09/2026). */
	export let correspondance: CorrespondanceAffaire | null = null;
	export let expanded = false;
	/** Allure d'archive : le ticket est clos depuis plus du délai de grâce. */
	export let archive = false;
	/** Le lecteur peut-il commenter / changer l'état ? (conseil syndical) */
	/** Le lecteur peut-il corriger ou supprimer ? (administrateur) */
	export let peutAdministrer = false;
	/**  Ce que le corps de la carte montre. La page en est propriétaire : elle
	     seule sait qu'un seul formulaire doit être ouvert à la fois.
	     ⚠️ UN seul mode d'évolution (#426) : le geste ne se déclare plus au clic,
	     il se lit dans les pastilles de la section Workflow, celle de l'état
	     courant étant active. */
	/**  `options` : le panneau qui change les SEULES options, sans ouvrir les huit
	 *   sections du formulaire (12/09/2026, demandé à l'écran). Un quatrième mode
	 *   et non un état à part : deux formulaires ouverts en même temps sur la même
	 *   carte n'auraient aucun sens, et `mode` porte déjà cette exclusion. */
	export let mode: 'lecture' | 'edition' | 'evolution' | 'options' = 'lecture';
	/** Le panneau d'options rapides attend-il le serveur ? */
	export let optionsRapidesEnCours = false;

	//  Le brouillon du panneau rapide : on ne touche PAS au ticket affiché tant
	//  que le serveur n'a pas répondu — sinon l'écran montre un état enregistré
	//  qui ne l'est pas, et le laisse faux si la requête échoue.
	//  `confidentiel` : la clé que le panneau attend. La case 🔒 n'y est plus
	//  rendue (en tête du Périmètre, 25/09/2026), et elle ne repart pas.
	const optionsRapidesInitiales = () => ({ ...optionsDuTicket(ticket), confidentiel: false });
	let optionsRapides = optionsRapidesInitiales();
	$: if (mode === 'options') optionsRapides = optionsRapidesInitiales();
	/** Enregistrement d'une évolution en cours — porté par la page (appel d'API). */
	export let evolutionEnCours = false;
	/**  L'entrée du fil en cours de CORRECTION, `null` si aucune. Portée par la
	 *   page : une seule entrée s'édite à la fois sur tout l'écran, sans quoi
	 *   deux formulaires ouverts ne diraient pas lequel enregistre quoi. */
	export let evolEnEdition: number | null = null;
	/** La correction est-elle en cours d'enregistrement ? */
	export let evolCorrectionEnCours = false;

	//  🔴 Les deux droits, calculés SUR CE TICKET — l'appelant ne peut pas les
	//  fournir : ils dépendent de qui l'a déposé, et une liste en affiche vingt.
	//
	//  Avant, le crayon n'apparaissait JAMAIS à l'auteur ni au « saisi pour »,
	//  que le serveur accepte depuis la v2.85.0.
	//
	//  ⚠️ `peutAdministrer` reste ce qu'il est pour la SUPPRESSION : effacer
	//  définitivement n'est pas éditer, et cela reste réservé à l'admin.
	$: peutEditerCeTicket = peutEditer(ticket, $currentUser?.id, $isAdmin);
	//  Une affaire absorbée n'a plus de Suite : son fil vit dans la principale (#1704).
	$: peutSuivreCeTicket =
		!ticket.fusionnee && peutCommenterCe(ticket, $currentUser?.id, $isAdmin, $isCS);

	const dispatch = createEventDispatcher<{
		basculer: void;
		evol_modifier: number;
		evol_supprimer: { ticket: Ticket; evolId: number };
		evol_corriger: unknown;
		evol_annuler: void;
		evoluer_ouvrir: void;
		options_ouvrir: void;
		options_enregistrer: unknown;
		modifier: void;
		supprimer: void;
		annuler: void;
		evoluer: unknown;
		/** L'affaire et son fil ont changé : un transfert défait, une synthèse produite. */
		fil_change: void;
	}>();

	//  🧾 La synthèse d'une affaire close (#1643) : lue par `SyntheseFil`.
	let etatSynthese: EtatSynthese | null = null;
	let filSynthese: SyntheseFil;
</script>

<div
	id="ticket-{ticket.id}"
	{...attributsNature(ticket)}
	class:carte-liste={!archive}
	class:history-item={archive}
	class:expanded
	class:urgent={ticketUrgent(ticket)}
	role="presentation"
	on:click={() => {
		if (!expanded) dispatch('basculer');
	}}
>
	<!--  Le geste de dépliage vit dans `EnteteCarte` : le TITRE plie, avec un
	      survol qui le dit (18/08/2026). Le conteneur ne porte plus
	      `role="button"` — il interceptait la sélection de texte, et obligeait
	      chaque bouton d'action à un `stopPropagation` pour qu'un clic sur ✏️ ne
	      déplie pas la carte au même instant. -->
	<!--  QUAND puis QUOI, dans la colonne de gauche (maquette B, 10/10/2026) :
	      la date n'est donc plus passée à l'en-tête — un seul fait, une place. -->
	<GouttiereAffaire affaire={ticket} />
	<EnteteCarte titre={ticket.titre} basculable ample on:toggle={() => dispatch('basculer')}>
		<svelte:fragment slot="titre-suffixe">
			<BadgeNouveau le={ticket.cree_le} />
		</svelte:fragment>
		<!--  🔴 L'EN-TÊTE PORTE LE PÉRIMÈTRE ET LE NUMÉRO (18/08/2026, signalé à
		      l'écran) : *« le périmètre devrait s'afficher dans l'état sous le titre
		      comme pour les actualités. Je ne comprends pas qu'il y ait une
		      différence de comportement, cela devrait être un squelette standard »*.

		      Le ticket était le SEUL des quatre écrans à cartes dépliables à ranger
		      son périmètre dans le corps : actualité, annonce et événement le
		      portaient déjà en tag. L'ordre des tags reprend celui de l'actualité —
		      état, puis 🔹 périmètre, puis les marqueurs, puis l'auteur — pour que
		      deux listes voisines se lisent de la même façon.

		      ⚠️ Le périmètre n'est donc PLUS passé à `FicheLecture` : il s'afficherait
		      deux fois sur la même carte. Le rendu de la section 4 en affichage, c'est
		      l'en-tête — et c'est vrai des quatre entités, ce qui referme l'écart que
		      le lot du calendrier avait laissé ouvert en le nommant.

		      Le NUMÉRO monte aussi : il n'était lisible qu'une fois la carte dépliée,
		      dans son pied, alors que c'est la référence qu'on cite au syndic. -->
		<svelte:fragment slot="tags">
			<!--  La dernière ligne vit dans `PastillesAffaire` (27/09/2026) : c'est la
			      norme, que le fil et l'actualité rendent à l'identique. -->
			<PastillesAffaire affaire={ticket} auteur={proprietaireNom} />
		</svelte:fragment>
		<svelte:fragment slot="actions">
			<ActionsTicket
				{ticket}
				{mode}
				peutSuivre={peutSuivreCeTicket}
				peutEditer={peutEditerCeTicket}
				{peutAdministrer}
				{archive}
				on:evoluer_ouvrir
				on:modifier
				on:options_ouvrir
				on:supprimer
				on:archiver
			/>
		</svelte:fragment>
		<!--  🔴 L'aperçu passe par l'EN-TÊTE (18/09/2026) : c'est ce qui permet aux
		      pastilles de descendre en dernière ligne, comme sur le fil d'activité.
		      Rendu après `</EnteteCarte>`, il était le FRÈRE de l'en-tête — aucun
		      ordre CSS ne fait passer un élément sous le frère d'un autre parent. -->
		<svelte:fragment slot="apercu">
			{#if !expanded}
				<ApercuTicket {ticket} dansLigne />
				{#if correspondance}
					<ExtraitRecherche {correspondance} archivee={ticket.archivee} />
				{/if}
			{/if}
		</svelte:fragment>
	</EnteteCarte>

	{#if expanded}
		<!--  Le corps ne replie pas la carte : on y saisit, on y clique des
		      vignettes. `role="presentation"` dit que ce conteneur n'est qu'un
		      relais — l'élément interactif, c'est la carte. -->
		<div
			class="carte-corps tk-body"
			role="presentation"
			on:click|stopPropagation
			on:keydown|stopPropagation
		>
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
							dispatch(
								'options_enregistrer',
								optionsVersTicket({
									epingle: optionsRapides.epingle,
									urgente: optionsRapides.urgente,
									brouillon: optionsRapides.brouillon,
									suiviKanban: optionsRapides.suiviKanban,
								}),
							)}
						on:annuler={() => dispatch('annuler')}
					/>
				</div>
			{:else if mode === 'edition'}
				<div class="tk-formulaire">
					<ChargementDiffere charger={() => import('$lib/components/FormulaireTicket.svelte')}>
						{#snippet contenu(FormulaireTicket)}
							<FormulaireTicket {ticket} on:modifie on:annule={() => dispatch('annuler')} />
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
								peutSuivre={peutSuivreCeTicket}
								saving={evolutionEnCours}
								on:submit={(e) => dispatch('evoluer', e.detail)}
								on:cancel={() => dispatch('annuler')}
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
					on:change={() => dispatch('fil_change')}
				/>
				<EtatListe compact erreur={erreurSuivi} />
				<!--  🧾 La synthèse d'une affaire close (#1643), comme sur la fiche. -->
				<SyntheseFil
					bind:this={filSynthese}
					bind:etat={etatSynthese}
					{ticket}
					{evolutions}
					on:change={() => dispatch('fil_change')}
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
							peutModifier={peutSuivreCeTicket}
							currentUserId={$currentUser?.id}
							estAdmin={$isAdmin}
							avecSuppression
							enEdition={evolEnEdition}
							on:modifier={(e) => dispatch('evol_modifier', e.detail)}
							on:supprimer={(e) => dispatch('evol_supprimer', { ticket, evolId: e.detail })}
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
												peutSuivre={peutSuivreCeTicket}
												saving={evolCorrectionEnCours}
												on:submit={(e) => dispatch('evol_corriger', e.detail)}
												on:cancel={() => dispatch('evol_annuler')}
											/>
										{/snippet}
									</ChargementDiffere>
								{/key}
							</svelte:fragment>
						</RubriqueHistorique>
					</div>
				{/if}
			{/if}
		</div>
	{/if}
</div>

<style>
	/*  Conteneur, survol, `expanded` et `urgent` viennent de `.carte-liste`
	    (app.css) : ne vivent ici que ce qui est propre à la carte d'un ticket.

	    ⚠️ `tk-expand` a été RETIRÉE du balisage (#431). Elle y était depuis
	    toujours, sur les deux cartes, et n'était définie NULLE PART qui l'atteigne :
	    sa seule définition vit dans le `<style>` d'`espace-cs`, donc scopée à cet
	    écran-là. Une classe utilisée et jamais définie n'échoue à aucun contrôle —
	    `svelte-check` sait dire qu'un sélecteur défini n'est pas utilisé, pas
	    l'inverse. La retirer ne change rien à l'écran : c'est bien la preuve
	    qu'elle ne faisait rien. */
	/*  L'en-tête vit dans `EnteteCarte` — titre, tags, date, actions et leur repli.
	    Ne reste ici que ce qui est propre à un ticket. */

	.tk-body {
		padding: 0.75rem 1rem 1rem;
		border-top: 1px solid var(--color-border);
	}
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

	/*  Allure d'archive — portée ici et non par la page hôte : le `<style>` d'une
	    page n'atteint pas le balisage d'un composant enfant. */
	.history-item {
		border-left: 4px solid var(--color-border);
		border-radius: var(--radius);
		background: var(--color-surface);
		opacity: 0.8;
		transition:
			opacity var(--duree-geste),
			border-left-color var(--duree-geste);
	}
	@media (hover: hover) and (pointer: fine) {
		.history-item:hover {
			opacity: 1;
		}
	}
	/*  ⚠️ Un ticket ARCHIVÉ porte `.history-item` et NON `.carte-liste` : la règle
	    globale de survol ne l'atteint pas. Sans ces deux lignes, son titre serait
	    le seul du site à ne pas répondre au survol — un écart invisible tant
	    qu'on ne déroule pas les archives. */
	@media (hover: hover) and (pointer: fine) {
		.history-item:hover :global(.ec-titre) {
			color: var(--color-primary);
		}
	}
	.history-item :global(.ec-titre) {
		transition: color var(--duree-geste);
	}
	.history-item.expanded {
		opacity: 1;
	}
</style>
