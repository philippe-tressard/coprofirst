<!--
  « Indisponible en démonstration », en tête d'un onglet d'administration que la
  démo publique ferme ENTIER — SMTP, assistant IA, WhatsApp, sauvegardes (spec
  `mode-demo.md` §8, #1906). Le serveur refuse ces gestes (`utils/demo`) ;
  l'encart dit pourquoi avant le clic, au lieu d'un 403 après.

  `saisie` : le RAPPEL en tête de chaque formulaire (`FormulaireCreation`, création
  et correction) — les personnages sont partagés, ce qu'on y écrit se lit par les
  autres visiteurs (spec §9, #1907). Une seule écriture de la notion « la démo
  prévient », deux phrases.

  Rien hors démo.
-->
<script lang="ts">
	import EncartAvertissement from '#lib/components/EncartAvertissement.svelte';
	import { modeDemoStore } from '#lib/stores/pageConfig.ts';

	/** Le rappel d'un formulaire, au lieu de l'onglet fermé. */
	export let saisie = false;
</script>

{#if $modeDemoStore}
	<div class="encart-demo">
		<EncartAvertissement role="note">
			{#if saisie}
				<strong>Démonstration.</strong>
				Ce que vous écrivez ici est visible des autres visiteurs : n'y mettez aucune donnée personnelle
				réelle.
			{:else}
				<strong>Indisponible en démonstration.</strong>
				Ces réglages se lisent, mais ne s'enregistrent ni ne s'essaient : rien ne part de la démo.
			{/if}
		</EncartAvertissement>
	</div>
{/if}

<style>
	.encart-demo {
		margin-bottom: 1rem;
	}
</style>
