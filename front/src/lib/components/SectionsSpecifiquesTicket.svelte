<!--
  SectionsSpecifiquesTicket.svelte — les sections 2 et 3 du cadre #430 pour un
  ticket : « Catégorie », « Saisi pour », les options de publication, et le
  workflow.

  ## Pourquoi ce fichier existe (05/09/2026)

  Extrait de `FormulaireTicket.svelte`, que le contrôle de modularité a refusé de
  laisser grossir (514 → 527 lignes). La bonne réponse n'était pas de raboter :
  ces quatre blocs forment ce qui est PROPRE au ticket, là où tout le reste du
  formulaire — sections 4 à 9 — vient déjà de `ChampsCommuns`. Le formulaire
  garde donc la soumission et l'assemblage ; ce fichier-ci, ce que le ticket a de
  particulier.

  ⚠️ **Il ne décide de rien.** La présence des sections reste gouvernée par
  `sectionPresente(TICKET, etat, …)`, comme partout ailleurs : une condition en
  dur rouvrirait la divergence silencieuse que le cadre supprime, et
  `lint:etats` la refuse.
-->
<script lang="ts">
	import { pliageDe, requisDe } from '#lib/pliage.ts';
	import SectionFormulaire from '#lib/components/SectionFormulaire.svelte';
	import SectionWorkflow from '#lib/components/SectionWorkflow.svelte';
	import ChoixPastilles from '#lib/components/ChoixPastilles.svelte';
	import { isCS } from '#lib/stores/auth.ts';
	import { LEGENDE_CARNET, STATUT_TICKET_OPTIONS, estActualite } from '#lib/tickets.ts';
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

	/** L'état de rendu — c'est lui, et non l'écran, qui décide des sections. */
	export let etat: Etat;
	/** Les catégories, déjà mises en forme pour `ChoixPastilles` par l'appelant. */
	export let OPTIONS_CATEGORIE: readonly {
		val: string;
		label: string;
		desc?: string;
		marque?: string;
		marqueAide?: string;
	}[] = [];
	/** Le formulaire est-il en correction ? Change le seul texte d'aide du workflow. */
	export let modeEdition = false;

	export let categorie = '';
	export let statut = 'ouvert';
	/**  🔴 LES TROIS OPTIONS DE PUBLICATION, en un objet lié (05/09/2026).
	 *
	 *   Un objet plutôt que trois `bind:` séparés : c'est LUI que l'écran reprend
	 *   du ticket (`optionsDuTicket`) et renvoie tel quel (`optionsVersTicket`).
	 *   Trois liaisons distinctes obligeraient chaque hôte à défaire puis refaire
	 *   le même objet — et le premier qui en oublierait une la remettrait à son
	 *   défaut sans que personne le voie. */
	export let options = {
		epingle: false,
		urgente: false,
		brouillon: false,
		suiviKanban: false,
		suiviActualite: false,
		etatSuivi: null as string | null,
	};
	/**  Les sections ÉTEINTES par la nature de l'affaire, avec leur motif
	 *   (`#lib/formulaire-affaire`, 23/09/2026) : grisées, pliées, sans champ. */
	export let inactives: Partial<Record<IdSection, string>> = {};
	/** L'équipement concerné (#1097) — une valeur de `TypeEquipement`, ou `''`. */
	export let equipement = '';
	//  🔁 Une ACTUALITÉ a un suivi OPTIONNEL : une case du conseil, puis ses trois
	//  états, choisis dès l'ouverture et corrigés en modification (10/10/2026) —
	//  une Suite trace ensuite l'avancée au fil. Facultatif, il se plie ; coché, il
	//  se déplie d'office (une valeur autre que le défaut).
	$: actualite = estActualite({ categorie });
	$: suiviCoche = actualite && options.suiviActualite;
</script>

