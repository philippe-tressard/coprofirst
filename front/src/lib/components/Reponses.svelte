<!--
  Composant partagé « Réponses » — utilisé par la boîte à idées, les petites
  annonces et les sondages pour une UX cohérente.

  Chaque réponse affiche nom + bâtiment + rôle de l'auteur. Les réponses du
  conseil syndical (est_cs) sont mises en avant (bord + fond bleu, ⭐) et
  remontées en tête (tri fait côté serveur). Le parent gère l'appel API via
  les callbacks onSubmit / onDelete (puis rafraîchit la liste).
-->
<script lang="ts">
	import type { ReponseCommunaute } from '#lib/api/index.ts';
	import { fmtDateShort } from '#lib/date.ts';

	import { peutCommenter } from '#lib/droits.ts';
	import { confirmer, SUPPRESSION } from '#lib/confirmation.ts';
	import { onDestroy } from 'svelte';
	import { membre } from '#lib/accordeon.ts';
	import IconeAction from '#lib/components/IconeAction.svelte';

	export let reponses: ReponseCommunaute[] = [];
	export let currentUserId: number | undefined = undefined;
	export let isCS = false;
	export let canRespond = true;
	export let placeholder = 'Votre réponse…';
	export let onSubmit: (contenu: string) => Promise<void> | void;
	export let onDelete: (repId: number) => Promise<void> | void;
	export let onReport: ((repId: number) => Promise<void> | void) | null = null;
	export let expanded = false;

	//  L'accordéon (30/09/2026) : ouvrir les réponses d'une idée replie celles
	//  d'une autre (`#lib/accordeon`). Le champ en cours de saisie n'est pas
	//  perdu — `content` vit dans le composant, seul l'affichage se replie.
	const accordeon = membre('reponses', () => (expanded = false));
	onDestroy(accordeon.liberer);
	let zone: HTMLElement;
	function basculerReponses() {
		expanded = !expanded;
		if (expanded) accordeon.prendre(zone);
	}

	let content = '';
	let submitting = false;

	$: nb = reponses?.length ?? 0;

	async function submit() {
		const c = content.trim();
		if (!c) return;
		submitting = true;
		try {
			await onSubmit(c);
			content = '';
		} catch {
			/* le parent affiche l'erreur (toast) ; on conserve le texte saisi */
		} finally {
			submitting = false;
		}
	}

	//  La boîte de la charte, et non `confirm()` natif (#605) : une réponse
	//  supprimée ne revient pas, le rouge le dit.
	async function remove(id: number) {
		if (!(await confirmer(SUPPRESSION('Cette réponse')))) return;
		await onDelete(id);
	}
</script>

