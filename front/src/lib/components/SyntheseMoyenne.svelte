<!--
  SyntheseMoyenne.svelte — M4, l'affaire face à la moyenne de l'exercice (#1643).

  Des barres doubles — l'affaire, la moyenne — pour la durée totale, la
  première réponse du syndic, les relances et les Suites. La moyenne est celle
  des autres affaires closes de même catégorie sur l'exercice comptable qui
  contient la clôture ; sous trois affaires, le serveur ne l'envoie pas, et ce
  composant ne rend rien.
-->
<script lang="ts">
	import type { ComparaisonSynthese, MetriquesSynthese } from '#lib/api/index.ts';
	import { fmtNombre } from '#lib/utils.ts';
	import { fmtJours, nomCategorie, partBarre } from '#lib/synthese.ts';

	export let metriques: MetriquesSynthese;

	$: comparaison = metriques.comparaison as ComparaisonSynthese | null;
	$: lignes = comparaison
		? [
				{
					libelle: 'Durée totale',
					affaire: metriques.duree_totale,
					moyenne: comparaison.duree_totale,
					format: fmtJours,
				},
				{
					libelle: '1ʳᵉ réponse du syndic',
					affaire: metriques.premiere_reponse_syndic,
					moyenne: comparaison.premiere_reponse_syndic,
					format: fmtJours,
				},
				{
					libelle: 'Relances',
					affaire: metriques.relances,
					moyenne: comparaison.relances,
					format: fmtNombre,
				},
				{
					libelle: 'Suites',
					affaire: metriques.suites,
					moyenne: comparaison.suites,
					format: fmtNombre,
				},
			]
		: [];
</script>

{#if comparaison}
	<figure class="moyenne">
		<dl class="lignes">
			{#each lignes as l (l.libelle)}
				<dt>{l.libelle}</dt>
				<dd>
					<span class="rang">
						<span class="barre affaire" style="width:{partBarre(l.affaire, l.moyenne)}%"></span>
						<span class="valeur">{l.format(l.affaire)}</span>
					</span>
					<span class="rang">
						<span class="barre moyenne-barre" style="width:{partBarre(l.moyenne, l.affaire)}%"
						></span>
						<span class="valeur">{l.format(l.moyenne)}</span>
					</span>
				</dd>
			{/each}
		</dl>
		<figcaption class="graphique-legende">
			<span class="graphique-cle"
				><span class="graphique-pastille affaire" aria-hidden="true"></span>cette affaire</span
			>
			<span class="graphique-cle"
				><span class="graphique-pastille moyenne-barre" aria-hidden="true"></span>moyenne des {comparaison.nombre}
				affaires « {nomCategorie(comparaison.categorie)} » closes de l'exercice {comparaison.exercice}</span
			>
		</figcaption>
	</figure>
{/if}

<style>
	.moyenne {
		margin: 0;
		display: flex;
		flex-direction: column;
		gap: 0.4rem;
	}
	.lignes {
		display: grid;
		grid-template-columns: 9rem minmax(0, 1fr);
		gap: 0.35rem 0.6rem;
		margin: 0;
		align-items: center;
	}
	dt {
		font-size: var(--fs-sm);
		color: var(--color-text-muted);
	}
	dd {
		margin: 0;
		display: flex;
		flex-direction: column;
		gap: 2px;
	}
	.rang {
		display: flex;
		align-items: center;
		gap: 0.4rem;
	}
	.barre {
		height: 0.55rem;
		border-radius: 2px;
	}
	.affaire {
		background: var(--color-primary);
	}
	.moyenne-barre {
		background: var(--color-border);
	}
	.valeur {
		font-size: var(--fs-xs);
		color: var(--color-text);
		font-variant-numeric: tabular-nums;
		white-space: nowrap;
	}
	@media (max-width: 480px) {
		.lignes {
			grid-template-columns: minmax(0, 1fr);
		}
	}
</style>
