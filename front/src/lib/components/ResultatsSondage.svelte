<!--
  Les résultats d'un sondage — une barre par réponse, et les réponses libres.

  Extrait de `routes/(app)/sondages/[id]/+page.svelte` le 28/09/2026 (#1329) :
  la page faisait 510 lignes et portait dix-sept attributs `style`. Le bloc
  part avec ses règles, à l'identique. Le TOTAL est calculé par la page, qui
  l'affiche aussi (« 12 votes ») : le recalculer ici en ferait deux écritures.

  Masqués jusqu'à la clôture, les résultats ne sont pas des barres vides : l'API
  n'envoie pas les décomptes, et un « 0 vote » se lirait « personne n'a voté ».
-->
<script lang="ts">
	import { fmtNombre } from '#lib/utils.ts';
	export let options: {
		id: number;
		libelle: string;
		champ_libre?: boolean;
		nb_votes?: number;
		reponses_libres?: string[];
	}[] = [];
	export let monVote: number | null = null;
	export let total = 0;
	export let visibles = false;

	function pct(nb: number) {
		if (total === 0) return 0;
		return Math.round((nb / total) * 100);
	}
</script>

{#if !visibles}
	<p class="resultats-masques">
		Les résultats de ce sondage ne seront visibles qu'après sa clôture.
	</p>
{:else}
	{#each options as opt (opt.id)}
		<div class="result-row" class:winner={opt.id === monVote}>
			<div class="result-label">
				{opt.libelle}
				{#if opt.champ_libre}<span class="champ-libre-badge" title="Champ de précision">✏️</span
					>{/if}
				{#if opt.id === monVote}<span class="badge badge-blue mon-vote">Mon vote ✓</span>{/if}
			</div>
			<div class="result-bar-wrap">
				<div class="result-bar" style="width:{pct(opt.nb_votes ?? 0)}%"></div>
			</div>
			<div class="result-pct">{pct(opt.nb_votes ?? 0)} %</div>
			<div class="result-votes">{fmtNombre(opt.nb_votes)}</div>
		</div>
		{#if opt.champ_libre && opt.reponses_libres?.length}
			<div class="reponses-libres-list">
				{#each opt.reponses_libres as rep, ri (`${ri}|${rep}`)}
					<blockquote class="reponse-libre-item">«&nbsp;{rep}&nbsp;»</blockquote>
				{/each}
			</div>
		{/if}
	{/each}
{/if}

<style>
	.result-row {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		margin-bottom: 0.6rem;
	}
	.result-label {
		min-width: 10rem;
		font-size: var(--fs-base);
	}
	.mon-vote {
		margin-left: 0.5rem;
	}
	.result-bar-wrap {
		flex: 1;
		height: 0.7rem;
		background: var(--color-bg);
		border-radius: 99px;
		overflow: hidden;
		border: 1px solid var(--color-border);
	}
	.result-bar {
		height: 100%;
		background: var(--color-primary);
		border-radius: 99px;
		transition: width var(--duree-apparition) var(--ease-out);
	}
	.result-pct {
		min-width: 3rem;
		text-align: right;
		font-size: var(--fs-md);
		font-weight: 600;
	}
	.result-votes {
		min-width: 3rem;
		text-align: right;
		font-size: var(--fs-sm);
		color: var(--color-text-muted);
	}
	.resultats-masques {
		font-size: var(--fs-base);
		color: var(--color-text-muted);
		background: var(--color-bg);
		border-radius: var(--radius);
		padding: 0.75rem 1rem;
		margin: 0;
	}
	.winner .result-bar {
		background: var(--color-success);
	}
	.reponses-libres-list {
		padding: 0.35rem 0 0.6rem 1rem;
	}
	.reponse-libre-item {
		margin: 0.25rem 0;
		padding: 0.3rem 0.6rem;
		border-left: 3px solid var(--color-primary);
		font-size: var(--fs-md);
		color: var(--color-text-muted);
		font-style: italic;
	}
</style>
