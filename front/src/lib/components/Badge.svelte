<!--
  LE badge dont la teinte vient d'une TABLE — l'état d'une affaire, d'un compte,
  d'un accès, d'un import… : `<Badge teinte={STATUT_BADGE[s]}>{libelle}</Badge>`.

  POURQUOI CE COMPOSANT EXISTE (15/10/2026, #1571). `class="badge {expr}"` était
  écrit trente fois, dans vingt-quatre fichiers. Devant une classe interpolée, le
  compilateur Svelte cesse de déclarer les sélecteurs inutilisés POUR TOUT LE
  FICHIER : chacune de ces lignes rendait son écran aveugle à `lint:css-orphelin`.
  `BadgeVerdict` et `BadgeEtatService` posaient déjà la teinte par `class:` ;
  la règle s'écrit ici une fois, et l'interpolation n'existe plus nulle part.

  Les teintes sont celles des feuilles (`.badge-*`, `styles/composants.css`), et
  `npm run lint:badge` exige que les deux listes concordent. Une teinte inconnue
  rend la base `.badge` seule — exactement ce que rendait la classe interpolée —,
  et le même contrôle refuse qu'une teinte soit écrite sans règle (#1986).

  Les attributs (`title`, `aria-label`) passent tels quels sur le `<span>`.
-->
<script lang="ts">
	/** La teinte : une classe `badge-*`, telle que la rendent les tables d'états. */
	export let teinte: string | null | undefined = undefined;
	/** Un cran sous le corps du badge (`--fs-2xs`), pour une liste dense. */
	export let compact = false;
</script>

<span
	class="badge"
	class:badge-blue={teinte === 'badge-blue'}
	class:badge-gray={teinte === 'badge-gray'}
	class:badge-green={teinte === 'badge-green'}
	class:badge-orange={teinte === 'badge-orange'}
	class:badge-purple={teinte === 'badge-purple'}
	class:badge-red={teinte === 'badge-red'}
	class:badge-teal={teinte === 'badge-teal'}
	class:badge-yellow={teinte === 'badge-yellow'}
	class:compact
	{...$$restProps}><slot /></span
>

<style>
	.compact {
		font-size: var(--fs-2xs);
	}
</style>