<div class="reponses-zone" bind:this={zone}>
	<button
		type="button"
		class="reponses-toggle"
		on:click={basculerReponses}
		aria-expanded={expanded}
		aria-label={expanded ? 'Masquer les réponses' : 'Voir les réponses'}
	>
		💬 {nb > 0 ? `${nb} réponse${nb > 1 ? 's' : ''}` : 'Répondre'}
	</button>

	{#if expanded}
		<div class="reponses-liste">
			{#each reponses as rep (rep.id)}
				<div class="reponse" class:cs={rep.est_cs}>
					<div class="reponse-tete">
						<span class="reponse-auteur">{rep.auteur_nom}</span>
						{#if rep.auteur_batiment}<span class="badge badge-gray">{rep.auteur_batiment}</span
							>{/if}
						{#if rep.auteur_role}<span
								class="badge"
								class:badge-blue={rep.est_cs}
								class:badge-gray={!rep.est_cs}>{rep.auteur_role}</span
							>{/if}
						{#if rep.est_cs}<span class="reponse-poids" title="Réponse du conseil syndical">⭐</span
							>{/if}
						<small class="reponse-date">{fmtDateShort(rep.cree_le)}</small>
						{#if onReport && rep.auteur_id !== currentUserId}
							<!--  Au trait, comme toutes les actions du site (10/10/2026) : le
							      pictogramme gris EST la discrétion que l'opacité réduite
							      donnait à l'émoji rouge. -->
							<button
								class="btn-icon reponse-signaler"
								title="Signaler cette réponse au conseil syndical"
								aria-label="Signaler cette réponse"
								on:click={() => onReport?.(rep.id)}><IconeAction icone="flag" /></button
							>
						{/if}
						{#if peutCommenter(rep, currentUserId, false, isCS)}
							<button
								class="btn-icon-danger reponse-suppr"
								title="Supprimer cette réponse"
								aria-label="Supprimer cette réponse"
								on:click={() => remove(rep.id)}><IconeAction icone="trash-2" /></button
							>
						{/if}
					</div>
					<div class="reponse-contenu">{rep.contenu}</div>
				</div>
			{/each}

			{#if canRespond}
				<!--  Le champ vit dans un `.field` : c'est la définition unique du champ,
				      fond beige compris. Il recomposait sa peau à la main — bordure, rayon,
				      remplissage, taille — donc un fond BLANC au milieu d'un site beige.
				      Signalé à l'écran le 28/08/2026, sur la page d'un sondage.
				      ⚠️ `lint:styles` ne l'a pas vu : il refuse un sélecteur d'élément NU,
				      et `.reponse-form textarea` est qualifié. Angle mort suivi en #593. -->
				<div class="reponse-form">
					<div class="field champ-en-ligne">
						<textarea bind:value={content} rows="2" {placeholder}></textarea>
					</div>
					<button class="btn btn-primary" disabled={submitting} on:click={submit}>
						{submitting ? 'Envoi…' : 'Répondre'}
					</button>
				</div>
			{/if}
		</div>
	{/if}
</div>

<style>
	.reponses-zone {
		margin-top: 0.5rem;
		border-top: 1px solid var(--color-border);
		padding-top: 0.5rem;
	}
	.reponses-toggle {
		background: none;
		border: none;
		color: var(--color-primary);
		font-size: var(--fs-md);
		font-weight: 600;
		cursor: pointer;
		padding: 0.1rem 0;
	}
	@media (hover: hover) and (pointer: fine) {
		.reponses-toggle:hover {
			text-decoration: underline;
		}
	}
	.reponses-liste {
		margin-top: 0.5rem;
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
	}
	.reponse {
		border: 1px solid var(--color-border);
		border-left: 3px solid var(--color-border);
		border-radius: var(--radius);
		padding: 0.5rem 0.7rem;
		background: var(--color-surface);
	}
	.reponse.cs {
		border-left-color: var(--color-primary);
		background: var(--color-primary-light);
	}
	.reponse-tete {
		display: flex;
		align-items: center;
		flex-wrap: wrap;
		gap: 0.4rem;
		margin-bottom: 0.25rem;
	}
	.reponse-auteur {
		font-weight: 600;
		font-size: var(--fs-md);
	}
	.reponse-poids {
		font-size: var(--fs-sm);
	}
	.reponse-date {
		color: var(--color-text-muted);
		font-size: var(--fs-2xs);
	}
	.reponse-suppr {
		margin-left: auto;
	}
	.reponse-signaler {
		margin-left: auto;
	}
	/*  Signaler PUIS supprimer : la corbeille suit le drapeau, elle ne se pousse
	    pas une seconde fois à droite. */
	.reponse-signaler + .reponse-suppr {
		margin-left: 0;
	}
	.reponse-contenu {
		font-size: var(--fs-md);
		white-space: pre-wrap;
		word-break: break-word;
	}
	.reponse-form {
		display: flex;
		gap: 0.5rem;
		align-items: flex-start;
		margin-top: 0.3rem;
	}
	/*  La PEAU du champ vient de `.field textarea` (composants.css). Ne restent
	    ici que la disposition — largeur dans la rangée — et le redimensionnement,
	    qui sont propres à ce contexte et ne recomposent rien. */
	.reponse-form .field {
		flex: 1;
	}
	.reponse-form textarea {
		resize: vertical;
	}
</style>
