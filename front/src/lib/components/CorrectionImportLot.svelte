<!--
  La correction d'une ligne de l'import des lots (Admin › Import des lots) :
  le lot en base, ses occupants, une note — ouverte sous la ligne corrigée.

  Extrait d'`OngletImportLots` le 08/10/2026 (#1571) : l'onglet frôlait les
  500 lignes, et ses styles en ligne ne pouvaient passer en classes sans le faire
  déborder. Le formulaire porte sa saisie (`bind:`) ; l'onglet garde l'appel
  réseau, qu'il lance sur `enregistre`.
-->
<script lang="ts">
	import IconeAction from '#lib/components/IconeAction.svelte';
	import type { LigneImportLot, MonLot, UtilisateurAdmin } from '#lib/api/index.ts';
	import { nomAffiche } from '#lib/noms.ts';
	import PiedFormulaire from '#lib/components/PiedFormulaire.svelte';

	export let imp: LigneImportLot;
	export let lots: MonLot[] = [];
	export let utilisateurs: UtilisateurAdmin[] = [];
	export let enCours = false;
	/** Le lot choisi, en chaîne — vide : non lié. */
	export let lot = '';
	export let occupants: { user_id: string; type_lien: string }[] = [];
	export let notes = '';

	const TYPES_LIEN = [
		{ value: 'propriétaire', label: 'Copropriétaire résident' },
		{ value: 'bailleur', label: 'Copropriétaire bailleur' },
		{ value: 'locataire', label: 'Locataire' },
		{ value: 'mandataire', label: 'Mandataire (gestion)' },
	];

	function ajouterOccupant() {
		occupants = [...occupants, { user_id: '', type_lien: 'locataire' }];
	}

	function supprimerOccupant(i: number) {
		occupants = occupants.filter((_, idx) => idx !== i);
	}
</script>

<div class="imp-edit-form card correction">
	<h3 class="titre-correction">
		Lier : <em
			>{imp.nom_coproprietaire ?? '—'} — Bât. {imp.batiment_nom ?? imp.batiment_id} n°{imp.numero}
			({imp.type_raw})</em
		>
	</h3>
	<!-- Lot en base -->
	<div class="field champ-lot">
		<label for="imp-lot-{imp.id}">Lot en base</label>
		<select id="imp-lot-{imp.id}" bind:value={lot}>
			<option value="">— Non lié —</option>
			{#each lots as l (l.id)}
				<option value={String(l.id)}
					>{l.batiment_nom ?? `Bât.${l.batiment_id}`} — {l.numero} ({l.type})</option
				>
			{/each}
		</select>
	</div>
	<!-- Occupants -->
	<div class="occupants-editor">
		<div class="occupants-header">
			<span class="titre-occupants">Occupants du lot</span>
			<button type="button" class="btn btn-sm btn-outline" on:click={ajouterOccupant}
				>+ Ajouter</button
			>
		</div>
		{#each occupants as occ, i (occ)}
			<div class="occupant-row">
				<select bind:value={occ.type_lien} class="select-role">
					{#each TYPES_LIEN as tl (tl.value)}
						<option value={tl.value}>{tl.label}</option>
					{/each}
				</select>
				<select bind:value={occ.user_id} class="select-user">
					<option value="">— Non lié —</option>
					{#each utilisateurs as u (u.id)}
						<option value={String(u.id)}>{nomAffiche(u)} ({u.email})</option>
					{/each}
				</select>
				<button
					type="button"
					class="btn-icon-danger"
					aria-label="Retirer cet occupant"
					title="Retirer"
					on:click={() => supprimerOccupant(i)}><IconeAction icone="trash-2" /></button
				>
			</div>
		{/each}
	</div>
	<!-- Notes -->
	<div class="field champ-notes">
		<label for="imp-notes-{imp.id}">Notes admin</label>
		<input id="imp-notes-{imp.id}" type="text" bind:value={notes} placeholder="Note interne…" />
	</div>
	<PiedFormulaire {enCours} soumission={false} on:annule on:enregistre />
</div>

<style>
	.correction {
		margin: 0.5rem 0;
	}
	.titre-correction {
		font-size: var(--fs-base);
		font-weight: 700;
		margin-bottom: 0.75rem;
	}
	.champ-lot {
		margin-bottom: 0.75rem;
	}
	.champ-notes {
		margin-top: 0.75rem;
	}
	.titre-occupants {
		font-size: var(--fs-md);
		font-weight: 600;
	}
	.occupants-editor {
		border: 1px solid var(--color-border);
		border-radius: 6px;
		padding: 0.5rem 0.75rem;
		margin-bottom: 0.25rem;
	}
	.occupants-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin-bottom: 0.5rem;
	}
	.occupant-row {
		display: flex;
		gap: 0.5rem;
		align-items: center;
		margin-bottom: 0.4rem;
	}
	.select-role {
		min-width: 180px;
		flex-shrink: 0;
	}
	.select-user {
		flex: 1;
		min-width: 0;
	}

	@media (max-width: 767px) {
		.occupant-row {
			flex-wrap: wrap;
		}
		.select-role {
			min-width: 140px;
		}
	}
</style>
