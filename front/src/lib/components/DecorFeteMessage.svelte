<!--
  Le MESSAGE de fête (#2312, révision du 30/10/2026 : le « reflet qui balaie »).

  Le décor ne change pas, et le message n'en dépend plus : il a sa place, fixe,
  sous le décor et aligné à droite, et son propre cycle — environ toutes les
  45 s, la première fois au plus tôt 8 s après le chargement. Pendant qu'il est
  visible, un éclat à la couleur de la fête (`REFLETS`, `#lib/decor-fetes`)
  traverse le texte, de droite à gauche.

  - Le texte : `messageDeFete` (`#lib/fetes`), au jour de Paris.
  - Rien en mouvement réduit ni sur mobile ; le cycle s'arrête quand l'onglet est
    masqué. Service coupé : `DecorFete` n'est pas rendu, ce composant non plus.
  - L'opacité, l'`aria-hidden` et le `pointer-events` sont ceux du décor, qui
    l'enveloppe. Feuille : celle de `DecorFete` (`styles/decor-fete.css`).
-->
<script lang="ts">
	import { onMount } from 'svelte';
	import { messageDeFete, type CodeFete } from '#lib/fetes.ts';
	import { degradeReflet } from '#lib/decor-fetes.ts';
	import { mouvementReduit } from '#lib/mouvement.ts';

	export let fete: CodeFete;
	export let jour: string;

	//  Le rythme du message — un tempo, pas la durée d'une animation : le fondu
	//  et le reflet, eux, se lisent dans la feuille.
	const PREMIERE_MS = 8_000;
	const CYCLE_MS = 45_000;
	const LECTURE_MS = 4_000;
	/** Comme la feuille du décor : ni mobile ni mouvement réduit. */
	const MOBILE = '(max-width: 767px)';

	let actif = false;
	let visible = false;
	let minuteur: ReturnType<typeof setTimeout> | undefined;

	function plusTard(ms: number, geste: () => void) {
		clearTimeout(minuteur);
		minuteur = setTimeout(geste, ms);
	}

	function montrer() {
		visible = true;
		plusTard(LECTURE_MS, () => {
			visible = false;
			plusTard(CYCLE_MS - LECTURE_MS, montrer);
		});
	}

	/** Onglet masqué : le message s'efface, le cycle repart au retour. */
	function surVisibilite() {
		clearTimeout(minuteur);
		visible = false;
		if (!document.hidden) plusTard(PREMIERE_MS, montrer);
	}

	onMount(() => {
		if (mouvementReduit() || window.matchMedia?.(MOBILE).matches) return;
		actif = true;
		document.addEventListener('visibilitychange', surVisibilite);
		plusTard(PREMIERE_MS, montrer);
		return () => {
			clearTimeout(minuteur);
			document.removeEventListener('visibilitychange', surVisibilite);
		};
	});
</script>

{#if actif}
	<span class="message-fete" class:visible style:--reflet={degradeReflet(fete)}
		>{messageDeFete(fete, jour)}</span
	>
{/if}
