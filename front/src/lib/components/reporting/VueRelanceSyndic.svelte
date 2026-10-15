<!--
  Reporting CS — **relance syndic** : toutes les affaires en cours, celles que le
  délai rend éligibles à une relance, et l'envoi groupé.

  Extrait d'`espace-cs/+page.svelte` avec #453. Autonome : c'est la seule vue dont
  les données ne viennent pas du chargement commun — `relanceSyndicList` applique
  le délai côté serveur. Elle expose `chargement` et `estVide` à la barre d'outils
  du parent, qui en a besoin : « Imprimer » refuse une page vide, et
  « Rafraîchir » doit savoir quoi recharger.
-->
<script lang="ts">
	import Badge from '$lib/components/Badge.svelte';
	import { messageErreur } from '$lib/erreurs';
	import { confirmer } from '$lib/confirmation';
	import { onMount } from 'svelte';
	import { TICKET } from '$lib/entites/ticket';
	import { categorieTicketLabel } from '$lib/tickets';
	import { tickets as ticketsApi, type Ticket, type ReponseRelance } from '$lib/api';
	import { toast } from '$lib/components/Toast.svelte';
	//  `fmtDatetime` vient de $lib/date — jamais un format réimplémenté ici.
	import { daysSince, fmtDatetime } from '$lib/date';
	import EtatListe from '$lib/components/EtatListe.svelte';
	import { essayer } from '$lib/chargement';
	import {
		STATUT_TICKET_BADGE as TK_STATUT_BADGE,
		STATUT_TICKET_LABELS as TK_STATUT_LABELS,
	} from '$lib/tickets';

	let relanceList: Ticket[] = [];
	let relanceDelaiJours = 30;
	let relanceLoading = false;
	let relanceLoaded = false;
	let relanceSelected: Set<number> = new Set();
	let relanceSending = false;

	/** Lu par la barre d'outils du parent — ne pas écrire depuis l'extérieur. */
	export let chargement = false;
	/** Idem : « rien à imprimer » se décide ici, pas dans la barre d'outils. */
	export let estVide = true;
	$: chargement = relanceLoading;
	$: estVide = relanceList.length === 0;

	/*  🔴 Sans état d'échec, la vue répondait « ✅ Aucun ticket syndic en cours » —
	    avec une COCHE VERTE. Un échec de chargement se lisait donc comme une bonne
	    nouvelle, sur l'écran même qui sert à relancer le syndic (#816). */
	let erreur = '';

	async function loadRelanceSyndic(force = false) {
		if (relanceLoaded && !force) return;
		relanceLoading = true;
		erreur = '';
		try {
			const resp = await ticketsApi.relanceSyndicList();
			relanceDelaiJours = resp.delai_jours;
			relanceList = resp.tickets;
			// Pré-sélectionner uniquement les tickets éligibles (passé le délai)
			relanceSelected = new Set(
				relanceList.filter((t) => daysSince(t.mis_a_jour_le) >= relanceDelaiJours).map((t) => t.id),
			);
			relanceLoaded = true;
		} catch (e) {
			toast('error', messageErreur(e, 'Erreur chargement relances syndic'));
			erreur = messageErreur(e, 'Chargement impossible');
		} finally {
			relanceLoading = false;
		}
	}

	async function envoiRelance() {
		const ids = Array.from(relanceSelected);
		if (ids.length === 0) return;
		if (
			!(await confirmer(
				`Envoyer la relance pour ${ids.length} ${TICKET.libelle.toLowerCase()}(s) au syndic ?`,
			))
		)
			return;
		relanceSending = true;
		try {
			const res = await ticketsApi.envoiRelance(ids);
			toast('success', `✅ Relance envoyée à ${res.relance_to}`);
			await loadRelanceSyndic(true);
		} catch (e) {
			toast('error', messageErreur(e, 'Erreur envoi relance'));
			//  Le serveur refuse une affaire close, archivée ou fusionnée depuis
			//  l'ouverture de l'écran : la liste rechargée ne la propose plus.
			await loadRelanceSyndic(true);
		} finally {
			relanceSending = false;
		}
	}

	//  🔴 LES RÉPONSES DU SYNDIC, conservées et relues ICI (04/09/2026).
	//
	//  Elles étaient captées et notifiées, jamais consultables : une notification
	//  se lit une fois puis descend dans la pile. Passé quelques jours, la réponse
	//  du syndic était en base et introuvable — le défaut que tout ce chantier
	//  corrige, déplacé de la boîte aux lettres vers une table de notifications.
	//
	//  ⚠️ Elles s'affichent sous la relance, jamais dans les fils : « pour le
	//  TK-123 on intervient jeudi, le TK-456 est clos » recopié dans quatre fils
	//  serait faux dans trois. Le conseil reporte là où c'est juste.
	let reponses: ReponseRelance[] = [];

	//  Une ligne discrète, pas un second bandeau : l'écran principal reste juste
	//  sans cet historique, mais ne doit pas le dire vide (#1459).
	let erreurReponses = '';
	async function loadReponses() {
		const [r, e] = await essayer(ticketsApi.relanceReponses(), { reponses: [] });
		[reponses, erreurReponses] = [r.reponses, e];
	}

	/** Rechargement demandé par la barre d'outils du parent. */
	export function recharger() {
		loadRelanceSyndic(true);
		loadReponses();
	}

	onMount(() => {
		loadRelanceSyndic();
		loadReponses();
	});
