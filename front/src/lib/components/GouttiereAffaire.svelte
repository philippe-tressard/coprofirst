<!--
  GouttiereAffaire.svelte — la gouttière d'une carte d'AFFAIRE : sa date
  (`mis_a_jour_le`, sinon `cree_le`) et sa NATURE (`natureDe`, dérivée par le
  serveur, jamais redérivée).

  Le dessin vit dans `Gouttiere` depuis que la page Affaires est devenue le
  standard du site (10/10/2026) : ce composant ne dit que CE QUE l'affaire y
  montre. Historique et arbitrages de la maquette B : `Gouttiere.svelte`.
-->
<script lang="ts">
	import Gouttiere from '$lib/components/Gouttiere.svelte';
	import { natureDe } from '$lib/tickets';

	/** L'affaire : ses natures (dérivées par le serveur) et ses deux dates. */
	export let affaire: { natures?: string[]; cree_le: string; mis_a_jour_le?: string | null };
</script>

<Gouttiere quand={affaire.mis_a_jour_le ?? affaire.cree_le} classe={natureDe(affaire)} />
