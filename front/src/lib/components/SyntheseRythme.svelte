<!--
  SyntheseRythme.svelte — M5, le nombre de Suites par semaine (#1643).

  UNE idée, et c'est ce qui l'a rendu lisible : la maquette a été incomprise
  deux fois tant qu'elle superposait une jauge et un histogramme. Une barre par
  semaine depuis l'ouverture ; une semaine sans aucune Suite est « muette », et
  marquée en rouge — « 2 semaines muettes sur 10 ».
-->
<script lang="ts">
	import type { MetriquesSynthese } from '#lib/api/index.ts';
	import { libelleMuettes } from '#lib/synthese.ts';

	export let metriques: MetriquesSynthese;

	$: max = Math.max(1, ...metriques.semaines);
</script>

<figure class="rythme">
	<div class="histogramme" role="img" aria-label="Suites par semaine : {libelleMuettes(metriques)}">
		{#each metriques.semaines as n, i (i)}
			<span
				class="semaine"
				class:muette={n === 0}
				style="height:{n === 0 ? 8 : Math.max(12, (n / max) * 100)}%"
				title="Semaine {i + 1} : {n} suite{n > 1 ? 's' : ''}"
			></span>
		{/each}
	</div>
	<figcaption class="legende">{libelleMuettes(metriques)}</figcaption>
</figure>

<style>
	.rythme {
		margin: 0;
		display: flex;
		flex-direction: column;
		gap: 0.3rem;
	}
	.histogramme {
		display: flex;
		align-items: flex-end;
		gap: 2px;
		height: 3.5rem;
		padding-bottom: 1px;
		border-bottom: 1px solid var(--color-border);
	}
	.semaine {
		flex: 1 1 0;
		min-width: 2px;
		max-width: 1.6rem;
		background: var(--color-primary);
		border-radius: 2px 2px 0 0;
	}
	.semaine.muette {
		background: var(--color-danger);
	}
	.legende {
		font-size: var(--fs-xs);
		color: var(--color-text-muted);
	}
</style>
