<!--
  L'onglet **Maintenance** de l'administration : les tâches planifiées des deux
  nœuds, l'intégrité référentielle, et le contrôle de santé quotidien.

  Extrait de `admin/+page.svelte` le 09/09/2026 (#852) — la page fait 1 741 lignes
  et son plafond de modularité lui interdit de grossir. Elle porte déjà dix-sept
  onglets sous forme de composants (`Onglet*.svelte`) : celui-ci était l'un des
  derniers écrits en ligne, et l'accueillir aurait demandé de l'agrandir.
-->
<script lang="ts">
	import ControleSante from '$lib/components/ControleSante.svelte';
	import CarteConservationAffaires from '$lib/components/CarteConservationAffaires.svelte';
	import CarteExportCopropriete from '$lib/components/CarteExportCopropriete.svelte';
	import ControlesFiabilite from '$lib/components/ControlesFiabilite.svelte';
	import ConsommationIA from '$lib/components/ConsommationIA.svelte';
	import TachesPlanifiees from '$lib/components/TachesPlanifiees.svelte';
	import { isAdmin, isOperateur } from '$lib/stores/auth';
</script>

<!--  🏢 La supervision technique (tâches, contrôles, base, santé)
      est à l'OPÉRATEUR de la plateforme (#1750, arbitrage du 10/10/2026) : le
      serveur la refuse à l'administrateur de copropriété qui ne l'est pas. Ce
      qui reste à l'administrateur — la consommation de l'IA, l'export de sa
      copropriété — porte des données de la résidence, que l'opérateur ne lit pas :
      l'opérateur qui n'est pas administrateur ne les voit donc pas (#2029). -->
{#if $isOperateur}
	<p class="muted intro-maintenance">
		Exécution des tâches planifiées sur les <strong>deux</strong> Raspberry&nbsp;Pi. Le nœud actif assure
		la maintenance applicative (purges, VACUUM) ; le nœud en veille fait son hygiène locale (cache de
		build, rotation des logs, images de base) et transmet son rapport au nœud actif.
	</p>
{:else}
	<p class="muted intro-maintenance">
		La supervision technique de l'installation — tâches planifiées, contrôles de fiabilité, base de
		données — est réservée à l'opérateur de la plateforme.
	</p>
{/if}

<!--  Les deux cartes « Sauvegarde quotidienne — historique » et « Agrégation
      télémétrie — historique » vivaient ici. Supprimées avec #299 : depuis que la
      synthèse déplie l'historique de chaque tâche et porte son bouton de
      lancement, elles montraient les MÊMES lignes, tirées des MÊMES endpoints,
      sous un titre construit exprès pour ressembler à celui de la synthèse.
      Ce qu'elles portaient d'unique — le lieu de stockage des archives et le rôle
      de l'agrégation — est déplacé dans `TachesPlanifiees` (AIDE_TACHE), et la
      profondeur d'historique y passe de 4 à 10 : retirer les cartes sans
      compenser aurait réduit en silence ce qu'un administrateur peut voir. -->
<!--  Le bloc « Installation » (rôle, version, inscription au registre) a son
      onglet depuis le rangement par niveau (#2062) : Exploitation › Installation. -->
{#if $isOperateur}
	<TachesPlanifiees />
	<ControlesFiabilite />
{/if}
{#if $isAdmin}
	<ConsommationIA />
{/if}
{#if $isOperateur}
	<ControleSante />
{/if}
{#if $isAdmin}
	<CarteExportCopropriete />
{/if}
<CarteConservationAffaires />

<style>
	.intro-maintenance {
		margin-bottom: 1.25rem;
	}
</style>
