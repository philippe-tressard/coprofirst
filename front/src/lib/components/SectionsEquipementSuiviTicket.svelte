<!--
  SectionsEquipementSuiviTicket.svelte — l'Équipement (#1097) et le Suivi d'une
  affaire, les deux sections que la saisie ESSENTIELLE range dans « Plus de détails »
  (#2595).

  Extrait de `SectionsSpecifiquesTicket` (qui garde la Catégorie) le 08/11/2026 : en
  saisie Complète il se rend juste après elle, à leur rang ; en saisie Essentielle,
  `FormulaireTicket` le pose dans le créneau `repliees` de `ChampsCommuns`, en tête
  du groupe — Équipement et Suivi précèdent toutes les sections de ce composant dans
  `SECTIONS_ORDRE`.

  ⚠️ Comme son parent, il ne décide de rien : la présence des sections reste
  gouvernée par `sectionPresente(TICKET, etat, …)`, et `sections` dit seulement
  lesquelles l'appelant veut ICI (une éteinte en saisie Essentielle n'est ni
  montrée ni rangée).
-->
<script lang="ts">
	import { pliageDe, requisDe } from '#lib/pliage.ts';
	import SectionWorkflow from '#lib/components/SectionWorkflow.svelte';
	import { isCS } from '#lib/stores/auth.ts';
	import { STATUT_TICKET_OPTIONS, estActualite } from '#lib/tickets.ts';
	import {
		AIDE_SUIVI_ACTUALITE,
		ETAT_SUIVI_DEFAUT,
		SUIVI_ACTUALITE_OPTIONS,
	} from '#lib/suivi-actualite.ts';
	import SectionEquipement from '#lib/components/SectionEquipement.svelte';
	import type { Etat, IdSection } from '#lib/entites/types.ts';
	import { sectionPresente } from '#lib/entites/types.ts';
	import { TICKET } from '#lib/entites/ticket.ts';
	import { SEPARATEUR } from '#lib/separateurs.ts';

	export let etat: Etat;
	export let modeEdition = false;
	export let categorie = '';
	export let statut = 'ouvert';
	/** Les options liées de l'affaire — voir `SectionsSpecifiquesTicket`. */
	export let options = {
		epingle: false,
		urgente: false,
		brouillon: false,
		suiviKanban: false,
		suiviActualite: false,
		etatSuivi: null as string | null,
	};
	export let inactives: Partial<Record<IdSection, string>> = {};
	export let equipement = '';
	/** Les sections à rendre ICI. */
	export let sections: readonly IdSection[] = ['equipement', 'suivi'];
	//  🔁 Le suivi d'une actualité est OPTIONNEL (10/10/2026) : coché, il se déplie d'office.
	$: actualite = estActualite({ categorie });
	$: suiviCoche = actualite && options.suiviActualite;
</script>

<!--  L'ÉQUIPEMENT (section 3, #1097) : le conseil le désigne, pour une
      catégorie du bâti. Ailleurs, grisé avec son motif (`inactivePour`). -->
{#if sections.includes('equipement') && sectionPresente(TICKET, etat, 'equipement')}
	<SectionEquipement
		pliable={pliageDe(TICKET, 'equipement')}
		inactive={inactives.equipement ?? ''}
		bind:equipement
	/>
{/if}

<!--  3. Suivi — où en est l'affaire. IDENTIQUE en création et en édition
	      depuis le cadre #430 : une correction corrige l'état comme elle corrige
	      un titre. 🔴 `SectionWorkflow`, la section de la Suite : elle était
	      réécrite ici à la main, et les deux avaient divergé (#1329).
	      Un résident ne peut pas faire avancer le suivi : la rangée est en
	      lecture, et le serveur refait le contrôle (liste blanche CS). -->
{#if sections.includes('suivi')}
	<SectionWorkflow
		idTitre="ticket-workflow-titre"
		options={actualite ? (suiviCoche ? SUIVI_ACTUALITE_OPTIONS : []) : STATUT_TICKET_OPTIONS}
		valeur={actualite ? (suiviCoche ? (options.etatSuivi ?? ETAT_SUIVI_DEFAUT) : '') : statut}
		lecture={!$isCS}
		pliable={actualite ? !suiviCoche : pliageDe(TICKET, 'suivi')}
		requis={!actualite && requisDe(TICKET, 'suivi')}
		inactive={inactives.suivi ?? ''}
		on:choisir={(e) => (actualite ? (options.etatSuivi = e.detail) : (statut = e.detail))}
	>
		{#if actualite}
			{#if $isCS}
				<div class="field champ-large">
					<label class="checkbox-field">
						<input type="checkbox" bind:checked={options.suiviActualite} />
						<span>Activer le suivi</span>
					</label>
					<p class="aide">{AIDE_SUIVI_ACTUALITE}</p>
				</div>
			{:else}
				<p class="aide">Seul le conseil syndical suit une actualité.</p>
			{/if}
		{:else if !$isCS}
			<p class="aide">
				{modeEdition
					? `Seul le conseil syndical fait avancer le suivi d’une ${TICKET.libelle.toLowerCase()}.`
					: 'Votre demande part en « Ouvert ». Le conseil syndical fait ensuite avancer son suivi.'}
			</p>
		{/if}

		<!--  🔴 LE SUIVI KANBAN EST DANS LE WORKFLOW, pas dans la Diffusion (#833).

	      Arbitré ainsi : les trois canaux de diffusion NOTIFIENT des gens ;
	      celui-ci INSCRIT l'objet dans un tableau. Ce n'est pas la même nature,
	      et l'ajouter à `CanauxNotification` l'aurait fait paraître sur les neuf
	      écrans qui portent la Diffusion — annonce de hall, sondage, calendrier —
	      où « inscrire au kanban » ne veut rien dire. C'est l'héritage partiel
	      dont l'en-tête de `SectionDiffusion` met en garde (#498).

	      Sa place est ici : le kanban répond à « où en est cet objet ? », qui est
	      exactement la question de la section 3 du cadre #430.

	      ⚠️ Réservé au conseil, et le serveur le refait
	      (`OPTIONS_RESERVEES_AU_CS`) : le tableau ordonne SON travail. -->
		{#if $isCS && categorie === 'etude_travaux'}
			<div class="field champ-large">
				<label class="checkbox-field">
					<input type="checkbox" bind:checked={options.suiviKanban} />
					<span>Suivre cette affaire au <strong>kanban</strong></span>
				</label>
				<p class="aide">
					Coché d’office pour « Étude &amp; travaux ». La carte se range d’après le statut ci-dessus
					: Ouvert{SEPARATEUR.fleche}CS, En cours{SEPARATEUR.fleche}Syndic, Résolu{SEPARATEUR.fleche}Terminé,
					Annulé{SEPARATEUR.fleche}Annulé.
				</p>
			</div>
		{/if}
	</SectionWorkflow>
{/if}
