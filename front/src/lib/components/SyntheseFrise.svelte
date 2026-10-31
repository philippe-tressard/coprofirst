<!--
  SyntheseFrise.svelte — M1, le temps passé à chaque étape (#1643).

  Une barre segmentée en jours ouvrés : l'étape la plus longue en couleur, les
  autres en gris, et un segment final coloré selon l'issue — résolue ou
  annulée. L'étape « À l'AG » n'y paraît que si l'affaire y est passée : c'est
  le serveur qui ne l'envoie pas autrement.
-->
<script lang="ts">
	import type { MetriquesSynthese } from '#lib/api/index.ts';
	import { fmtJours, libelleEtape, libelleIssue, segmentsFrise } from '#lib/synthese.ts';
	import { SEPARATEUR } from '#lib/separateurs.ts';

	export let metriques: MetriquesSynthese;

	$: segments = segmentsFrise(metriques);
	$: resume = segments.map((s) => `${libelleEtape(s.statut)} ${fmtJours(s.jours)}`).join(', ');
</script>

<figure class="frise">
	<div
		class="barre"
		role="img"
		aria-label="Temps par étape : {resume}, puis affaire {libelleIssue(metriques.issue)}"
	>
		{#each segments as s (s.statut)}
			<span
				class="segment"
				class:longue={s.statut === metriques.etape_plus_longue}
				style="flex-grow:{s.part}"
			></span>
		{/each}
		<span class="segment issue" class:annulee={metriques.issue === 'annulé'}></span>
	</div>
	<figcaption class="graphique-legende">
		{#each segments as s (s.statut)}
			<span class="graphique-cle" class:longue={s.statut === metriques.etape_plus_longue}>
				<span class="graphique-pastille" aria-hidden="true"></span>
				{libelleEtape(s.statut)}{SEPARATEUR.point}{fmtJours(s.jours)}
			</span>
		{/each}
		<span class="graphique-cle issue" class:annulee={metriques.issue === 'annulé'}>
			<span class="graphique-pastille" aria-hidden="true"></span>
			{libelleIssue(metriques.issue)}
		</span>
	</figcaption>
</figure>

<style>
	.frise {
		margin: 0;
		display: flex;
		flex-direction: column;
		gap: 0.4rem;
	}
	.barre {
		display: flex;
		gap: 2px;
		height: 1.1rem;
		border-radius: var(--radius);
		overflow: hidden;
	}
	.segment {
		flex: 1 1 0;
		min-width: 0.4rem;
		background: var(--color-border);
	}
	.segment.longue,
	.graphique-cle.longue .graphique-pastille {
		background: var(--color-primary);
	}
	.segment.issue {
		flex: 0 0 0.6rem;
	}
	.segment.issue,
	.graphique-cle.issue .graphique-pastille {
		background: var(--color-success);
	}
	.segment.issue.annulee,
	.graphique-cle.issue.annulee .graphique-pastille {
		background: var(--color-danger);
	}
	.graphique-cle.longue {
		color: var(--color-text);
		font-weight: 600;
	}
</style>
