<!--
  Le badge NEW d'une carte, à côté de son titre — le même sur tout le site.

  🔴 Il était écrit CINQ fois (#1329) — affaire, actualité, annonce, idée,
  sondage — puis unifié en « Nouveau » gris ; le fil d'activité, lui, gardait
  son propre « NEW » rouge. Arbitré à l'écran le 26/09/2026 : **un seul badge,
  le NEW rouge du fil**. Le fil l'emploie désormais aussi.

  La règle de fraîcheur est `isNouveau` (`#lib/date`) quand on donne une date ;
  le fil, qui a la sienne (`isNew`, `#lib/flux`), passe son verdict par `si`.

  Fixe, sans pulsation : le fil le faisait battre en continu. Une animation
  permanente sur une liste parcourue plusieurs fois par jour fatigue sans rien
  apprendre (`emil-design-eng` : ce qu'on voit souvent ne s'anime pas).
-->
<script lang="ts">
	import { isNouveau } from '#lib/date.ts';

	/** La date de création de l'objet ; absente, `si` décide seul (le fil). */
	export let le: string | null | undefined = undefined;
	/** Une condition de plus, propre à l'écran (une annonce archivée n'est plus nouvelle). */
	export let si = true;

	$: visible = si && (le === undefined || (!!le && isNouveau(le)));
</script>

{#if visible}<span class="badge-nouveau">NEW</span>{/if}

<style>
	.badge-nouveau {
		display: inline-block;
		margin-left: 0.45em;
		padding: 0.1rem 0.35rem;
		border-radius: 0.2rem;
		background: var(--color-danger-plein);
		color: var(--color-sur-plein);
		font-size: 0.6rem;
		font-weight: 700;
		letter-spacing: 0.06em;
		line-height: 1.4;
		vertical-align: middle;
		flex-shrink: 0;
	}
</style>
