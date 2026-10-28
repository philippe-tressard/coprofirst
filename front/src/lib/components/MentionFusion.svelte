<!--
  MentionFusion.svelte — « 🔀 Fusionnée dans TK-… » : où se poursuit le suivi (#1704).

  Une affaire absorbée à la clôture d'une autre n'a plus de fil à elle : ses
  suites ont rejoint la principale, et le serveur lui refuse toute Suite
  (`refuser_si_absorbee`). Cette mention prend la place du bouton « Ajouter une
  suite » et dit où aller.

  Le numéro n'est donné qu'à qui LIT la principale (`fusionnee_dans`, rendu par
  le serveur) ; aux autres, le fait seul — un lien ne révèle rien.
-->
<script lang="ts">
	import type { Ticket } from '#lib/api/index.ts';
	import { lienTicket } from '#lib/tickets.ts';

	export let ticket: Pick<Ticket, 'fusionnee' | 'fusionnee_dans'>;
</script>

{#if ticket.fusionnee}
	<p class="aide mention-fusion">
		🔀 Fusionnée dans
		{#if ticket.fusionnee_dans}
			<a href={lienTicket(ticket.fusionnee_dans.id)}>{ticket.fusionnee_dans.numero}</a> : son suivi se
			poursuit là-bas.
		{:else}
			une autre affaire, où son suivi se poursuit.
		{/if}
	</p>
{/if}

<style>
	.mention-fusion {
		margin: 0;
	}
</style>
