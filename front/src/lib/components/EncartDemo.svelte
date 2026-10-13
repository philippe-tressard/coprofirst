<!--
  « Indisponible en démonstration », en tête d'un onglet d'administration que la
  démo publique ferme ENTIER — SMTP, assistant IA, WhatsApp, sauvegardes (spec
  `mode-demo.md` §8, #1906). Le serveur refuse ces gestes (`utils/demo`) ;
  l'encart dit pourquoi avant le clic, au lieu d'un 403 après.

  Rien hors démo.
-->
<script lang="ts">
	import EncartAvertissement from '$lib/components/EncartAvertissement.svelte';
	import { modeDemoStore } from '$lib/stores/pageConfig';
</script>

{#if $modeDemoStore}
	<div class="encart-demo">
		<EncartAvertissement role="note">
			<strong>Indisponible en démonstration.</strong>
			Ces réglages se lisent, mais ne s'enregistrent ni ne s'essaient : rien ne part de la démo.
		</EncartAvertissement>
	</div>
{/if}

<style>
	.encart-demo {
		margin-bottom: 1rem;
	}
</style>
