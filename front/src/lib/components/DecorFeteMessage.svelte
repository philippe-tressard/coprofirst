<!--
  Le MESSAGE de fête (#2312, proposition n° 3 arbitrée le 30/10/2026).

  Le décor ne change pas : l'élément qui bouge déjà (`PAUSES`, `#lib/decor-fetes`)
  marque une pause, et le message apparaît en fondu là où il s'est arrêté, puis
  s'efface et le mouvement reprend. Environ toutes les 45 s, la première fois au
  plus tôt 8 s après le chargement.

  - Le texte : `messageDeFete` (`#lib/fetes`), au jour de Paris.
  - Rien en mouvement réduit ni sur mobile ; le cycle s'arrête quand l'onglet est
    masqué. Service coupé : `DecorFete` n'est pas rendu, ce composant non plus.
  - L'opacité, l'`aria-hidden` et le `pointer-events` sont ceux du décor, qui
    l'enveloppe. Feuille : celle de `DecorFete` (`styles/decor-fete.css`).
-->
<script lang="ts">
	import { onMount, tick } from 'svelte';
	import { messageDeFete, type CodeFete } from '#lib/fetes.ts';
	import { PAUSES } from '#lib/decor-fetes.ts';
	import { finDesAnimations, mouvementReduit } from '#lib/mouvement.ts';

	export let fete: CodeFete;
	export let jour: string;
	/** Le décor, où vivent l'élément qui bouge et le message. */
	export let racine: HTMLElement;

	//  Le rythme du message — un tempo, pas la durée d'une animation : le fondu,
	//  lui, se lit dans la charte (`--duree-apparition`).
	const PREMIERE_MS = 8_000;
	const CYCLE_MS = 45_000;
	/** L'élément s'arrête un instant avant que le message n'apparaisse. */
	const ARRET_MS = 600;
	const LECTURE_MS = 2_500;
	/** Comme la feuille du décor : ni mobile ni mouvement réduit. */
	const MOBILE = '(max-width: 767px)';

	let texte = '';
	let x = 0;
	let y = 0;
	let visible = false;
	let bulle: HTMLElement | undefined;
	let minuteur: ReturnType<typeof setTimeout> | undefined;
	let arretees: Animation[] = [];

	const modulo = (n: number) => ((n % 1) + 1) % 1;

	function plusTard(ms: number, geste: () => void) {
		clearTimeout(minuteur);
		minuteur = setTimeout(geste, ms);
	}

	/** Attend l'instant où l'élément qui bouge atteint son arrêt. */
	function attendreArret() {
		const { cible, phase } = PAUSES[fete];
		const element = racine.querySelector(cible);
		const animation = element?.getAnimations()[0];
		const temps = animation?.effect?.getComputedTiming();
		const duree = Number(temps?.duration);
		if (!element || !temps || !(duree > 0)) return plusTard(CYCLE_MS, attendreArret);
		const ecoule = modulo((Number(temps.localTime) - Number(temps.delay ?? 0)) / duree);
		plusTard(modulo(phase - ecoule) * duree, () => arreter(element));
	}

	function arreter(element: Element) {
		arretees = element.getAnimations();
		arretees.forEach((a) => a.pause());
		const r = element.getBoundingClientRect();
		const cadre = racine.getBoundingClientRect();
		x = r.left + r.width / 2 - cadre.left;
		y = r.top + r.height / 2 - cadre.top;
		texte = messageDeFete(fete, jour);
		plusTard(ARRET_MS, () => {
			visible = true;
			plusTard(LECTURE_MS, effacer);
		});
	}

	async function effacer() {
		visible = false;
		await tick();
		if (bulle) await finDesAnimations(bulle);
		reprendre();
		plusTard(CYCLE_MS, attendreArret);
	}

	function reprendre() {
		arretees.forEach((a) => a.play());
		arretees = [];
	}

	/** Onglet masqué : tout s'arrête, le mouvement reprend, le cycle repart au retour. */
	function surVisibilite() {
		clearTimeout(minuteur);
		visible = false;
		reprendre();
		if (!document.hidden) plusTard(CYCLE_MS, attendreArret);
	}

	onMount(() => {
		if (mouvementReduit() || window.matchMedia?.(MOBILE).matches) return;
		document.addEventListener('visibilitychange', surVisibilite);
		plusTard(PREMIERE_MS, attendreArret);
		return () => {
			clearTimeout(minuteur);
			document.removeEventListener('visibilitychange', surVisibilite);
			reprendre();
		};
	});
</script>

{#if texte}
	<span bind:this={bulle} class="message-fete" class:visible style:left="{x}px" style:top="{y}px"
		>{texte}</span
	>
{/if}
