<!--
  « Résidence & statut » du profil : ce que le compte connecté est — profil
  d'utilisateur, bâtiment, lots, rôles, état du compte, ancienneté, dernière
  connexion. Lecture seule ; la demande de modification reste à la page.

  Extrait de `profil/+page.svelte` le 08/10/2026 (#1571) : la page frôlait les
  500 lignes, et ses styles en ligne ne pouvaient passer en classes sans la faire
  déborder. Le bloc lit le compte dans le store, comme la page le faisait.
-->
<script lang="ts">
	import { SEPARATEUR } from '#lib/separateurs.ts';
	import Badge from '#lib/components/Badge.svelte';
	import type { MonLot } from '#lib/api/index.ts';
	import { currentUser } from '#lib/stores/auth.ts';
	import { badgesDeRoles, LIBELLES_STATUT } from '#lib/roles.ts';
	import { fmtDateShort as fmtDate, fmtDatetimeShort as fmtDatetime } from '#lib/date.ts';
	import { etageLabel, fmtNombre, lotTypeLabel } from '#lib/utils.ts';

	/** Les lots du compte (`lots.mesList()`), chargés par la page. */
	export let lots: MonLot[] = [];

	$: derniereConnexion = $currentUser?.derniere_connexion ?? null;
</script>

<dl class="info-grid">
	<dt>Profil d'utilisateur</dt>
	<dd>{LIBELLES_STATUT[$currentUser?.statut ?? ''] ?? $currentUser?.statut ?? '—'}</dd>

	<dt>Bâtiment</dt>
	<dd>{$currentUser?.batiment_nom ?? '—'}</dd>

	{#if lots.length > 0}
		<dt>Lot{lots.length > 1 ? 's' : ''}</dt>
		<dd>
			{#each lots as lot (lot.id)}
				<span class="ligne-lot">
					{#if lot.batiment_nom}{lot.batiment_nom} —
					{/if}
					N° {lot.numero}{SEPARATEUR.point}{lotTypeLabel(lot.type)}
					{#if lot.type_appartement}
						({lot.type_appartement}){/if}
					{#if lot.etage != null}{SEPARATEUR.point}{etageLabel(lot.etage, { suffixe: true })}{/if}
					{#if lot.superficie}{SEPARATEUR.point}{fmtNombre(lot.superficie)} m²{/if}
				</span>
			{/each}
		</dd>
	{/if}

	<dt>Rôle(s)</dt>
	<dd class="roles-compte">
		{#each badgesDeRoles($currentUser?.roles?.length ? $currentUser.roles : [$currentUser?.role ?? 'résident']) as b (b.label)}
			<Badge teinte={b.cls}>{b.label}</Badge>
		{/each}
	</dd>

	<dt>Statut du compte</dt>
	<dd>
		{#if $currentUser?.actif}
			<span class="badge badge-green">Actif</span>
		{:else}
			<span class="badge badge-red">Inactif</span>
		{/if}
	</dd>

	<dt>Membre depuis</dt>
	<dd>{fmtDate($currentUser?.cree_le)}</dd>

	<dt>Dernière connexion</dt>
	<dd>{fmtDatetime(derniereConnexion)}</dd>
</dl>

<style>
	.info-grid {
		display: grid;
		grid-template-columns: auto 1fr;
		gap: 0.4rem 0.75rem;
		font-size: var(--fs-base);
		margin-bottom: 0.25rem;
	}
	.info-grid dt {
		font-weight: 500;
		color: var(--color-text-muted);
		white-space: nowrap;
	}
	.info-grid dd {
		margin: 0;
	}
	.ligne-lot {
		display: block;
	}
	.roles-compte {
		display: flex;
		gap: 0.35rem;
		flex-wrap: wrap;
	}
</style>
