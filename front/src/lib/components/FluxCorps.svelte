<!--
  Le CORPS DÉPLIÉ d'une carte du fil — ce qu'on lit après avoir ouvert la ligne :
  lieu, prestataire, dates, état, pièces jointes, réaction du conseil syndical, et
  le lien vers l'écran d'origine.

  Extrait de `FluxCard` le 11/09/2026, au fil de l'eau : la carte était à 511
  lignes et devait accueillir l'auteur en rangée. Le plafond de modularité (rang 1)
  refuse qu'un fichier déjà au-dessus de 500 grossisse, et c'est le corps qui s'en
  détache le plus proprement — il ne dépend d'aucun état de la carte, seulement de
  l'élément qu'elle porte.

  🔴 Ce qui est visible REPLIÉ ne se répète pas ici. Le périmètre l'a appris le
  18/08/2026, l'auteur le 11/09 : une méta portée par la rangée de l'en-tête
  s'afficherait deux fois sur toute carte ouverte.
-->
<script lang="ts">
	import BadgeEtatAffaire from '$lib/components/BadgeEtatAffaire.svelte';
	import type { FluxItem } from '$lib/api';
	import { fmtDatetimeShort } from '$lib/date';
	import { typeVoirLabel } from '$lib/flux';
	import { safeHtml } from '$lib/sanitize';
	import PiecesJointes from './PiecesJointes.svelte';
	import FluxAffaireEtapes from './FluxAffaireEtapes.svelte';

	export let item: FluxItem;
	/**  L'adresse de l'écran d'origine — calculée par la carte, qui connaît déjà
	 *   le type de l'élément. La recalculer ici la ferait diverger. */
	export let lien: string | null;

	//  Les deux listes viennent du même `meta` : les dériver ici plutôt que de les
	//  recevoir évite deux props pour une donnée que le composant a déjà.
	$: debut = item.meta?.debut as string | undefined;
	//  🔴 Le badge d'état — teinte de `$lib/tickets`, repli gris pour l'état d'un
	//  autre objet (événement, idée) — est `BadgeEtatAffaire` (#2173). Ce fichier
	//  en a porté une copie en ternaire imbriqué, puis la table lue sur place.
	$: photos = (item.meta?.photos_urls as string[] | undefined) ?? [];
	$: fichiers = (item.meta?.fichiers_urls as string[] | undefined) ?? [];
	//  Une AFFAIRE a le corps de la liste Affaires — les trois étapes, ouvertes sur
	//  « La suite » (arbitrage n° 66) : le serveur pose `demande` sur ses seules
	//  cartes (`flux/tickets._meta_ticket`), la donnée décide.
	$: estAffaire = !!item.meta?.demande;
</script>

