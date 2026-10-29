<script module lang="ts">
	import { tick } from 'svelte';
	import { get, writable } from 'svelte/store';

	export interface ToastMessage {
		id: number;
		type: 'success' | 'error' | 'info' | 'warning';
		message: string;
		/** Il s'en va : la classe `sortant` joue sa sortie, `retirer` l'ôte ensuite. */
		sortant?: boolean;
	}

	export const toasts = writable<ToastMessage[]>([]);

	//  🔴 Une ERREUR reste jusqu'à ce qu'on la ferme (#2168, audit `apple-design`) :
	//  partie au bout de 4 s, elle n'était lue que par qui la regardait à cet
	//  instant (WCAG 2.2.1). Trois au plus : la quatrième pousse la plus ancienne.
	const PERSISTANTS: ReadonlySet<ToastMessage['type']> = new Set(['error', 'warning']);
	const PERSISTANTS_MAX = 3;

	let counter = 0;
	/** Les comptes à rebours des messages qui partent seuls : restant, et départ s'il court. */
	const minuteries = new Map<number, { restant: number; depuis: number | null; h?: number }>();
	let suspendu = false;

	function demarrer(id: number) {
		const m = minuteries.get(id);
		if (!m || m.depuis !== null) return;
		m.depuis = Date.now();
		m.h = window.setTimeout(() => fermer(id), m.restant);
	}

	//  🔴 Un message SIMPLE, à une place fixe (arbitré le 26/09/2026). La suite
	//  d'un geste sur un élément naît de l'élément (`BoutonLien`) : ce n'est pas
	//  un message, et ce toast n'en porte plus — il l'a porté un jour (#1357).
	export function toast(type: ToastMessage['type'], message: string, duration = 4000) {
		const liste = get(toasts);
		//  Le même message déjà affiché ne s'empile pas une seconde fois.
		if (liste.some((t) => !t.sortant && t.type === type && t.message === message)) return;
		const id = ++counter;
		toasts.update((t) => [...t, { id, type, message }]);
		if (PERSISTANTS.has(type)) {
			const restants = liste.filter((t) => !t.sortant && PERSISTANTS.has(t.type));
			if (restants.length >= PERSISTANTS_MAX) fermer(restants[0].id);
			return;
		}
		minuteries.set(id, { restant: duration, depuis: null });
		if (!suspendu) demarrer(id);
	}

	/** Le message s'en va par le chemin de son entrée ; `retirer` suit. */
	export function fermer(id: number) {
		const m = minuteries.get(id);
		if (m?.h) clearTimeout(m.h);
		minuteries.delete(id);
		toasts.update((t) => t.map((x) => (x.id === id ? { ...x, sortant: true } : x)));
	}

	function retirer(id: number) {
		toasts.update((t) => t.filter((x) => x.id !== id));
	}

	/** Survol, focus, onglet caché : les comptes à rebours s'arrêtent tous. */
	function suspendre() {
		suspendu = true;
		for (const m of minuteries.values()) {
			if (m.depuis === null) continue;
			clearTimeout(m.h);
			m.restant -= Date.now() - m.depuis;
			m.depuis = null;
		}
	}

	function reprendre() {
		suspendu = false;
		for (const id of minuteries.keys()) demarrer(id);
	}
</script>

<script lang="ts">
	import { onMount } from 'svelte';
	import IconeAction from '#lib/components/IconeAction.svelte';
	import { finDesAnimations } from '#lib/mouvement.ts';

	onMount(() => {
		const visibilite = () => (document.hidden ? suspendre() : reprendre());
		document.addEventListener('visibilitychange', visibilite);
		return () => document.removeEventListener('visibilitychange', visibilite);
	});

	/**
	 *  La sortie s'achève quand ses animations sont finies ou annulées —
	 *  `finDesAnimations` dit pourquoi on ne guette pas `transitionend`.
	 */
	function sortie(noeud: HTMLElement, t: ToastMessage) {
		return {
			async update(n: ToastMessage) {
				if (!n.sortant || t.sortant) return (t = n);
				t = n;
				await tick();
				await finDesAnimations(noeud);
				retirer(n.id);
			},
		};
	}
</script>

