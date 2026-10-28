<!--
  MoyennesAffaires.svelte — les moyennes d'un ENSEMBLE d'affaires closes.

  Un rendu, deux écrans : le bilan de l'exercice du carnet (`BilanCarnet`, #1645,
  une fois par catégorie) et la fiche d'un prestataire (`MetriquesPrestataire`,
  #1646). Le serveur calcule tout (`utils/synthese_affaire/agregats`), chaque
  affaire mesurée comme sa synthèse : ce composant pose les chiffres.

  🔴 Une moyenne absente se dit « — », jamais « 0 j » : une affaire sans relance
  n'a pas de délai de réaction, elle n'en a pas un nul. Et chaque moyenne
  partielle dit sur combien d'affaires elle porte.
-->
<script lang="ts">
	import type { ResumeAffaires } from '#lib/api/index.ts';
	import { fmtJours, libelleEtape, surAffaires } from '#lib/synthese.ts';
	import { fmtNombre } from '#lib/utils.ts';
	import TuilesChiffres from './TuilesChiffres.svelte';

	export let resume: ResumeAffaires;
	/** Le nom de la liste de tuiles, pour un lecteur d'écran. */
	export let libelle = 'Moyennes des affaires closes';

	$: tuiles = [
		{
			libelle: 'Durée moyenne',
			valeur: fmtJours(resume.duree_totale),
			detail: 'jours ouvrés',
		},
		{
			libelle: '1ʳᵉ réponse du syndic',
			valeur: fmtJours(resume.premiere_reponse_syndic),
			detail:
				resume.premiere_reponse_syndic === null
					? 'aucune à mesurer'
					: "en moyenne, après l'ouverture",
		},
		{
			libelle: 'Relances au syndic',
			valeur: fmtNombre(resume.relances),
			detail:
				resume.relances_par_affaire === null
					? ''
					: `${fmtNombre(resume.relances_par_affaire)} par affaire`,
		},
		{
			libelle: 'Réaction après relance',
			valeur: fmtJours(resume.reaction_relance),
			detail: resume.reactions
				? `en moyenne, ${surAffaires(resume.reactions)}`
				: 'aucune à mesurer',
		},
	];
</script>

<TuilesChiffres {tuiles} {libelle} />

{#if resume.etapes.length}
	<div class="table-wrap">
		<table class="table">
			<caption class="sr-only">Temps moyen par étape du kanban, en jours ouvrés</caption>
			<thead>
				<tr>
					<th scope="col">Étape</th>
					<th scope="col" class="nombre">Durée moyenne (jours ouvrés)</th>
					<th scope="col" class="nombre">Affaires</th>
				</tr>
			</thead>
			<tbody>
				{#each resume.etapes as e (e.statut)}
					<tr>
						<td>{libelleEtape(e.statut)}</td>
						<td class="nombre">{fmtJours(e.jours)}</td>
						<td class="nombre">{fmtNombre(e.nombre)}</td>
					</tr>
				{/each}
			</tbody>
		</table>
	</div>
{/if}
