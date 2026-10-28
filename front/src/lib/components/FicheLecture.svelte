<!--
  FicheLecture.svelte — le SQUELETTE EN LECTURE : le pendant de
  `FormulaireCreation` pour l'affichage.

  ## Pourquoi il naît (17/08/2026, #431)

  Le cadre #430 pose ses sections dans un ordre immuable, **et cet ordre vaut
  aussi pour l'affichage**. Or c'est le seul des quatre rendus qui n'avait aucun
  point d'héritage : mesuré sur 42 couples menu/entité, **l'affichage n'empruntait
  le motif d'aucun formulaire — 0 cas sur 42**. Chaque écran rangeait ses notions
  dans l'ordre où elles avaient été ajoutées.

  Sur les tickets, la carte affichait *description → photos → périmètre*, quand
  les deux formulaires demandent *périmètre → description → photos*. Et la fiche
  d'un ticket rendait `[...photos_urls, ...fichiers_urls]` dans UN seul bloc :
  la fusion des sections 7 et 8, que le cadre interdit explicitement.

  ## Ce qu'il décide, et ce qu'il ne décide pas

  Il décide **l'ORDRE** — et il le lit dans la déclaration de l'entité, pas dans
  ce fichier : `sectionsDe(entite, 'affichage')`. Le jour où une entité déclare
  qu'elle n'a pas de documents, la section disparaît d'elle-même, ici comme dans
  ses formulaires.

  Il ne décide RIEN du contenu métier. Les sections 1, 2, 3 et 5 arrivent par
  slots — l'écran seul sait ce qu'elles portent (un badge de statut, un
  « Saisi par X pour Y », une rangée de catégories). Le squelette garantit
  seulement qu'elles sont **à leur place**.

  ⚠️ Les slots sont rendus DANS la boucle, à la position déclarée de leur
  section : c'est ce qui fait que `<svelte:fragment slot="workflow">` ne peut
  pas atterrir ailleurs qu'en troisième position, quoi qu'écrive l'appelant.

  ## Le périmètre ne s'affiche pas quand il vaut la résidence entière

  Règle du projet (CLAUDE.md, front §4) : 🔹 = périmètre logique, et il n'est pas
  affiché quand il vaut le défaut. La carte de la liste le faisait ; la fiche du
  ticket, non — elle écrivait « 🔹 Copropriété entière » sur tous les tickets de
  la résidence. Un objet se rend toujours de la même façon (R3).
-->
<script lang="ts">
	import type { AffaireLiee } from '#lib/api/index.ts';
	import type { EntiteDeclaree } from '#lib/entites/types.ts';
	import { sectionsDe } from '#lib/entites/types.ts';
	import PiecesJointes from './PiecesJointes.svelte';
	import { safeDescription } from '#lib/sanitize.ts';
	import { perimetreLabel, estPerimetreParDefaut, relire } from '#lib/utils.ts';
	import { perimetresStore } from '#lib/stores/perimetres.ts';

	/** La déclaration de l'entité affichée — `TICKET`, puis `ACTUALITE`… */
	export let entite: EntiteDeclaree;

	//  ── 4. Périmètre ─────────────────────────────────────────────────────────
	export let perimetre: string[] | null | undefined = [];

	//  ── 6. Description ───────────────────────────────────────────────────────
	export let description = '';
	/** L'intervenant, déjà composé (`intervenantAffiche`) — vide : rien. */
	export let intervenant = '';
	/** L'équipement, déjà en libellé (`equipLabel`) — vide : rien (#1097). */
	export let equipement = '';

	//  ── 7. Photos · 8. Documents — DEUX sections, jamais une seule ───────────
	export let photos: string[] | null | undefined = [];
	export let documents: string[] | null | undefined = [];
	/** `grand` = on vient regarder la photo du dégât ; `vignette` = on la survole. */
	export let formatPieces: 'vignette' | 'grand' = 'grand';
	/** Les affaires liées que le serveur a jugées lisibles pour ce lecteur (#1342). */
	export let affairesLiees: AffaireLiee[] | null | undefined = [];

	$: sections = sectionsDe(entite, 'affichage');
	//  🔴 `$perimetresStore` n'est pas lu : il dit à Svelte que ce calcul dépend
	//  de l'arbre, que `estPerimetreParDefaut` et `perimetreLabel` lisent dans un
	//  état de MODULE. Sans lui, une fiche ouverte avant l'arrivée de l'arbre
	//  affiche le code brut, et rien ne revient le corriger (#947).
	$: textePerimetre = relire($perimetresStore, () =>
		perimetre?.length && !estPerimetreParDefaut(perimetre) ? perimetreLabel(perimetre) : '',
	);
