<!--
  **Le bandeau « je n'ai pas tout reçu »** — pour les données de RÉFÉRENCE.

  ## Pourquoi il n'est pas `EtatListe` (#522)

  `EtatListe` sert une liste **affichée** : il choisit entre « chargement »,
  « échec » et « vide », et le lecteur voit le résultat à l'endroit où la liste
  aurait été.

  Une donnée de référence ne s'affiche pas. Elle garnit un `<select>`, une table
  de correspondance, un rapprochement automatique. Quand elle manque, l'écran ne
  se vide pas : il devient **subtilement faux** — des « Bât. ? » à la place des
  numéros de bâtiment, un menu déroulant sans options, un rapprochement qui ne
  trouve rien et n'a rien cherché.

  🔴 C'est plus discret qu'une liste vide, donc plus durable. Le 19/08/2026, une
  liste vide a suffi à faire croire à une perte de données ; une table de
  correspondance vide, elle, ne fait rien croire du tout — elle laisse
  simplement travailler sur un écran qui ment.

  ⚠️ Le ticket #522 le disait dans ses précautions : *« un sélecteur vide et un
  sélecteur en échec ne se rendent pas de la même façon, et `EtatListe` n'est pas
  le bon outil pour eux »*. D'où ce second composant — et deux composants, pas
  trois : c'est la nature de la donnée qui tranche, pas l'écran.

  ## Où le poser

  En **haut** de l'écran concerné, avant le contenu. Un bandeau posé au milieu
  d'une page longue est lu après ce qu'il devait qualifier.
-->
<script lang="ts">
	import EncartAvertissement from '#lib/components/EncartAvertissement.svelte';
	/** Non vide = au moins une donnée de référence n'a pas pu être chargée. */
	export let erreur = '';
	/**  Ce que le lecteur risque de mal interpréter s'il l'ignore. Obligatoire
	 *   dans les faits : sans lui, le bandeau dit « quelque chose a échoué » sans
	 *   dire ce que ça change — et un avertissement qui ne dit pas ce qu'il
	 *   change se fait ignorer en deux jours. */
	export let consequence = '';
</script>

{#if erreur}
	<div class="chargement-partiel">
		<EncartAvertissement role="status">
			<strong>Affichage incomplet.</strong>
			{erreur}
			{#if consequence}<span class="cp-consequence">{consequence}</span>{/if}
		</EncartAvertissement>
	</div>
{/if}

<style>
	/*  L'allure est celle d'`EncartAvertissement` (#1455) — elle venait de
	    `.alert-warning`, aux couleurs en dur. Seul l'espacement vit ici. */
	.chargement-partiel {
		margin-bottom: 1rem;
	}
	.cp-consequence {
		display: block;
		margin-top: 0.25rem;
		font-size: var(--fs-md);
		opacity: 0.9;
	}
</style>
