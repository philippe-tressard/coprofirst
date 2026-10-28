<script lang="ts">
	//  ── Le lien d'une affaire montre SA CARTE, dépliée (15/10/2026) ──────────
	//  Cette page est atteinte par un lien : courriel, groupe, « Copier le lien ».
	//  Elle rendait une FICHE à part — en-tête, boutons « Changer le statut »,
	//  Historique —, et la même affaire se lisait autrement qu'au fil d'activité
	//  et dans la liste (signalé à l'écran). Elle rend désormais la carte de la
	//  liste, seule et dépliée : même corps, mêmes gestes, par la même porte
	//  (`$lib/affaires-en-liste`). Le changement d'état passe par la Suite, comme
	//  partout ailleurs ; la corbeille, par les Archives (`ux-patterns` §8).
	//
	//  Ce qui lui reste PROPRE : le fil de MESSAGES, que la carte ne porte pas —
	//  les notifications de réponse pointent un message (`#msg-42`), et
	//  `?repondre=1` ouvre l'éditeur d'emblée.
	import { onMount, tick } from 'svelte';
	import { writable } from 'svelte/store';
	import { goto } from '$app/navigation';
	import { lieu } from '$lib/lieu.svelte';
	import { isAdmin } from '$lib/stores/auth';
	import { tickets as ticketsApi, ApiError, type Ticket, type TicketMessage } from '$lib/api';
	import { affairesEnListe } from '$lib/affaires-en-liste';
	import { estArchive } from '$lib/recherche-affaires';
	import { toast } from '$lib/components/Toast.svelte';
	import { estAbsent, messageErreur } from '$lib/erreurs';
	import ListeTickets from '$lib/components/ListeTickets.svelte';
	import FilMessagesTicket from '$lib/components/FilMessagesTicket.svelte';
	import FilAriane from '$lib/components/FilAriane.svelte';
	import EtatListe from '$lib/components/EtatListe.svelte';
	import { TICKET } from '$lib/entites/ticket';
	import { HREF_VERS_PAGE } from '$lib/pages';
	import { siteNomStore } from '$lib/stores/pageConfig';
	import { estActualite } from '$lib/tickets';
	import { aboutirGeste, ouvrirGeste } from '$lib/aboutissement';

	$: _siteNom = $siteNomStore;
	$: ticketId = Number($lieu.params.id);

	//  Une liste d'UNE affaire : c'est ce qui donne à cette page la carte de la
	//  liste, sans en écrire une seconde. Une suppression la vide — on rejoint
	//  alors la liste, la page n'a plus d'objet.
	const liste = writable<Ticket[]>([]);
	//  💬 L'icône de la carte ouvre le formulaire de réponse SUR PLACE, sous la
	//  carte : c'est ici qu'il vit, avec son envoi (`sendMessage`).
	const affaires = affairesEnListe(liste, {
		apresSuppression: () => goto('/tickets'),
		repondre: () => (repondreOuvert = true),
	});
	const { etat, gestes } = affaires;
	$: ticket = $liste[0] ?? null;

	let messages: TicketMessage[] = [];
	let loading = true;
	/**  Non vide = on n'a PAS pu lire l'affaire. Distinct de « elle n'existe pas ». */
	let erreur = '';
	let sending = false;
	//  Lié à `EvolForm` : le formulaire de réponse le propose en section
	//  Diffusion, la page décide de ce qu'il masque.
	let newInterne = false;

	// ── Lire d'abord, écrire ensuite ───────────────────────────────────────
	// On vient ici pour LIRE : le bloc de réponse est replié derrière un bouton,
	// et ne s'ouvre d'emblée que sur une intention explicite (`?repondre=1`),
	// que les liens de notification ne portent pas.
	let repondreOuvert = false;
	$: if (repondreOuvert) ouvrirGeste('affaire.repondre'); //  Le geste mesuré (#1633).
	let msgVise: number | null = null;

	onMount(async () => {
		//  `$lieu.url`, pas `window.location` : on arrive ici par l'icône 💬 d'une
		//  liste (`lienReponse`), une navigation du client.
		repondreOuvert = $lieu.url.searchParams.get('repondre') === '1';
		// Ancre `#msg-42` : les notifications de réponse pointent sur le message
		// qui a déclenché l'alerte — on y descend, plutôt qu'en haut d'un fil long.
		const ancre = window.location.hash.match(/^#msg-(\d+)$/);
		if (ancre) msgVise = Number(ancre[1]);
		try {
			const [lu, lus] = await Promise.all([
				ticketsApi.get(ticketId),
				ticketsApi.messages(ticketId),
			]);
			liste.set([lu]);
			messages = lus;
			await affaires.deplier(lu);
			if (msgVise !== null) {
				await tick();
				document.getElementById(`msg-${msgVise}`)?.scrollIntoView({ block: 'center' });
			}
		} catch (err) {
			//  🔴 « Introuvable » et « illisible » ne sont PAS la même chose (#816) :
			//  seul un 404 constate une absence.
			if (estAbsent(err)) toast('error', `${TICKET.libelle} introuvable`);
			else if (err instanceof ApiError) erreur = err.message;
			else erreur = 'Affaire illisible pour le moment — réessayez dans un instant.';
		} finally {
			loading = false;
		}
	});

	//  UNE seule forme d'évolution sur cet écran (#431) : la réponse enregistre un
	//  `TicketMessage`, qui alimente le fil de bulles ; le fil de la carte se relit.
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
			await affaires.chargerFil(ticketId);
		} catch (err) {
			toast('error', messageErreur(err));
		} finally {
			sending = false;
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
	<!--  Le titre de la page, pour qui navigue par les titres : la carte porte le
	      sien en bouton (il plie la carte), qui n'est pas un intitulé. -->
	<h1 class="sr-only">{ticket.titre}</h1>
	<div class="colonne-lecture affaire-seule">
		<ListeTickets
			tickets={$liste}
			archive={estArchive(ticket)}
			{...$etat}
			peutAdministrer={$isAdmin}
			{gestes}
		/>
	</div>

	<!--  LE FIL DES MESSAGES — à ne pas confondre avec le fil de la carte, au-dessus :
	      deux tables, deux fils. Pas de messages sur une actualité : elle informe,
	      on n'y répond pas au conseil comme dans un dossier. -->
	{#if !estActualite(ticket)}
		<FilMessagesTicket
			{ticket}
			{messages}
			evolutions={$etat.evolsMap[ticket.id] ?? []}
			{msgVise}
			{sending}
			bind:repondreOuvert
			bind:newInterne
			on:envoyer={(e) => sendMessage(e)}
		/>
	{/if}
{/if}

<style>
	/*  La colonne de lecture : la même largeur pour la carte et le fil des
	    messages — `.colonne-lecture` (`normes.css`), posée sur chaque bloc. */
	.affaire-seule {
		margin-bottom: 1rem;
	}
</style>
