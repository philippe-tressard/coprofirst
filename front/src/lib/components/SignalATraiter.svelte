<!--
  Le SIGNAL rouge « à traiter » : combien de choses attendent un geste.

  Ce n'est pas un nombre d'objets — celui-là est `Compte`, en Bleu Seine — mais
  une alerte, en rouge : autre notion, autre couleur (`lint:vignette-compte`).

  Extrait d'`Onglet.svelte` le 21/10/2026 (#2062) : la rangée des GROUPES de
  `BarreOnglets` porte le même signal que l'onglet, additionné sur le groupe.
  Une règle scopée ne franchit pas son composant ; recopiée, elle aurait
  divergé au premier ajustement.

  Rien n'est rendu pour `0` : un compteur à zéro n'apprend rien.
-->
<script lang="ts">
	export let n: number | null = null;
</script>

{#if n}<span class="signal">{n}</span>{/if}

<style>
	.signal {
		background: var(--color-danger);
		color: var(--color-surface);
		border-radius: 999px;
		font-size: var(--fs-2xs);
		padding: 0.1rem 0.45rem;
		font-weight: 700;
	}
</style>
