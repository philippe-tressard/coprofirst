<script lang="ts">
	import Badge from '$lib/components/Badge.svelte';
	import { etatAffiche } from '$lib/suivi-actualite';
	import { confirmer, SUPPRESSION } from '$lib/confirmation';
	import { estAbsent, messageErreur } from '$lib/erreurs';
	import { demanderFusion } from '$lib/fusion-affaires';
	import { onMount, tick } from 'svelte';
	import { page } from '$app/stores';
	import { isCS, isAdmin } from '$lib/stores/auth';
	import {
		tickets as ticketsApi,
		ApiError,
		type Ticket,
		type TicketEvolution,
		type TicketMessage,
	} from '$lib/api';
	import { toast } from '$lib/components/Toast.svelte';
	import FicheLecture from '$lib/components/FicheLecture.svelte';
	import HistoriqueTicket from '$lib/components/HistoriqueTicket.svelte';
	import FilMessagesTicket from '$lib/components/FilMessagesTicket.svelte';
	import TransfertsVerses from '$lib/components/TransfertsVerses.svelte';
	import { TICKET } from '$lib/entites/ticket';
	import { HREF_VERS_PAGE } from '$lib/pages';
	import { siteNomStore } from '$lib/stores/pageConfig';
	import FilAriane from '$lib/components/FilAriane.svelte';
	import { fmtDateLong, fmtDateShort } from '$lib/date';
	import { intervenantAffiche } from '$lib/prestataires';
	import {
		BADGE_PRIORITE,
		LIBELLE_PRIORITE,
		STATUTS_TICKET,
		STATUT_TICKET_BADGE,
		STATUT_TICKET_LABELS as STATUT_LABELS,
		categorieTicketLabel,
		estActualite,
		estTicketClos,
	} from '$lib/tickets';
	import EtatListe from '$lib/components/EtatListe.svelte';
	import { aboutirGeste, ouvrirGeste } from '$lib/aboutissement';

	$: _siteNom = $siteNomStore;

	let ticket: Ticket | null = null;
	let messages: TicketMessage[] = [];
	let evolutions: TicketEvolution[] = [];
	let erreurSuivi = '';
	let loading = true;
	/**  Non vide = on n'a PAS pu lire le ticket. Distinct de « il n'existe pas ». */
	let erreur = '';
	let sending = false;
	let updatingStatus = false;
	//  Lié à `EvolForm` : le formulaire de réponse le propose en section
	//  Diffusion, la page décide de ce qu'il masque (pièces jointes et adresse
	//  externe n'ont pas de sens sur un message qui ne sort pas du CS).
	let newInterne = false;

	// Évolutions
	//  ⚠️ Les quatre états du fil (formulaire ouvert, entrée en correction, deux
	//  drapeaux d'enregistrement) et leurs trois handlers vivaient ICI. Ils sont
	//  partis dans `HistoriqueTicket` avec le balisage qu'ils servaient : c'est
	//  ce qui garantit qu'un geste ajouté au fil arrivera sur les DEUX écrans, la
	//  liste et cette fiche, au lieu d'un seul (18/08/2026).
	$: ticketId = Number($page.params.id);

	//  ── Un seul geste pour changer d'état, sur cet écran comme ailleurs ──────
	//  Cette page portait DEUX commandes pour le même geste, à quelques
	//  centimètres l'une de l'autre : les boutons « Changer le statut » (qui
	//  proposaient `annulé`) et le formulaire d'évolution (qui proposait `fermé`
	//  à la place). Arbitré le 17/08/2026 (#415) : les boutons restent, le
	//  formulaire d'évolution ne sert plus qu'au commentaire.

	//  Les messages du fil sont d'anciens textes bruts pour certains : un contenu
	//  qui ne commence pas par une balise est enveloppé avant assainissement — c'est
	//  exactement ce que fait `safeDescription`, qui portait ici une copie littérale
	//  sous le nom `renderContent` (#429). La DESCRIPTION du ticket, elle, passe par
	//  `FicheLecture` — un objet se rend toujours de la même façon (R3).

	$: statutBadge = STATUT_TICKET_BADGE[ticket?.statut ?? ''] ?? 'badge-gray';
	$: statutLabel = STATUT_LABELS[ticket?.statut ?? ''] ?? ticket?.statut ?? '';
	//  Le suivi d'une actualité, s'il est activé (10/10/2026) — en lecture : il
	//  s'avance par une Suite, pas par les boutons d'une affaire.
	$: suiviActu = ticket && estActualite(ticket) ? etatAffiche(ticket) : null;
	//  `canReply` valait `statut !== 'fermé'` — le seul état qui interdisait de
	//  répondre, et il n'existe plus (#415, migration 0149). La condition n'est
	//  pas transposée à `clos` : elle fermerait la discussion sur les tickets
	//  résolus, qui l'acceptent aujourd'hui. Répondre reste donc toujours
	//  possible ; c'est `clos` qui change le libellé du bouton, plus bas.

	// ── Lire d'abord, écrire ensuite ───────────────────────────────────────
	// Cette page est atteinte surtout par un lien de notification (WhatsApp,
	// e-mail) : on y vient pour LIRE. Or l'éditeur, les photos, les documents et
	// le champ e-mail formaient un écran entier de contrôles avant même l'échange
	// — sur mobile, toute la page. Pire, un ticket déjà résolu proposait un
	// éditeur complet, suggérant une action que personne n'avait demandée.
	// Le bloc de réponse est donc replié derrière un bouton, et ne s'ouvre
	// d'emblée que sur une intention explicite (`?repondre=1`), que les liens de
	// notification ne portent pas.
	let repondreOuvert = false;
	$: if (repondreOuvert) ouvrirGeste('affaire.repondre'); //  Le geste mesuré (#1633).
	let msgVise: number | null = null;
	$: clos = !!ticket && estTicketClos(ticket.statut);

	async function loadEvolutions() {
		try {
			evolutions = await ticketsApi.evolutions(ticketId);
			erreurSuivi = '';
		} catch (e) {
			//  Dit, jamais avalé (29/09/2026) : avalé, un 403 rendait un fil VIDE (TK-124285).
			erreurSuivi = messageErreur(e);
		}
	}

	onMount(async () => {
		// Intention explicite : un lien « répondre » ouvre l'éditeur d'emblée.
		// Les liens de notification, eux, mènent à la lecture.
		repondreOuvert = new URLSearchParams(window.location.search).get('repondre') === '1';
		// Ancre `#msg-42` : les notifications de réponse pointent sur le message qui
		// a déclenché l'alerte. Sans ce défilement, le lecteur atterrissait en haut
		// d'un fil parfois long, à lui de retrouver la nouveauté.
		const ancre = window.location.hash.match(/^#msg-(\d+)$/);
		if (ancre) msgVise = Number(ancre[1]);
		try {
			[ticket, messages] = await Promise.all([
				ticketsApi.get(ticketId),
				ticketsApi.messages(ticketId),
			]);
			await loadEvolutions();
			if (msgVise !== null) {
				await tick();
				document.getElementById(`msg-${msgVise}`)?.scrollIntoView({ block: 'center' });
			}
		} catch (err) {
			//  🔴 « Introuvable » et « illisible » ne sont PAS la même chose (#816).
			//  Ce `catch` disait « Ticket introuvable » à un 500, à une session
			//  expirée et à une coupure réseau — et l'écran affirmait ensuite une
			//  absence qu'il n'avait pas constatée. Seul un 404 la constate.
			if (estAbsent(err)) toast('error', `${TICKET.libelle} introuvable`);
			else if (err instanceof ApiError) erreur = err.message;
			else erreur = 'Ticket illisible pour le moment — réessayez dans un instant.';
		} finally {
			loading = false;
		}
	});

	//  ── UNE seule forme d'évolution sur cet écran (#431) ─────────────────────
	//  Cette page portait `EvolForm` **et** un formulaire de réponse écrit à la
	//  main, à quelques centimètres : jeux de champs presque identiques, deux
	//  libellés de bouton pour le même geste (« Envoyer » contre « Enregistrer »),
	//  et une case « Message interne » posée au milieu du commentaire alors que
	//  c'est une décision de diffusion. Le formulaire à la main a disparu ; ce que
	//  la réponse enregistre — un `TicketMessage`, qui alimente le fil de bulles —
	//  n'a pas changé.
	async function sendMessage(e: CustomEvent) {
		const data = e.detail;
		if (!data.contenu?.trim()) return;
		sending = true;
		try {
			const msg = await ticketsApi.addMessage(ticketId, {
				contenu: data.contenu,
				interne: !!data.interne,
				fichiers_urls: data.fichiers_urls ?? [],
				assiste_ia: data.assiste_ia,
				email_externe: data.email_externe,
			});
			aboutirGeste('affaire.repondre');
			messages = [...messages, msg];
			newInterne = false;
			repondreOuvert = false;
			await loadEvolutions();
		} catch (err) {
			toast('error', messageErreur(err));
		} finally {
			sending = false;
		}
	}

	//  ── Le changement d'état est une TRANSITION, pas une correction ──────────
	//  Ces boutons passaient par `PATCH /tickets/{id}`, qui écrivait lui-même une
	//  évolution « Statut : X → Y ». Depuis que l'édition rouvre le workflow
	//  (cadre #430), le `PATCH` ne peut plus produire de transition — il écrirait
	//  une étape de suivi à chaque faute de frappe rattrapée. Il écrit désormais
	//  une **correction**, et la transition passe par l'endpoint qui la trace
	//  vraiment : date, auteur, courriel à l'auteur du ticket.
	async function updateStatus(s: string) {
		if (!ticket) return;
		//  Clore demande s'il faut absorber les affaires liées ouvertes (#1704).
		const fusionner = await demanderFusion(ticket, s);
		if (fusionner === null) return;
		updatingStatus = true;
		try {
			await ticketsApi.addEvolution(ticketId, { type: 'etat', nouveau_statut: s, fusionner });
			ticket = await ticketsApi.get(ticketId);
			await loadEvolutions();
			toast('success', 'Statut mis à jour');
		} catch (err) {
			toast('error', messageErreur(err, 'Erreur de mise à jour'));
		} finally {
			updatingStatus = false;
		}
	}

	/** Un transfert annulé change la fiche ET son fil : les deux se relisent. */
	async function recharger() {
		try {
			ticket = await ticketsApi.get(ticketId);
		} catch (e) {
			toast('error', messageErreur(e));
		}
		await loadEvolutions();
	}

	async function deleteTicket() {
		if (!ticket) return;
		if (!(await confirmer(SUPPRESSION(`${TICKET.libelle} #${ticket.numero}`)))) return;
		try {
			await ticketsApi.delete(ticketId);
			toast('success', `${TICKET.libelle} supprimée`);
			window.location.href = '/tickets';
		} catch (e) {
			toast('error', messageErreur(e));
		}
	}
</script>

<svelte:head><title>{TICKET.libelle} #{ticketId} — {_siteNom}</title></svelte:head>

<FilAriane
	segments={[{ libelle: HREF_VERS_PAGE['/tickets']?.navLabel ?? TICKET.libelle, href: '/tickets' }]}
	courant={ticket?.titre ?? TICKET.libelle}
/>

{#if loading}
	<EtatListe chargement />
{:else if erreur}
	<!--  L'échec AVANT le vide : dire « introuvable » quand on n'a pas pu
	      regarder, c'est affirmer une absence qu'on n'a pas constatée. -->
	<div class="empty-state">
		<h3>Impossible d’afficher cette affaire</h3>
		<p>{erreur}</p>
	</div>
{:else if !ticket}
	<div class="empty-state"><h3>{TICKET.libelle} introuvable</h3></div>
{:else}
	<!--  La fiche suit l'ORDRE DES NEUF SECTIONS, comme les formulaires : c'est
	      `FicheLecture` qui le lit dans la déclaration `TICKET`, et les slots ne
	      peuvent donc pas atterrir ailleurs qu'à la place de leur section.
	      Avant #431, l'écran commençait par le badge d'état (section 3) puis le
	      titre (section 1), et rendait `[...photos_urls, ...fichiers_urls]` dans
	      UN seul bloc — la fusion des sections 7 et 8, que le cadre interdit. -->
	<div class="ticket-header card colonne-lecture">
		<FicheLecture
			entite={TICKET}
			perimetre={ticket.perimetre_cible ?? []}
			description={ticket.description}
			intervenant={intervenantAffiche(ticket)}
			photos={ticket.photos_urls ?? []}
			documents={ticket.fichiers_urls ?? []}
			affairesLiees={ticket.affaires_liees}
		>
			<svelte:fragment slot="titre">
				<div class="ticket-meta">
					<span class="badge badge-gray">{categorieTicketLabel(ticket.categorie)}</span>
				</div>
				<h1 class="ticket-titre">{ticket.titre}</h1>
				<p class="ticket-dates">
					{fmtDateLong(ticket.cree_le)}
					{#if ticket.mis_a_jour_le && ticket.mis_a_jour_le !== ticket.cree_le}
						&middot; mis à jour le {fmtDateShort(ticket.mis_a_jour_le)}
					{/if}
				</p>
			</svelte:fragment>

			<svelte:fragment slot="specifiques">
				{#if ticket.saisi_pour_affichage && $isCS}
					<p class="ticket-saisi-pour">
						👤 Saisi par <strong>{ticket.auteur_nom ?? 'inconnu'}</strong> pour
						<strong>{ticket.saisi_pour_affichage}</strong>
						{#if ticket.saisi_pour_email}
							· <a href="mailto:{ticket.saisi_pour_email}">{ticket.saisi_pour_email}</a>
						{/if}
					</p>
				{/if}
			</svelte:fragment>

			<!--  Une ACTUALITÉ n'a pas de cycle (#1091) : ni état, ni « Changer le
			      statut ». Son suivi optionnel (10/10/2026) se lit ici, et s'avance
			      par une Suite. -->
			<svelte:fragment slot="workflow">
				{#if !estActualite(ticket)}
					<div class="ticket-meta">
						<Badge teinte={statutBadge}>{statutLabel}</Badge>
						{#if ticket.priorite && ticket.priorite !== 'normale'}
							<Badge teinte={BADGE_PRIORITE[ticket.priorite] ?? 'badge-gray'}
								>{LIBELLE_PRIORITE[ticket.priorite] ?? ticket.priorite}</Badge
							>
						{/if}
					</div>
					<!--  Une affaire absorbée n'a plus d'état à changer (#1704). -->
					{#if $isCS && !ticket.fusionnee}
						<div class="status-actions">
							<span class="status-label">Changer le statut :</span>
							<div class="status-boutons">
								{#each STATUTS_TICKET as s (s.value)}
									<button
										class="btn btn-sm"
										class:btn-primary={ticket.statut === s.value}
										class:btn-outline={ticket.statut !== s.value}
										disabled={updatingStatus || ticket.statut === s.value}
										on:click={() => updateStatus(s.value)}>{s.label}</button
									>
								{/each}
							</div>
						</div>
					{/if}
				{:else if suiviActu}
					<div class="ticket-meta">
						<Badge teinte={STATUT_TICKET_BADGE[suiviActu] ?? 'badge-gray'}
							>{STATUT_LABELS[suiviActu] ?? suiviActu}</Badge
						>
					</div>
				{/if}
			</svelte:fragment>

			<svelte:fragment slot="pied">
				{#if ticket.destinataire_syndic}
					<p class="ticket-envoi">📧 Envoyé au syndic</p>
				{/if}
			</svelte:fragment>
		</FicheLecture>
	</div>

	<!--  LE FIL DES MESSAGES — extrait le 05/09/2026 dans `FilMessagesTicket`.
	      Une rubrique complète (balisage, styles, geste de réponse) que le
	      contrôle de modularité a refusé de laisser grossir ici. À ne pas
	      confondre avec l'Historique juste en dessous : deux tables, deux fils. -->
	<!--  Pas de fil de messages sur une actualité : elle informe, on n'y répond
	      pas au conseil comme dans un dossier. Sa Suite, elle, reste. -->
	{#if !estActualite(ticket)}
		<FilMessagesTicket
			{ticket}
			{messages}
			{evolutions}
			{msgVise}
			{clos}
			{sending}
			bind:repondreOuvert
			bind:newInterne
			on:envoyer={(e) => sendMessage(e)}
		/>
	{/if}

	<!--  Les transferts de courriel versés ici, et ce qui les défait (#1482) :
	      rendu par qui peut les défaire seulement, et au-dessus de l'Historique
	      dont ils ont écrit les Suites. Un geste recharge la fiche. -->
	<TransfertsVerses {ticketId} on:change={recharger} />

	<!--  L'HISTORIQUE — le fil, avec ses gestes. Extrait le 18/08/2026 dans
	      `HistoriqueTicket` : la liste et cette fiche le rendaient chacune de
	      leur côté, et les deux câblages ont divergé DEUX FOIS, dans les deux
	      sens — le crayon manquait à la liste, la corbeille manquait ici. -->
	<HistoriqueTicket {ticketId} {ticket} {evolutions} {erreurSuivi} on:change={loadEvolutions} />

	<!-- Suppression admin -->
	{#if $isAdmin}
		<div class="zone-suppression colonne-lecture">
			<button class="btn btn-outline btn-sm btn-supprimer" on:click={deleteTicket}>
				&#x1F5D1;️ Supprimer définitivement
			</button>
		</div>
	{/if}
{/if}

<style>
	/*  ⚠️ Le fil d'évolutions n'a plus AUCUN style ici : `.evol-list`, `.evol-item`,
	    `.evol-meta`… vivent dans `RubriqueHistorique`, avec le balisage qu'ils
	    habillent. Les laisser ici en aurait fait la quatrième copie d'un même
	    bloc, et Svelte ne les aurait de toute façon pas appliqués au composant. */

	/*  `.etat-chargement` est parti avec son paragraphe : `EtatListe` le rend et le
	    stylise (#1045). C'en était une copie, sous le même nom de classe.

	    `.back-link` est parti dans `FilAriane` (#365) : il était défini trois
	    fois à l'identique dans le dépôt, et disait « Retour aux tickets » là où
	    le sondage disait « Communauté ». */

	/*  La colonne de lecture : la même largeur pour la fiche, le fil et
	    l'Historique — `.colonne-lecture` (`normes.css`), posée sur chaque
	    bloc. Elle vivait ici sur `.messages`, que l'extraction du fil a
	    rendue morte : la barre « Répondre » débordait (01/10/2026). */
	.ticket-header {
		border-left: 4px solid var(--color-primary);
		margin-bottom: 1rem;
	}
	.ticket-meta {
		display: flex;
		gap: 0.4rem;
		flex-wrap: wrap;
		margin-bottom: 0.4rem;
	}
	.ticket-titre {
		font-size: 1.1rem;
		font-weight: 700;
		margin: 0.6rem 0 0.3rem;
	}
	.ticket-dates {
		font-size: var(--fs-base);
		color: var(--color-text-muted);
	}
	.ticket-envoi {
		font-size: var(--fs-sm);
		color: var(--color-text-muted);
		margin-top: 0.5rem;
	}
	.ticket-saisi-pour {
		font-size: var(--fs-md);
		color: var(--color-text-muted);
		margin: 0.5rem 0;
		padding: 0.5rem 0.75rem;
		background: var(--color-bg-muted, #f5f5f5);
		border-radius: var(--radius);
	}
	.status-actions {
		margin-top: 0.75rem;
		padding-top: 0.75rem;
		border-top: 1px solid var(--color-border);
	}
	.status-label {
		font-size: var(--fs-sm);
		font-weight: 500;
		color: var(--color-text-muted);
	}
	.status-boutons {
		display: flex;
		gap: 0.4rem;
		flex-wrap: wrap;
		margin-top: 0.3rem;
	}

	/*  🔴 `.bloc-historique` a été retirée le 06/09/2026 (#810) — deux règles,
	    zéro balisage. Le reste d'un bloc parti, invisible depuis des mois : cet
	    écran porte une classe interpolée, et Svelte cesse alors de déclarer les
	    sélecteurs inutilisés pour TOUT le fichier. Trouvée en neutralisant
	    temporairement les interpolations du front pour mesurer ce que
	    l'aveuglement masquait. */

	.zone-suppression {
		margin-top: 2rem;
		padding-top: 1rem;
		border-top: 1px solid var(--color-border);
	}
	.btn-supprimer {
		color: var(--color-danger);
		border-color: var(--color-danger);
	}
</style>
