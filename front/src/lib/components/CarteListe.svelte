<!--
  CarteListe.svelte — **le conteneur de TOUTE carte de liste du site** : la
  boîte `.carte-liste`, sa gouttière, son geste de dépliage et ses états
  (déplié, urgent, archivé). Une carte ne les écrit plus : elle les déclare.

  ## 🔴 Pourquoi (10/10/2026, demandé à l'écran)

  « Toute cette normalisation des cartes et gouttières, standardise-la dans un
  objet pour avoir toujours le même comportement, quelle que soit son
  occurrence. » La veille de cette demande, la page Affaires était devenue le
  standard du site (#1819) : quatorze cartes recopiaient le même conteneur —
  `class="carte-liste a-gouttiere"`, `role="presentation"`, le clic qui déplie
  une carte repliée, `<Gouttiere>` en premier enfant. Et une gouttière sortait
  par le bas d'une carte courte : elle était posée en absolu, le correctif a dû
  passer par chaque copie.

  Les copies avaient DIVERGÉ là où rien ne se voit — l'état « archivé » :

  | | rendu | revient à l'opacité pleine |
  |---|---|---|
  | annonce (`.attenue`) | 0,8 | au survol |
  | actualité (`.attenue`) | 0,8 | au survol, et dépliée |
  | contrat, prestataire (`.attenue`) | 0,8 | dépliée (la classe tombait) |
  | question de FAQ inactive (`.item-inactive`) | 0,55 | jamais |
  | affaire archivée (`.history-item`, sans `.carte-liste`) | 0,8, liseré gris, sans le filet | au survol, et dépliée |

  Retenu : la forme la plus disante, celle de l'actualité et de l'affaire —
  0,8, pleine au survol (au pointeur seulement) et une fois dépliée. Elle vit
  dans `normes.css` (`.carte-liste.attenue`), et la carte la demande par
  `archive`.

  ## Ce que la carte porte, et ce que chaque objet déclare

  | Porté ici | Déclaré par l'appelant |
  |---|---|
  | `.carte-liste`, et `.a-gouttiere` dès qu'il y a une gouttière | rien : la colonne naît de `quand`, `classe` ou du créneau `gouttiere` |
  | la gouttière (`Gouttiere`) : QUAND, puis ce qui CLASSE | `quand`, `classe` ; `heure` quand le jour est l'intitulé du groupe (le fil) ; le créneau `gouttiere` (le vote d'une idée) |
  | le geste ASYMÉTRIQUE (`ux-patterns` §3) : repliée, toute la carte ouvre | `onDeplier` — absent, la carte ne se déplie pas (idée, sondage, relevé) |
  | ce qui ANNONCE le dépliage : l'appui, le survol à la souris, le focus | `onApprocher` — précharger un corps différé (#1860) |
  | déplié, urgent, archivé | `expanded`, `urgent`, `archive` |
  | l'ancre des liens profonds | `id` |
  | — | ses classes propres (`class`) et ses attributs (`data-nature`…), transmis |

  ⚠️ Le reste — `EnteteCarte`, le corps `.carte-corps` — se rend dans le
  créneau par défaut : ce sont des enfants DIRECTS de la carte, ce que la
  grille de `.a-gouttiere` attend (`normes.css`).

  ⚠️ Une classe passée par `class` vit dans CE composant : le `<style>` de
  l'appelant ne l'atteint qu'en `:global(…)`. C'est pourquoi les teintes et les
  états de carte sont dans `normes.css`, pas chez chaque carte.

  🔒 `npm run lint:carte-liste` refuse le conteneur, la gouttière ou un état de
  carte écrits ailleurs qu'ici.
-->
<script lang="ts">
	import Gouttiere from './Gouttiere.svelte';
	import type { ClasseGouttiere } from '#lib/gouttiere.ts';

	/** L'ancre de la carte (`ticket-42`) : liens profonds, 🔗, fil d'activité. */
	export let id: string | undefined = undefined;
	/** La date qui SITUE l'objet (ISO), en tête de la gouttière — ou rien. */
	export let quand: string | null | undefined = null;
	/** Ce qui le classe, sous la date — ou rien. */
	export let classe: ClasseGouttiere | null = null;
	/** La gouttière dit l'HEURE de `quand`, le jour étant l'intitulé du groupe (le fil). */
	export let heure = false;
	export let expanded = false;
	export let urgent = false;
	/** Rendue aux Archives (ou retirée) : la carte s'efface tant qu'on ne la vise pas. */
	export let archive = false;
	/**  Ce que fait un clic sur la carte REPLIÉE — rien quand elle est dépliée :
	 *   seul son titre la replie (`EnteteCarte basculable`). Absent, la carte ne
	 *   se déplie pas. */
	export let onDeplier: (() => void) | null = null;
	/**  Appelé quand la main s'APPROCHE d'une carte repliée — l'appui (avant le
	 *   clic), le survol à la souris, le focus au clavier : la carte y précharge
	 *   ce que son dépliage affichera (#1860), pour que le corps n'attende pas un
	 *   aller-retour. Le survol au doigt n'existe pas : le tactile passe par l'appui. */
	export let onApprocher: (() => unknown) | null = null;
	//  Un préchargement qui échoue se TAIT : le dépliage, lui, le dira
	//  (`ChargementDiffere`). Sans ce `catch`, le rejet sortirait en exception
	//  de la page — hors ligne, au simple survol d'une carte.
	const approcher = () => {
		if (expanded || !onApprocher) return;
		Promise.resolve(onApprocher()).catch(() => {});
	};
	let classes = '';
	export { classes as class };

	$: gouttiere = !!(quand || classe || $$slots.gouttiere);
</script>

<div
	{id}
	class="carte-liste {classes}"
	class:a-gouttiere={gouttiere}
	class:expanded
	class:urgent
	class:attenue={archive}
	role="presentation"
	{...$$restProps}
	on:click={() => {
		if (!expanded) onDeplier?.();
	}}
	on:pointerdown={approcher}
	on:pointerenter={(e) => e.pointerType === 'mouse' && approcher()}
	on:focusin={approcher}
>
	{#if gouttiere}
		<Gouttiere {quand} {classe} {heure}><slot name="gouttiere" /></Gouttiere>
	{/if}
	<slot />
</div>
