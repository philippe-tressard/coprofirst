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
  (`TicketEvolution`, rendu par la carte — `CorpsCarteTicket`). Deux tables, deux fils, deux
  composants — les fusionner effacerait la distinction que l'écran fait exprès.
-->
<script lang="ts">
	import ChargementDiffere from '#lib/components/ChargementDiffere.svelte';
	import { contexteCommentaire } from '#lib/assistant.ts';
	import { createEventDispatcher } from 'svelte';
	import { fmtDatetime } from '#lib/date.ts';
	import { safeDescription } from '#lib/sanitize.ts';
	import { estModerateur } from '#lib/stores/auth.ts';
	import PiecesJointes from '#lib/components/PiecesJointes.svelte';
	import IconeAction from '#lib/components/IconeAction.svelte';
	import PiedFormulaire from '#lib/components/PiedFormulaire.svelte';
	import RichEditor from '#lib/components/RichEditor.svelte';
	import { confirmer } from '#lib/confirmation.ts';
	import { TICKET } from '#lib/entites/ticket.ts';
	import { conditionsDeLaSuite } from '#lib/formulaire-affaire.ts';
	import { motifWhatsappInterdit } from '#lib/options-publication.ts';
	import { ticketLuDuSeulConseil } from '#lib/lecture-ticket.ts';
	import { gesteReponse } from '#lib/tickets.ts';
	import type { Ticket, TicketMessage, TicketEvolution } from '#lib/api/index.ts';
	import { nomCopie } from '#lib/saisi-pour.ts';

	/** Le ticket, pour son auteur et sa confidentialité. */
	export let ticket: Ticket;
	/** Les messages du fil, déjà chargés par la page. */
	export let messages: TicketMessage[] = [];
	/** Les évolutions — `EvolForm` s'en sert pour hériter le périmètre. */
	export let evolutions: TicketEvolution[] = [];
	/** Le message pointé par l'ancre d'une notification, encadré à l'arrivée. */
	export let msgVise: number | null = null;

	/** Le formulaire de réponse est-il ouvert ? Lié par l'appelant, qui l'ouvre
	 *  aussi depuis une ancre. */
	export let repondreOuvert = false;
	/** « Message interne » — lié parce que la page en dépend pour son envoi. */
	export let newInterne = false;
	/** Envoi en cours : désarme le bouton du formulaire. */
	export let sending = false;

	/**  Corriger ou retirer SON message (#2722) : la page appelle l'API, ce composant
	 *   tient seulement le geste. `corriger` rend vrai quand c'est enregistré. */
	export let corriger: (id: number, contenu: string) => Promise<boolean> = async () => false;
	export let retirer: (id: number) => Promise<void> = async () => {};

	/** Le message en cours de correction, et son texte. */
	let enCorrection: number | null = null;
	let texte = '';
	let enregistre = false;

	function commencer(m: TicketMessage) {
		enCorrection = m.id;
		texte = m.contenu;
	}
	async function enregistrer() {
		if (enCorrection === null || !texte.trim() || enregistre) return;
		enregistre = true;
		try {
			if (await corriger(enCorrection, texte)) enCorrection = null;
		} finally {
			enregistre = false;
		}
	}
	async function supprimer(m: TicketMessage) {
		const ok = await confirmer({
			message: 'Supprimer ce message ? Il disparaît aussi de l’Historique.',
			libelleConfirmer: 'Supprimer',
			danger: true,
		});
		if (ok) await retirer(m.id);
	}

	//  L'ENVOI reste à la page : c'est elle qui appelle l'API, recharge le fil et
	//  tient les erreurs. Ce composant rend le fil et transmet la saisie — il ne
	//  décide de rien.
	const dispatch = createEventDispatcher<{ envoyer: unknown }>();

	//  Qui peut répondre, et ce que le bouton dit — une règle, `gesteReponse`.
	$: reponse = gesteReponse(ticket);

	/**  Le formulaire OUVERT se met sous les yeux, curseur dans le texte : on l'ouvre
	 *   par son bouton, et il naît plus bas, hors de l'écran au téléphone. L'éditeur arrive en différé
	 *   (`ChargementDiffere`, puis l'éditeur riche) : on l'attend, sans délai écrit. */
	function auPremierPlan(noeud: HTMLElement) {
		const viser = () => {
			const zone = noeud.querySelector<HTMLElement>('[contenteditable="true"]');
			if (!zone) return false;
			zone.focus({ preventScroll: true });
			noeud.scrollIntoView({ block: 'center' });
			return true;
		};
		if (viser()) return;
		const veille = new MutationObserver(() => viser() && veille.disconnect());
		veille.observe(noeud, { childList: true, subtree: true, attributes: true });
		return { destroy: () => veille.disconnect() };
	}
</script>

<div class="messages colonne-lecture">
	{#each messages as msg (msg.id)}
		{#if !msg.interne || $estModerateur}
			<div
				id="msg-{msg.id}"
				class="message-bubble"
				class:own={msg.est_auteur}
				class:interne={msg.interne}
				class:message-vise={msgVise === msg.id}
			>
				<div class="msg-header">
					<strong>{msg.auteur_nom}</strong>
					{#if msg.interne}<span class="badge badge-yellow msg-badge">interne</span>{/if}
					<span class="msg-time">{fmtDatetime(msg.cree_le)}</span>
				</div>
				{#if enCorrection === msg.id}
					<RichEditor bind:value={texte} minHeight="80px" />
					<PiedFormulaire
						petit
						soumission={false}
						enCours={enregistre}
						desactive={!texte.trim()}
						on:enregistre={enregistrer}
						on:annule={() => (enCorrection = null)}
					/>
				{:else}
					<div class="msg-body">{@html safeDescription(msg.contenu)}</div>
				{/if}
				<!--  Son auteur seulement, tant que l'affaire est ouverte : la même règle que
				      la route (`messages._message_de_l_auteur`) — le serveur refuse le reste. -->
				{#if msg.est_auteur && !ticket.close && enCorrection !== msg.id}
					<div class="msg-actions">
						<button
							type="button"
							class="btn-icon"
							aria-label="Modifier mon message"
							title="Modifier"
							on:click={() => commencer(msg)}
						>
							<IconeAction icone="pencil" />
						</button>
						<button
							type="button"
							class="btn-icon-danger"
							aria-label="Supprimer mon message"
							title="Supprimer"
							on:click={() => supprimer(msg)}
						>
							<IconeAction icone="trash-2" />
						</button>
					</div>
				{/if}
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
	{#if !reponse}
		<!-- rien à répondre ici -->
	{:else if !repondreOuvert}
		<div class="card carte-repondre">
			<button type="button" class="btn btn-outline" on:click={() => (repondreOuvert = true)}>
				{reponse.glyphe}
				{reponse.libelle}
			</button>
		</div>
	{:else}
		<div class="card reply-form" use:auPremierPlan>
			{#key repondreOuvert}
				<ChargementDiffere charger={() => import('#lib/components/EvolForm.svelte')}>
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
							showEmail={$estModerateur && !newInterne}
							avecInterne={$estModerateur}
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
		background: var(--color-info-fond);
		align-self: flex-end;
		border-color: var(--color-info-bordure);
	}
	.message-bubble.interne {
		background: var(--color-jaune-fond);
		border-color: var(--color-warning-bordure);
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
	.msg-actions {
		display: flex;
		justify-content: flex-end;
		gap: 0.4rem;
		margin-top: 0.4rem;
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
