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

  Depuis le 05/11/2026 (#2525), le relevé — échéances, ordre, compteurs, année
  de référence — est SERVI par `GET /reporting/renouvellements`, que l'app iOS
  lit aussi : ce fichier et ses deux enfants le lisent, sans rien recalculer.
-->
<script lang="ts">
	import VueRenouvellementsContrats from './VueRenouvellementsContrats.svelte';
	import VueRenouvellementsAudits from './VueRenouvellementsAudits.svelte';
	import type { ReleveRenouvellements } from '#lib/api/index.ts';

	export let releve: ReleveRenouvellements | null = null;

	$: compteurs = releve?.compteurs;
	$: renKpiPreavis = compteurs?.contrats_en_preavis ?? 0;
	$: renKpiContrats = compteurs?.echeances_contrats_annee ?? 0;
	$: renKpiDiags = compteurs?.audits_a_planifier ?? 0;
</script>

<!-- ── Renouvellement contrats & audits ──────────────────────────── -->
<div class="kpi-row kpi-espaces">
	<div class="kpi-card" class:kpi-alert={renKpiPreavis > 0}>
		<div class="kpi-value">{renKpiPreavis}</div>
		<div class="kpi-label">Contrats en préavis</div>
	</div>
	<div class="kpi-card">
		<div class="kpi-value">{renKpiContrats}</div>
		<div class="kpi-label">Échéances contrats en {releve?.annee ?? ''}</div>
	</div>
	<div class="kpi-card" class:kpi-alert={renKpiDiags > 0}>
		<div class="kpi-value">{renKpiDiags}</div>
		<div class="kpi-label">Audits à (re)planifier</div>
	</div>
</div>

<VueRenouvellementsContrats {releve} />

<VueRenouvellementsAudits {releve} />

<style>
	.kpi-espaces {
		margin-bottom: 1rem;
	}
</style>
