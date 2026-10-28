<!--
  SectionEquipement.svelte — la section 3 du cadre : SUR QUOI porte l'affaire.

  Sortie de `SectionsSpecifiquesTicket` le 24/09/2026 (#1207) : la Suite du
  conseil en a besoin à son tour, et la recopier aurait fait deux listes, deux
  aides et deux résumés pour le même champ. Le conseil la désigne, pour une
  catégorie du bâti ; les règles serveur vivent dans `utils/intervenant`.

  🔴 Elle sert aussi le CONTRAT et le PRESTATAIRE depuis le 26/09/2026 (#1329) :
  chacun écrivait sa liste déroulante à la main — trois rendus, trois options
  vides différentes (« — Aucun — », « — Sélectionner — », aucune). Ce qui varie
  est passé en props : la liste, le requis, l'aide.
-->
<script lang="ts">
	import SectionFormulaire from '#lib/components/SectionFormulaire.svelte';
	import { SECTIONS_LIBELLE } from '#lib/entites/types.ts';
	import { EQUIPEMENTS_AFFAIRE, equipLabel, type TypeEquipementOption } from '#lib/prestataires.ts';

	/** La valeur de `TypeEquipement`, ou `''`. */
	export let equipement = '';
	export let idPrefixe = 'ticket';
	/** Relayé depuis la déclaration (`lint:pliage-transmis`). */
	export let pliable = false;
	/** Le motif d'extinction (`inactivePour`), ou `''`. */
	export let inactive = '';
	/**  La liste proposée : celle d'une affaire par défaut, TOUS les types pour
	 *   un contrat ou un prestataire (`EQUIPEMENTS`). */
	export let options: readonly TypeEquipementOption[] = EQUIPEMENTS_AFFAIRE;
	/** Lu dans la déclaration (`requisDe`), jamais écrit ici. */
	export let requis = false;
	/** L'aide sous le champ — celle de l'affaire par défaut ; `''` : aucune. */
	export let aide = 'Au carnet d’entretien, l’affaire résolue se range sous cet équipement.';
</script>

<SectionFormulaire
	titre={SECTIONS_LIBELLE.equipement}
	{pliable}
	{inactive}
	{requis}
	rempli={equipement !== ''}
	resume={equipement ? equipLabel(equipement) : 'aucun'}
	valeurModifiee={equipement !== ''}
	pour="{idPrefixe}-equipement"
>
	<div class="field">
		<select id="{idPrefixe}-equipement" bind:value={equipement} required={requis}>
			<option value="">{requis ? '— Sélectionner —' : '— Aucun —'}</option>
			{#each options as e (e.val)}<option value={e.val}>{e.label}</option>{/each}
		</select>
	</div>
	{#if aide}<p class="aide">{aide}</p>{/if}
</SectionFormulaire>
