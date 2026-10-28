<!--
  UN onglet — le bouton d'une rangée `.tabs`, qu'il change de panneau ou qu'il
  mène ailleurs.

  ## Pourquoi ce composant (16/08/2026)

  La rangée d'onglets de l'administration mélange **deux mécanismes**, et c'est
  légitime : « À traiter » bascule un panneau **dans** la page, « Fiche
  copropriété » **navigue** vers une autre route. Un `<button>` d'un côté, un
  `<a>` de l'autre — on ne peut pas faire autrement sans perdre le clic milieu et
  l'ouverture dans un nouvel onglet, ni sans aveugler
  `scripts/check-routes-atteignables.mjs`, qui cherche le littéral `/admin/…`.

  Ce qui n'était pas légitime, c'est que la différence **se voie**. Elle se voyait
  de deux façons, toutes deux signalées par l'utilisateur :

  1. la **police** — les contrôles de formulaire n'héritent pas de `font-family`,
     donc les `<button>` sortaient en Arial et les `<a>` en Segoe UI. Corrigé à la
     racine dans `app.css` (`button, input, select, textarea { font-family: inherit }`),
     et ça dépassait de loin les onglets : toute la couche de saisie du site était
     concernée, les zones de texte long en chasse fixe ;
  2. le **soulignement au survol**, que la règle globale `a:hover` ajoutait aux
     seuls liens.

  Deux corrections successives, deux fois insuffisantes, parce qu'elles traitaient
  les symptômes un par un. Verdict de l'utilisateur : *« je ne comprends pas
  pourquoi ça n'utilise pas la même configuration que les autres sous-menus ;
  encore une fois standardise »*. Il a raison : tant que quinze onglets sont écrits
  à la main, le seizième réintroduira l'écart.

  **Ce composant est donc le seul endroit qui décide de la forme d'un onglet.**
  L'écran dit ce que l'onglet EST — actif ou non, avec un compte ou non, menant
  ici ou là — jamais comment il se rend.

  ## Le contrat

  - `href` fourni → un `<a>` : l'onglet mène ailleurs ;
  - `href` absent → un `<button type="button">` : l'onglet bascule un panneau,
    et l'écran écoute `on:click`.

  `type="button"` n'est pas décoratif : dans un `<form>`, un `<button>` sans type
  vaut `submit` et enverrait le formulaire au premier clic.
-->
<script lang="ts">
	import SignalATraiter from '#lib/components/SignalATraiter.svelte';

	/** Destination. Absent : l'onglet bascule un panneau au lieu de naviguer. */
	export let href: string | null = null;

	/** Onglet courant — souligné et coloré. */
	export let actif = false;

	/**  Compte à afficher en pastille rouge. `null` ou `0` : aucune pastille —
	     un compteur à zéro n'apprend rien et fait du bruit. */
	export let compte: number | null = null;

	/**  Le service que cet onglet règle est COUPÉ : l'onglet se grise, et reste
	     ouvrable — on y règle un service avant de l'activer. */
	export let eteint = false;
</script>

{#if href}
	<a
		{href}
		class="tab-btn"
		class:active={actif}
		class:eteint
		title={eteint ? 'Service coupé — il s’active dans Services' : undefined}
	>
		<slot />{#if eteint}<span class="sr-only"> (service coupé)</span>{/if}
		<SignalATraiter n={compte} />
	</a>
{:else}
	<button
		type="button"
		class="tab-btn"
		class:active={actif}
		class:eteint
		title={eteint ? 'Service coupé — il s’active dans Services' : undefined}
		on:click
	>
		<slot />{#if eteint}<span class="sr-only"> (service coupé)</span>{/if}
		<SignalATraiter n={compte} />
	</button>
{/if}

<style>
	/*  `.tabs` et `.tab-btn` vivent dans la feuille commune ; le compte rouge est
	    `SignalATraiter`, partagé avec la rangée des groupes de `BarreOnglets`
	    depuis le 21/10/2026 (#2062). */
	/*  Grisé, pas désactivé : l'onglet d'un service coupé s'ouvre toujours. Ouvert,
	    il reprend sa pleine couleur — on lit ce qu'on règle. */
	.eteint:not(.active) {
		opacity: 0.5;
	}
</style>
