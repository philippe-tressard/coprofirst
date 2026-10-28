<!--
  Visionneuse plein écran — regarder une photo sans quitter l'application.

  Avant, une photo cliquée s'ouvrait via `<a target="_blank">` : on sortait de la
  PWA vers un onglet brut, et le retour ramenait sur une page dont l'article
  s'était refermé. Sur mobile, c'était le geste le plus coûteux de l'écran.

  Les photos sont déjà réduites à 1600 px au téléversement (`uploads._save_image`),
  il n'existe aucune miniature : le fichier affiché ici est celui que la vignette
  avait déjà téléchargé. Ouvrir en grand ne coûte donc aucun octet de plus.

  Props :
    - photos : URLs à parcourir
    - index  : photo affichée à l'ouverture
  Événement : `fermer`
-->
<script lang="ts">
	import { createEventDispatcher, onDestroy, tick } from 'svelte';
	import { poserCouche } from '$lib/couche';
	import { finDesAnimations, mouvementReduit } from '$lib/mouvement';

	export let photos: string[] = [];
	export let index = 0;

	const dispatch = createEventDispatcher();

	function fermer() {
		retirerCouche();
		dispatch('fermer');
	}

	function precedente() {
		index = (index - 1 + photos.length) % photos.length;
	}

	function suivante() {
		index = (index + 1) % photos.length;
	}

	//  ── Glissement (#334, puis #2169) ──────────────────────────────────────────
	//  `pointer*` couvre le doigt, le stylet et le glisser-souris d'un seul jeu
	//  d'écouteurs. Le geste ne lisait que son départ et son arrivée : la photo
	//  ne suivait pas le doigt, changeait d'un coup au lâcher, et un geste vif
	//  mais court ne comptait pas. Elle SUIT désormais le doigt (`transform`
	//  posé directement, jamais par une variable CSS héritée), et le lâcher
	//  décide sur la distance OU la vitesse ; la photo part du côté où le doigt
	//  la pousse, la suivante arrive de l'autre. Ce que le CSS anime, ses durées
	//  le disent (`--duree-apparition`) : le script ne fait qu'attendre.
	const AMORCE = 10; // px — en deçà, c'est un appui qui a tremblé, pas un glissement
	const SEUIL_GLISSEMENT = 45; // px — au-delà, la photo change, même lentement
	const VITESSE_JETEE = 0.11; // px/ms — un geste vif change de photo, même court
	const FENETRE_VITESSE = 100; // ms — la vitesse du lâcher, pas celle du geste entier
	let image: HTMLImageElement;
	let geste: {
		id: number;
		x0: number;
		dx: number;
		suit: boolean;
		trace: [number, number][];
	} | null = null;
	let aGlisse = false;
	/** La photo suit le doigt : aucune transition tant qu'il la tient. */
	let suit = false;

	/**
	 * PURE. Au-delà d'un bord, la photo résiste de plus en plus au lieu de
	 * s'arrêter net (apple-design §9) : seule, elle n'a nulle part où aller.
	 */
	function elastique(depasse: number, dimension: number, k = 0.55): number {
		return (depasse * dimension * k) / (dimension + k * Math.abs(depasse));
	}

	/** PURE. La vitesse au lâcher, en px/ms, sur les derniers instants du geste. */
	function vitesse(trace: [number, number][]): number {
		const fin = trace[trace.length - 1];
		const debut = trace.find(([, t]) => fin[1] - t <= FENETRE_VITESSE) ?? fin;
		return fin[1] === debut[1] ? 0 : (fin[0] - debut[0]) / (fin[1] - debut[1]);
	}

	function debutGeste(e: PointerEvent) {
		//  Un second doigt n'enlève pas la photo au premier ; un bouton garde son clic.
		if (!e.isPrimary || geste || (e.target as Element).closest('button')) return;
		geste = {
			id: e.pointerId,
			x0: e.clientX,
			dx: 0,
			suit: false,
			trace: [[e.clientX, e.timeStamp]],
		};
		aGlisse = false;
	}

	function suiteGeste(e: PointerEvent) {
		if (!geste || e.pointerId !== geste.id) return;
		geste.dx = e.clientX - geste.x0;
		geste.trace.push([e.clientX, e.timeStamp]);
		if (!geste.suit && Math.abs(geste.dx) < AMORCE) return;
		if (!geste.suit) {
			geste.suit = true;
			(e.currentTarget as Element).setPointerCapture(e.pointerId);
			suit = true;
		}
		const dx = photos.length < 2 ? elastique(geste.dx, window.innerWidth) : geste.dx;
		image.style.transform = `translateX(${dx}px)`;
	}

	async function finGeste(e: PointerEvent) {
		if (!geste || e.pointerId !== geste.id) return;
		//  L'instant du lâcher compte : un doigt qui s'est arrêté avant de lâcher n'a plus d'élan.
		geste.trace.push([e.clientX, e.timeStamp]);
		const { dx, suit: suivait, trace } = geste;
		geste = null;
		if (!suivait) return;
		aGlisse = true;
		suit = false;
		const v = vitesse(trace);
		const change =
			photos.length > 1 &&
			(Math.abs(dx) >= SEUIL_GLISSEMENT ||
				(Math.abs(v) > VITESSE_JETEE && Math.sign(v) === Math.sign(dx)));
		if (!change) {
			image.style.transform = ''; // elle revient, en partant d'où elle est
			return;
		}
		await changer(dx > 0 ? -1 : 1);
	}

	function abandonGeste() {
		geste = null;
		suit = false;
		if (image) image.style.transform = '';
	}

	/** La photo sort du côté où on la pousse ; la voisine entre de l'autre. */
	async function changer(sens: 1 | -1) {
		const reduit = mouvementReduit();
		image.style.opacity = '0';
		if (!reduit) image.style.transform = `translateX(${-sens * window.innerWidth}px)`;
		await finDesAnimations(image);
		sens > 0 ? suivante() : precedente();
		await tick();
		//  Placée de l'autre côté sans transition, puis rendue à sa place.
		suit = true;
		image.style.transform = reduit ? '' : `translateX(${sens * 25}%)`;
		await tick();
		void image.offsetWidth;
		suit = false;
		await tick();
		image.style.transform = '';
		image.style.opacity = '';
	}

	//  Un glissement amorcé sur le fond produit AUSSI un `click` en fin de geste :
	//  sans ce garde-fou, naviguer d'une photo à l'autre refermerait la visionneuse.
	function fondClique(e: MouseEvent) {
		if (aGlisse) {
			aGlisse = false;
			return;
		}
		if (e.target === e.currentTarget) fermer();
	}

	//  Précharger les voisines : il n'existe aucune miniature côté serveur, chaque
	//  photo pèse jusqu'à 1600 px. Sans cela, chaque flèche ouvre sur un cadre vide
	//  le temps du téléchargement — c'est ce qui fait paraître l'écran lent.
	$: if (typeof Image !== 'undefined' && photos.length > 1) {
		for (const decalage of [-1, 1]) {
			const voisine = photos[(index + decalage + photos.length) % photos.length];
			if (voisine) new Image().src = voisine;
		}
	}

	function auClavier(e: KeyboardEvent) {
		if (e.key === 'ArrowLeft' && photos.length > 1) precedente();
		else if (e.key === 'ArrowRight' && photos.length > 1) suivante();
	}

	//  Défilement du fond et Échap : `$lib/couche.ts`, partagé avec `Modale`.
	//  Ouverte depuis une modale, la visionneuse ne rend plus le défilement en se
	//  fermant, et Échap ne ferme qu'elle (#1042). Posée au montage et non dans
	//  un `on:click` : elle s'ouvre au clavier comme à la souris.
	const retirerCouche = poserCouche(fermer);
	onDestroy(retirerCouche);
