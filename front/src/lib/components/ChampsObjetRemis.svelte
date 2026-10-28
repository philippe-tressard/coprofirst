<!--
  Les champs d'un objet remis au locataire — type, libellé, quantité, référence,
  date de remise, notes.

  Extraits le 11/09/2026 parce que la boîte s'ouvre désormais à DEUX endroits :
  au-dessus du tableau pour AJOUTER (le geste « + » y est), et DANS la rangée de
  l'objet pour le CORRIGER (`ux-patterns` §14 ter — la boîte s'ouvre là où est le
  geste). Deux copies des mêmes champs auraient divergé au premier ajustement.
-->
<script lang="ts">
	import ChoixPastilles from '#lib/components/ChoixPastilles.svelte';
	import EtoileRequis from '#lib/components/EtoileRequis.svelte';

	export let types: readonly { val: string; label: string; desc?: string }[] = [];
	export let fType = '';
	export let fLibelle = '';
	export let fQuantite: number | string = 1;
	export let fReference = '';
	export let fRemisLe = '';
	export let fNotes = '';
</script>

<ChoixPastilles
	options={types}
	bind:valeur={fType}
	tous={false}
	libelle="Type d’objet"
	libelleVisible
	requis
/>

<div class="form-grid">
	<label class="field champ-large">
		<span>Libellé<EtoileRequis vide={!fLibelle.trim()} /></span>
		<input type="text" bind:value={fLibelle} required maxlength="120" />
	</label>
	<label class="field">
		Quantité
		<input type="number" bind:value={fQuantite} min="1" max="99" />
	</label>
	<label class="field">
		Référence
		<input type="text" bind:value={fReference} maxlength="60" />
	</label>
	<label class="field">
		Remis le
		<input type="date" bind:value={fRemisLe} />
	</label>
	<label class="field champ-large">
		Notes
		<textarea bind:value={fNotes} rows="2" maxlength="500"></textarea>
	</label>
</div>
