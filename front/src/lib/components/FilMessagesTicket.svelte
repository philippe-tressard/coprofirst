<!--
  FilMessagesTicket.svelte — le fil de MESSAGES d'un ticket : les bulles, et le
  geste « Répondre ».

  ## Pourquoi ce fichier existe (05/09/2026)

  Extrait de `tickets/[id]/+page.svelte`, que le contrôle de modularité a refusé
  de laisser grossir (523 → 526 lignes). Ce n'est pas une coupe de circonstance :
  ce bloc est une RUBRIQUE au sens du cadre #430 — un balisage, ses styles, et
  un geste —, et ses vingt règles CSS (`.message-bubble`, `.msg-*`) habillaient
  depuis la page un balisage qui n'a jamais servi ailleurs.

  ⚠️ **À ne pas confondre avec l'HISTORIQUE.** Ce fil-ci porte les messages
  échangés (`TicketMessage`) ; l'Historique porte les évolutions du dossier
  (`TicketEvolution`, rendu par `HistoriqueTicket`). Deux tables, deux fils, deux
  composants — les fusionner effacerait la distinction que l'écran fait exprès.
-->
<script lang="ts">
	import ChargementDiffere from '$lib/components/ChargementDiffere.svelte';
	import { contexteCommentaire } from '$lib/assistant';
	import { createEventDispatcher } from 'svelte';
	import { nomAffiche } from '$lib/noms';
	import { fmtDatetime } from '$lib/date';
	import { safeDescription } from '$lib/sanitize';
	import { currentUser, isCS } from '$lib/stores/auth';
	import PiecesJointes from '$lib/components/PiecesJointes.svelte';
	import { TICKET } from '$lib/entites/ticket';
	import { conditionsDeLaSuite } from '$lib/formulaire-affaire';
	import { motifWhatsappInterdit } from '$lib/options-publication';
	import { ticketLuDuSeulConseil } from '$lib/lecture-ticket';
	import type { Ticket, TicketMessage, TicketEvolution } from '$lib/api';
	import { nomCopie } from '$lib/saisi-pour';

	/** Le ticket, pour son auteur et sa confidentialité. */
	export let ticket: Ticket;
	/** Les messages du fil, déjà chargés par la page. */
	export let messages: TicketMessage[] = [];
	/** Les évolutions — `EvolForm` s'en sert pour hériter le périmètre. */
	export let evolutions: TicketEvolution[] = [];
	/** Le message pointé par l'ancre d'une notification, encadré à l'arrivée. */
	export let msgVise: number | null = null;
	/** Le ticket est-il clos ? Change le seul libellé du bouton. */
	export let clos = false;

	/** Le formulaire de réponse est-il ouvert ? Lié par l'appelant, qui l'ouvre
	 *  aussi depuis une ancre. */
	export let repondreOuvert = false;
	/** « Message interne » — lié parce que la page en dépend pour son envoi. */
	export let newInterne = false;
	/** Envoi en cours : désarme le bouton du formulaire. */
	export let sending = false;

	//  L'ENVOI reste à la page : c'est elle qui appelle l'API, recharge le fil et
	//  tient les erreurs. Ce composant rend le fil et transmet la saisie — il ne
	//  décide de rien.
	const dispatch = createEventDispatcher<{ envoyer: unknown }>();
</script>