<!--  Chaque message porte SON rôle : `alert` pour une erreur, annoncée sur-le-champ,
      `status` pour le reste, annoncé à la pause suivante (#2168). Le conteneur n'en
      impose plus aucun : chaque toast portait `role="alert"` dans un conteneur
      `aria-live="polite"`, deux politiques contradictoires pour le même message. -->
<section
	class="toast-container"
	aria-label="Messages"
	on:mouseenter={suspendre}
	on:mouseleave={reprendre}
	on:focusin={suspendre}
	on:focusout={reprendre}
>
	{#each $toasts as t (t.id)}
		<!--  🔴 Quatre `class:` plutôt que `class="toast toast-{t.type}"` (#810).
		      Ce n'est pas un goût : devant une classe INTERPOLÉE, Svelte cesse de
		      déclarer les sélecteurs inutilisés **pour tout le fichier**, et
		      `lint:css-orphelin` devient aveugle sur l'écran entier. Mesuré :
		      une règle morte ajoutée ici n'était pas signalée avant, elle l'est
		      maintenant.

		      ⚠️ La conversion ne vaut QUE parce que les quatre classes sont
		      locales et connues. Là où l'interpolation vient d'une table de
		      correspondance (`badge {STATUT_BADGE[…]}`), l'éclater en `class:`
		      recopierait la table dans le balisage — c'est-à-dire exactement ce
		      que la table supprime. Ces fichiers-là restent déclarés non
		      mesurables, avec leur raison. -->
		<div
			class="toast"
			class:toast-success={t.type === 'success'}
			class:toast-error={t.type === 'error'}
			class:toast-warning={t.type === 'warning'}
			class:toast-info={t.type === 'info'}
			class:sortant={t.sortant}
			role={t.type === 'error' ? 'alert' : 'status'}
			use:sortie={t}
		>
			<span class="toast-texte">{t.message}</span>
			<button
				type="button"
				class="btn-icon toast-fermer"
				aria-label="Fermer le message"
				on:click={() => fermer(t.id)}><IconeAction icone="x" /></button
			>
		</div>
	{/each}
</section>

<style>
	.toast-container {
		position: fixed;
		bottom: 5rem;
		right: 1rem;
		z-index: 9999;
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
		max-width: 340px;
	}
	/*  Au téléphone, en bas au CENTRE : à portée du pouce, la même place pour tous
	    (le standard des « snackbars »). Il monte par le bas, et repart par le bas. */
	@media (max-width: 767px) {
		.toast-container {
			left: 1rem;
			max-width: none;
			align-items: center;
		}
		.toast {
			animation-name: monte;
		}
		.toast.sortant {
			transform: translateY(8px);
		}
	}
	@keyframes monte {
		from {
			opacity: 0;
			transform: translateY(8px);
		}
	}

	.toast {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		padding: 0.5rem 0.5rem 0.5rem 1rem;
		border-radius: var(--radius);
		font-size: var(--fs-base);
		box-shadow: var(--shadow);
		/*  Jetons du site : 200 ms, courbe « ease-out » forte (`emil-design-eng`).
		    L'ENTRÉE par une animation au montage, la SORTIE par une transition :
		    elle repart d'où le message se trouve, même s'il entrait encore. */
		animation: slide-in var(--duree-apparition) var(--ease-out);
		transition:
			opacity var(--duree-apparition) var(--ease-out),
			transform var(--duree-apparition) var(--ease-out);
	}
	/*  Il repart par où il est venu : la droite au bureau, le bas au téléphone.
	    ⚠️ `animation: none` : fermé PENDANT son entrée, le message gardait
	    l'animation, qui masque la transition — sans fin de transition, il
	    restait invisible dans la pile. Sans elle, la sortie part de la valeur
	    affichée à cet instant (trouvé par `e2e/toast.spec.ts`). */
	.toast.sortant {
		animation: none;
		opacity: 0;
		transform: translateX(1rem);
		pointer-events: none;
	}
	.toast-texte {
		flex: 1;
		min-width: 0;
		overflow-wrap: anywhere;
	}
	.toast-fermer {
		flex-shrink: 0;
	}

	.toast-success {
		background: var(--color-success-fond);
		color: var(--color-success-texte);
		border-left: 4px solid var(--color-success);
	}
	.toast-error {
		background: var(--color-danger-fond);
		color: var(--color-danger);
		border-left: 4px solid var(--color-danger);
	}
	.toast-warning {
		background: var(--color-warning-fond);
		color: var(--color-warning-texte);
		border-left: 4px solid var(--color-warning);
	}
	.toast-info {
		background: var(--color-primary-light);
		color: var(--color-primary-dark);
		border-left: 4px solid var(--color-primary);
	}

	@keyframes slide-in {
		from {
			opacity: 0;
			transform: translateX(1rem);
		}
		to {
			opacity: 1;
			transform: translateX(0);
		}
	}
	@keyframes fondu {
		from {
			opacity: 0;
		}
	}
	/*  Mouvement réduit : le glissement tombe, le fondu reste — à l'entrée comme
	    à la sortie, il dit qu'un message arrive ou s'en va. */
	@media (prefers-reduced-motion: reduce) {
		.toast {
			animation-name: fondu;
		}
		.toast,
		.toast.sortant {
			transform: none;
		}
	}
</style>
