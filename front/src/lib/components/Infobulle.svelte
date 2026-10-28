<!--
  **L'infobulle** — une phrase qui s'ouvre AU TOUCHER, au clic et au clavier, sous
  l'élément qui la porte.

  ## Pourquoi un composant (15/10/2026)

  Au doigt il n'y a pas de survol : un `title` ne s'y montre jamais (leçon du
  07/09/2026, #1311). `PastilleLecture` avait donc écrit sa bulle — état, clic
  dehors, Échap, `aria-expanded`, style —, et la posture d'une installation en
  demandait une seconde (coches du registre). Une seule écriture ici, pour les deux.

  ## Ce qu'elle fait sans qu'on le demande

  - Le déclencheur est un VRAI `<button>` : Entrée et Espace l'ouvrent, il prend le
    focus, et son nom accessible (`libelle`) dit ce qu'il montre.
  - Elle se ferme au clic dehors, à Échap (le focus revient au bouton) et au
    défilement (`ux-patterns` §17). Échap passe par la pile de `#lib/couche`
    (`poserEchap`) : ouverte dans une modale, la bulle se ferme seule.
    ⚠️ Le bouton arrête la propagation de ses touches (Entrée ne doit pas
    déplier la carte) — SAUF Échap. `PastilleLecture` écrivait
    `on:keydown|stopPropagation` et écoutait Échap sur la fenêtre : la bulle ne
    se fermait pas quand le bouton avait le focus, c'est-à-dire chaque fois
    qu'on l'avait ouverte au clavier. Et `lint:couches` ne le voyait pas (le
    `=>` d'un gestionnaire coupait sa recherche). Le clic dehors s'écoute en CAPTURE : un autre
    déclencheur qui arrête la propagation (pour ne pas déplier sa carte) ferme
    quand même celle-ci — deux bulles ouvertes à la fois se recouvraient.
  - Elle naît du déclencheur (origine en haut, 96 % → 100 %, `--ease-out`) et se
    retourne vers la gauche quand elle sortirait de l'écran : jamais un défilement
    horizontal au téléphone.
  - Le déclencheur ne porte aucun style visible : ce qu'on met dans le slot garde
    le sien (un `.badge`, une coche). Une classe passée en prop obligerait à
    l'interpoler, et une seule interpolation rend `lint:css-orphelin` aveugle sur
    tout le fichier (voir `MedaillonRole`).

  UTILISATION :
    <Infobulle libelle="Qui la lit : Copropriétaires" titre="…au survol…">
      <span class="badge badge-blue">Copropriétaires</span>
      <svelte:fragment slot="bulle"><strong>…</strong> La phrase entière.</svelte:fragment>
    </Infobulle>
-->
<script lang="ts">
	import { onDestroy, tick } from 'svelte';
	import { poserEchap } from '#lib/couche.ts';

	/** Le nom accessible du déclencheur : ce qu'il montre, et son état. */
	export let libelle: string;
	/** À la souris, la même phrase au survol — elle évite le clic, sans remplacer la bulle. */
	export let titre = '';

	let ouverte = false;
	let aGauche = false;
	let racine: HTMLElement;
	let bouton: HTMLButtonElement;
	let bulle: HTMLElement;
	const id = `infobulle-${Math.random().toString(36).slice(2, 8)}`;

	async function basculer() {
		ouverte = !ouverte;
		if (!ouverte) return;
		aGauche = false;
		await tick();
		//  Marge de 8 px : la bulle ne touche jamais le bord de l'écran.
		aGauche = bulle.getBoundingClientRect().right > window.innerWidth - 8;
	}

	function clicDehors(e: MouseEvent) {
		if (ouverte && !racine.contains(e.target as Node)) ouverte = false;
	}

	function fermerAuClavier() {
		ouverte = false;
		bouton?.focus();
	}

	//  Échap n'appartient à la bulle que tant qu'elle est ouverte.
	let retirerEchap: (() => void) | null = null;
	$: if (ouverte && !retirerEchap) retirerEchap = poserEchap(fermerAuClavier);
	$: if (!ouverte && retirerEchap) {
		retirerEchap();
		retirerEchap = null;
	}
	onDestroy(() => retirerEchap?.());
</script>

<svelte:window on:click|capture={clicDehors} on:scroll={() => (ouverte = false)} />

<span class="infobulle" bind:this={racine}>
	<!--  Le clic ne déplie pas la carte qui la porte : la bulle est un geste à elle. -->
	<button
		bind:this={bouton}
		type="button"
		class="infobulle-bouton"
		aria-expanded={ouverte}
		aria-controls={id}
		aria-label={libelle}
		title={titre || undefined}
		on:click|stopPropagation={basculer}
		on:keydown={(e) => {
			if (e.key !== 'Escape') e.stopPropagation();
		}}
	>
		<slot />
	</button>
	<span
		bind:this={bulle}
		class="infobulle-bulle"
		class:infobulle-a-gauche={aGauche}
		{id}
		role="status"
		hidden={!ouverte}
	>
		<slot name="bulle" />
	</span>
</span>

<style>
	.infobulle {
		position: relative;
		display: inline-flex;
		min-width: 0;
		max-width: 100%;
	}
	.infobulle-bouton {
		display: inline-flex;
		align-items: center;
		min-width: 0;
		max-width: 100%;
		margin: 0;
		padding: 0;
		border: none;
		background: none;
		color: inherit;
		text-align: inherit;
		cursor: pointer;
		/*  `font-family` et non `font: inherit` : le raccourci réinitialisait la
		    taille et la graisse d'un `.badge` posé dedans (#1308). */
		font-family: inherit;
		line-height: inherit;
	}
	/*  La bulle reste dans la carte : ancrée sous le déclencheur, bornée à la
	    largeur de l'écran moins la gouttière. */
	.infobulle-bulle {
		position: absolute;
		top: calc(100% + 0.3rem);
		left: 0;
		z-index: 5;
		width: max-content;
		max-width: min(18rem, calc(100vw - 2rem));
		padding: 0.5rem 0.65rem;
		border: 1px solid var(--color-border);
		border-radius: var(--radius);
		background: var(--color-surface);
		box-shadow: var(--shadow);
		font-size: var(--fs-sm);
		font-weight: 400;
		line-height: 1.4;
		color: var(--color-text);
		text-align: left;
		white-space: normal;
		transform-origin: 0 0;
		animation: infobulle-entree var(--duree-apparition) var(--ease-out);
	}
	.infobulle-a-gauche {
		left: auto;
		right: 0;
		transform-origin: 100% 0;
	}
	.infobulle-bulle[hidden] {
		display: none;
	}
	.infobulle-bulle :global(strong) {
		display: block;
		margin-bottom: 0.15rem;
	}
	@keyframes infobulle-entree {
		from {
			opacity: 0;
			transform: scale(0.96) translateY(-4px);
		}
	}
	@media (prefers-reduced-motion: reduce) {
		.infobulle-bulle {
			animation: none;
		}
	}
</style>
