<!--
  AideSource.svelte — « d'où vient cette valeur, et cette saisie sert-elle ? »

  ## Pourquoi ce composant (29/08/2026, #535)

  Quand une valeur est DÉRIVÉE d'une autre source, le champ qui la saisissait
  reste souvent en place — et devient un piège : on y corrige un texte que
  personne ne lit, en croyant avoir changé la valeur.

  🔴 C'est la moitié qui manque à beaucoup de dérivations. On remplace la source,
  on oublie le formulaire qui alimentait l'ancienne. Le premier cas était le nom
  du syndic, dérivé du contrat désigné ; il y en aura d'autres — c'est tout
  l'objet de #535.

  ⚠️ Ce composant ne DÉCIDE rien : il rend visible une décision prise ailleurs,
  côté serveur. L'écran qui l'emploie doit aussi désactiver le champ — dire sans
  empêcher laisserait croire à un bug.

  UTILISATION :
    <AideSource active={source === 'contrat'}
      origine="contrat de syndic" ou="Prestataires → Contrats"
      repli="Aucun contrat de syndic désigné : c'est cette saisie qui s'affiche." />
-->
<script lang="ts">
	import { SEPARATEUR } from '#lib/separateurs.ts';
	/** La valeur vient-elle de l'autre source ? Faux = la saisie sert encore. */
	export let active = false;
	/** Ce qui fait foi, en toutes lettres : « contrat de syndic ». */
	export let origine = '';
	/** Où l'on va pour changer la valeur : « Prestataires → Contrats ». */
	export let ou = '';
	/** Ce qu'on dit quand la saisie sert encore. */
	export let repli = '';
</script>

<span class="aide">
	{#if active}
		&#x1F517; Vient du <strong>{origine}</strong>{#if ou}{SEPARATEUR.tiret}se change dans {ou}{/if}.
	{:else}
		&#x2139;&#xFE0F; {repli}
	{/if}
</span>

<style>
</style>
