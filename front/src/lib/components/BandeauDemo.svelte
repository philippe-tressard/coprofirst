<!--
  Le bandeau permanent de la DÉMO PUBLIQUE (spec `mode-demo.md` §8, #1906).

  Rendu en tête de la colonne de contenu du squelette `(app)` — sous la barre
  mobile fixe, que le layout racine aurait laissée le recouvrir — et sur la page
  de connexion. Rien hors démo : il ne coûte rien à une installation ordinaire.

  Purement informatif (`role="note"`, rien de focalisable) : il ne s'intercale
  pas dans l'ordre du clavier, avant le contenu. La teinte est celle de
  `EncartAvertissement`, seule écriture de la notion.
-->
<script lang="ts">
	import EncartAvertissement from '#lib/components/EncartAvertissement.svelte';
	import { modeDemoStore } from '#lib/stores/pageConfig.ts';

	/** Dans la carte de connexion : pleine largeur de la carte, détaché de ce qui suit. */
	export let dansCarte = false;
</script>

{#if $modeDemoStore}
	<div class="bandeau-demo" class:dans-carte={dansCarte}>
		<EncartAvertissement role="note">
			<strong>Démonstration — résidence fictive.</strong>
			Ce que vous saisissez est visible des autres visiteurs et effacé chaque nuit. Aucun courriel, message
			WhatsApp ni appel à l'IA n'est réellement envoyé.
		</EncartAvertissement>
	</div>
{/if}

<style>
	.bandeau-demo {
		margin: 0.75rem 1rem 0;
	}
	.bandeau-demo.dans-carte {
		margin: 0 0 1rem;
	}
</style>
