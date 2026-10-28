<script lang="ts">
	import { confirmer, SUPPRESSION } from '#lib/confirmation.ts';
	//  🔴 Les deux `class:` du gabarit remplacent un ternaire INTERPOLÉ (#810).
	//  Devant `class="… {cond ? 'a' : 'b'}"`, Svelte cesse de déclarer les
	//  sélecteurs inutilisés pour TOUT le fichier — le contrôle devenait aveugle
	//  sur cet écran. Deux valeurs locales et connues : la conversion ne coûte rien.
	import EntetePage from '#lib/components/EntetePage.svelte';
	import EtatListe from '#lib/components/EtatListe.svelte';
	import { essayer } from '#lib/chargement.ts';
	import { onMount } from 'svelte';
	import { notifications as notifApi, type Notification } from '#lib/api/index.ts';
	import { toast } from '#lib/components/Toast.svelte';
	import {
		getPageConfig,
		configStore,
		siteNomStore,
		defautsDePage,
	} from '#lib/stores/pageConfig.ts';
	import { safeRichContent } from '#lib/sanitize.ts';
	import { fmtTime, fmtDateShort } from '#lib/date.ts';

	$: _pc = getPageConfig($configStore, 'notifications', defautsDePage('notifications'));
	$: _siteNom = $siteNomStore;

	let items: Notification[] = [];
	let loading = true;
	/*  🔴 Sans cette variable, un chargement en échec laissait `items` à `[]` et
	    l'écran répondait « Aucune notification — Vous êtes à jour ! ». Le toast
	    d'erreur, lui, s'efface au bout de quelques secondes ; le mensonge reste.
	    C'est l'incident #519 reproduit sur un autre écran. */
	let erreur = '';
	let deleting = new Set<number>();

	onMount(async () => {
		await load();
	});

	async function load() {
		loading = true;
		//  `essayer` rend `[valeur, erreur]` — jamais l'un sans l'autre.
		[items, erreur] = await essayer(notifApi.list(), []);
		loading = false;
	}

	async function markRead(id: number) {
		try {
			await notifApi.markRead(id);
			items = items.map((n) => (n.id === id ? { ...n, lue: true } : n));
		} catch {
			toast('error', 'Erreur');
		}
	}

	async function markAll() {
		try {
			await notifApi.markAllRead();
			items = items.map((n) => ({ ...n, lue: true }));
			toast('success', 'Toutes les notifications marquées comme lues');
		} catch {
			toast('error', 'Erreur');
		}
	}

	async function remove(id: number) {
		if (!(await confirmer(SUPPRESSION('Cette notification')))) return;
		deleting = new Set([...deleting, id]);
		try {
			await notifApi.delete(id);
			items = items.filter((n) => n.id !== id);
		} catch {
			toast('error', 'Erreur lors de la suppression');
		} finally {
			deleting.delete(id);
			deleting = deleting;
		}
	}

	$: unread = items.filter((n) => !n.lue).length;
	$: sections = grouper(items);

	/**
	 *  Les notifications en SECTIONS — titre, contenu, format de date.
	 *
	 *  🔴 Ce découpage rendait `{ today, older }`, et le gabarit portait alors
	 *  **deux blocs de trente-huit lignes recopiés au caractère près** : même
	 *  carte, même pastille de non-lu, mêmes deux boutons. La seule différence
	 *  était `fmtTime` d'un côté et `fmtDateShort` de l'autre.
	 *
	 *  Ce qui varie entre deux sections est une DONNÉE — un titre, un formateur —
	 *  et non une raison d'écrire le rendu deux fois. La section porte donc les
	 *  trois, le gabarit ne connaît plus qu'une carte, et une troisième section
	 *  (« cette semaine ») coûterait désormais une ligne.
	 *
	 *  ⚠️ Une section vide n'est pas rendue, comme avant : les `{#if …length > 0}`
	 *  du gabarit se ramènent au filtre ci-dessous.
	 */
	function grouper(notifs: Notification[]) {
		const maintenant = Date.now();
		const recentes: Notification[] = [];
		const anciennes: Notification[] = [];
		for (const n of notifs) {
			const age = maintenant - new Date(n.cree_le).getTime();
			(age < 86400000 ? recentes : anciennes).push(n);
		}
		return [
			{ titre: "Aujourd'hui", notifs: recentes, format: fmtTime, espace: false },
			{ titre: 'Plus anciennes', notifs: anciennes, format: fmtDateShort, espace: true },
		].filter((section) => section.notifs.length > 0);
	}
