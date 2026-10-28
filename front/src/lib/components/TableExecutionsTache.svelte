<!--
  Les dernières exécutions d'une tâche planifiée, dépliées sous sa ligne dans
  « Tâches planifiées » (Admin › Maintenance).

  Extrait de `TachesPlanifiees` le 08/10/2026 (#1571) : l'écran frôlait les
  500 lignes, et ses styles en ligne ne pouvaient passer en classes sans le faire
  déborder. La table ne lit que les lignes qu'on lui donne ; les colonnes et le
  motif d'échec viennent de `#lib/taches-colonnes`, comme avant.
-->
<script lang="ts">
	import type { ExecutionTache } from '#lib/api/index.ts';
	import { colonnesVisibles, motifEchec } from '#lib/taches-colonnes.ts';

	export let lignes: ExecutionTache[] = [];
</script>

<div class="table-wrap">
	<table class="table table-executions">
		<thead>
			<tr>
				{#each colonnesVisibles(lignes) as c (c.titre)}
					<th>{c.titre}</th>
				{/each}
			</tr>
		</thead>
		<tbody>
			{#each lignes as l (l)}
				<tr>
					{#each colonnesVisibles(lignes) as c (c.titre)}
						<!--  La condition porte sur le RENDU, pas sur le titre : une colonne
						      sans `valeur` est, par définition, celle dont la cellule est
						      écrite à la main. Tester le libellé aurait marché aussi, mais
						      il aurait suffi de renommer « Statut » pour casser le tableau
						      sans que rien ne lève — et TypeScript l'a refusé, à raison. -->
						{#if !c.valeur}
							<td>
								<span
									class="badge"
									class:badge-red={l.statut === 'erreur' || l.statut === 'echouee'}
									class:badge-green={l.statut !== 'erreur' && l.statut !== 'echouee'}
								>
									{l.statut ?? '—'}
								</span>
								<!--  Le motif de l'échec était porté par la carte supprimée
								      avec #299 : sans lui, un statut « erreur » ne dit pas
								      pourquoi. Sa colonne dépend de la table (`motifEchec`, #1681). -->
								{#if motifEchec(l)}<span title={motifEchec(l)} class="motif-echec">⚠️</span>{/if}
							</td>
						{:else}
							<td style={c.style ?? ''}>{c.valeur(l)}</td>
						{/if}
					{/each}
				</tr>
			{/each}
		</tbody>
	</table>
</div>

<style>
	.table-executions {
		font-size: var(--fs-sm);
		margin: 0.25rem 0;
	}
	.motif-echec {
		margin-left: 0.4rem;
		cursor: help;
	}
</style>