</script>

<svelte:window on:keydown={auClavier} />

<div
	class="lb-fond"
	role="dialog"
	aria-modal="true"
	aria-label="Photo en plein écran"
	tabindex="-1"
	on:click={fondClique}
	on:keydown={(e) =>
		(e.key === 'Enter' || e.key === ' ') && e.target === e.currentTarget && fermer()}
	on:pointerdown={debutGeste}
	on:pointermove={suiteGeste}
	on:pointerup={finGeste}
	on:pointercancel={abandonGeste}
>
	<button class="lb-fermer" aria-label="Fermer la photo" on:click|stopPropagation={fermer}>×</button
	>

	{#if photos.length > 1}
		<button
			class="lb-nav lb-prec"
			aria-label="Photo précédente"
			on:click|stopPropagation={precedente}>‹</button
		>
		<button class="lb-nav lb-suiv" aria-label="Photo suivante" on:click|stopPropagation={suivante}
			>›</button
		>
	{/if}

	<!-- Aucun écouteur sur l'image : la fermeture ne se déclenche que si la cible
	     du clic est le fond LUI-MÊME (`e.target === e.currentTarget`). Cliquer la
	     photo ne referme donc pas, sans avoir à poser un `stopPropagation` sur un
	     élément non interactif — ce que l'analyse d'accessibilité refuse à juste
	     titre : un lecteur d'écran annoncerait une image cliquable qui n'est pas
	     une commande. -->
	<img
		bind:this={image}
		class="lb-image"
		class:lb-suit={suit}
		src={photos[index]}
		alt="Photo {index + 1} sur {photos.length}"
		draggable="false"
	/>

	{#if photos.length > 1}
		<p class="lb-compteur">{index + 1} / {photos.length}</p>
	{/if}
</div>

<style>
	.lb-fond {
		position: fixed;
		inset: 0;
		z-index: 200;
		background: rgba(0, 0, 0, 0.88);
		display: flex;
		align-items: center;
		justify-content: center;
		padding: 1rem;
		/*  Le glissement horizontal est à la visionneuse ; le pincement reste au
		    navigateur (agrandir une photo). Sans cette ligne, le navigateur
		    prenait le geste pour lui et l'annulait (`pointercancel`). */
		touch-action: pan-y pinch-zoom;
	}
	.lb-image {
		max-width: 100%;
		max-height: 92vh;
		object-fit: contain;
		border-radius: 4px;
		cursor: default;
		user-select: none;
		transition:
			transform var(--duree-apparition) var(--ease-out),
			opacity var(--duree-apparition) var(--ease-out);
	}
	/*  Pendant que le doigt la tient, elle le suit sans retard : aucune transition. */
	.lb-image.lb-suit {
		transition: none;
	}
	/*  Mouvement réduit : la photo suit encore le doigt (c'est lui qui la
	    déplace), mais le changement se fait en fondu, sans glissement. */
	@media (prefers-reduced-motion: reduce) {
		.lb-image {
			transition: opacity var(--duree-apparition) var(--ease-out);
		}
	}
	.lb-fermer,
	.lb-nav {
		position: absolute;
		background: rgba(0, 0, 0, 0.45);
		color: var(--color-sur-voile);
		border: none;
		border-radius: 50%;
		cursor: pointer;
		line-height: 1;
		display: flex;
		align-items: center;
		justify-content: center;
	}
	/*  44 px partout : cible tactile minimale (standards/11 §10). Le bouton de
	    fermeture était à 40 px — mesuré en vérification mobile, donc corrigé. Sur
	    téléphone, c'est le bouton le plus utilisé de cet écran. */
	.lb-fermer {
		top: 1rem;
		right: 1rem;
		width: 44px;
		height: 44px;
		font-size: var(--fs-chiffre);
	}
	.lb-nav {
		top: 50%;
		transform: translateY(-50%);
		width: 44px;
		height: 44px;
		font-size: 2rem;
	}
	.lb-prec {
		left: 0.75rem;
	}
	.lb-suiv {
		right: 0.75rem;
	}
	@media (hover: hover) and (pointer: fine) {
		.lb-fermer:hover,
		.lb-nav:hover {
			background: rgba(0, 0, 0, 0.75);
		}
	}
	.lb-compteur {
		position: absolute;
		bottom: 1rem;
		left: 50%;
		transform: translateX(-50%);
		margin: 0;
		color: var(--color-sur-voile);
		font-size: var(--fs-md);
		background: rgba(0, 0, 0, 0.45);
		padding: 0.2rem 0.7rem;
		border-radius: 999px;
	}
</style>
