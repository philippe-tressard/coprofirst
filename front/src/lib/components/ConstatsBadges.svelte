<!--
  **Les badges dont l'accès diffère de ce que leurs lots justifient** — Espace CS ›
  Badges & accès (#2217).

  Un badge « mal doté » ne se voyait qu'à la porte fermée, un badge « trop doté »
  jamais. Le constat se calcule côté serveur (`utils/acces_constats`) ; cet encart
  le montre, avec le même rendu que les constats des lots (`ConstatsLots`).

  ⚠️ Jamais bloquant : un écart se règle à la main, en corrigeant le badge dans le
  parc. Et rien ne s'affiche tant que la lecture n'a pas abouti — un constat qu'on
  n'a pas pu lire ne se présente pas comme « aucun écart ».
-->
<script lang="ts">
	import { onMount } from 'svelte';
	import ConstatsLots from '#lib/components/ConstatsLots.svelte';
	import { acces, type ConstatPatrimoine } from '#lib/api/index.ts';

	let constats: ConstatPatrimoine[] | null = null;

	onMount(async () => {
		try {
			constats = await acces.constatsBadges();
		} catch {
			constats = null; // l'encart se tait : le parc reste utilisable
		}
	});
</script>

{#if constats && constats.length}
	<div class="constats-badges">
		<p class="constats-badges-titre">Écarts entre les badges et leurs lots</p>
		<ConstatsLots {constats} />
	</div>
{/if}

<style>
	.constats-badges {
		margin-bottom: 1rem;
	}
	.constats-badges-titre {
		margin: 0 0 0.5rem;
		font-weight: 600;
	}
</style>
