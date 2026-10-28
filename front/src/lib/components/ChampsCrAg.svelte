<!--
  Les deux champs propres à un compte-rendu d'AG — l'année et la date de l'AG.

  Extraits le 24/09/2026 (#1254) : la création (`residence`) et la correction
  (`FormulaireEditionDocument`) les écrivaient chacune chez elle, avec la même
  règle `.paire` recopiée dans les deux `<style>`. La création a reçu son
  étoile de champ requis, la correction non : deux copies qui divergeaient
  déjà au premier ajustement.

  ⚠️ `requis` n'est vrai qu'à la CRÉATION : c'est l'écran de création
  (`addCrAg`) qui refuse un CR sans année ni date. Le serveur, lui, les tient
  pour facultatives (`documents.py`), et la correction ne les exige donc pas —
  lui prêter une exigence qu'il n'a pas marquerait requis ce qui ne l'est pas.
-->
<script lang="ts">
	import EtoileRequis from '#lib/components/EtoileRequis.svelte';

	export let annee: string | number = '';
	export let dateAg = '';
	/** Préfixe des `id` : la création et la correction peuvent être ouvertes ensemble. */
	export let idPrefixe = 'ag';
	export let requis = false;
</script>

<div class="form-grid-2">
	<label class="field" for="{idPrefixe}-annee">
		<span
			>Année{#if requis}<EtoileRequis vide={!annee} />{/if}</span
		>
		<input
			id="{idPrefixe}-annee"
			type="number"
			bind:value={annee}
			min="1900"
			max="2100"
			placeholder="2025"
		/>
	</label>
	<label class="field" for="{idPrefixe}-date">
		<span
			>Date de l'AG{#if requis}<EtoileRequis vide={!dateAg} />{/if}</span
		>
		<input id="{idPrefixe}-date" type="date" bind:value={dateAg} />
	</label>
</div>
