<!--
  **Les caractéristiques d'un lot** — type, étage, superficie — en liste de
  définitions.

  ## Pourquoi ce composant (#779, 01/10/2026)

  « Mes lots » écrivait cette liste TROIS fois : le lot loué d'un locataire, les
  lots qu'il possède en propre, le lot choisi d'un copropriétaire. Les copies
  avaient divergé sur les cas limites : le type affiché sous condition dans
  l'une, sans dans les deux autres ; l'étage testé contre `undefined` dans
  l'une seulement — un lot sans étage connu y affichait « Étage » vide.

  Les lignes propres à chaque usage (le numéro, le bâtiment, les dates du bail)
  passent par les slots `avant` et `apres` : la liste reste une seule liste, et
  son ordre — l'identité, puis les caractéristiques, puis le reste — ne se
  recompose pas.

  🔒 `npm run lint:caracteristiques-lot` refuse un `<dt>Étage</dt>` ou un
  `<dt>Superficie</dt>` écrit ailleurs.

  ## La désignation du règlement (#2215)

  `designation` — un `MonLot` — ajoute ce que l'état descriptif dit du lot : sa porte
  ou sa place, où il est SITUÉ, ce qui le DESSERT, ses tantièmes (absents pour qui
  n'a pas à les lire : le serveur rend `null`), la phrase qui explique la charge et les
  alertes du lot — le tout par `DetailReglementLot`, écrit une fois pour toutes les vues.
  Les libellés des périmètres viennent du serveur aussi : aucun n'est recomposé ici.
-->
<script lang="ts">
	import DetailReglementLot from '$lib/components/DetailReglementLot.svelte';
	import type { MonLot } from '$lib/api';
	import { etageLabel, lotTypeComplet } from '$lib/utils';

	export let type: string | null | undefined = null;
	export let typeAppartement: string | null | undefined = null;
	export let etage: number | null | undefined = null;
	export let superficie: number | null | undefined = null;
	/** Le lot tel que `/lots/mes-lots` le rend — sa désignation du règlement. */
	export let designation: Pick<
		MonLot,
		'numero_usage' | 'perimetres' | 'quotes_parts' | 'explication' | 'alertes'
	> | null = null;

	$: situe = (designation?.perimetres ?? []).filter((p) => p.relation === 'situe_dans');
	$: dessert = (designation?.perimetres ?? []).filter((p) => p.relation === 'desservi_par');
</script>

<dl class="caracteristiques-lot">
	<slot name="avant" />
	{#if type}
		<dt>Type</dt>
		<dd class="type-lot">{lotTypeComplet(type, typeAppartement)}</dd>
	{/if}
	{#if etage !== null && etage !== undefined}
		<dt>Étage</dt>
		<dd>{etageLabel(etage)}</dd>
	{/if}
	{#if superficie}
		<dt>Superficie</dt>
		<dd>{superficie} m²</dd>
	{/if}
	{#if designation?.numero_usage}
		<dt>Porte ou place</dt>
		<dd>{designation.numero_usage}</dd>
	{/if}
	{#if situe.length}
		<dt>Situé dans</dt>
		<dd>{situe.map((p) => p.libelle).join(', ')}</dd>
	{/if}
	{#if dessert.length}
		<dt>Desservi par</dt>
		<dd>{dessert.map((p) => p.libelle).join(', ')}</dd>
	{/if}
	<slot name="apres" />
</dl>
{#if designation}
	<DetailReglementLot lot={designation} />
{/if}

<style>
	.caracteristiques-lot {
		display: grid;
		grid-template-columns: auto 1fr;
		gap: 0.4rem 0.8rem;
		font-size: var(--fs-base);
	}
	/*  `:global` : les lignes des slots sont rendues par l'appelant, et doivent
	    avoir le même aspect que celles du composant. */
	.caracteristiques-lot :global(dt) {
		font-weight: 500;
		color: var(--color-text-muted);
	}
	.caracteristiques-lot :global(dd) {
		margin: 0;
	}
	.type-lot {
		text-transform: capitalize;
	}
</style>