<div class="messages colonne-lecture">
	{#each messages as msg (msg.id)}
		{@const isOwn = msg.auteur?.id === $currentUser?.id}
		{#if !msg.interne || $isCS}
			<div
				id="msg-{msg.id}"
				class="message-bubble"
				class:own={isOwn}
				class:interne={msg.interne}
				class:message-vise={msgVise === msg.id}
			>
				<div class="msg-header">
					<strong>{nomAffiche(msg.auteur)}</strong>
					{#if msg.interne}<span class="badge badge-yellow msg-badge">interne</span>{/if}
					<span class="msg-time">{fmtDatetime(msg.cree_le)}</span>
				</div>
				<div class="msg-body">{@html safeDescription(msg.contenu)}</div>
				{#if msg.fichiers_urls?.length}
					<div class="msg-pj">
						<PiecesJointes urls={msg.fichiers_urls} size={80} />
					</div>
				{/if}
			</div>
		{/if}
	{/each}

	<!--  Absorbée (#1704) : la discussion se poursuit dans la principale, et
	      l'Historique, juste dessous, le dit — une seule fois. -->
	{#if ticket.fusionnee}
		<!-- rien à répondre ici -->
	{:else if !repondreOuvert}
		<div class="card carte-repondre">
			<button type="button" class="btn btn-outline" on:click={() => (repondreOuvert = true)}>
				{clos ? '↩️ Rouvrir la discussion' : '💬 Répondre'}
			</button>
		</div>
	{:else}
		<div class="card reply-form">
			{#key repondreOuvert}
				<ChargementDiffere charger={() => import('$lib/components/EvolForm.svelte')}>
					{#snippet contenu(EvolForm)}
						<EvolForm
							entrees={evolutions}
							idPrefixe="tk-msg"
							auteurNom={nomCopie(ticket)}
							titre="Répondre"
							entite={TICKET}
							conditions={conditionsDeLaSuite(ticket)}
							assistant={contexteCommentaire(ticket)}
							avecPiecesJointes={!newInterne}
							whatsappInterdit={motifWhatsappInterdit(
								!!ticket && ticketLuDuSeulConseil(ticket),
								'ticket',
							)}
							showEmail={$isCS && !newInterne}
							avecInterne={$isCS}
							bind:interne={newInterne}
							saving={sending}
							on:submit={(e) => dispatch('envoyer', e.detail)}
							on:cancel={() => (repondreOuvert = false)}
						/>
					{/snippet}
				</ChargementDiffere>
			{/key}
		</div>
	{/if}
</div>

<style>
	/* Message pointé par l'ancre d'une notification : un cadre suffit à le
	   situer, sans clignotement ni couleur criarde — on vient lire, pas être
	   alerté une seconde fois. */
	.message-vise {
		outline: 2px solid var(--color-primary);
		outline-offset: 3px;
		border-radius: 10px;
	}

	.messages {
		display: flex;
		flex-direction: column;
		gap: 0.75rem;
	}
	.message-bubble {
		background: var(--color-bg);
		border: 1px solid var(--color-border);
		border-radius: var(--radius);
		padding: 0.75rem 1rem;
		align-self: flex-start;
		max-width: 90%;
	}
	.message-bubble.own {
		background: #eff6ff;
		align-self: flex-end;
		border-color: #bfdbfe;
	}
	.message-bubble.interne {
		background: #fefce8;
		border-color: #fef08a;
		opacity: 0.9;
	}
	.msg-header {
		display: flex;
		align-items: center;
		gap: 0.4rem;
		font-size: var(--fs-sm);
		margin-bottom: 0.3rem;
		flex-wrap: wrap;
	}
	.msg-header strong {
		font-size: var(--fs-md);
	}
	.msg-badge {
		font-size: var(--fs-2xs);
	}
	.msg-time {
		color: var(--color-text-muted);
		margin-left: auto;
	}
	.msg-body {
		font-size: var(--fs-base);
		line-height: 1.55;
		margin: 0;
	}
	.msg-body :global(p) {
		margin: 0 0 0.4em;
	}
	.msg-body :global(p:last-child) {
		margin-bottom: 0;
	}
	.msg-body :global(ul),
	.msg-body :global(ol) {
		padding-left: 1.3em;
		margin: 0 0 0.4em;
	}
	.msg-body :global(strong) {
		font-weight: 600;
	}
	.msg-pj {
		margin-top: 0.4rem;
	}

	.carte-repondre {
		text-align: center;
		padding: 0.9rem;
	}
	.reply-form {
		margin-top: 0.5rem;
	}
</style>