</script>

{#each sections as s (s.id)}
	{#if s.id === 'titre'}
		<slot name="titre" />
	{:else if s.id === 'nature'}
		<slot name="specifiques" />
	{:else if s.id === 'suivi'}
		<slot name="workflow" />
	{:else if s.id === 'equipement'}
		{#if equipement}
			<p class="fiche-intervenant">Équipement : <strong>{equipement}</strong></p>
		{/if}
	{:else if s.id === 'intervenant'}
		{#if intervenant}
			<p class="fiche-intervenant">Intervenant : <strong>{intervenant}</strong></p>
		{/if}
	{:else if s.id === 'perimetre'}
		{#if textePerimetre}
			<p class="fiche-perimetre">&#x1F539; {textePerimetre}</p>
		{/if}
	{:else if s.id === 'destinataires'}
		<slot name="destinataires" />
	{:else if s.id === 'description'}
		{#if description}
			<div class="rich-content fiche-description">{@html safeDescription(description)}</div>
		{/if}
	{:else if s.id === 'pieces_jointes'}
		<!--  UNE section depuis #1095, DEUX réservoirs : le modèle distingue les
		      photos (des URLs) des documents (des entités `Document`), et ce lot ne
		      touche pas au modèle. Ce qui a fusionné est la section, pas la donnée.

		      ⚠️ Les deux rendus se suivent dans le même bloc : les séparer par un
		      titre rouvrirait la section que la table ne déclare plus. -->
		{#if photos?.length}
			<div class="fiche-pieces"><PiecesJointes urls={photos} format={formatPieces} /></div>
		{/if}
		{#if documents?.length}
			<div class="fiche-pieces"><PiecesJointes urls={documents} format={formatPieces} /></div>
		{/if}
	{:else if s.id === 'affaires_liees'}
		<!--  Chaque affaire se reconnaît à son TITRE, pas à son seul numéro (#1342). -->
		{#if affairesLiees?.length}
			<p class="fiche-intervenant fiche-liees">
				Affaires liées :
				{#each affairesLiees as a, i (a.id)}{i ? ' · ' : ''}<a href="/tickets/{a.id}"
						><strong>{a.numero}</strong> {a.titre}</a
					>{/each}
			</p>
		{/if}
	{/if}
{/each}

<!--  Ce qui n'est pas une des sections du cadre : la ligne de métadonnées, les
      commandes de l'écran. Toujours en dernier, jamais entre deux sections. -->
<slot name="pied" />

<style>
	/*  Ces trois classes sont définies ICI, sur des éléments que CE composant
	    rend : une classe posée par un parent sur le balisage d'un enfant n'est
	    pas atteinte par le `<style>` du parent — c'est la panne qui a envoyé des
	    pastilles nues en production (v2.67.11). */
	.fiche-perimetre,
	.fiche-intervenant {
		font-size: var(--fs-sm);
		color: var(--color-text-muted);
		margin: 0.25rem 0 0.5rem;
	}
	.fiche-description {
		font-size: var(--fs-base);
		line-height: 1.6;
		margin-bottom: 0.5rem;
	}
	.fiche-description :global(p) {
		margin: 0 0 0.5em;
	}
	.fiche-description :global(p:last-child) {
		margin-bottom: 0;
	}
	.fiche-description :global(ul),
	.fiche-description :global(ol) {
		padding-left: 1.3em;
		margin: 0 0 0.5em;
	}
	.fiche-pieces {
		margin-bottom: 0.5rem;
	}
	.fiche-liees a {
		color: inherit;
	}
</style>
