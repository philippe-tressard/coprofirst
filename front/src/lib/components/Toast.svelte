<script module lang="ts">
	import { writable } from 'svelte/store';

	export interface ToastMessage {
		id: number;
		type: 'success' | 'error' | 'info' | 'warning';
		message: string;
	}

	export const toasts = writable<ToastMessage[]>([]);

	let counter = 0;

	//  🔴 Un message SIMPLE, à une place fixe (arbitré le 26/09/2026). La suite
	//  d'un geste sur un élément naît de l'élément (`BoutonLien`) : ce n'est pas
	//  un message, et ce toast n'en porte plus — il l'a porté un jour (#1357).
	export function toast(type: ToastMessage['type'], message: string, duration = 4000) {
		const id = ++counter;
		toasts.update((t) => [...t, { id, type, message }]);
		setTimeout(() => dismiss(id), duration);
	}

	function dismiss(id: number) {
		toasts.update((t) => t.filter((x) => x.id !== id));
	}
</script>

<div class="toast-container" aria-live="polite">
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
			role="alert"
		>
			<span>{t.message}</span>
		</div>
	{/each}
</div>

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
	    (le standard des « snackbars »). Il monte par le bas. */
	@media (max-width: 767px) {
		.toast-container {
			left: 1rem;
			max-width: none;
			align-items: center;
		}
		.toast {
			animation-name: monte;
		}
	}
	@keyframes monte {
		from {
			opacity: 0;
			transform: translateY(8px);
		}
	}

	.toast {
		padding: 0.75rem 1rem;
		border-radius: var(--radius);
		font-size: var(--fs-base);
		box-shadow: var(--shadow);
		/*  Jetons du site : 200 ms, courbe « ease-out » forte (`emil-design-eng`). */
		animation: slide-in var(--duree-apparition) var(--ease-out);
	}

	.toast-success {
		background: var(--color-success-fond);
		color: var(--color-success);
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
</style>
