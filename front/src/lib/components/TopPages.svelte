<script lang="ts">
	/**
	 * Top pages de la télémétrie — tableau et sa ligne de total.
	 *
	 * Extrait de `routes/(app)/admin/+page.svelte` le 13/08/2026 : le total des
	 * vues manquait (signalé par l'utilisateur), et ce fichier dépasse 2 200
	 * lignes — le contrôle de modularité refuse qu'il grossisse. L'étoffer sur
	 * place aurait été refusé au pré-check ; le découper est ce que la règle
	 * « au fil de l'eau » demande.
	 *
	 * Son intitulé passe par `PanneauTelemetrie` depuis le 03/10/2026 :
	 * `.titre-panneau`, écrit ici, était la copie au caractère près de l'intitulé
	 * des autres panneaux. Un BLOC de la section « Fréquentation », pas une
	 * section : l'onglet regroupe graphe, top pages et utilisateurs actifs.
	 */
	import PanneauTelemetrie from '#lib/components/PanneauTelemetrie.svelte';
	import { fmtNombre, fmtPartEnPourcent } from '#lib/utils.ts';
	import { SEPARATEUR } from '#lib/separateurs.ts';

	export let pages: { page: string; total: number; uniques: number }[] = [];

	/** Vues comptées ici mais rattachées à aucun utilisateur (#354).
	    Ce tableau compte TOUTES les vues ; celui des utilisateurs n'en retient que
	    les attribuables. Deux nombres côte à côte sur un même écran engagent une
	    promesse de cohérence : quand ils diffèrent, l'écran doit le dire — c'est
	    plus important que la cause. */
	export let vuesNonAttribuees = 0;

	//  Calculé UNE fois. Il l'était à l'intérieur de la boucle, donc recalculé
	//  pour chaque ligne : sans effet visible, mais quadratique.
	$: totalVues = pages.reduce((s, p) => s + p.total, 0);
	//  Le `|| 1` protège la division, jamais l'affichage : un total de 0 doit
	//  s'afficher 0, pas 1 (`standards/04` : ne pas présenter une valeur de repli
	//  comme une mesure).
	$: diviseur = totalVues || 1;
</script>

{#if pages.length > 0}
	<PanneauTelemetrie titre="🏆 Top pages" niveau="bloc">
		<div class="table-wrap">
			<table class="table">
				<thead>
					<tr>
						<th>Page</th>
						<th class="num">Vues</th>
						<th class="num">Utilisateurs</th>
						<th class="num">%</th>
					</tr>
				</thead>
				<tbody>
					{#each pages as p (p.page)}
						<tr>
							<td><code class="chemin">{p.page}</code></td>
							<td class="num-fort">{fmtNombre(p.total)}</td>
							<td class="num-attenue">{fmtNombre(p.uniques)}</td>
							<td class="num-attenue">{fmtPartEnPourcent(p.total, diviseur, 1)}</td>
						</tr>
					{/each}
				</tbody>
				<tfoot>
					<tr class="total">
						<td
							>Total{SEPARATEUR.tiret}{fmtNombre(pages.length)} page{pages.length > 1
								? 's'
								: ''}</td
						>
						<td class="num">{fmtNombre(totalVues)}</td>
						<td class="num-attenue">
							<!--  Additionner la colonne serait FAUX : un même utilisateur compte
						      dans chaque page qu'il a vue, et la somme dirait « 17 personnes »
						      là où il n'y en a qu'une. Le nombre réel d'utilisateurs distincts
						      est celui de l'indicateur en tête d'écran. -->
							<span
								title="La somme des utilisateurs par page compterait plusieurs fois la même personne. Le nombre d'utilisateurs distincts est donné par l'indicateur « Utilisateurs » en haut de cette page."
								>—</span
							>
						</td>
						<td class="num-attenue">
							{fmtPartEnPourcent(totalVues, totalVues, 1)}
						</td>
					</tr>
				</tfoot>
			</table>
		</div>
		<svelte:fragment slot="pied">
			{#if vuesNonAttribuees > 0}
				<p>
					Dont <strong>{fmtNombre(vuesNonAttribuees)}</strong> vue{vuesNonAttribuees > 1 ? 's' : ''}
					non rattachée{vuesNonAttribuees > 1 ? 's' : ''} à un utilisateur{SEPARATEUR.tiret}enregistrée{vuesNonAttribuees >
					1
						? 's'
						: ''}
					avant l'ouverture de la session ou après son expiration. C'est ce qui explique l'écart avec
					le tableau « Utilisateurs les plus actifs ».
				</p>
			{/if}
			<p>
				Les pourcentages se rapportent aux vues des pages listées ci-dessus, pas au total du site.
			</p>
		</svelte:fragment>
	</PanneauTelemetrie>
{/if}

<style>
	tfoot tr.total > td {
		border-top: 2px solid var(--color-border);
		font-weight: 700;
		padding-top: 0.5rem;
	}
	.num {
		text-align: right;
	}
	.chemin {
		font-size: var(--fs-md);
	}
	.num-fort {
		text-align: right;
		font-weight: 600;
	}
	.num-attenue {
		text-align: right;
		color: var(--color-text-muted);
	}
</style>
