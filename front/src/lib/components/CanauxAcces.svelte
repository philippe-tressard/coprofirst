<script lang="ts">
	/**
	 * **Accès : web ou application, par appareil** — les vues de la période par canal d'accès
	 * (site web, app iPhone, plus tard app Android). Demandé le 14/11/2026 :
	 * « c'est important de comprendre comment l'appli est consommée ».
	 *
	 * Un BLOC de la section « Fréquentation », au tableau comme « Qui vient » :
	 * le serveur calcule la part (`part`) et les libellés — l'app iOS montre la
	 * même répartition, elle ne se recalcule pas ici (`standards/09` §8). Les
	 * visiteurs ne s'additionnent pas d'un canal à l'autre ; au-delà des 30 jours
	 * d'évènements (Année, Total), ils ne sont pas connus et la colonne s'efface.
	 *
	 * Chaque canal se DÉPLIE sur ses classes d'appareil (#2774 : téléphone, tablette,
	 * ordinateur ; iPhone, iPad…), dans l'ordre et avec la part — en % du canal —
	 * que sert l'API. Un canal dont aucune vue ne dit son appareil ne se déplie pas.
	 */
	import PanneauTelemetrie from '#lib/components/PanneauTelemetrie.svelte';
	import type { PartCanal } from '#lib/api/index.ts';
	import { basculer } from '#lib/accordeon.ts';
	import { fmtNombre } from '#lib/utils.ts';

	export let canaux: PartCanal[] = [];

	$: avecVisiteurs = canaux.some((c) => c.visiteurs != null);
	$: unSeul = canaux.length === 1 ? canaux[0] : null;

	/** Le canal déplié — un à la fois. */
	let ouvert: string | null = null;
	/** Se déplie-t-il ? Seulement s'il dit au moins un appareil précis. */
	const depliable = (c: PartCanal) => (c.appareils ?? []).some((a) => a.appareil !== 'non_precise');
</script>

{#if canaux.length > 0}
	<PanneauTelemetrie titre="📱 Accès : web ou application, par appareil" niveau="bloc">
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
							<td>
								{#if depliable(c)}
									<button
										type="button"
										class="deplier"
										aria-expanded={ouvert === c.canal}
										aria-controls="appareils-{c.canal}"
										on:click={() => (ouvert = basculer(ouvert, c.canal))}
									>
										<span class="chevron" aria-hidden="true">{ouvert === c.canal ? '▾' : '▸'}</span>
										{c.libelle}
									</button>
								{:else}
									{c.libelle}
								{/if}
							</td>
							<td class="nombre">{fmtNombre(c.vues)}</td>
							<td class="nombre">{fmtNombre(c.part)} %</td>
							{#if avecVisiteurs}
								<td class="nombre">{c.visiteurs == null ? '—' : fmtNombre(c.visiteurs)}</td>
							{/if}
						</tr>
						{#if ouvert === c.canal}
							{#each c.appareils ?? [] as a (a.appareil)}
								<tr
									class="appareil"
									id={a === c.appareils?.[0] ? `appareils-${c.canal}` : undefined}
								>
									<td>{a.libelle}</td>
									<td class="nombre">{fmtNombre(a.vues)}</td>
									<td class="nombre">{fmtNombre(a.part)} % du canal</td>
									{#if avecVisiteurs}<td class="nombre"></td>{/if}
								</tr>
							{/each}
						{/if}
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

<style>
	.deplier {
		display: inline-flex;
		align-items: center;
		gap: 0.4rem;
		min-height: 44px;
		padding: 0 0.25rem;
		margin-left: -0.25rem;
		border: 0;
		border-radius: var(--radius);
		background: none;
		color: inherit;
		font: inherit;
		text-align: left;
		cursor: pointer;
		transition: background-color var(--duree-geste);
	}
	.deplier:active {
		background: var(--color-primary-light);
	}
	@media (hover: hover) and (pointer: fine) {
		.deplier:hover {
			background: var(--color-primary-light);
		}
	}
	.chevron {
		width: 1ch;
		color: var(--color-text-muted);
	}
	.appareil td:first-child {
		padding-left: 2rem;
	}
	.appareil td {
		font-size: var(--fs-sm);
		color: var(--color-text-muted);
	}
</style>
