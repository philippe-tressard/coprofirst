<!--
  Le badge d'ÉTAT d'une affaire — son « Suivi » : la teinte et le libellé de la
  table de `$lib/tickets`, `badge-gray` pour un état qu'elle ne connaît pas.

  ## Pourquoi (#2173, 23/10/2026)

  La section « Affaires liées » demandait le suivi de chaque affaire, et le badge
  était déjà écrit TROIS fois — `PastillesAffaire`, `TableauAffaires`,
  `FluxCorps` —, chacun avec son repli gris et son libellé. La quatrième copie
  aurait été la mienne : la notion s'écrit ici, les quatre la rendent.
  🔒 `npm run lint:badge-etat-affaire` refuse la table lue ailleurs.

  ⚠️ `badge-gray` en repli : le fil montre aussi des états d'autres objets (un
  événement, une idée) que la table ne connaît pas — `statutTicketLabel` rend
  alors la valeur brute, jamais une chaîne vide.
-->
<script lang="ts">
	import Badge from '$lib/components/Badge.svelte';
	import { STATUT_TICKET_BADGE, statutTicketLabel } from '$lib/tickets';

	export let statut: string | null | undefined;
	/** Un cran sous le corps du badge, pour une liste dense (`Badge`). */
	export let compact = false;
</script>

<Badge teinte={STATUT_TICKET_BADGE[statut ?? ''] ?? 'badge-gray'} {compact}
	>{statutTicketLabel(statut)}</Badge
>
