<script lang="ts">
	/**
	 * **Accès : site ou application** — les vues de la période par canal d'accès
	 * (site web, app iPhone, plus tard app Android). Demandé le 14/11/2026 :
	 * « c'est important de comprendre comment l'appli est consommée ».
	 *
	 * Un BLOC de la section « Fréquentation », au tableau comme « Qui vient » :
	 * le serveur calcule la part (`part`) et les libellés — l'app iOS montre la
	 * même répartition, elle ne se recalcule pas ici (`standards/09` §8). Les
	 * visiteurs ne s'additionnent pas d'un canal à l'autre ; au-delà des 30 jours
	 * d'évènements (Année, Total), ils ne sont pas connus et la colonne s'efface.
	 */
	import PanneauTelemetrie from '#lib/components/PanneauTelemetrie.svelte';
	import type { PartCanal } from '#lib/api/index.ts';
	import { fmtNombre } from '#lib/utils.ts';

	export let canaux: PartCanal[] = [];

	$: avecVisiteurs = canaux.some((c) => c.visiteurs != null);
	$: unSeul = canaux.length === 1 ? canaux[0] : null;
</script>

{#if canaux.length > 0}
	<PanneauTelemetrie titre="📱 Accès : site ou application" niveau="bloc">
		<div class="table-wrap">
			<table class="table">
				<thead>
					<tr>
						<th>Accès</th>
						<th class="nombre">Vues</th>
						<th class="nombre">%</th>
						{#if avecVisiteurs}<th class="nombre">Utilisateurs</th>{/if}
					</tr>
				</thead>
				<tbody>
					{#each canaux as c (c.canal)}
						<tr>
							<td>{c.libelle}</td>
							<td class="nombre">{fmtNombre(c.vues)}</td>
							<td class="nombre">{fmtNombre(c.part)} %</td>
							{#if avecVisiteurs}
								<td class="nombre">{c.visiteurs == null ? '—' : fmtNombre(c.visiteurs)}</td>
							{/if}
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
		<svelte:fragment slot="pied">
			{#if unSeul}
				<p>
					Toutes les vues de la période viennent de : {unSeul.libelle}. L’application ne compte ses
					pages vues que depuis la version qui les envoie.
				</p>
			{:else if avecVisiteurs}
				<p>
					Un utilisateur qui passe par le site et par l’application compte dans les deux lignes : la
					colonne « Utilisateurs » ne s’additionne pas.
				</p>
			{/if}
		</svelte:fragment>
	</PanneauTelemetrie>
{/if}