<div class="flux-body" role="presentation" on:click|stopPropagation>
	{#if item.meta?.lieu}<p class="flux-meta-line">📍 {item.meta.lieu}</p>{/if}
	<!--  ⚠️ Le périmètre n'est PAS répété ici : il est déjà en badge dans
		      l'en-tête de la carte, visible replié comme déplié. Il s'affichait
		      deux fois sur toute carte dépliée — le même défaut que celui corrigé
		      sur les tickets le même jour, dans l'autre sens. -->
	{#if item.meta?.prestataire}<p class="flux-meta-line">🔧 {item.meta.prestataire}</p>{/if}
	<!-- `fin` est facultatif : l'exiger masquait la date de tenue de
		     tout événement sans heure de fin — désormais l'information
		     essentielle, puisque la ligne du fil est datée de l'annonce. -->
	{#if debut}
		<p class="flux-meta-line">
			🕐 {fmtDatetimeShort(String(debut))}{#if item.meta?.fin}
				→ {fmtDatetimeShort(String(item.meta.fin))}{/if}
		</p>
	{/if}
	<!--  ⚠️ L'auteur n'est PLUS répété ici : il est en rangée de l'en-tête, visible
	      replié comme déplié (11/09/2026). C'est le même défaut que le périmètre
	      ci-dessus, corrigé le 18/08 — une méta visible repliée ne se redit pas. -->
	<!--  L'état d'une affaire est déjà dans sa ligne de pastilles, pliée comme
	      dépliée : « État : Résolu » le redisait juste dessous (TK-109008). -->
	{#if item.meta?.statut && !estAffaire}
		<p class="flux-meta-line">
			État :
			<BadgeEtatAffaire statut={String(item.meta.statut)} />
		</p>
	{/if}
	<!--  🔴 LA DERNIÈRE MISE À JOUR D'ABORD, le texte d'origine ensuite
		      (#531, demandé à l'écran le 20/08/2026 sur la carte dépliée).

		      Une carte du fil répond à « quoi de neuf ». Ce qui est neuf, c'est
		      le commentaire du jour ; la description d'origine est le CONTEXTE
		      qui permet de le comprendre. L'ordre inverse obligeait à lire un
		      texte parfois vieux de plusieurs semaines avant d'atteindre la
		      seule ligne qu'on venait chercher.

		      ⚠️ La condition ne teste PAS le type : `evol_contenu` n'est posé
		      que par une carte de mise à jour, et le vérifier deux fois ferait
		      de cette liste de types une seconde déclaration à tenir. Elle a
		      immédiatement divergé la première fois : le calendrier a eu son
		      Historique le 18/08/2026, le fil a su le fournir, et RIEN ne
		      s'affichait. La donnée décide, pas une énumération de types. -->
	{#if estAffaire}
		<!--  Une affaire : la brique des trois étapes, chaque rubrique avec SES
		      pièces — le même composant que la liste (n° 66, 18/10/2026). -->
		<FluxAffaireEtapes {item} />
	{:else}
		{#if item.meta?.evol_contenu}
			<div class="flux-reaction">
				<span class="flux-reaction-icon">💬</span>
				<div class="flux-reaction-body">
					{#if item.meta?.evol_auteur}<span class="flux-reaction-auteur"
							>{item.meta.evol_auteur}</span
						>{/if}
					<p class="flux-reaction-text">{item.meta.evol_contenu}</p>
				</div>
			</div>
		{/if}
		<!--  Le texte d'origine, en dessous : il rappelle DE QUOI il s'agit. -->
		{#if item.meta?.full_html}
			<div class="flux-full-content rich-content">
				{@html safeHtml(String(item.meta.full_html))}
			</div>
		{:else if item.meta?.description}
			<p class="flux-full-content">{item.meta.description}</p>
		{:else if item.detail}
			<p class="flux-full-content">{item.detail}</p>
		{/if}
		{#if photos.length || fichiers.length}
			<!-- Les pièces jointes de devis sont des PDF : le composant
			     distingue image et document, une fois pour toutes.
			     Format « grand » : la carte est dépliée, l'utilisateur a
			     demandé à voir. -->
			<div class="flux-photos">
				<PiecesJointes urls={[...photos, ...fichiers]} format="grand" />
			</div>
		{/if}
	{/if}
	{#if lien}
		<a href={lien} class="flux-link">{typeVoirLabel(item)}</a>
	{/if}
</div>

<style>
	/*  Aligné sur le titre d'`EnteteCarte` (10/10/2026) : le retrait de 1,7 rem
	    le calait sous l'émoji de rubrique, parti dans la gouttière. Le retrait
	    latéral est celui de la carte (`FluxCard`, `.flux-corps-carte`). */
	.flux-body {
		border-top: 1px solid var(--color-border);
		padding: 0.75rem 0 0;
	}
	.flux-meta-line {
		font-size: var(--fs-md);
		color: var(--color-text-muted);
		margin: 0.15rem 0;
	}
	.flux-reaction {
		display: flex;
		gap: 0.5rem;
		align-items: flex-start;
		margin: 0.6rem 0 0.3rem;
		padding: 0.5rem 0.75rem;
		border-radius: 6px;
		background: var(--color-primary-light);
		border-left: 3px solid var(--color-primary);
		font-size: var(--fs-md);
	}
	.flux-reaction-icon {
		flex-shrink: 0;
		font-size: var(--fs-md);
		margin-top: 0.1rem;
	}
	.flux-reaction-body {
		display: flex;
		flex-direction: column;
		gap: 0.15rem;
		min-width: 0;
	}
	.flux-reaction-auteur {
		font-size: var(--fs-xs);
		font-weight: 600;
		color: var(--color-primary);
	}
	.flux-reaction-text {
		margin: 0;
		color: var(--color-text);
		line-height: 1.45;
	}
	.flux-full-content {
		font-size: var(--fs-md);
		line-height: 1.55;
		margin: 0.5rem 0;
	}
	.flux-link {
		font-size: var(--fs-sm);
		color: var(--color-primary);
		font-weight: 500;
		text-decoration: none;
		display: inline-block;
		margin-top: 0.5rem;
	}

	.flux-photos {
		margin: 0.5rem 0;
	}
</style>
