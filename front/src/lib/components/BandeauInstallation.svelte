<!--
  Le bandeau permanent de ce qu'EST l'installation, quand l'écran doit le dire :
  la DÉMO PUBLIQUE (spec `mode-demo.md` §8, #1906), et l'installation SUSPENDUE
  par la référence, en lecture seule (spec multi-copropriétés §4.11, D20, R6 #1882).
  Une seule écriture pour les deux : c'était `BandeauDemo`, élargi par R6.

  Rendu en tête de la colonne de contenu du squelette `(app)` — sous la barre
  mobile fixe, que le layout racine aurait laissée le recouvrir — et sur la page
  de connexion. Rien sinon : il ne coûte rien à une installation ordinaire.

  Purement informatif (`role="note"`, rien de focalisable) : il ne s'intercale
  pas dans l'ordre du clavier, avant le contenu. La teinte est celle de
  `EncartAvertissement`, seule écriture de la notion. Les deux faits sont
  calculés par le serveur (`GET /config`), jamais saisis.
-->
<script lang="ts">
	import EncartAvertissement from '#lib/components/EncartAvertissement.svelte';
	import { installationSuspendueStore, modeDemoStore } from '#lib/stores/pageConfig.ts';
	import { SEPARATEUR } from '#lib/separateurs.ts';
	import { BANDEAU_SUSPENDUE } from '#lib/bandeaux-installation.ts';

	/** Dans la carte de connexion : pleine largeur de la carte, détaché de ce qui suit. */
	export let dansCarte = false;
</script>

{#if $installationSuspendueStore}
	<div class="bandeau-installation" class:dans-carte={dansCarte}>
		<EncartAvertissement role="note">
			<strong>{BANDEAU_SUSPENDUE.titre}{SEPARATEUR.tiret}{BANDEAU_SUSPENDUE.precision}.</strong>
			{BANDEAU_SUSPENDUE.texte}
		</EncartAvertissement>
	</div>
{/if}
{#if $modeDemoStore}
	<div class="bandeau-installation" class:dans-carte={dansCarte}>
		<EncartAvertissement role="note">
			<strong>Démonstration{SEPARATEUR.tiret}résidence fictive.</strong>
			Ce que vous saisissez est visible des autres visiteurs et effacé chaque nuit. Aucun courriel, message
			WhatsApp ni appel à l'IA n'est réellement envoyé.
		</EncartAvertissement>
	</div>
{/if}

<style>
	.bandeau-installation {
		margin: 0.75rem 1rem 0;
	}
	.bandeau-installation.dans-carte {
		margin: 0 0 1rem;
	}
</style>
