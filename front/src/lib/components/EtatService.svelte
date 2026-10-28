<!--
  La ligne d'état d'un service, en tête de son onglet de réglages (IA, WhatsApp,
  réponses par courriel).

  ## Un interrupteur, un seul endroit

  Un service s'active et se coupe dans **Administration › Services**, et nulle
  part ailleurs (14/10/2026, demandé : « tout est centralisé dans cet onglet ;
  il faudrait supprimer cette seconde activation »). Les onglets de réglages
  portaient chacun leur case, qui écrivait la même clé : deux commandes pour un
  geste, et un « Enregistrer » d'onglet pouvait rétablir un service qu'on venait
  de couper. Ils ne font plus que DIRE l'état, et renvoyer à l'interrupteur.

  🔒 `test_services_registre.py` refuse qu'un écran autre que l'onglet Services
  écrive une clé d'activation.
-->
<script lang="ts">
	import BadgeEtatService from '#lib/components/BadgeEtatService.svelte';

	/** Le service est-il activé — la clé d'activation lue par l'onglet. */
	export let actif: boolean;
</script>

<div class="etat-service">
	<BadgeEtatService etat={actif ? 'actif' : 'coupe'} />
	<p class="aide">
		{#if actif}
			Ce service est activé.
		{:else}
			Ce service est coupé : ses réglages restent enregistrés et peuvent se tester.
		{/if}
		Il s’active et se coupe dans <a href="/admin?onglet=services">Services</a>.
		<slot />
	</p>
</div>

<style>
	.etat-service {
		display: flex;
		align-items: baseline;
		gap: 0.5rem;
		margin-bottom: 0.75rem;
	}
	.etat-service .aide {
		margin: 0;
	}
</style>
