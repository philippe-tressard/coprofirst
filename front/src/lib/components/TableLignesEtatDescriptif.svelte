<!--
  Le tableau « Lignes lues » de l'atelier de l'ÉTAT DESCRIPTIF (#2213) — extrait de
  l'atelier le 25/10/2026 : il dépassait les 500 lignes (`standards/02` §6).

  Treize clés de charges tiennent mal dans une carte. Le tableau défile DANS sa
  carte (la dernière colonne n'est plus rognée), garde la colonne Lot en place, abrège
  les en-têtes de clés (le nom entier reste dans l'infobulle et pour les lecteurs
  d'écran) et pose au pied une ligne Somme — calculée sur TOUTES les lignes, pas sur
  celles qu'une recherche laisse —, qui dit l'écart au dénominateur déclaré.
-->
<script lang="ts">
	import type { EtatDescriptif, LigneEtatDescriptif } from '$lib/api';
	import { abregerCle, libelleEcart, sommeDeCle } from '$lib/etat-descriptif';
	import { parAttribut } from '$lib/table-statuts';

	/** Les lignes à montrer (la recherche en écarte). */
	export let lignes: LigneEtatDescriptif[];
	/** Toutes les lignes lues : les sommes ne dépendent pas de la recherche. */
	export let toutes: LigneEtatDescriptif[];
	export let cles: EtatDescriptif['cles'];

	const { libelle: NATURE } = parAttribut({
		logement: { libelle: 'Logement' },
		commerce: { libelle: 'Commerce' },
		cave: { libelle: 'Cave' },
		parking: { libelle: 'Parking' },
		divers: { libelle: 'Divers' },
	});
</script>

<div
	class="defilement"
	tabindex="0"
	role="region"
	aria-label="Lignes lues — défiler pour voir toutes les clés"
>
	<table class="table imp-table-dense">
		<thead>
			<tr>
				<th class="lot">Lot</th><th>Bât.</th><th>Nature</th><th>Porte / place</th>
				<th>Niv.</th><th>Desserte</th>
				{#each cles as cle (cle.code)}
					<th class="nombre" title="{cle.libelle} — sur {cle.denominateur}">
						<span class="sr-only">{cle.libelle}</span>
						<span aria-hidden="true">{abregerCle(cle.libelle)}</span>
						<span class="denominateur" aria-hidden="true">/{cle.denominateur}</span>
					</th>
				{/each}
			</tr>
		</thead>
		<tbody>
			{#each lignes as l (l.rang)}
				<tr>
					<td class="lot numero-lot">
						{l.lot}
						{#if l.lot_origine}<span class="aide-ligne">divisé de {l.lot_origine}</span>{/if}
					</td>
					<td>{l.batiment ?? '—'}</td>
					<td class:illisible={!l.nature_lue}>
						{l.nature_lue ? NATURE[l.nature_lue] : (l.nature ?? '—')}
					</td>
					<td>{l.numero_usage ?? '—'}</td>
					<td>{l.niveau ?? '—'}</td>
					<td>{l.circulation ?? 'Direct'}</td>
					{#each cles as cle (cle.code)}
						<td class="nombre">{l.quotes[cle.code] ?? ''}</td>
					{/each}
				</tr>
			{/each}
		</tbody>
		{#if cles.length}
			<tfoot>
				<tr>
					<th class="lot" scope="row">Somme</th>
					<td colspan="5"></td>
					{#each cles as cle (cle.code)}
						{@const somme = sommeDeCle(toutes, cle.code)}
						<td
							class="nombre"
							class:ecart={somme !== cle.denominateur}
							title={libelleEcart(cle.denominateur, somme)}
						>
							{somme}
						</td>
					{/each}
				</tr>
			</tfoot>
		{/if}
	</table>
</div>

<style>
	/*  Le tableau défile DANS la carte, pas avec elle : la dernière colonne n'est plus
	    rognée par le bord, et ce qui reste à voir se devine à un bord estompé — pas à
	    une barre, pas à un trait (`apple-design` §12). Deux ombres peintes en `scroll`
	    (elles restent au bord) sont recouvertes par deux voiles peints en `local` (ils
	    suivent le contenu) : au bout du défilement le voile cache l'ombre, sans script.
	    La colonne Lot reste en place : on sait toujours de quel lot on lit les tantièmes. */
	/*  `position: relative` : les noms entiers des clés (`.sr-only`, en absolu) se posent dans
	    la zone qui défile. Sans lui ils s'ancraient à la page, au bout de la ligne — et le
	    navigateur mobile élargissait toute la page pour eux (25/10/2026). */
	.defilement {
		position: relative;
		overflow-x: auto;
		overscroll-behavior-x: contain;
		background:
			linear-gradient(to right, var(--color-surface) 30%, transparent) left center / 1.5rem 100%
				no-repeat local,
			linear-gradient(to left, var(--color-surface) 30%, transparent) right center / 1.5rem 100%
				no-repeat local,
			linear-gradient(to right, rgb(26 26 46 / 0.14), transparent) left center / 0.75rem 100%
				no-repeat scroll,
			linear-gradient(to left, rgb(26 26 46 / 0.14), transparent) right center / 0.75rem 100%
				no-repeat scroll;
	}
	.defilement:focus-visible {
		outline: 2px solid var(--color-primary);
		outline-offset: 2px;
	}
	.defilement table {
		width: max-content;
		min-width: 100%;
	}
	.defilement th,
	.defilement td {
		white-space: nowrap;
	}
	.defilement .lot {
		position: sticky;
		left: 0;
		z-index: 1;
		background: var(--color-surface);
	}
	.defilement thead th.lot,
	.defilement tfoot th.lot {
		background: var(--color-bg);
	}
	.denominateur {
		display: block;
		font-weight: 400;
		text-transform: none;
		letter-spacing: 0;
	}
	tfoot th,
	tfoot td {
		border-top: 2px solid var(--color-border);
		font-weight: 600;
		background: var(--color-bg);
	}
	tfoot td.ecart {
		color: var(--color-warning-texte);
	}
	.nombre {
		text-align: right;
		font-variant-numeric: tabular-nums;
	}
	.numero-lot {
		font-weight: 600;
	}
	.aide-ligne {
		display: block;
		font-weight: 400;
		font-size: var(--fs-xs);
		color: var(--color-text-muted);
	}
	.illisible {
		color: var(--color-danger);
	}
</style>
