<!--
  **Mes charges selon le règlement** — le tableau croisé de « Mes lots » (#2251, maquette A
  arbitrée le 25/10/2026).

  Une ligne par clé, une colonne par lot (« Logement 15 », « Cave 417 », « Place 450 »),
  puis le total et le pourcentage. Sous chaque clé, ce qu'elle finance selon le règlement
  (« Escalier A' — l'escalier qui dessert les deux niveaux de sous-sol ») et combien de lots
  y contribuent. Il remplace trois rendus redondants — le total par clé, le tableau de
  chaque lot, la phrase de la carte — qui ne nommaient pas les lots.

  - Un seul lot : pas de colonne « Total », elle redirait la colonne du lot.
  - Sur téléphone (moins de 768 px), au-delà de deux lots : une clé par bloc — le total,
    ce qu'elle finance, puis la part de chaque lot dessous —, sans défilement de côté.
  - L'écart d'une clé (ses parts ne font pas le dénominateur) se dit UNE fois, sous le
    tableau, par la note du serveur : il concerne la copropriété, pas la part du lecteur.
  - La mention sous le tableau dit ce que vaut ce tableau : une lecture du règlement ; ce
    que l'on paie, seul le syndic le dit (demandé le 25/10/2026) — et où le joindre.
  - Aligné sur l'appel de fonds (#2252) : sous chaque clé, son libellé chez le syndic quand
    le conseil l'a saisi ; les clés que le syndic n'appelle pas en ce moment passent dans un
    bloc replié, avec leur part — repliées, jamais cachées.

  Rien n'est calculé ici au-delà d'une addition (`$lib/charges-lots`) : les parts, les
  définitions et les notes viennent du serveur. Rien ne s'affiche sans part lisible (un
  locataire reçoit `null`).
-->
<script lang="ts">
	import { onDestroy } from 'svelte';
	import BlocDeCle from '$lib/components/BlocDeCle.svelte';
	import Icon from '$lib/components/Icon.svelte';
	import { AVIS_CHARGES, FICHE_DU_SYNDIC, lotSurligne, tableauDesCharges } from '$lib/charges-lots';
	import type { MonLot } from '$lib/api';
	import { fmtNombre, fmtPartEnPourcent } from '$lib/utils';

	export let lots: Pick<MonLot, 'id' | 'numero' | 'nature' | 'type' | 'quotes_parts'>[];

	$: tableau = tableauDesCharges(lots);
	$: plusieurs = tableau.colonnes.length > 1;
	$: notes = [...tableau.lignes, ...tableau.nonAppelees].filter((l) => l.note);

	//  Le surlignage demandé par une carte s'éteint seul : il désigne, il ne marque pas.
	let minuterie: ReturnType<typeof setTimeout> | undefined;
	const desabonner = lotSurligne.subscribe((id) => {
		clearTimeout(minuterie);
		if (id !== null) minuterie = setTimeout(() => lotSurligne.set(null), 2500);
	});
	onDestroy(() => {
		clearTimeout(minuterie);
		desabonner();
	});

	//  Un seul lot : sa colonne porte la part entière (« 218/10 006 »), faute de Total.
	const part = (n: number | undefined, sur: number | null) =>
		n === undefined ? '—' : sur ? `${fmtNombre(n)}/${fmtNombre(sur)}` : fmtNombre(n);
</script>

