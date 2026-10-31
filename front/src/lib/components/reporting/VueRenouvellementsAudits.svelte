<!--
  Reporting CS — les DIAGNOSTICS et contrôles réglementaires, rangés par année.

  Extrait de `VueRenouvellements.svelte` le 27/08/2026 (#453), avec la frise des
  contrats. Les deux sections ne partageaient que la carte qui les entoure.

  ⚠️ Les règles `.audit-year-*` ne servent qu'ici et voyagent avec ce balisage,
  variante d'impression comprise.
-->
<script lang="ts">
	import { fmtDate } from '#lib/date.ts';
	import { relire } from '#lib/utils.ts';
	import { anneeCourante, diagnosticsAvecEcheance, type DiagType } from '#lib/reporting.ts';
	import { SEPARATEUR } from '#lib/separateurs.ts';

	export let reportDiagTypes: DiagType[] = [];

	//  Relue à chaque recalcul, pour la même raison que la frise : un onglet resté
	//  ouvert la nuit du réveillon rangerait les audits sous l'année passée.
	$: ANNEE_COURANTE = relire(reportDiagTypes, anneeCourante);

	//  Dérivation partagée avec le parent, qui en compte les urgences.
	$: diagsAvecNext = diagnosticsAvecEcheance(reportDiagTypes);

	$: diagsAvecEcheance = diagsAvecNext.filter((d) => d.nextDate !== null);
	$: diagsSansEcheance = diagsAvecNext.filter((d) => d.nextDate === null && !d.isPermanent);
	$: diagsPermanents = diagsAvecNext.filter((d) => d.isPermanent);

	$: diagsParAnnee = (() => {
		const map = new Map<number, typeof diagsAvecEcheance>();
		for (const d of diagsAvecEcheance) {
			const y = d.nextDate!.getFullYear();
			if (y < ANNEE_COURANTE || y > ANNEE_COURANTE + 10) continue;
			if (!map.has(y)) map.set(y, []);
			map.get(y)!.push(d);
		}
		return [...map.entries()].sort((a, b) => a[0] - b[0]);
	})();
</script>

<!-- Section 2 : Diagnostics et Contrôles Réglementaires -->
<section class="report-card">
	<h3>
		🔍 Diagnostics et Contrôles Réglementaires{SEPARATEUR.tiret}{ANNEE_COURANTE}–{ANNEE_COURANTE +
			10}
	</h3>
	<p class="report-intro">
		Échéances issues de Résidence / Diagnostics et Contrôles Réglementaires, calculées depuis le
		dernier rapport + fréquence légale.
	</p>

	{#if diagsAvecNext.length === 0}
		<div class="empty-state">
			<h3>Aucun diagnostic applicable</h3>
			<p>Tous les diagnostics sont non applicables.</p>
		</div>
	{:else}
		<!-- Grille par année -->
		{#each diagsParAnnee as [annee, diags] (annee)}
			<div class="audit-year-group" class:audit-year-current={annee === ANNEE_COURANTE}>
				<h4 class="audit-year-title">
					{annee}
					<span
						class="badge"
						class:badge-orange={annee === ANNEE_COURANTE}
						class:badge-blue={annee !== ANNEE_COURANTE}
						>{diags.length} audit{diags.length > 1 ? 's' : ''}</span
					>
				</h4>
				<div class="report-table-wrap">
					<table class="report-table compact">
						<thead>
							<tr
								><th>Diagnostic</th><th>Code</th><th>Fréquence</th><th>Dernier rapport</th><th
									>Prochaine échéance</th
								><th>Statut</th></tr
							>
						</thead>
						<tbody>
							{#each diags as d (d.id)}
								<tr>
									<td><strong>{d.nom}</strong></td>
									<td>{d.code}</td>
									<td>{d.frequence ?? 'N/A'}</td>
									<td>{d.lastRapportDate ? fmtDate(d.lastRapportDate) : 'N/A'}</td>
									<td>{d.nextDate ? fmtDate(d.nextDate.toISOString()) : 'N/A'}</td>
									<td>
										{#if d.urgence === 'depasse'}<span class="badge badge-red">Dépassé</span>
										{:else if d.urgence === 'annee'}<span class="badge badge-orange"
												>À faire en {ANNEE_COURANTE}</span
											>
										{:else}<span class="badge badge-blue">{annee}</span>
										{/if}
									</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
			</div>
		{/each}

		<!-- Diagnostics permanents -->
		{#if diagsPermanents.length > 0}
			<div class="audit-year-group groupe-suivant">
				<h4 class="audit-year-title">
					Permanent
					<span class="badge badge-blue">{diagsPermanents.length}</span>
				</h4>
				<p class="report-intro">Diagnostics à validité permanente (sauf si révision nécessaire).</p>
				<div class="report-table-wrap">
					<table class="report-table compact">
						<thead>
							<tr
								><th>Diagnostic</th><th>Code</th><th>Fréquence</th><th>Dernier rapport</th><th
									>Statut</th
								></tr
							>
						</thead>
						<tbody>
							{#each diagsPermanents as d (d.id)}
								<tr>
									<td><strong>{d.nom}</strong></td>
									<td>{d.code}</td>
									<td>{d.frequence ?? 'N/A'}</td>
									<td>{d.lastRapportDate ? fmtDate(d.lastRapportDate) : 'N/A'}</td>
									<td><span class="badge badge-green">✓ Permanent</span></td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
			</div>
		{/if}

		<!-- Diagnostics sans échéance calculable -->
		{#if diagsSansEcheance.length > 0}
			<div class="audit-year-group groupe-suivant">
				<h4 class="audit-year-title">
					Sans échéance calculable
					<span class="badge badge-gray">{diagsSansEcheance.length}</span>
				</h4>
				<p class="report-intro">Diagnostics sans rapport initial ou sans fréquence définie.</p>
				<div class="report-table-wrap">
					<table class="report-table compact">
						<thead>
							<tr
								><th>Diagnostic</th><th>Code</th><th>Fréquence</th><th>Dernier rapport</th><th
									>Statut</th
								></tr
							>
						</thead>
						<tbody>
							{#each diagsSansEcheance as d (d.id)}
								<tr>
									<td><strong>{d.nom}</strong></td>
									<td>{d.code}</td>
									<td>{d.frequence ?? 'N/A'}</td>
									<td>{d.lastRapportDate ? fmtDate(d.lastRapportDate) : 'N/A'}</td>
									<td>
										{#if d.rapports.length === 0}<span class="badge badge-gray">Aucun rapport</span>
										{:else}<span class="badge badge-gray">À planifier</span>
										{/if}
									</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
			</div>
		{/if}
	{/if}
</section>

<style>
	/* ── Renouvellements : audits par année ───────────────────────── */
	.audit-year-group {
		margin-bottom: 1.2rem;
	}
	.audit-year-group:last-child {
		margin-bottom: 0;
	}
	.audit-year-title {
		font-size: var(--fs-lg);
		font-weight: 700;
		margin: 0 0 0.5rem;
		display: flex;
		align-items: center;
		gap: 0.5rem;
	}
	.audit-year-current {
		border-left: 3px solid var(--color-warning);
		padding-left: 0.75rem;
	}

	@media print {
		.audit-year-group {
			break-inside: auto;
		}
		.audit-year-title {
			break-after: avoid;
		}
		.report-table {
			break-inside: auto;
		}
		.report-table tr {
			break-inside: avoid;
		}
	}
	.groupe-suivant {
		margin-top: 1rem;
	}
</style>
