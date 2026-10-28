<!--
  Les constats du PATRIMOINE — ceux de l'état descriptif avant son application
  (#2213) et ceux de l'onglet Lots (#2216) : un badge de gravité, le message, les
  lots qu'il cite. Le modèle est un seul côté serveur (`utils/constats`), le rendu
  l'est ici.

  Ordre : ce qui bloque ou ne se calcule pas d'abord, puis ce qu'il faut savoir.
  Au-delà de douze lots cités, le compte suffit à agir.

  ⚠️ À ne pas confondre avec `ListeConstats`, qui lit les lignes textuelles de
  `check-reliability.sh` (« [FAIL] … ») : autre source, autre forme.
-->
<script lang="ts">
	import Badge from '#lib/components/Badge.svelte';
	import type { ConstatPatrimoine } from '#lib/api/index.ts';
	import { parAttribut } from '#lib/table-statuts.ts';

	export let constats: ConstatPatrimoine[] = [];
	/** Ce qu'on dit quand il n'y en a aucun. */
	export let videTexte = 'Aucun constat.';

	const { libelle: GRAVITE, badge: TEINTE } = parAttribut({
		bloquant: { libelle: 'Bloquant', badge: 'badge-red' },
		inconnu: { libelle: 'Inconnu', badge: 'badge-gray' },
		avertissement: { libelle: 'À savoir', badge: 'badge-orange' },
		information: { libelle: 'Information', badge: 'badge-blue' },
	});
	const RANG: Record<string, number> = {
		bloquant: 0,
		inconnu: 1,
		avertissement: 2,
		information: 3,
	};
	const LOTS_MONTRES = 12;

	$: ordonnes = [...constats].sort((a, b) => (RANG[a.gravite] ?? 9) - (RANG[b.gravite] ?? 9));
</script>

{#if ordonnes.length === 0}
	<p class="muted">{videTexte}</p>
{:else}
	<ul class="constats">
		{#each ordonnes as c (c.code + c.message)}
			<li>
				<Badge teinte={TEINTE[c.gravite]}>{GRAVITE[c.gravite] ?? c.gravite}</Badge>
				<div>
					<p class="constat-message">{c.message}</p>
					{#if c.lots.length}
						<p class="aide">
							Lot{c.lots.length > 1 ? 's' : ''}
							{c.lots.slice(0, LOTS_MONTRES).join(', ')}{c.lots.length > LOTS_MONTRES
								? ` et ${c.lots.length - LOTS_MONTRES} autre(s)`
								: ''}
						</p>
					{/if}
				</div>
			</li>
		{/each}
	</ul>
{/if}

<style>
	.constats {
		list-style: none;
		margin: 0;
		padding: 0;
		display: grid;
		gap: 0.75rem;
	}
	.constats li {
		display: grid;
		grid-template-columns: auto 1fr;
		gap: 0.6rem;
		align-items: start;
	}
	.constat-message {
		margin: 0;
	}
</style>
