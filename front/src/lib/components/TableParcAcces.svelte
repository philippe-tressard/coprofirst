<!--
  **La table du parc d'accès** — une ligne par badge, avec ses gestes.

  ## Pourquoi ce composant (14/09/2026, #953)

  `BadgesCopropriete` garde ce qui est à lui : les filtres, la recherche, l'état
  de saisie et les trois gestes. La table, elle, rend des lignes — et le plafond
  de modularité a désigné la césure quand les gestes l'ont fait franchir les 500
  lignes.

  ⚠️ **Les styles partent avec le balisage**, c'est la seule façon qu'ils
  s'appliquent : Svelte scope le style au composant qui REND. Les laisser
  derrière les aurait rendus inertes — c'est la panne des pastilles nues de la
  v2.67.11.

  ## Ce qu'il ne décide pas

  Ni le tri, ni les droits, ni ce qu'un geste déclenche : il ÉMET, l'écran
  décide. Une table qui saurait supprimer aurait besoin de connaître les droits,
  et la règle vivrait alors à deux endroits.
-->
<script lang="ts">
	import Badge from '#lib/components/Badge.svelte';
	import IconeAction from '#lib/components/IconeAction.svelte';
	import { createEventDispatcher } from 'svelte';
	import BadgePerimetre from '#lib/components/BadgePerimetre.svelte';
	import { statutAccesBadge, statutAccesLabel } from '#lib/types-acces.ts';
	import type { AccesAdmin } from '#lib/api/index.ts';

	type Ligne = AccesAdmin & { type: string };

	const dispatch = createEventDispatcher<{
		trier: string;
		editer: Ligne;
		supprimer: Ligne;
	}>();

	export let lignes: Ligne[] = [];
	export let labelType: Record<string, string> = {};
	export let triCol = 'porteur';
	export let triAsc = true;
	/** La ligne dont la correction est ouverte — `type-id`, ou `null`. */
	export let editId: string | null = null;
	/**  🔒 Le droit de supprimer, décidé par l'écran et relayé tel quel.
	 *
	 *   ⚠️ La table ne lit PAS le magasin d'authentification : elle rendrait alors
	 *   une décision d'accès, et il y aurait deux endroits où la lire. */
	export let estAdmin = false;
</script>

<div class="table-wrap">
	<table class="table table-parc">
		<thead>
			<!--  🔴 De vrais `<button>` dans les `<th>` : un `<th>` cliquable sans
			      bouton n'est ni atteignable au clavier ni annoncé comme
			      actionnable (`CLAUDE.md`, règle 3). `aria-sort` dit au lecteur
			      d'écran ce que la flèche montre à l'œil. -->
			<tr>
				{#each [['type', 'Type'], ['code', 'Code'], ['porteur', 'Porteur'], ['lot', 'Lot'], ['acces', 'Accès'], ['statut', 'Statut']] as [col, libelle] (col)}
					<th aria-sort={triCol === col ? (triAsc ? 'ascending' : 'descending') : 'none'}>
						<button type="button" class="th-tri" on:click={() => dispatch('trier', col)}>
							{libelle}<span class="th-fleche" aria-hidden="true"
								>{triCol === col ? (triAsc ? '▲' : '▼') : ''}</span
							>
						</button>
					</th>
				{/each}
				<!--  La colonne des gestes ne se trie pas : elle ne porte pas de
				      donnée. Son en-tête reste vide plutôt que de s'intituler
				      « Actions » — le libellé n'apprend rien et prend la place. -->
				<th aria-label="Actions"></th>
			</tr>
		</thead>
		<tbody>
			{#each lignes as a (a.type + a.id)}
				<tr>
					<td>{labelType[a.type]}</td>
					<td class="bc-code">{a.code}</td>
					<td>
						{a.porteur_nom}
						{#if a.chez_locataire}
							<span class="badge badge-blue bc-chez">Chez le locataire</span>
						{/if}
					</td>
					<td>{a.lot_libelle ?? '—'}</td>
					<!--  🔹 `BadgePerimetre` : le composant qui rend ce badge partout
					      ailleurs. Il ne rend RIEN quand le périmètre est vide — et
					      un accès vide veut dire « on ne sait pas », ce que le tiret
					      dit mieux qu'une pastille. -->
					<td>
						<BadgePerimetre perimetre={a.perimetre_cible ?? []}>
							<span class="bc-vide">—</span>
						</BadgePerimetre>
					</td>
					<td>
						<Badge teinte={statutAccesBadge(a.statut)}>{statutAccesLabel(a.statut)}</Badge>
					</td>
					<!--  Crayon puis corbeille, au trait — l'ordre arrêté par la carte de ticket. La
					      corbeille n'apparaît que pour l'admin : l'écran dit alors
					      la même chose que le serveur, ni plus ni moins. -->
					<td class="bc-gestes">
						<button
							class="btn-icon btn-icon-edit"
							type="button"
							title="Corriger cet accès"
							aria-label="Corriger cet accès"
							aria-pressed={editId === `${a.type}-${a.id}`}
							on:click={() => dispatch('editer', a)}><IconeAction icone="pencil" /></button
						>
						{#if estAdmin}
							<button
								class="btn-icon btn-icon-danger"
								type="button"
								title="Supprimer définitivement"
								aria-label="Supprimer définitivement"
								on:click={() => dispatch('supprimer', a)}><IconeAction icone="trash-2" /></button
							>
						{/if}
					</td>
				</tr>
				{#if editId === `${a.type}-${a.id}`}
					<!--  🔴 La correction s'ouvre À LA PLACE de l'objet — ici, sous sa
					      ligne, sur toute la largeur. La règle dit « dans la carte, à
					      la place de son corps » ; une ligne de tableau n'a pas de
					      corps, et la ligne suivante est ce qui s'en approche le plus
					      sans déplacer ce qu'on regarde (`ux-patterns` §14 ter).
					      Aucune `cle` n'est nécessaire : rien n'a bougé. -->
					<tr>
						<td colspan="7" class="bc-edition">
							<slot name="edition" />
						</td>
					</tr>
				{/if}
			{/each}
		</tbody>
	</table>
</div>

<style>
	.bc-gestes {
		display: flex;
		gap: 0.3rem;
		white-space: nowrap;
	}
	.bc-vide {
		color: var(--color-text-muted);
	}
	.bc-edition {
		background: var(--color-bg);
		padding: 0.75rem 1rem;
	}
	.th-tri {
		display: inline-flex;
		align-items: center;
		gap: 0.3rem;
		background: none;
		border: 0;
		padding: 0;
		font: inherit;
		color: inherit;
		cursor: pointer;
	}
	.th-fleche {
		font-size: 0.7em;
	}
	.bc-code {
		font-family: monospace;
	}
	.bc-chez {
		font-size: var(--fs-2xs);
		margin-left: 0.35rem;
	}
	.table-parc {
		font-size: var(--fs-md);
	}
</style>
