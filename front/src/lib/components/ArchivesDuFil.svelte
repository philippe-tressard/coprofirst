<!--
  **Les Archives du fil d'activité** — ce qui a plus de trente jours, replié,
  groupé par JOUR.

  ## Pourquoi ce composant (#516)

  Extrait de `tableau-de-bord/+page.svelte` quand le garde-fou de modularité a
  refusé qu'elle grossisse (#453). Ce bloc est aussi celui que #516 touche :
  autant qu'il vive à l'endroit dont il porte le nom.

  ## 🔴 Le mot est commun, le rendu ne l'est PAS — et c'est déclaré

  Cinq écrans ont adopté `ArchivesParAnnee` le 20/08 (Actualités, Tickets,
  Espace CS, Petites annonces, Accès & sécurité). Celui-ci non, et le calendrier
  non plus : ils groupent autrement.

  | Écran | Groupement | Pourquoi |
  |---|---|---|
  | les cinq | par **année** | des objets qu'on retrouve par millésime |
  | Calendrier | année ▸ **mois** | trois types mêlés sur une échelle longue |
  | **ici** | par **jour** | un fil d'activité SE LIT par jour — l'année y masquerait ce qui fait tout son intérêt |

  ⚠️ Ce qui est commun, et doit le rester : le **mot**, qui vient de
  `TITRE_ARCHIVES`. Le ticket demandait d'unifier le vocabulaire ; le rendu suit
  la nature de ce qu'il montre, à condition de le DIRE — c'est ce que fait ce
  commentaire, et ce qui distingue une divergence assumée d'un oubli.

  ## La frise est dans la CHARTE, plus recopiée ici

  🔴 Ce paragraphe disait l'inverse jusqu'au 31/08/2026 : *« `.flux-timeline` et
  `.flux-day-label` sont **recopiées** depuis la page […] les remonter en ferait
  des règles globales pour deux usages sans raison de rester identiques »*.

  Elles avaient TOUTES les raisons de rester identiques — c'est la même frise, vue
  à deux endroits. `lint:charte` l'a établi le jour où elles sont montées dans
  `composants.css` : les copies d'ici redéfinissaient dix propriétés, **toutes
  identiques**, donc dix règles qui ne servaient à rien.

  ⚠️ La justification était vraie sur son premier terme (Svelte scope au fichier)
  et fausse sur sa conclusion. Une duplication déclarée reste une duplication : la
  déclarer dit qu'on l'a vue, pas qu'elle est saine.

  Ce qui reste ici est ce qui DIFFÈRE : l'atténuation qui distingue l'archive
  du fil vivant — devenue la variante `archives` de `FriseDuFil` (#779,
  01/10/2026), quand la boucle des cartes, écrite ici ET dans la page, a
  rejoint la frise.
-->
<script lang="ts">
	import SectionRepliee from '#lib/components/SectionRepliee.svelte';
	import FriseDuFil from '#lib/components/FriseDuFil.svelte';
	import { TITRE_ARCHIVES } from '#lib/archives.ts';
	import type { GroupeDuFil } from '#lib/flux.ts';

	/** Les éléments archivés, déjà groupés par jour (`grouperParJour`). */
	export let groupesParJour: GroupeDuFil[] = [];
	/** Combien d'éléments au total — affiché sur le bandeau. */
	export let compte = 0;
	/** Lié : la page anime la section selon son ordre d'apparition. */
	export let ouvert = false;
	/**  ⚠️ L'identifiant d'un élément du fil est une CHAÎNE, pas un nombre : il
	 *   préfixe le type (`pub-12`, `ticket-7`) parce que le fil mêle plusieurs
	 *   entités et que leurs identifiants numériques se recouvrent. Je l'avais
	 *   typé `number` par réflexe — `svelte-check` l'a refusé. */
	export let itemDeplie: string | null = null;
	export let onBasculer: (id: string) => void;
	/**  Retirer une carte du fil. Le composant ne le fait pas lui-même : il n'a
	 *   ni la liste ni le droit d'écrire. Même contrat que `onBasculer`. */
	export let onMasquer: (id: string) => void = () => {};
</script>

<SectionRepliee titre={TITRE_ARCHIVES} {compte} bind:ouvert />
{#if ouvert}
	<FriseDuFil groupes={groupesParJour} variante="archives" {itemDeplie} {onBasculer} {onMasquer} />
{/if}
