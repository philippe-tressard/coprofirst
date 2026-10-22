<!--
  VueKanbanAffaires.svelte — l'onglet « Kanban » de la page Affaires.

  ## Pourquoi (#1092, lot 5, arbitré le 23/09/2026)

  Le Calendrier disparaît : ses événements deviennent des affaires, et son
  kanban devient un onglet d'Affaires — *Liste · Kanban · Archives*. Les six
  colonnes restent ; chacune a désormais son état d'affaire (`en_ag`,
  `chez_prestataire` sont nés pour cela), et la correspondance s'écrit dans
  `$lib/kanban` (`COLONNE_PAR_STATUT_TICKET`), jamais ici.

  ## Glisser une carte — le revirement, et sa raison

  Le kanban du Calendrier déclarait les affaires « non déplaçables à la
  souris » : le geste aurait été une seconde façon de faire avancer un dossier.
  L'utilisateur a tranché l'inverse le 23/09/2026, avec sa forme : **le conseil
  seul glisse une carte, et le glissement est une Suite d'état sans texte, qui
  n'avertit personne** (`notifier: false`). Il n'y a donc pas de second chemin :
  c'est LE chemin des Suites, avec son historique au fil.

  Paraissent les affaires suivies (`suivi_kanban`) et non archivées : une
  colonne « Terminé » qui accumulerait tout ce qui a jamais été clos cesserait
  de dire ce qui vient de l'être. Les archives ont leur onglet.
-->
<script lang="ts">
	import {
		KANBAN_COLS,
		MOT_COLONNE_VIDE,
		colonneDuTicket,
		COLONNE_PAR_STATUT_TICKET,
	} from '$lib/kanban';
	import { categorieTicketLabel, lienTicket } from '$lib/tickets';
	import { perimetreTags } from '$lib/perimetres-pastilles';
	import { perimetresStore } from '$lib/stores/perimetres';
	import { relire } from '$lib/utils';
	import { tickets as ticketsApi, type Ticket } from '$lib/api';
	import { messageErreur } from '$lib/erreurs';
	import { demanderFusion } from '$lib/fusion-affaires';
	import { toast } from '$lib/components/Toast.svelte';
	import { createEventDispatcher } from 'svelte';
	import InitPrestataires from '$lib/components/InitPrestataires.svelte';

	export let tickets: Ticket[] = [];
	/** Le conseil glisse les cartes ; les autres lisent. */
	export let peutDeplacer = false;
	//  La page tient la liste : elle y reporte le nouvel état.
	const dispatch = createEventDispatcher<{ deplace: { id: number; statut: string } }>();

	//  La colonne → l'état : l'inverse de la table de `$lib/kanban`, dérivé, jamais recopié.
	const STATUT_PAR_COLONNE: Record<string, string> = Object.fromEntries(
		Object.entries(COLONNE_PAR_STATUT_TICKET).map(([statut, col]) => [col, statut]),
	);

	$: suivis = tickets.filter((t) => t.suivi_kanban && !t.archivee && colonneDuTicket(t.statut));
	$: colonnes = KANBAN_COLS.map((c) => ({
		...c,
		cartes: suivis.filter((t) => colonneDuTicket(t.statut) === c.id),
	}));
	$: pastilles = relire($perimetresStore, () => perimetreTags);

	let saisie: Ticket | null = null;
	//  La colonne où la carte tomberait (#2170) : sans elle, on ne savait où
	//  elle tombait qu'au lâcher. Celle d'où la carte vient ne s'allume pas.
	let cible: string | null = null;
	function lacher() {
		saisie = null;
		cible = null;
	}
	function quitter(e: DragEvent, colonne: string) {
		const vers = e.relatedTarget as Node | null;
		if (cible === colonne && !(e.currentTarget as Node).contains(vers)) cible = null;
	}
	async function deposer(colonne: string) {
		const t = saisie;
		lacher();
		const statut = STATUT_PAR_COLONNE[colonne];
		if (!t || !statut || statut === t.statut) return;
		//  Glisser en « Résolu » clôt : la fusion se demande ici aussi (#1704).
		const fusionner = await demanderFusion(t, statut);
		if (fusionner === null) return;
		try {
			await ticketsApi.addEvolution(t.id, {
				type: 'etat',
				nouveau_statut: statut,
				notifier: false,
				fusionner,
			});
			for (const id of [t.id, ...fusionner]) dispatch('deplace', { id, statut });
		} catch (e) {
			toast('error', messageErreur(e));
		}
	}
</script>

{#if peutDeplacer}
	<!--  Le pré-remplissage de l'exercice — au conseil, comme le glissement (#1193). -->
	<InitPrestataires {tickets} on:cree />
{/if}
<p class="kanban-count-total">
	{suivis.length} affaire{suivis.length > 1 ? 's' : ''} suivie{suivis.length > 1 ? 's' : ''}
</p>
<div class="kanban">
	{#each colonnes as col (col.id)}
		<div
			class="kanban-col"
			role="group"
			aria-label={col.label}
			class:kanban-col-cible={cible === col.id}
			on:dragenter={() => saisie && colonneDuTicket(saisie.statut) !== col.id && (cible = col.id)}
			on:dragleave={(e) => quitter(e, col.id)}
			on:dragover|preventDefault
			on:drop|preventDefault={() => deposer(col.id)}
		>
			<div class="kanban-col-header" style="border-top-color:{col.color}">
				<span>{col.label}</span>
				<span class="kanban-count">{col.cartes.length}</span>
			</div>
			{#each col.cartes as t (t.id)}
				<a
					class="kanban-card card"
					href={lienTicket(t.id)}
					draggable={peutDeplacer ? 'true' : 'false'}
					class:kanban-card-saisie={saisie?.id === t.id}
					on:dragstart={() => (saisie = t)}
					on:dragend={lacher}
				>
					<div class="kanban-card-tags">
						{#each pastilles((t.perimetre_cible ?? []).join(',')) as tag (tag.code)}
							<span class="kb-tag" style="background:{tag.color}">{tag.label}</span>
						{/each}
					</div>
					{#if t.prestataire_nom}<span class="kanban-card-prest">{t.prestataire_nom}</span>{/if}
					<strong class="kanban-card-titre">{t.titre}</strong>
					<div class="kanban-card-footer">
						<span class="kanban-card-type">{categorieTicketLabel(t.categorie)} · #{t.numero}</span>
					</div>
				</a>
			{:else}
				<p class="kanban-empty">{MOT_COLONNE_VIDE}</p>
			{/each}
		</div>
	{/each}
</div>

<style>
	/*  La colonne qui recevrait la carte se marque pendant le glissement, et la
	    carte saisie s'efface à demi : le geste se lit AVANT le lâcher (#2170). */
	.kanban-col {
		transition:
			background var(--duree-geste),
			border-color var(--duree-geste);
	}
	.kanban-col.kanban-col-cible {
		background: var(--color-primary-light);
		border-color: var(--color-primary);
	}
	.kanban-card.kanban-card-saisie {
		opacity: 0.5;
	}
</style>