</script>

<svelte:head><title>{_pc.titre} — {_siteNom}</title></svelte:head>

<a href="/tableau-de-bord" class="back-link">← Tableau de bord</a>

<EntetePage titre={_pc.titre} descriptif={_pc.descriptif} icone={_pc.icone || 'bell'}>
	{#if unread > 0}
		<span class="text-muted-md">{unread} non lue{unread > 1 ? 's' : ''}</span>
		<button class="btn btn-outline btn-sm" on:click={markAll}>Tout marquer lu</button>
	{/if}
</EntetePage>

{#if loading || erreur || items.length === 0}
	<EtatListe
		chargement={loading}
		{erreur}
		vide={items.length === 0}
		titreErreur="Impossible d’afficher vos notifications"
		titreVide="Aucune notification"
		messageVide="Vous êtes à jour !"
	/>
{:else}
	{#each sections as section (section.titre)}
		<h2 class="section-title" class:section-espacee={section.espace}>{section.titre}</h2>
		{#each section.notifs as n (n.id)}
			<div
				class="notif-row card"
				class:notif-read={n.lue}
				class:notif-unread={!n.lue}
				role="article"
			>
				<div class="notif-body">
					{#if !n.lue}<div class="unread-dot"></div>{/if}
					<div class="notif-content">
						<div class="entete-notif">
							<strong class="titre-notif">{n.titre}</strong>
							{#if n.urgente}<span class="badge badge-red">Urgent</span>{/if}
						</div>
						<p class="corps-notif">
							{@html safeRichContent(n.corps)}
						</p>
						<small class="date-notif">{section.format(n.cree_le)}</small>
					</div>
				</div>
				<div class="notif-actions">
					{#if !n.lue}
						<button class="btn btn-outline btn-sm" on:click={() => markRead(n.id)}
							>Marquer lu</button
						>
					{/if}
					<!--  Le glyphe ✕ ne dit rien à un lecteur d'écran, et ce bouton SUPPRIME :
					      le libellé nomme donc le geste et son objet, pas la croix. -->
					<button
						class="btn btn-danger btn-sm"
						aria-label="Supprimer cette notification"
						title="Supprimer cette notification"
						disabled={deleting.has(n.id)}
						on:click={() => remove(n.id)}>✕</button
					>
				</div>
			</div>
		{/each}
	{/each}
{/if}

<style>
	/*  Seul l'espacement bas diffère de la charte (#607, 28/08/2026). */
	.section-title {
		margin-bottom: 0.5rem;
	}
	/*  L'écart au-dessus des sections qui suivent la première — il était écrit
	    en style INLINE sur le second titre, ce qui obligeait à recopier le bloc
	    entier pour l'obtenir. Une classe le rend paramétrable. */
	.section-espacee {
		margin-top: 1.25rem;
	}
	.notif-row {
		display: flex;
		justify-content: space-between;
		align-items: flex-start;
		padding: 0.85rem 1rem;
		margin-bottom: 0.4rem;
		gap: 0.5rem;
	}
	.notif-unread {
		border-left: 3px solid var(--color-primary);
	}
	.notif-read {
		opacity: 0.7;
	}
	.notif-body {
		display: flex;
		align-items: flex-start;
		gap: 0.6rem;
		flex: 1;
		min-width: 0;
	}
	.notif-content {
		flex: 1;
		min-width: 0;
	}
	.notif-actions {
		display: flex;
		gap: 0.35rem;
		flex-shrink: 0;
	}
	.unread-dot {
		width: 8px;
		height: 8px;
		border-radius: 50%;
		background: var(--color-primary);
		margin-top: 6px;
		flex-shrink: 0;
	}

	/*  Ce lien de retour est plus discret et plus proche du contenu que la norme :
	    variation assumee, le reste vient de la charte (#607, 28/08/2026). */
	.back-link {
		display: inline-flex;
		align-items: center;
		gap: 0.3rem;
		font-size: var(--fs-md);
		color: var(--color-text-muted);
		margin-bottom: 0.75rem;
	}
	@media (hover: hover) and (pointer: fine) {
		.back-link:hover {
			color: var(--color-primary);
		}
	}
	.entete-notif {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		margin-bottom: 0.2rem;
	}
	.titre-notif {
		font-size: var(--fs-lg);
	}
	.corps-notif {
		font-size: var(--fs-base);
		color: var(--color-text-muted);
		margin: 0;
	}
	.date-notif {
		color: var(--color-text-muted);
		font-size: var(--fs-xs);
	}
</style>
