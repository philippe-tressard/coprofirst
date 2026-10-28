<!--
  SectionsCiblageEvolution.svelte — le PÉRIMÈTRE et les DESTINATAIRES d'une
  entrée du fil, sections 4 et 5 du cadre #430.

  ## Pourquoi ce fichier existe (05/09/2026)

  Le bloc du périmètre vivait dans `EvolForm`, qui a atteint son plafond de
  modularité en accueillant les destinataires. Mais l'extraction n'est pas qu'un
  moyen de faire de la place : les deux sections partagent leur rendu et diffèrent
  par leur **aide**, et c'est cette différence qu'il fallait nommer.

  Sur un ticket, préciser le périmètre veut dire *« on a trouvé d'où vient la
  fuite »*. Sur une actualité, cela veut dire *« ce ciblage était faux, voici le
  bon »*. Même sélecteur, deux gestes — l'aide est donc une propriété, jamais une
  phrase écrite ici.

  ## Ce que « le dernier état » veut dire (05/09/2026)

  Demandé à l'écran : *« les sections Options de publication, Périmètre et
  Destinataires doivent être visibles même pour chaque commentaire ; tu remets le
  dernier état pour chacun, et le nouveau sauvegardé deviendra validé »*.

  Les deux champs partent donc **remplis** de ce qui est en vigueur, et non vides :
  on corrige ce qu'on voit. Ce sont les DÉCLARATIONS d'entité qui ouvrent ces
  sections (`#lib/entites/…`) — un ticket les garde fermées, et rien ne change
  pour lui.

  ⚠️ Tout le rendu vient de `ChampsCommuns` : ce composant ne redéfinit rien, il
  choisit ce qui s'affiche et ce qu'on en dit. Une deuxième écriture du sélecteur
  de périmètre est exactement ce que #463 a supprimé.
-->
<script lang="ts">
	import ChampsCommuns from '#lib/components/ChampsCommuns.svelte';
	import type { EntiteDeclaree } from '#lib/entites/types.ts';

	export let idPrefixe: string;
	/**  L'entité porteuse : c'est elle qui dit le PLIAGE, comme en édition.
	 *   Sans elle, Périmètre et Destinataires s'ouvraient toujours (#1329). */
	export let entite: EntiteDeclaree | null = null;

	/** La section 4 est-elle ouverte pour cette entité, à l'état `evolution` ? */
	export let avecPerimetre = false;
	export let perimetre: string[] = [];
	/** Le périmètre COURANT de l'objet porteur, affiché en badge : on voit d'où l'on part. */
	export let perimetreBadge = '';
	/** Ce que « préciser le périmètre » veut dire ICI. Vide : aucune aide. */
	export let aidePerimetre = '';

	/** La section 5. */
	export let avecDestinataires = false;
	export let destinataires: string[] = [];
	/** Ceux d'une affaire sans choix du conseil (#1343) — `null` : une actualité. */
	export let destinatairesParDefaut: string[] | null = null;
	/** « Résident concerné » d'une affaire (#1321) — `confidentiel`, lié. */
	export let confidentiel = false;
	/** Ce bloc ouvre-t-il le formulaire ? (pas de filet au-dessus) */
	export let premiere = false;
</script>

{#if avecPerimetre || avecDestinataires}
	<ChampsCommuns
		{idPrefixe}
		{entite}
		{premiere}
		{avecPerimetre}
		bind:perimetre
		{perimetreBadge}
		{avecDestinataires}
		bind:destinataires
		{destinatairesParDefaut}
		bind:brouillon={confidentiel}
	>
		<!--  `svelte:fragment` et non un `{#if}` autour du `<p slot>` : un élément
		      porteur de `slot=` doit être enfant DIRECT du composant. -->
		<svelte:fragment slot="aidePerimetre">
			{#if aidePerimetre}<p class="aide">{aidePerimetre}</p>{/if}
		</svelte:fragment>
	</ChampsCommuns>
{/if}

<!--  Aucun `<style>` : `.aide-bloc` est une classe de la CHARTE. La redéfinir ici
      la réécrivait à l'identique sur deux propriétés et changeait la troisième
      sans que personne l'ait décidé — c'est exactement ce que `lint:charte`
      refuse, et il l'a refusé. -->
