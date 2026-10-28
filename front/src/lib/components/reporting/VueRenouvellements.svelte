<!--
  Reporting CS — renouvellement des contrats et audits réglementaires.

  ## Ce que ce fichier est devenu (27/08/2026, #453)

  Il portait 456 lignes — 700 une fois reformaté, donc largement au-dessus du
  seuil de modularité (rang 1) — et DEUX sections indépendantes qui ne
  partageaient que la carte qui les entoure. Chacune est sortie avec ses styles :

    VueRenouvellementsContrats.svelte   la frise des échéances de l'année
    VueRenouvellementsAudits.svelte     les diagnostics rangés par année

  Il ne reste ici que ce qui les CHEVAUCHE réellement : les trois compteurs du
  bandeau, qui lisent les deux jeux de données à la fois. C'est la seule raison
  pour laquelle ce composant existe encore.

  ⚠️ Les dérivations (`contratsAvecEcheance`, `diagnosticsAvecEcheance`) vivent
  dans `#lib/reporting.ts` et non ici : ce fichier ET ses deux enfants en ont
  besoin. Les recopier aurait rendu le découpage plus coûteux que le fichier
  unique — un découpage qui duplique n'est pas un découpage.
-->
<script lang="ts">
	import VueRenouvellementsContrats from './VueRenouvellementsContrats.svelte';
	import { relire } from '#lib/utils.ts';
	import VueRenouvellementsAudits from './VueRenouvellementsAudits.svelte';
	import {
		anneeCourante,
		contratsAvecEcheance,
		diagnosticsAvecEcheance,
		type DiagType,
		type ReportContrat,
		type ReportPrestataire,
	} from '#lib/reporting.ts';

	export let reportContrats: ReportContrat[] = [];
	export let reportPrestataires: ReportPrestataire[] = [];
	export let reportDiagTypes: DiagType[] = [];
	/** Note moyenne et nombre d'avis par prestataire, calculés une fois en amont. */
	export let reportNoteMoyParPrest: Map<number, { moy: number; nb: number }> = new Map();

	$: ANNEE_COURANTE = relire(reportContrats, anneeCourante);

	$: contratsAvecFin = contratsAvecEcheance(
		reportContrats,
		reportPrestataires,
		reportNoteMoyParPrest,
	);
	$: diagsAvecNext = diagnosticsAvecEcheance(reportDiagTypes);

	$: renKpiContrats = contratsAvecFin.filter((c) => {
		if (!c.dateFin) return false;
		if (c.dateFin.getFullYear() === ANNEE_COURANTE) return true;
		if (c.datePreavis && c.datePreavis.getFullYear() === ANNEE_COURANTE) return true;
		return false;
	}).length;
	$: renKpiPreavis = contratsAvecFin.filter(
		(c) => c.urgence === 'preavis' || c.urgence === 'inconnu',
	).length;
	$: renKpiDiags = diagsAvecNext.filter(
		(d) => d.urgence === 'depasse' || d.urgence === 'annee' || d.urgence === 'inconnu',
	).length;
</script>

<!-- ── Renouvellement contrats & audits ──────────────────────────── -->
<div class="kpi-row kpi-espaces">
	<div class="kpi-card" class:kpi-alert={renKpiPreavis > 0}>
		<div class="kpi-value">{renKpiPreavis}</div>
		<div class="kpi-label">Contrats en préavis</div>
	</div>
	<div class="kpi-card">
		<div class="kpi-value">{renKpiContrats}</div>
		<div class="kpi-label">Échéances contrats en {ANNEE_COURANTE}</div>
	</div>
	<div class="kpi-card" class:kpi-alert={renKpiDiags > 0}>
		<div class="kpi-value">{renKpiDiags}</div>
		<div class="kpi-label">Audits à (re)planifier</div>
	</div>
</div>

<VueRenouvellementsContrats {reportContrats} {reportPrestataires} {reportNoteMoyParPrest} />

<VueRenouvellementsAudits {reportDiagTypes} />

<style>
	.kpi-espaces {
		margin-bottom: 1rem;
	}
</style>
