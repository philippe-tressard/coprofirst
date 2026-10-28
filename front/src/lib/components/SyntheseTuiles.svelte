<!--
  SyntheseTuiles.svelte — M2, les six chiffres d'une affaire close (#1643).

  Durée totale · étape la plus longue · Suites · relances (et la réaction du
  syndic après la dernière) · première réponse du syndic · semaines muettes.
  Tout est CALCULÉ par le serveur et figé à la production : ce composant ne
  mesure rien, il choisit les chiffres. Leur rendu est `TuilesChiffres`, partagé
  avec les moyennes d'un ensemble d'affaires (#1645, #1646).
-->
<script lang="ts">
	import type { MetriquesSynthese } from '#lib/api/index.ts';
	import { fmtJours, libelleEtape } from '#lib/synthese.ts';
	import TuilesChiffres from './TuilesChiffres.svelte';

	export let metriques: MetriquesSynthese;

	$: plusLongue = metriques.etapes.find((e) => e.statut === metriques.etape_plus_longue);
	$: tuiles = [
		{ libelle: 'Durée totale', valeur: fmtJours(metriques.duree_totale), detail: 'jours ouvrés' },
		{
			libelle: 'Étape la plus longue',
			valeur: plusLongue ? fmtJours(plusLongue.jours) : '—',
			detail: plusLongue ? libelleEtape(plusLongue.statut) : '',
		},
		{ libelle: 'Suites', valeur: String(metriques.suites), detail: '' },
		{
			libelle: 'Relances',
			valeur: String(metriques.relances),
			detail: metriques.relances > 0 ? `réaction : ${fmtJours(metriques.reaction_relance)}` : '',
		},
		{
			libelle: '1ʳᵉ réponse du syndic',
			valeur: fmtJours(metriques.premiere_reponse_syndic),
			detail: "après l'ouverture",
		},
		{
			libelle: 'Semaines muettes',
			valeur: String(metriques.semaines_muettes),
			detail: `sur ${metriques.semaines.length}`,
		},
	];
</script>

<TuilesChiffres {tuiles} libelle="Chiffres de l'affaire" />
