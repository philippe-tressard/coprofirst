<!--
  🛡️ « Confidentielle : le conseil syndical seulement » — EN TÊTE de la section
  Destinataires, pour une actualité comme pour une affaire (lot 1 de la
  pastille de lecture, arbitré le 25/09/2026).

  Elle vivait dans la Mise en avant, sous la clé `brouillon` (« Visibilité
  réservée au conseil syndical »). Elle n'y mettait rien en avant : elle dit qui
  LIT. Elle a donc rejoint la section qui répond à cette question, avec la même
  forme que sa jumelle « Réservé au périmètre » (`CaseReservePerimetre`) —
  case, icône du catalogue, libellé.

  Elle passe outre tout le reste : cochée, le périmètre réservé et les profils
  s'éteignent (ce sont les porteurs qui les éteignent — ils la lisent).

  ⚠️ Elle écrit `confidentiel`, que le serveur honore pour les deux natures
  (`ticket_visible`, `reservee_au_conseil`) : c'est lui qui décide.
-->
<script lang="ts">
	import Icon from '#lib/components/Icon.svelte';
	import { optionPublication } from '#lib/options-publication.ts';

	export let coche = false;

	const option = optionPublication('brouillon');
</script>

<label class="checkbox-field case-confidentielle" title={option?.aide}>
	<input type="checkbox" bind:checked={coche} />
	<Icon name="shield-check" size={15} />
	Confidentielle : le conseil syndical seulement
</label>
{#if coche}
	<p class="aide">
		Elle passe outre le périmètre et les destinataires : rien ne sort, ni groupe WhatsApp, ni
		affiche. Décochez pour les retrouver.
	</p>
{/if}

<style>
	/*  En tête de section, comme sa jumelle du Périmètre. */
	.case-confidentielle {
		margin-bottom: 0.5rem;
	}
	@media (max-width: 480px) {
		.case-confidentielle {
			min-height: 44px;
		}
	}
</style>