<!--  2. NATURE — la catégorie de l'affaire, et elle seule.
	      🔴 Ce commentaire décrivait l'ancien monde jusqu'au 22/09/2026 : « DEUX
	      champs nommés, la catégorie puis Saisi pour », et concluait que « R4 ne
	      déclare que des sections, pas des champs : ce motif `api` vit dans la
	      déclaration EN COMMENTAIRE, faute de pouvoir s'y écrire ».
	      La scission de #1095 a levé cette limite — « Au nom de » est une section
	      (10), déclarée avec son motif d'absence, et rendue par `ChampsCommuns` à
	      son rang. Le commentaire, lui, était resté : il disait indéclarable ce
	      qui venait d'être déclaré, dans le fichier où l'on va vérifier. -->
{#if sectionPresente(TICKET, etat, 'nature')}
	<!--  `requis` LU dans la déclaration, et `rempli` transmis : l'étoile
	      restait rouge même une catégorie choisie (#1329). -->
	<SectionFormulaire
		titre="Catégorie"
		requis={requisDe(TICKET, 'nature')}
		rempli={!!categorie}
		idTitre="ticket-categorie-titre"
	>
		<!--  🔴 `ChoixPastilles` en mode radio depuis le 30/08/2026, signalé à
			      l'écran : *« dans tickets tu ne peux pas réduire ces pastilles à la
			      même taille que nouveau prestataire »*. C'étaient des cartes maison,
			      deux fois plus hautes que les pastilles du même site pour la même
			      question posée.
			      `ux-patterns` refusait la conversion — à raison : `Pastille` rendait
			      un `<button>`, et un `radiogroup` y aurait perdu ses flèches. La
			      réponse a été d'ENRICHIR l'objet plutôt que de le contourner : la
			      pastille sait désormais porter un `<input type="radio">`, masqué à
			      l'œil mais pas à l'accessibilité. -->
		<!--  ⚠️ `defilante={false}` : huit catégories ne tiennent pas sur une ligne,
		      et trois d'entre elles étaient hors du cadre (07/09/2026). On ne
		      choisit pas dans une liste dont on ignore la fin — un filtre qu'on
		      rate se rattrape, une catégorie ratée range le ticket ailleurs. -->
		<ChoixPastilles
			options={OPTIONS_CATEGORIE}
			bind:valeur={categorie}
			tous={false}
			radio="ticket-categorie"
			libelle="Catégorie"
			avecDetail
			defilante={false}
			grille
		/>
		<!--  🔴 La LÉGENDE du repère 📒 (21/09/2026, demandé à l'écran).
		      Un signe que rien n'explique n'apprend rien à qui le voit pour la
		      première fois — et ce qu'il annonce n'est pas un détail de
		      rangement : l'affaire, une fois close, entre dans un document
		      qu'un acquéreur peut réclamer.
		      ⚠️ La phrase se LIT dans `#lib/tickets` (`LEGENDE_CARNET`), à côté
		      du drapeau qui pose le repère. Recopiée ici, elle survivrait au
		      jour où la liste des catégories concernées change. -->
		<p class="aide">{LEGENDE_CARNET}</p>
	</SectionFormulaire>
{/if}

<!--  🔴 « Au nom de » (10) et « Mise en avant » (11) ne sont PLUS rendues ici.

      Elles l'étaient, et ce composant étant rendu avant `ChampsCommuns`, elles
      sortaient en 3ᵉ et 4ᵉ position — dix et onze rangs trop tôt. Signalé à
      l'écran le 21/09/2026 : *« L'ordre des sections du tableau n'est pas
      respecté »* (#1124).

      ⚠️ Aucun contrôle ne pouvait le voir : `ChampSaisiPour` et
      `SectionOptionsPublication` PORTENT leur intitulé, donc aucun `titre=`
      ne les trahissait, et `check-ordre-sections` ne lisait que des `titre=`.

      Elles viennent maintenant de `ChampsCommuns` (`avecSaisiPour`,
      `avecOptions`), qui rend dans l'ordre de `SECTIONS_ORDRE` — la même
      porte que pour l'actualité, l'idée et l'événement. -->

<!--  L'ÉQUIPEMENT (section 3, #1097) : le conseil le désigne, pour une
      catégorie du bâti. Ailleurs, grisé avec son motif (`inactivePour`). -->
{#if sectionPresente(TICKET, etat, 'equipement')}
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
				Coché d’office pour « Étude &amp; travaux ». La carte se range d’après le statut ci-dessus :
				Ouvert{SEPARATEUR.fleche}CS, En cours{SEPARATEUR.fleche}Syndic, Résolu{SEPARATEUR.fleche}Terminé,
				Annulé{SEPARATEUR.fleche}Annulé.
			</p>
		</div>
	{/if}
</SectionWorkflow>

<style>
	/*  Le style PART AVEC le balisage (05/09/2026) : il est resté ici quand les
	    sections 2 et 3 ont été extraites, et `lint:classes-nues` l'a vu tout de
	    suite — c'est la régression des pastilles nues (v2.67.11), qui s'était
	    reproduite trois fois le 19/08. Svelte scope au FICHIER : une classe
	    employée ici doit être définie ici. */
</style>
