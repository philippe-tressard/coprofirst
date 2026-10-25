<!--
  **La vue bailleur de « Mes lots »** — les lots possédés, leurs locataires
  regroupés, et les lots vacants.

  Extraite de `mon-lot/+page.svelte` le 30/09/2026 (#779) : un bloc de 140
  lignes de balisage et 90 de styles, qui ne partage avec la page que les
  listes qu'elle charge (lots, baux actifs) et trois gestes qu'elle porte
  (créer un bail, ouvrir les accès, corriger un locataire).
-->
<script lang="ts">
	import { goto } from '$app/navigation';
	import type { Bail, MonLot } from '$lib/api';
	import { nomLocataire } from '$lib/bail';
	import BadgeStatutBail from '$lib/components/BadgeStatutBail.svelte';
	import DetailReglementLot from '$lib/components/DetailReglementLot.svelte';
	import TotauxCharges from '$lib/components/TotauxCharges.svelte';
	import { designationDuLot } from '$lib/charges-lots';
	import { fmtDateShort as fmt } from '$lib/date';
	import { etageLabel, lotTypeComplet } from '$lib/utils';

	export let lots: MonLot[] = [];
	export let bauxActifs: Bail[] = [];
	/** L'adresse de la gestion locative — la page la compose (`routeSousOnglet`). */
	export let routeGestion: string;
	export let onCreerBail: (lotId: number) => void;
	export let onAcces: (bail: Bail) => void;
	export let onModifierLocataire: (bail: Bail) => void;

	$: lotsAvecBail = lots.map((l) => ({
		...l,
		bail: bauxActifs.find((b) => b.lot_id === l.id) ?? null,
	}));
	//  Un locataire par carte, ses baux regroupés ; un locataire sans compte se
	//  reconnaît à son bail.
	$: locatairesMap = (() => {
		const map = new Map<number | string, { bail: Bail; baux: Bail[] }>();
		for (const b of bauxActifs) {
			const key = b.locataire_id ?? `ext_${b.id}`;
			if (!map.has(key)) map.set(key, { bail: b, baux: [] });
			map.get(key)!.baux.push(b);
		}
		return [...map.values()];
	})();
	$: lotsVacants = lots.filter((l) => !bauxActifs.find((b) => b.lot_id === l.id));
</script>

<!-- Le total de mes charges, tous mes lots confondus (#2215) -->
<TotauxCharges {lots} />

<!-- Section 1 : Tous les lots possédés -->
<div class="lots-section-label">🏢 Lots possédés ({lots.length})</div>
<div class="lots-possedes-grid">
	{#each lotsAvecBail as lot (lot.id)}
		<div class="lot-possede-card card" class:lot-occupe={!!lot.bail} class:lot-vacant={!lot.bail}>
			<div class="lpc-header">
				<span class="lbc-lot-badge">{lot.batiment_nom ?? '—'} / {lot.numero}</span>
				{#if lot.bail}
					<span class="badge badge-green etat-lot">Occupé</span>
				{:else}
					<span class="badge badge-gray etat-lot">Vacant</span>
				{/if}
			</div>
			<div class="lpc-details">
				<span class="badge badge-gray type-lot"
					>{lotTypeComplet(lot.type, lot.type_appartement)}</span
				>
				{#if lot.etage !== null}<span class="text-muted-sm"
						>{etageLabel(lot.etage, { suffixe: true })}</span
					>{/if}
				{#if lot.superficie}<span class="text-muted-sm">{lot.superficie} m²</span>{/if}
			</div>
			<!--  Où est le lot et ce qui le dessert, puis la phrase qui explique la charge, les parts
			      clé par clé et les alertes (#2215) : écrits une fois, côté serveur et dans
			      `DetailReglementLot`. -->
			{#if lot.numero_usage || lot.perimetres?.length}
				<p class="text-muted-sm designation-lot">{designationDuLot(lot)}</p>
			{/if}
			<DetailReglementLot {lot} />
			{#if lot.bail}
				<div class="lpc-occupant">👤 {nomLocataire(lot.bail)}</div>
			{:else}
				<button class="btn btn-sm btn-primary btn-bail" on:click={() => onCreerBail(lot.id)}>
					+ Créer un bail
				</button>
			{/if}
		</div>
	{/each}
</div>

<!-- Section 2 : Locataires (lots regroupés par locataire) -->
{#if locatairesMap.length > 0}
	<div class="lots-section-label label-suivant">
		👥 Locataires ({locatairesMap.length})
	</div>
	{#each locatairesMap as loc (loc.bail.locataire_id ?? `ext_${loc.bail.id}`)}
		{@const premierBail = loc.bail}
		<div class="locataire-card card">
			<div class="loc-header">
				<div class="loc-name">
					👤 <strong>{nomLocataire(premierBail)}</strong>
					<BadgeStatutBail statut={premierBail.statut} compact />
				</div>
				<div class="loc-contact">
					{#if premierBail.locataire_email}<a
							href="mailto:{premierBail.locataire_email}"
							class="courriel-locataire">📬 {premierBail.locataire_email}</a
						>{/if}
					{#if premierBail.locataire_telephone}<span class="text-muted-md"
							>📞 {premierBail.locataire_telephone}</span
						>{/if}
				</div>
			</div>
			<div class="loc-lots">
				{#each loc.baux as bail (bail.id)}
					{@const lot = lots.find((l) => l.id === bail.lot_id)}
					{#if lot}
						<div class="loc-lot-row">
							<span class="lbc-lot-badge">{lot.batiment_nom ?? '—'} / {lot.numero}</span>
							<span class="badge badge-gray type-lot"
								>{lotTypeComplet(lot.type, lot.type_appartement)}</span
							>
							<span class="text-muted-sm"
								>Depuis le {fmt(bail.date_entree)}{bail.date_sortie_prevue
									? ` · Sortie prévue ${fmt(bail.date_sortie_prevue)}`
									: ''}</span
							>
						</div>
					{/if}
				{/each}
			</div>
			<div class="lbc-actions">
				<button class="btn btn-sm btn-outline" on:click={() => goto(routeGestion)}
					>📋 Gestion locative</button
				>
				<button class="btn btn-sm btn-outline" on:click={() => onAcces(premierBail)}
					>🔑 Accès</button
				>
				<button
					class="btn-icon-edit"
					aria-label="Modifier le locataire"
					title="Modifier"
					on:click={() => onModifierLocataire(premierBail)}>&#x270F;&#xFE0F;</button
				>
			</div>
		</div>
	{/each}
{/if}

<!-- Lots vacants (rappel rapide) -->
{#if lotsVacants.length > 0}
	<div class="lots-section-label label-suivant">
		🔓 Lots vacants ({lotsVacants.length})
	</div>
	<p class="note-vacants">
		Ces lots n'ont pas de bail actif. Créez un bail depuis la fiche du lot ci-dessus ou l'onglet <strong
			>Gestion locative</strong
		>.
	</p>
{/if}

<style>
	.designation-lot {
		margin: 0.5rem 0 0;
	}
	.lot-vacant {
		opacity: 0.8;
		border-style: dashed;
	}
	.lbc-actions {
		display: flex;
		gap: 0.4rem;
		flex-wrap: wrap;
		margin-top: 0.3rem;
	}
	/* Lots possédés grid */
	.lots-possedes-grid {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(min(220px, 100%), 1fr));
		gap: 0.6rem;
		margin-bottom: 0.6rem;
	}
	.lot-possede-card {
		padding: 0.85rem 1rem;
		display: flex;
		flex-direction: column;
		gap: 0.35rem;
	}
	.lot-possede-card.lot-occupe {
		border-left: 3px solid var(--color-success);
	}
	.lot-possede-card.lot-vacant {
		border-left: 3px dashed var(--color-border);
		opacity: 0.8;
	}
	.lpc-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		gap: 0.4rem;
	}
	.lpc-details {
		display: flex;
		flex-wrap: wrap;
		gap: 0.4rem;
		align-items: center;
	}
	.lpc-occupant {
		font-size: var(--fs-md);
		color: var(--color-text-muted);
	}

	/* Locataire cards */
	.locataire-card {
		padding: 1rem 1.2rem;
		margin-bottom: 0.6rem;
	}
	.loc-header {
		display: flex;
		flex-direction: column;
		gap: 0.3rem;
		margin-bottom: 0.6rem;
	}
	.loc-name {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		flex-wrap: wrap;
		font-size: var(--fs-lg);
	}
	.loc-contact {
		display: flex;
		flex-wrap: wrap;
		gap: 0.6rem;
		align-items: center;
	}
	.loc-lots {
		border-top: 1px solid var(--color-border);
		padding-top: 0.5rem;
		display: flex;
		flex-direction: column;
		gap: 0.35rem;
		margin-bottom: 0.5rem;
	}
	.loc-lot-row {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		flex-wrap: wrap;
		padding: 0.3rem 0.5rem;
		background: var(--color-neutre-fond);
		border-radius: var(--radius);
	}
	.etat-lot {
		font-size: var(--fs-2xs);
	}
	.type-lot {
		font-size: var(--fs-2xs);
		text-transform: capitalize;
	}
	.btn-bail {
		margin-top: 0.4rem;
	}
	.label-suivant {
		margin-top: 1.8rem;
	}
	.courriel-locataire {
		color: var(--color-primary);
		font-size: var(--fs-md);
	}
	.note-vacants {
		font-size: var(--fs-md);
		color: var(--color-text-muted);
		margin: 0 0 0.6rem;
	}
</style>
