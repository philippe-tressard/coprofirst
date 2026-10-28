<!--
  **Les avis portés sur un prestataire** — la liste, et le geste qui en retire un.

  ## 🔴 Ce que le ticket disait, et ce qui était vrai (#807, 06/09/2026)

  Le ticket annonçait « un résident ne peut pas retirer sa propre notation ».
  C'était faux, et la lecture de l'endpoint l'a montré : **seul le conseil
  syndical ou l'administrateur peut noter** (`require_cs_or_admin` sur
  `POST /prestataires/notations`). Il n'y a donc pas de résident qui aurait noté
  par erreur — c'est un outil interne du CS.

  Le vrai défaut est plus simple, et il portait sur les mêmes personnes : le CS
  pouvait **poser** une note et pas la **retirer**. `DELETE
  /prestataires/notations/{id}` existait, réservé au CS, et aucun écran ne
  l'appelait. Un membre qui se trompe de prestataire, ou qui note deux fois la
  même intervention, n'avait aucun recours.

  ⚠️ Et il n'y avait nulle part où poser le bouton : l'écran n'affichait que la
  **moyenne**, dans un badge. Les avis individuels — qui, quand, quel
  commentaire — n'étaient visibles nulle part. Ajouter une suppression sans la
  liste aurait donné un geste sans cible.

  ## Le droit affiché est celui que le SERVEUR applique

  `require_cs_or_admin`, ni plus ni moins (`ux-patterns` §15). Le composant ne
  restreint pas la suppression à l'auteur de la note : l'endpoint ne le fait pas,
  et un écran plus étroit que le serveur rend une capacité introuvable — plus
  large, il produit un 403 sur un geste qu'il a lui-même proposé.

  ⚠️ **L'auteur est affiché**, lui, et c'est ce qui rend la modération
  responsable : on voit qui a noté avant de retirer.
-->
<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import { prestataires as prestApi, type Notation } from '#lib/api/index.ts';
	import { messageErreur } from '#lib/erreurs.ts';
	import { toast } from '#lib/components/Toast.svelte';
	import { confirmer } from '#lib/confirmation.ts';
	import { fmtDate } from '#lib/date.ts';
	import { etoiles, moyenneNotes } from '#lib/notations.ts';
	import IconeAction from './IconeAction.svelte';

	/** Les notations de CE prestataire, déjà filtrées par l'appelant. */
	export let notations: Notation[] = [];
	/** Vrai pour le conseil syndical et l'administration — ce que l'endpoint exige. */
	export let peutSupprimer = false;
	/**  `true` = le badge de moyenne (dans l'en-tête de la carte) · `false` = la
	 *   liste détaillée (dans le corps déplié). Deux vues de la même donnée, donc
	 *   un seul composant : les séparer aurait donné deux endroits où changer la
	 *   façon d'écrire une note. */
	export let resume = false;

	$: moyenne = moyenneNotes(notations);

	const dispatch = createEventDispatcher<{ supprimee: number }>();

	//  Les plus récentes d'abord : un avis vieux de deux ans n'est pas ce qu'on
	//  vient lire quand on ouvre une fiche.
	$: triees = [...notations].sort(
		(a, b) => new Date(b.cree_le).getTime() - new Date(a.cree_le).getTime(),
	);

	async function supprimer(n: Notation) {
		const ok = await confirmer({
			titre: 'Retirer cet avis',
			message:
				`Note ${n.note}/5 de ${n.auteur_nom ?? 'un membre du CS'}` +
				(n.commentaire ? ` — « ${n.commentaire} »` : '') +
				'\n\nLa suppression est définitive, et la moyenne du prestataire sera recalculée.',
			libelleConfirmer: 'Retirer l’avis',
			danger: true,
		});
		if (!ok) return;
		try {
			await prestApi.deleteNotation(n.id);
			toast('success', 'Avis retiré.');
			dispatch('supprimee', n.id);
		} catch (e) {
			toast('error', messageErreur(e, 'Suppression impossible'));
		}
	}
</script>

{#if resume}
	<!--  Le BADGE de moyenne — il vivait dans la carte du prestataire avec ses
	      deux fonctions de calcul. Le rendre ici met la note et les avis qui la
	      composent au même endroit : c'est la même notion, vue de deux
	      distances. -->
	{#if moyenne !== null}
		<span class="not-badge badge" title="{moyenne}/5 ({notations.length} avis)">
			{etoiles(moyenne)}
			{moyenne}
		</span>
	{/if}
{:else if triees.length}
	<div class="not-liste">
		<span class="detail-label">Avis du conseil syndical ({triees.length})</span>
		{#each triees as n (n.id)}
			<div class="not-item">
				<div class="not-entete">
					<span class="not-etoiles" aria-label="{n.note} sur 5">{etoiles(n.note)}</span>
					<span class="not-auteur">{n.auteur_nom ?? '—'}</span>
					<span class="not-date">{fmtDate(n.cree_le)}</span>
					{#if peutSupprimer}
						<button
							type="button"
							class="btn-icon-danger"
							title="Retirer cet avis"
							aria-label="Retirer l’avis de {n.auteur_nom ?? 'ce membre'}"
							on:click|stopPropagation={() => supprimer(n)}><IconeAction icone="trash-2" /></button
						>
					{/if}
				</div>
				{#if n.commentaire}
					<p class="not-commentaire">{n.commentaire}</p>
				{/if}
			</div>
		{/each}
	</div>
{/if}

<style>
	.not-badge {
		margin-left: 0.25rem;
		color: var(--color-warning-texte);
	}
	.not-liste {
		display: flex;
		flex-direction: column;
		gap: 0.4rem;
		margin-top: 0.75rem;
	}
	.not-item {
		border-top: 1px solid var(--color-border);
		padding-top: 0.4rem;
	}
	.not-entete {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		flex-wrap: wrap;
		font-size: var(--fs-md);
	}
	.not-etoiles {
		color: var(--color-warning-texte);
		letter-spacing: 0.05em;
	}
	.not-auteur {
		font-weight: 600;
	}
	.not-date {
		color: var(--color-text-muted);
		font-size: var(--fs-sm);
		/*  Pousse le bouton à droite sans le coller à la date sur un écran étroit,
		    où la ligne se replie. */
		margin-right: auto;
	}
	.not-commentaire {
		margin: 0.2rem 0 0;
		font-size: var(--fs-md);
		color: var(--color-text-muted);
		/*  Le commentaire vient d'un humain : les retours à la ligne comptent, et
		    il n'est PAS rendu en HTML — donc rien à assainir. */
		white-space: pre-wrap;
	}
</style>
