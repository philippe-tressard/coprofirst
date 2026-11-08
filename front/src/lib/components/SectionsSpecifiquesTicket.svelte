<!--
  SectionsSpecifiquesTicket.svelte — la section 2 du cadre #430 pour un ticket :
  la « Catégorie ». L'Équipement et le Suivi, qui la suivaient ici, vivent dans
  `SectionsEquipementSuiviTicket` depuis le 08/11/2026 (#2595).

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
	import { requisDe } from '#lib/pliage.ts';
	import SectionFormulaire from '#lib/components/SectionFormulaire.svelte';
	import ChoixPastilles from '#lib/components/ChoixPastilles.svelte';
	import { LEGENDE_CARNET } from '#lib/tickets.ts';
	import type { Etat } from '#lib/entites/types.ts';
	import { sectionPresente } from '#lib/entites/types.ts';
	import { TICKET } from '#lib/entites/ticket.ts';

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
	export let categorie = '';
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

<style>
	/*  Le style PART AVEC le balisage (05/09/2026) : il est resté ici quand les
	    sections 2 et 3 ont été extraites, et `lint:classes-nues` l'a vu tout de
	    suite — c'est la régression des pastilles nues (v2.67.11), qui s'était
	    reproduite trois fois le 19/08. Svelte scope au FICHIER : une classe
	    employée ici doit être définie ici. */
</style>
