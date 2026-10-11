<!--
  ListeTickets.svelte — une suite de `CarteTicket`, et le câblage qui va avec.

  ## Pourquoi (17/08/2026, #431)

  `tickets/+page.svelte` porte DEUX listes du même objet : les tickets actifs, et
  ceux de la section Historique, groupés par année. Extraire la carte a supprimé
  115 lignes recopiées, mais laissait le **branchement** de la carte — quel mode,
  quel gestionnaire pour chacun des six événements — écrit deux fois. Une
  duplication de 14 lignes n'est pas moins une duplication qu'une de 115 : c'est
  seulement plus discret, et donc plus durable.

  Ce composant ne décide rien. Il ne connaît ni l'API, ni l'ordre de tri, ni le
  délai de grâce : la page reste propriétaire de l'état (*quel ticket est déplié,
  lequel est en correction*) et des appels. Il n'apporte qu'une chose — que les
  deux listes se câblent forcément pareil.

  ## 🔴 Les gestes passent par UN objet, plus par treize `on:` (12/09/2026)

  Ce fichier prévenait lui-même : *« c'est le prix de ce relais ; il se paie à
  chaque nouvel événement »*. Il s'est payé — l'ajout du panneau d'options
  rapides demandait **deux événements de plus, relayés à trois niveaux et câblés
  DEUX fois** dans la page, une fois par liste. Vingt-six lignes pour deux gestes.

  Les événements Svelte ne se transmettent pas en bloc (`{...props}` ne porte que
  des props) : tant qu'ils sont des `on:`, chaque liste doit les réécrire. Ils
  sont donc regroupés dans **une prop `gestes`**, que les deux listes passent à
  l'identique — et qu'un oubli rend visible tout de suite, puisque le type la
  décrit.

  ⚠️ C'est la forme qu'`ActionsActualite` employait déjà (`onCommenter`,
  `onModifier`, `onOptions`) : ce n'est pas une exception, c'est l'alignement sur
  le voisin.
-->
<script lang="ts">
	import ActualiteEnListe from './ActualiteEnListe.svelte';
	import CarteTicket from './CarteTicket.svelte';
	import type { CorrespondanceAffaire, Ticket, TicketEvolution } from '$lib/api';
	import { estActualite, type GestesTicket } from '$lib/tickets';

	/**  Tout ce que la page fait quand la liste bouge — le type vit dans
	 *   `$lib/tickets`, avec le reste du vocabulaire du ticket. */
	export let gestes: GestesTicket;

	export let tickets: Ticket[] = [];
	/** Allure d'archive — les tickets clos depuis plus du délai de grâce. */
	export let archive = false;
	export let expandedIds: Set<number> = new Set();
	export let evolsMap: Record<number, TicketEvolution[]> = {};
	/** Le fil qu'on n'a pas pu charger, par affaire — dit par la carte. */
	export let evolsErreurs: Record<number, string> = {};
	/** Le ticket ouvert en correction, s'il y en a un. */
	export let ticketEnEdition: number | null = null;
	/** Le ticket ouvert en nouvelle entrée d'Historique, s'il y en a un. */
	export let ticketEnEvolution: number | null = null;
	/** Celui dont le panneau d'options rapides est ouvert, ou `null`. */
	export let ticketEnOptions: number | null = null;
	/** Le panneau d'options attend-il le serveur ? */
	export let optionsRapidesEnCours = false;
	export let evolutionEnCours = false;
	/** L'entrée du fil en cours de correction, et son enregistrement. */
	export let evolEnEdition: number | null = null;
	export let evolCorrectionEnCours = false;
	export let peutAdministrer = false;
	/** Quand la liste est une recherche : ce qui a fait trouver chaque affaire. */
	export let correspondances: Map<number, CorrespondanceAffaire> = new Map();

	/**  Ce que la page a ouvert sur UNE carte — écrit une fois pour les deux
	 *   cartes, qui le lisent de la même façon. ⚠️ `$:` et non `const` : le
	 *   gabarit ne suit que la FONCTION, et une constante ne changerait jamais —
	 *   ouvrir un formulaire n'aurait plus rien rouvert. */
	$: modeDe = (id: number): 'lecture' | 'edition' | 'evolution' | 'options' =>
		ticketEnEdition === id
			? 'edition'
			: ticketEnEvolution === id
				? 'evolution'
				: ticketEnOptions === id
					? 'options'
					: 'lecture';
</script>

{#each tickets as t (t.id)}
	<!--  🔴 Une ACTUALITÉ garde sa carte (#1091, #1092) : c'est une affaire, avec
	      les mêmes gestes, mais elle se lit comme une information — sans numéro
	      ni état de suivi. Les gestes passent ENTIERS, par le même objet. -->
	{#if estActualite(t)}
		<ActualiteEnListe
			ticket={t}
			evolutions={evolsMap[t.id] ?? []}
			erreurSuivi={evolsErreurs[t.id] ?? ''}
			expanded={expandedIds.has(t.id)}
			{archive}
			mode={modeDe(t.id)}
			{evolutionEnCours}
			{peutAdministrer}
			{optionsRapidesEnCours}
			{evolEnEdition}
			{evolCorrectionEnCours}
			{gestes}
			correspondance={correspondances.get(t.id) ?? null}
		/>
	{:else}
		<!--  ⚠️ CHAQUE événement de la carte doit être RELAYÉ ici, et un oubli ne se voit
	      pas : le 18/08/2026, `evol_supprimer` manquait — la corbeille s'affichait,
	      le clic partait, et l'événement mourait dans ce composant. Bouton
	      parfaitement inerte, sans la moindre erreur.

	      Trois niveaux — page → liste → carte — et il suffit qu'un maillon se taise.
	      C'est le prix de ce relais ; il vaut la suppression des 115 lignes recopiées
	      qui l'ont fait naître, mais il se paie à chaque nouvel événement. -->
		<CarteTicket
			ticket={t}
			evolutions={evolsMap[t.id] ?? []}
			erreurSuivi={evolsErreurs[t.id] ?? ''}
			correspondance={correspondances.get(t.id) ?? null}
			expanded={expandedIds.has(t.id)}
			{archive}
			{evolutionEnCours}
			{peutAdministrer}
			{optionsRapidesEnCours}
			mode={modeDe(t.id)}
			on:basculer={() => gestes.basculer(t)}
			on:evoluer_ouvrir={() => gestes.evoluerOuvrir(t)}
			on:modifier={() => gestes.modifier(t)}
			on:options_ouvrir={() => gestes.optionsOuvrir(t)}
			on:options_enregistrer={(e) => gestes.optionsEnregistrer(t, e.detail)}
			on:supprimer={() => gestes.supprimer(t)}
			on:archiver={() => gestes.archiver(t)}
			{evolEnEdition}
			{evolCorrectionEnCours}
			on:evoluer={(e) => gestes.evoluer(t, e.detail)}
			on:evol_modifier={(e) => gestes.evolModifier(e.detail)}
			on:evol_corriger={(e) => gestes.evolCorriger(t, e.detail)}
			on:evol_supprimer={(e) => gestes.evolSupprimer(e.detail)}
			on:evol_annuler={() => gestes.evolAnnuler()}
			on:modifie={(e) => gestes.modifie(e.detail)}
			on:annuler={() => gestes.annuler()}
			on:fil_change={() => gestes.filChange(t)}
		/>
	{/if}
{/each}
