<!--
  L'en-tête d'une page : retour éventuel, titre, actions.

  Une seule écriture pour tout le site (#363). Avant ce composant, l'en-tête était
  écrit de douze façons : `.page-header` redéfini en CSS local dans six pages et
  surchargé en ligne dans six autres, le style du `<h1>` recopié **en ligne** dans
  onze pages, et trois formes de bouton retour pour deux classes.

  Le défaut visible qui l'a déclenché : `tickets/nouveau` réécrivait `.page-header`
  avec `display:flex; align-items:center; gap:1rem` — l'intention est claire, un
  groupe serré à gauche — sans redéclarer le `justify-content: space-between` de la
  règle globale, dont elle héritait donc en silence. Résultat : le titre projeté à
  l'autre bout de l'écran, seul écran du site dans ce cas, et personne ne l'avait
  voulu. C'est le « piège de l'héritage partiel » de `standards/11-interface-et-ux.md`
  §1 bis.

  Disposition, la même partout : [retour] titre à GAUCHE · actions à DROITE.
  C'est déjà ce que faisaient seize pages sur dix-sept.

  Le conteneur `.page-header` reste porté par `app.css` — y compris son passage en
  colonne et en `sticky` sous 640 px. Ce composant ne le redéfinit pas : il n'écrit
  que ce que la règle globale ne dit pas.
-->
<script lang="ts">
	import Icon from '#lib/components/Icon.svelte';
	import { safeHtml } from '#lib/sanitize.ts';

	export let titre: string;
	/** Nom d'icône Lucide. Toute page en porte une — sauf à ne pas savoir laquelle. */
	export let icone: string | null = null;
	/** Cible du bouton de retour. Absent = pas de retour. */
	export let retour: string | null = null;
	/*  ⚠️ La prop `marge` A ÉTÉ RETIRÉE le 17/08/2026 — ne pas la réintroduire.
	 *
	 *   Elle existait parce que six pages voulaient un écart plus serré :
	 *   0, .5rem, .75rem et 1rem, contre 1.5rem partout ailleurs. Centraliser les
	 *   valeurs les avait rendues explicites sans les réduire — la dette était
	 *   nommée dans `ux-patterns` §13, et elle a duré.
	 *
	 *   Le symptôme se voyait : en passant d'`/actualites` à `/calendrier`, le
	 *   titre et le bouton SAUTAIENT de quelques pixels, alors que les deux pages
	 *   utilisent le même composant (#372). Six valeurs pour une notion, c'est
	 *   six façons d'avoir raison séparément et une seule d'avoir tort ensemble.
	 *
	 *   Arbitré par l'utilisateur : 1.5rem, la valeur de tous les autres écrans.
	 *   Un écran qui aurait vraiment besoin d'autre chose doit d'abord expliquer
	 *   pourquoi lui — pas recevoir une prop qui rouvre les six. */
	/**  Aligne l'en-tête sur la largeur de saisie (720 px) au lieu de la pleine
	 *   largeur. À activer quand un formulaire est ouvert dans la page : sinon
	 *   son bouton d'annulation se pose au bord droit de l'ÉCRAN, très loin de la
	 *   boîte qu'il annule — signalé par l'utilisateur le 15/08/2026 (#367).
	 *
	 *   Réservé à ce cas : hors saisie, la liste occupe toute la largeur et
	 *   contraindre l'en-tête décalerait le bouton par rapport à ce qu'il domine. */
	export let alignerSaisie = false;
	/**  Le descriptif de la PAGE — la phrase grise sous le titre, administrable
	 *   (`_pc.descriptif`). Il était écrit à la main dans DOUZE écrans, et l'un
	 *   d'eux (Résidence) le posait SOUS les onglets, juste au-dessus du descriptif
	 *   de l'onglet « Fiche », qui portait le même texte : la phrase se lisait deux
	 *   fois (#1369). Rendu ici, il a une place et une seule : sous l'en-tête,
	 *   au-dessus des onglets. Ce que dit l'onglet, `BarreOnglets` le rend. */
	export let descriptif: string | null = null;
</script>

<div class="page-header" class:largeur-saisie={alignerSaisie}>
	<div class="entete-principal">
		{#if retour}
			<a href={retour} class="btn btn-outline entete-retour">← Retour</a>
		{/if}
		<h1>
			{#if icone}<Icon name={icone} size={20} />{/if}{titre}
		</h1>
	</div>
	{#if $$slots.default}
		<div class="entete-actions"><slot /></div>
	{/if}
</div>
<!--  HORS du conteneur : sous 640 px, `.page-header` devient collant, et la
      phrase ne doit pas rester à l'écran pendant le défilement. -->
{#if descriptif}
	<div class="page-subtitle">{@html safeHtml(descriptif)}</div>
{/if}

<style>
	/*  Retour et titre forment UN bloc : sans ce groupe, `space-between` les
	    écarterait aux deux bouts — exactement le défaut corrigé ici. */
	.entete-principal {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		min-width: 0;
	}
	.entete-retour {
		flex-shrink: 0;
	}

	h1 {
		display: flex;
		align-items: center;
		gap: 0.4rem;
		font-size: var(--fs-titre-page);
		font-weight: 700;
		min-width: 0;
	}

	.entete-actions {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		flex-wrap: wrap;
	}

	/*  Aucune largeur n'est écrite ici : c'est la classe globale `largeur-saisie`
	    (app.css) qui est posée sur le conteneur. Recopier « 720 px » aurait créé
	    la deuxième valeur qui dérive le jour où la première change. */
</style>
