<!--
  ChampFrequence.svelte — le rythme d'un passage : « toutes les X semaines »,
  « mensuelle », « X fois par an », « tous les X ans ».

  Extrait le 23/09/2026 (#1092, lot 5). La fréquence s'écrivait DEUX fois, et
  différemment : le contrat proposait quatre unités dont « mensuelle » sans
  nombre, l'événement trois dont « tous les N mois ». L'affaire Entretien, qui
  reçoit les maintenances du calendrier, en aurait été la troisième. Le contrat
  fait référence — c'est lui qui fixe le rythme d'un prestataire — et ses unités
  se lisent dans `FREQUENCES` (`#lib/prestataires`), jamais dans l'écran.

  Forme standard d'un champ de section : `.field` puis `<label for>` — la même
  que « Début » et « Fin » juste au-dessus, en deux colonnes qui repassent en
  une sur téléphone (`.form-grid-2`).

  « Mensuelle » ne demande pas de nombre : il vaut 1, posé ici pour que le
  serveur reçoive toujours une paire complète.

  🆕 `duContrat` (#1445) : sous contrat, le rythme est CELUI DU CONTRAT — il se
  lit, il ne se saisit pas. Deux rythmes pour une même visite divergeraient.
-->
<script lang="ts">
	import ChoixPastilles from '#lib/components/ChoixPastilles.svelte';
	import { FREQUENCES, frequenceLabel } from '#lib/prestataires.ts';
	import { SEPARATEUR } from '#lib/separateurs.ts';

	export let frequenceType: string | null | undefined = '';
	export let frequenceValeur: number | string | null | undefined = null;
	export let idPrefixe = 'frequence';
	/** Le contrat qui cadre l'intervention : son rythme s'affiche, rien ne se saisit. */
	export let duContrat: {
		frequence_type?: string | null;
		frequence_valeur?: number | null;
	} | null = null;

	//  « Aucune » est la valeur vide : `null` (fiche jamais réglée) s'y ramène.
	let choix = frequenceType ?? '';
	$: frequenceType = choix;
	$: unite = FREQUENCES.find((f) => f.val === frequenceType);
	$: if (unite && !unite.nombre) frequenceValeur = 1;
</script>

{#if duContrat}
	<p class="aide frequence">
		Fréquence : {frequenceLabel(duContrat) || 'aucune'}{SEPARATEUR.tiret}celle du contrat.
	</p>
{:else}
	<div class="form-grid form-grid-2 frequence">
		<!--  Cinq valeurs : des pastilles (#1329), « Aucune » pour la valeur vide. -->
		<ChoixPastilles
			options={FREQUENCES}
			bind:valeur={choix}
			tous="Aucune"
			libelle="Fréquence"
			libelleVisible
			defilante={false}
		/>
		{#if unite?.nombre}
			<div class="field">
				<label for="{idPrefixe}-valeur">{unite.nombre}</label>
				<input id="{idPrefixe}-valeur" type="number" min="1" bind:value={frequenceValeur} />
			</div>
		{/if}
	</div>
{/if}

<style>
	/*  Seul l'écart : la disposition vient de `.form-grid-2` (`champs.css`). */
	.frequence {
		margin-top: 0.75rem;
	}
</style>
