<!--
  **Le fil d'activité** — des cartes `FluxCard` groupées sous l'intitulé de
  leur jour.

  🔴 Plus de ligne de temps depuis le 10/10/2026 (maquette B du fil, choisie à
  l'écran) : chaque carte a la gouttière du site, qui dit l'HEURE puis la
  rubrique — le jour étant l'intitulé du groupe. Le trait vertical et ses
  puces de couleur disaient la même chose une seconde fois. Le nom du composant
  est resté ; la frise, c'est désormais la colonne des heures.

  ## Pourquoi ce composant (#779, 01/10/2026)

  La boucle « intitulé du jour, puis ses cartes, chacune dépliable et
  retirable » était écrite deux fois — le fil récent de l'accueil et
  `ArchivesDuFil` —, et une troisième fois sans intitulé pour le bandeau
  Épinglé. Trois copies du même câblage de `FluxCard` (clé, dépliage, retrait)
  qui devaient rester d'accord sans rien pour le vérifier.

  ## Trois variantes, une frise

  | `variante` | Où | Ce qui diffère |
  |---|---|---|
  | `fil` | le fil récent de l'accueil | rien |
  | `archives` | `ArchivesDuFil` | chaque carte a l'allure archivée (`CarteListe archive`) |
  | `epingle` | le bandeau Épinglé | un seul groupe, sans intitulé : la gouttière y dit la DATE, pas l'heure |

  Un groupe sans intitulé (`label: null`) n'en affiche pas : c'est le cas du
  bandeau Épinglé, qui n'a qu'un groupe. Ses cartes disent alors la date, et
  non l'heure : sans intitulé, rien ne dirait le jour (12/10/2026).

  L'intitulé du jour (`.flux-day-label`) vit dans la charte (`composants.css`) ;
  la clé d'une carte, dans `cleFluxItem` (`#lib/flux`).
-->
<script lang="ts">
	import FluxCard from '#lib/components/FluxCard.svelte';
	import { cleFluxItem, type GroupeDuFil } from '#lib/flux.ts';

	export let groupes: GroupeDuFil[] = [];
	export let variante: 'fil' | 'archives' | 'epingle' = 'fil';
	/**  ⚠️ Une CHAÎNE (`pub-12`, `ticket-7`) : le fil mêle plusieurs tables, dont
	 *   les identifiants numériques se recouvrent. */
	export let itemDeplie: string | null = null;
	export let onBasculer: (id: string) => void;
	/**  Retirer une carte du fil. La frise ne le fait pas elle-même : elle n'a
	 *   ni la liste ni le droit d'écrire. */
	export let onMasquer: (id: string) => void = () => {};
</script>

<div class="flux-groupes">
	{#each groupes as groupe (groupe.label)}
		{#if groupe.label}<div class="flux-day-label">{groupe.label}</div>{/if}
		{#each groupe.items as item (cleFluxItem(item))}
			<FluxCard
				{item}
				heure={groupe.label !== null}
				expanded={itemDeplie === item.id}
				archive={variante === 'archives'}
				on:toggle={(e) => onBasculer(e.detail)}
				on:masquer={(e) => onMasquer(e.detail)}
			/>
		{/each}
	{/each}
</div>