</script>

{#if erreurReponses}
	<EtatListe compact erreur={erreurReponses} />
{:else if reponses.length}
	<section class="report-card carte-espacee">
		<h3 class="rep-titre">&#x1F4E8; Réponses du syndic aux relances</h3>
		<p class="rep-aide">
			Ces réponses portent sur <strong>plusieurs dossiers à la fois</strong> : elles ne sont volontairement
			ajoutées à aucun fil. À reporter dans les affaires concernées.
		</p>
		{#each reponses as rep (rep.id)}
			<article class="rep-carte">
				<header class="rep-entete">
					<span class="rep-de">{rep.expediteur}</span>
					<span class="rep-quand">{fmtDatetime(rep.recue_le)}</span>
				</header>
				{#if rep.tickets.length}
					<p class="rep-tickets">
						Relance portant sur&nbsp;: {#each rep.tickets as num, i (num)}<span
								class="badge badge-gray">#{num}</span
							>{#if i < rep.tickets.length - 1}&nbsp;{/if}{/each}
					</p>
				{/if}
				<p class="rep-texte">{rep.contenu || '(message sans texte lisible)'}</p>
			</article>
		{/each}
	</section>
{/if}

{#if relanceLoading || erreur || relanceList.length === 0}
	<EtatListe
		chargement={relanceLoading}
		{erreur}
		vide={relanceList.length === 0}
		titreErreur="Impossible d’afficher les tickets syndic"
		titreVide="✅ Aucune affaire en cours"
		messageVide="Aucune affaire n'est ouverte ou en cours : rien à relancer."
	/>
{:else}
	{@const eligibles = relanceList.filter((t) => daysSince(t.mis_a_jour_le) >= relanceDelaiJours)}
	<section class="report-card carte-espacee">
		<h3>🔔 Affaires syndic — suivi des relances</h3>
		<p class="report-intro">
			{relanceList.length} affaire(s) en cours.
			{#if eligibles.length > 0}
				<strong>{eligibles.length} éligible(s) à la relance</strong> (sans modification depuis plus
				de {relanceDelaiJours} jours).
			{:else}
				Aucune affaire ne dépasse le délai de {relanceDelaiJours} jours pour l'instant.
			{/if}
		</p>

		<div class="liste-relances">
			{#each relanceList as t (t.id)}
				{@const jours = daysSince(t.mis_a_jour_le)}
				{@const eligible = jours >= relanceDelaiJours}
				{@const selected = relanceSelected.has(t.id)}
				<div
					class="relance-item"
					class:relance-item-unselected={!selected}
					class:relance-item-pending={!eligible}
				>
					<div class="relance-item-top">
						<label class="choix-relance">
							<input
								type="checkbox"
								checked={selected}
								on:change={() => {
									const s = new Set(relanceSelected);
									if (s.has(t.id)) s.delete(t.id);
									else s.add(t.id);
									relanceSelected = s;
								}}
							/>
							<span class="relance-numero">{t.numero}</span>
							<span class="relance-titre">{t.titre}</span>
						</label>
						<div class="relance-item-right">
							{#if eligible}
								{#if (t.relance_count ?? 0) > 0}
									<span class="badge badge-red">Relance n°{(t.relance_count ?? 0) + 1}</span>
								{:else}
									<span class="badge badge-orange">1ère relance</span>
								{/if}
								<span class="relance-date relance-date-overdue" title="Dernière modification"
									>{jours}j sans modif.</span
								>
							{:else}
								<span class="badge badge-gray">En attente</span>
								<span class="relance-date" title="Dernière modification"
									>{jours}j / {relanceDelaiJours}j</span
								>
							{/if}
						</div>
					</div>
					<div class="relance-item-meta">
						<Badge teinte={TK_STATUT_BADGE[t.statut] ?? 'badge-gray'}
							>{TK_STATUT_LABELS[t.statut] ?? t.statut}</Badge
						>
						<span class="badge badge-gray">{categorieTicketLabel(t.categorie)}</span>
					</div>
				</div>
			{/each}
		</div>

		<div class="form-actions no-print">
			<button
				class="btn btn-primary"
				disabled={relanceSending || relanceSelected.size === 0}
				on:click={envoiRelance}
			>
				{relanceSending
					? '…'
					: `📧 Envoyer la relance (${relanceSelected.size} affaire${relanceSelected.size > 1 ? 's' : ''})`}
			</button>
		</div>
	</section>
{/if}

<style>
	/* ── Relance syndic ───────────────────────────────────────────────── */
	.relance-item {
		background: var(--color-surface);
		border: 1px solid var(--color-border);
		border-left: 4px solid var(--color-primary);
		border-radius: var(--radius);
		padding: 0.65rem 0.9rem;
		transition: opacity var(--duree-geste);
	}
	.relance-item-unselected {
		opacity: 0.5;
		border-left-color: var(--color-border);
	}
	.relance-item-pending {
		border-left-color: var(--color-text-muted);
		background: var(--color-bg-subtle, #f9fafb);
	}
	.relance-item-top {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		flex-wrap: wrap;
	}
	.relance-item-meta {
		display: flex;
		align-items: center;
		gap: 0.4rem;
		flex-wrap: wrap;
		margin-top: 0.4rem;
	}
	.relance-numero {
		font-size: var(--fs-sm);
		font-weight: 700;
		color: var(--color-primary);
		white-space: nowrap;
	}
	.relance-titre {
		font-size: var(--fs-base);
		font-weight: 600;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		min-width: 0;
		flex: 1;
	}
	.relance-item-right {
		display: flex;
		align-items: center;
		gap: 0.4rem;
		margin-left: auto;
		flex-shrink: 0;
	}
	.relance-date {
		font-size: var(--fs-xs);
		color: var(--color-text-muted);
		white-space: nowrap;
	}
	.relance-date-overdue {
		color: var(--color-warning-texte);
		font-weight: 600;
	}

	.rep-titre {
		margin-bottom: 0.35rem;
	}
	.rep-aide {
		font-size: var(--fs-md);
		color: var(--color-text-muted);
		margin-bottom: 0.75rem;
	}
	.rep-carte {
		border: 1px solid var(--color-border);
		border-left: 3px solid var(--color-primary);
		border-radius: 0 var(--radius) var(--radius) 0;
		padding: 0.6rem 0.8rem;
		margin-bottom: 0.6rem;
		background: var(--color-bg);
	}
	.rep-entete {
		display: flex;
		justify-content: space-between;
		align-items: baseline;
		gap: 0.5rem;
		flex-wrap: wrap;
		margin-bottom: 0.3rem;
	}
	.rep-de {
		font-weight: 600;
		font-size: var(--fs-base);
	}
	.rep-quand {
		font-size: var(--fs-sm);
		color: var(--color-text-muted);
	}
	.rep-tickets {
		font-size: var(--fs-sm);
		color: var(--color-text-muted);
		margin-bottom: 0.4rem;
	}
	/*  `pre-wrap` : une réponse de courriel porte ses propres retours à la ligne,
	    et les écraser collerait des paragraphes que le syndic a séparés. */
	.rep-texte {
		white-space: pre-wrap;
		font-size: var(--fs-base);
		margin: 0;
	}
	.carte-espacee {
		margin-bottom: 1.5rem;
	}
	.liste-relances {
		display: flex;
		flex-direction: column;
		gap: 0.75rem;
		margin-bottom: 1.25rem;
	}
	.choix-relance {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		cursor: pointer;
		flex: 1;
		min-width: 0;
	}
</style>
