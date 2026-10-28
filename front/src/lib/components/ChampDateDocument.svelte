<!--
  **La date d'un document de « Ma résidence »** — celle qu'il porte, jamais celle
  de son dépôt : la date d'un règlement, d'un rapport de diagnostic.

  ## Pourquoi (11/10/2026)

  La gouttière d'une fiche montre QUAND (arbitré le 11/10/2026) : la date de
  l'AG pour un compte-rendu, la date du document pour un règlement ou un
  diagnostic. Arbitré le même jour : la date est DEMANDÉE — étoile de champ
  requis —, PROPOSÉE — l'appelant pré-remplit, aujourd'hui à la création, la
  date connue ou celle du dépôt à la correction (`jourIso`) — et MODIFIABLE.

  Quatre formulaires l'écrivent (règlement et rapport, création et correction) :
  un champ, une écriture.
-->
<script lang="ts">
	import EtoileRequis from '#lib/components/EtoileRequis.svelte';

	/** `AAAA-MM-JJ`, ou vide. */
	export let valeur = '';
	export let libelle = 'Date du document';
	/** Préfixe de l'`id` : la création et la correction peuvent être ouvertes ensemble. */
	export let idPrefixe: string;
</script>

<label class="field" for="{idPrefixe}-date-document">
	<span>{libelle}<EtoileRequis vide={!valeur} /></span>
	<input id="{idPrefixe}-date-document" type="date" required bind:value={valeur} />
</label>
