<!--
  L'historique des derniers e-mails envoyés, sous les modèles d'e-mail de
  l'administration.

  Extrait d'`OngletModelesEmail` le 08/10/2026 (#1571) : l'onglet frôlait les
  500 lignes, et ses styles en ligne ne pouvaient passer en classes sans le faire
  déborder. Le bloc ne lit que ce que l'onglet a chargé — la liste, son état —,
  et n'écrit rien.
-->
<script lang="ts">
	import type { EnvoiEmail } from '#lib/api/index.ts';
	import { fmtDatetimeShort as fmt } from '#lib/date.ts';
	import EtatListe from '#lib/components/EtatListe.svelte';

	export let historique: EnvoiEmail[] = [];
	export let chargement = true;
	/** Non vide = la liste n'a pas pu être lue : elle ne se dit pas vide. */
	export let erreur = '';
</script>

<hr class="separateur-section" />
<h3 class="titre-historique">📬 Historique des envois</h3>
<p class="muted intro-historique">
	10 derniers emails envoyés (ou tentatives). Purgé automatiquement après 90 jours.
</p>
{#if chargement || erreur || historique.length === 0}
	<EtatListe
		{chargement}
		{erreur}
		vide={historique.length === 0}
		titreErreur="Impossible d’afficher l’historique d’envoi"
		titreVide="Aucun e-mail envoyé"
		messageVide="L'historique est vide."
	/>
{:else}
	<div class="card carte-historique">
		<table class="table table-historique">
			<thead class="sticky-head"
				><tr><th>Date</th><th>Template</th><th>Destinataire</th><th>Sujet</th><th>Statut</th></tr
				></thead
			>
			<tbody>
				{#each historique as h (h.id)}
					<tr>
						<td class="date-envoi">{fmt(h.cree_le)}</td>
						<td><code class="code-modele">{h.code}</code></td>
						<td class="destinataire" title={h.destinataire}>{h.destinataire}</td>
						<td class="sujet" title={h.sujet}>{h.sujet || '—'}</td>
						<td>
							{#if h.statut === 'succes'}<span class="badge badge-green">✓</span>
							{:else if h.statut === 'erreur'}<span class="badge badge-red" title={h.erreur ?? ''}
									>✗</span
								>
							{:else}<span class="badge badge-gray" title={h.erreur ?? ''}>ignoré</span>{/if}
						</td>
					</tr>
				{/each}
			</tbody>
		</table>
	</div>
{/if}

<style>
	.titre-historique {
		font-size: var(--fs-xl);
		font-weight: 700;
		margin-bottom: 0.75rem;
	}
	.intro-historique {
		font-size: var(--fs-md);
		margin-bottom: 0.75rem;
	}
	.carte-historique {
		overflow: auto;
		max-height: 420px;
	}
	.table-historique {
		font-size: var(--fs-md);
	}
	.date-envoi {
		white-space: nowrap;
	}
	.code-modele {
		font-size: var(--fs-xs);
	}
	.destinataire {
		max-width: 180px;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.sujet {
		max-width: 200px;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
</style>
