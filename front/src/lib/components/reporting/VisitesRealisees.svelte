<!--
  Les VISITES RÉALISÉES de l'année, dans le mode « Suivi entretiens
  périodiques », avant le point CS / Syndic (17/10/2026).

  Le tableau du mode ne montre que les entretiens NON clos : une visite faite
  n'y paraît plus, et le bilan au-dessus ne disait que leur nombre. Elles se
  listent ici, la plus récente en tête — date de réalisation, affaire,
  prestataire.

  Les visites viennent du bilan (`BilanVisites`, lié par le parent) : un seul
  appel à `GET /tickets/entretiens-periodiques`, et l'état « réalisée » est
  CALCULÉ au serveur (`utils/entretien_periodique.etat_visite`) — l'écran ne
  fait que le filtrer. Aucune réalisée : la section se tait, le compteur du
  bilan dit déjà 0.
-->
<script lang="ts">
	import type { VisitePeriodique } from '#lib/api/index.ts';
	import { fmtDate } from '#lib/date.ts';
	import { lienTicket } from '#lib/tickets.ts';

	export let visites: VisitePeriodique[];

	$: realisees = visites
		.filter((v) => v.etat === 'realisee')
		.sort((a, b) => (b.ferme_le ?? '').localeCompare(a.ferme_le ?? ''));
</script>

{#if realisees.length > 0}
	<section class="report-card" aria-labelledby="titre-visites-realisees">
		<h3 id="titre-visites-realisees">✅ Visites réalisées</h3>
		<div class="report-table-wrap">
			<table class="report-table compact">
				<thead>
					<tr><th>Réalisée le</th><th>Affaire</th><th>Prestataire</th></tr>
				</thead>
				<tbody>
					{#each realisees as v (v.id)}
						<tr>
							<td class="date">{v.ferme_le ? fmtDate(v.ferme_le) : '—'}</td>
							<td>
								<a href={lienTicket(v.id)} class="affaire">
									<span class="numero">{v.numero}</span>
									{v.titre}
								</a>
							</td>
							<td>
								{v.prestataire_nom ?? '—'}
								{#if v.contrat_libelle}<span class="contrat">{v.contrat_libelle}</span>{/if}
							</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
	</section>
{/if}

<style>
	.date {
		white-space: nowrap;
	}
	.affaire {
		color: inherit;
		text-decoration: none;
	}
	.numero {
		font-weight: 700;
		color: var(--color-primary);
		margin-right: 0.35rem;
		white-space: nowrap;
	}
	.contrat {
		display: block;
		font-size: var(--fs-xs);
		color: var(--color-text-muted);
	}
	@media (hover: hover) and (pointer: fine) {
		.affaire:hover {
			color: var(--color-primary);
		}
	}
</style>