{#if tableau.lignes.length || tableau.nonAppelees.length}
	<section
		id="mes-charges"
		class="card mes-charges"
		class:en-blocs={tableau.colonnes.length > 2}
		aria-labelledby="titre-mes-charges"
	>
		<h2 id="titre-mes-charges" class="section-title">Mes charges selon le règlement</h2>
		<p class="aide">
			{plusieurs
				? 'Votre part de chaque clé de charges, lot par lot, et le total pour l’ensemble de vos lots.'
				: 'Votre part de chaque clé de charges.'}
		</p>

		<div class="table-wrap vue-tableau">
			<table class="table charges">
				<thead>
					<tr>
						<th scope="col">Clé de charges</th>
						{#each tableau.colonnes as col (col.id)}
							<th scope="col" class="nombre" class:surligne={$lotSurligne === col.id}>
								{col.nom}
							</th>
						{/each}
						{#if plusieurs}<th scope="col" class="nombre">Total</th>{/if}
						<th scope="col" class="nombre">%</th>
					</tr>
				</thead>
				<tbody>
					{#each tableau.lignes as l (l.cle)}
						<tr>
							<th scope="row">
								<span class="cle">{l.libelle}</span>
								{#if l.description}<span class="finance">{l.description}</span>{/if}
								{#if l.libelleSyndic}<span class="finance"
										>Sur l’appel de fonds : {l.libelleSyndic}</span
									>{/if}
								{#if l.nbLots > 1}<span class="contributeurs">{l.nbLots} lots y contribuent</span
									>{/if}
							</th>
							{#each tableau.colonnes as col (col.id)}
								<td
									class="nombre"
									class:absent={l.parts[col.id] === undefined}
									class:surligne={$lotSurligne === col.id}
									>{part(l.parts[col.id], plusieurs ? null : l.denominateur)}</td
								>
							{/each}
							{#if plusieurs}
								<td class="nombre total">{fmtNombre(l.total)}/{fmtNombre(l.denominateur)}</td>
							{/if}
							<td class="nombre">{fmtPartEnPourcent(l.total, l.denominateur)}</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>

		<!--  Sur téléphone, au-delà de deux lots : une clé par bloc (la classe `en-blocs`
		      bascule l'affichage, sans second chargement). -->
		<ul class="vue-blocs">
			{#each tableau.lignes as l (l.cle)}
				<li><BlocDeCle ligne={l} colonnes={tableau.colonnes} /></li>
			{/each}
		</ul>

		{#if tableau.nonAppelees.length}
			<details class="non-appelees">
				<summary
					>Prévues au règlement, non appelées actuellement ({tableau.nonAppelees.length})</summary
				>
				<p class="aide">
					Le syndic n’appelle pas ces clés en ce moment : elles ne figurent pas sur votre appel de
					fonds. Votre part, celle de l’acte, reste la même le jour où il les appelle.
				</p>
				<ul class="blocs">
					{#each tableau.nonAppelees as l (l.cle)}
						<li><BlocDeCle ligne={l} colonnes={tableau.colonnes} /></li>
					{/each}
				</ul>
			</details>
		{/if}

		{#each notes as l (l.cle)}
			<p class="aide note"><Icon name="file-text" size={16} />« {l.libelle} » : {l.note}</p>
		{/each}
		<p class="aide note"><Icon name="help-circle" size={16} />{AVIS_CHARGES}</p>
		<p class="aide note">
			<Icon name="mail" size={16} />Une question sur un montant ?
			<a href={FICHE_DU_SYNDIC}>Contacter le syndic</a>
		</p>
	</section>
{/if}

<style>
	.mes-charges {
		margin-bottom: 1rem;
	}
	.charges tbody th {
		text-align: left;
		text-transform: none;
		background: transparent;
		color: var(--color-text);
		font-weight: 500;
		font-size: var(--fs-base);
		vertical-align: top;
	}
	.nombre {
		text-align: right;
		font-variant-numeric: tabular-nums;
		white-space: nowrap;
	}
	.total {
		font-weight: 600;
	}
	.absent {
		color: var(--color-text-muted);
	}
	/*  Le lot que sa carte désigne : un aplat discret, le temps de le retrouver. */
	.surligne {
		background: var(--color-primary-light);
		transition: background-color var(--duree-apparition) var(--ease-out);
	}
	.cle {
		font-weight: 600;
	}
	.finance,
	.contributeurs {
		display: block;
		font-weight: 400;
		font-size: var(--fs-sm);
		color: var(--color-text-muted);
		line-height: 1.4;
		margin-top: 0.15rem;
	}
	.contributeurs {
		font-size: var(--fs-xs);
	}
	.note {
		display: flex;
		gap: 0.4rem;
		align-items: flex-start;
		margin: 0.6rem 0 0;
	}
	.vue-blocs,
	.blocs {
		list-style: none;
		margin: 0;
		padding: 0;
	}
	.vue-blocs {
		display: none;
	}
	.vue-blocs li,
	.blocs li {
		padding: 0.6rem 0;
		border-bottom: 1px solid var(--color-border);
	}
	.non-appelees {
		margin-top: 0.75rem;
	}
	.non-appelees summary {
		cursor: pointer;
		font-weight: 600;
		font-size: var(--fs-sm);
	}
	.non-appelees .aide {
		margin: 0.4rem 0 0;
	}
	@media (max-width: 767px) {
		.en-blocs .vue-tableau {
			display: none;
		}
		.en-blocs .vue-blocs {
			display: block;
		}
	}
</style>
