<!--
  MentionConservation.svelte — « 🗄️ Conservée le … » : ce qu'une affaire échue a
  perdu, et où c'est parti (#2014).

  À son échéance (2, 5 ou 10 exercices après sa clôture, selon sa catégorie),
  une affaire perd ses pièces jointes — archivées hors ligne par l'administration
  — et ses auteurs, qui se lisent « Un résident » ou « Le conseil syndical ». Son
  texte reste. Sans cette mention, une affaire sans photo ni nom se lirait comme
  une affaire mal saisie. La règle vit au serveur (`utils/conservation_application`).
-->
<script lang="ts">
	import type { Ticket } from '#lib/api/index.ts';
	import { fmtDate } from '#lib/date.ts';

	export let ticket: Pick<Ticket, 'conservee_le'>;
</script>

{#if ticket.conservee_le}
	<p class="aide">
		🗄️ Conservée le {fmtDate(ticket.conservee_le)}&nbsp;: ses pièces jointes sont archivées hors
		ligne par l’administration, et ses auteurs ne sont plus nommés. Son texte reste.
	</p>
{/if}
