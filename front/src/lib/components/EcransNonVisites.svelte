<script lang="ts">
	/**
	 * **Écrans non visités** — le pendant des « Top pages » (#1630) : ce que
	 * PERSONNE n'a ouvert sur la période, pour décider quoi simplifier, regrouper
	 * ou retirer.
	 *
	 * La liste des écrans est celle de `pages.ts` (la table unique), soustraite des
	 * pages vues que le serveur rend déjà (`top_pages`, non bornée) : aucune liste
	 * recopiée côté API, le front et l'API ne partageant aucun fichier. La
	 * comparaison est dans `#lib/ecrans-non-visites`, éprouvée par
	 * `npm run lint:ecrans-non-visites`.
	 *
	 * Un bloc de la section « Fréquentation » (comme `TopPages`), montré sur les
	 * vues **Mois** et **Année** seulement : sur une journée, presque tout écran est
	 * « non visité », et la liste ne dirait rien.
	 */
	import { fmtNombre } from '#lib/utils.ts';
	import PanneauTelemetrie from '#lib/components/PanneauTelemetrie.svelte';
	import { PAGES } from '#lib/pages.ts';
	import { PAGES_ROLES } from '#lib/pages-roles.ts';
	import { ecransDeclares, ecransNonVisites } from '#lib/ecrans-non-visites.ts';

	export let pages: { page: string; total: number; uniques: number }[] = [];
	/** « 30 derniers jours », « 12 derniers mois » : ce que couvrent les pages vues. */
	export let periode = '';

	//  La table ne change pas pendant la visite : l'aplatir une fois.
	const declares = ecransDeclares(PAGES, new Set(PAGES_ROLES.map((p) => p.id)));

	$: bilan = ecransNonVisites(declares, pages);
</script>

<!--  Aucune page vue : la période est vide, et ce serait lister TOUT le site
      comme « mort » — une absence de mesure lue comme une mesure. -->
{#if pages.length > 0}
	<PanneauTelemetrie titre="💤 Écrans non visités" {periode} niveau="bloc">
		{#if bilan.nonVisites.length === 0}
			<p class="resume">
				Les {fmtNombre(bilan.total)} écrans du site ont tous été ouverts sur la période.
			</p>
		{:else}
			<p class="resume">
				<strong>{bilan.nonVisites.length}</strong> écran{bilan.nonVisites.length > 1 ? 's' : ''}
				sur {fmtNombre(bilan.total)} n’{bilan.nonVisites.length > 1 ? 'ont' : 'a'} reçu aucune visite.
			</p>
			<div class="table-wrap">
				<table class="table">
					<thead>
						<tr><th>Écran</th><th>Adresse</th></tr>
					</thead>
					<tbody>
						{#each bilan.nonVisites as e (e.route)}
							<tr>
								<td>
									{e.libelle}
									{#if e.reserve}
										<span
											class="badge badge-gray"
											title="Cet écran n’est pas ouvert à tous les profils (conseil syndical, administrateur, propriétaire, non-locataire) : moins de comptes le voient, il n’est pas mort pour autant."
											>Réservé</span
										>
									{/if}
								</td>
								<td><code>{e.route}</code></td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		{/if}
		<svelte:fragment slot="pied">
			<p>
				L’administration compte pour un seul écran : ses onglets ne se distinguent pas dans la
				mesure. Un écran de détail (une affaire, un sondage) n’est pas dans cette liste.
			</p>
		</svelte:fragment>
	</PanneauTelemetrie>
{/if}

<style>
	.resume {
		margin: 0 1rem 0.75rem;
		color: var(--color-text-muted);
	}
</style>
