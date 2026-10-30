<script lang="ts">
	import { fmtNombre } from '#lib/utils.ts';
	import type { Batiment, Copropriete } from '#lib/api/index.ts';
	/**
	 * Fiche d'identité de la résidence — adresse, immatriculation, lots,
	 * assurance, et composition par bâtiment.
	 *
	 * Extrait de `routes/(app)/residence/+page.svelte` le 13/08/2026 : cette page
	 * fait 1 459 lignes et la règle de modularité (rang 1) refuse qu'elle grossisse
	 * — or il fallait y ajouter le second décompte de lots de la fiche ANAH.
	 *
	 * La coupe emporte le bloc AVEC sa feuille de style. Les classes `info-*` et
	 * `batiment-table` étaient à portée locale (styles Svelte scopés) : les laisser
	 * derrière aurait rendu ce composant sans style, et les recopier aurait créé
	 * une seconde source pour les mêmes règles. Elles ne servaient nulle part
	 * ailleurs dans la page — la coupe est donc nette, sans duplication.
	 */
	import { fmtDateShort as fmt, libelleExercice } from '#lib/date.ts';

	/**  Comment s'écrit l'échéance d'un contrat sur cette fiche.
	 *
	 *   🔴 Une SEULE écriture pour l'assurance et le syndic : ce sont deux
	 *   contrats de même nature, et la fiche les traite comme le même geste.
	 *   Deux rendus recopiés divergeraient au premier ajustement.
	 *
	 *   ⚠️ « reconduit tacitement » n'est pas décoratif. Sans lui, une échéance
	 *   REPORTÉE (le contrat court une année de plus, faute d'avoir été dénoncé)
	 *   ne se distingue pas d'un terme négocié — et l'on relancerait le premier
	 *   comme le second. Signalé par l'utilisateur le 29/08/2026 : une assurance
	 *   non stoppée est automatiquement reconduite. */
	function echeance(date: string | null | undefined, reconduit: boolean): string {
		if (!date) return '';
		return ` — échéance ${fmt(date)}${reconduit ? ' (reconduit tacitement)' : ''}`;
	}

	/**  Le mandat de syndic ne se reconduit pas : échu, il appelle une AG.
	 *
	 *   🔴 Signalé le 29/08/2026 : *« c'est l'assurance qui est reconduite
	 *   tacitement, pas le syndic »*. Un mandat est voté en assemblée générale
	 *   pour un terme ; passé ce terme il a CESSÉ. L'afficher comme une échéance
	 *   ordinaire — pire, reportée — supprimait de la fiche le seul signal qui
	 *   demande une décision. */
	function mandat(date: string | null | undefined, echu: boolean): string {
		if (!date) return '';
		return echu ? ` — mandat échu depuis le ${fmt(date)}` : ` — mandat jusqu'au ${fmt(date)}`;
	}

	export let copropriete: Copropriete;
	export let batiments: Batiment[] = [];

	$: hasOrphanLots = (copropriete?.nb_parkings_communs ?? 0) > 0;
	$: totalAppart = batiments.reduce((s, b) => s + (b.nb_appartements ?? 0), 0);
	$: totalCave = batiments.reduce((s, b) => s + (b.nb_caves ?? 0), 0);
	$: totalParking =
		batiments.reduce((s, b) => s + (b.nb_parkings ?? 0), 0) +
		(copropriete?.nb_parkings_communs ?? 0);
	$: totalLocaux = batiments.reduce((s, b) => s + (b.nb_locaux_commerciaux ?? 0), 0);
</script>

<div class="card carte-fiche">
	{#if copropriete.adresse}
		<div class="bloc-adresse">
			<span class="info-label">Adresse</span>
			<div class="info-value valeur-adresse">{copropriete.adresse}</div>
		</div>
	{/if}

	<!--  DEUX rangées, et la coupe n'est pas cosmétique : au-dessus ce que la
	      copropriété EST (immatriculation, lots), au-dessous ce qu'elle a
	      CONTRACTÉ (assurance, syndic). Une seule grille auto-remplie mettait les
	      quatre premiers champs sur une ligne et laissait le syndic seul sur la
	      suivante — un orphelin que rien ne rattachait à l'assurance, alors que
	      ce sont deux contrats de même nature (signalé à l'écran le 29/08/2026).

	      ⚠️ Deux colonnes fixes pour les contrats, pas `auto-fill` : sur un large
	      écran l'assurance et le syndic doivent rester CÔTE À CÔTE, et une grille
	      auto-remplie y aurait glissé un troisième champ le jour où l'on en
	      ajoute un. Sous 560 px, la colonne unique reprend la main. -->
	{#if copropriete.numero_immatriculation || copropriete.nb_lots_total || copropriete.nb_lots_principaux}
		<div class="info-grid">
			{#if copropriete.numero_immatriculation}
				<div class="info-item">
					<span class="info-label">N° immatriculation</span>
					<span class="info-value info-highlight">{copropriete.numero_immatriculation}</span>
				</div>
			{/if}
			{#if copropriete.nb_lots_principaux}
				<div class="info-item">
					<span class="info-label">Lots d'habitation, commerces et bureaux</span>
					<span class="info-value">{fmtNombre(copropriete.nb_lots_principaux)}</span>
				</div>
			{/if}
			{#if copropriete.nb_lots_total}
				<div class="info-item">
					<span class="info-label">Lots au total</span>
					<span class="info-value">{fmtNombre(copropriete.nb_lots_total)}</span>
				</div>
			{/if}
			{#if copropriete.mois_debut_exercice}
				<div class="info-item">
					<span class="info-label">Exercice comptable</span>
					<span class="info-value">{libelleExercice(copropriete.mois_debut_exercice)}</span>
				</div>
			{/if}
		</div>
	{/if}

	{#if copropriete.assurance_compagnie || copropriete.syndic_cabinet}
		<div class="contrats-grid">
			{#if copropriete.assurance_compagnie}
				<div class="info-item">
					<span class="info-label">🛡️ Assurance</span>
					<span class="info-value"
						>{copropriete.assurance_compagnie}{echeance(
							copropriete.assurance_echeance,
							copropriete.assurance_reconduit,
						)}</span
					>
				</div>
			{/if}
			{#if copropriete.syndic_cabinet}
				<!--  Le lien mène à l'annuaire, qui porte les PERSONNES — la fiche ne
				      les recopie pas (`syndic_du_contrat` : l'organisation ici, les
				      gens là-bas). -->
				<div class="info-item">
					<span class="info-label">🏢 Syndic</span>
					<span class="info-value">
						<a href="/annuaire#syndic">{copropriete.syndic_cabinet}</a><span
							class:mandat-echu={copropriete.syndic_echu}
							>{mandat(copropriete.syndic_echeance, copropriete.syndic_echu)}</span
						>
					</span>
				</div>
			{/if}
		</div>
	{/if}

	{#if batiments.length > 0}
		<div class="bloc-composition">
			<p class="info-label label-composition">Composition</p>
			<div class="table-wrap">
				<table class="batiment-table">
					<thead>
						<tr>
							<th>Bâtiment</th>
							<th>Parkings</th>
							<th>Caves</th>
							<th>Appartements</th>
							<th>Loc. commerciaux</th>
						</tr>
					</thead>
					<tbody>
						{#each batiments as b (b.id)}
							<tr>
								<td class="batiment">Bât. {b.numero}</td>
								<td>{(b.nb_parkings ?? 0) > 0 ? fmtNombre(b.nb_parkings) : '—'}</td>
								<td>{(b.nb_caves ?? 0) > 0 ? fmtNombre(b.nb_caves) : '—'}</td>
								<td>{(b.nb_appartements ?? 0) > 0 ? fmtNombre(b.nb_appartements) : '—'}</td>
								<td
									>{(b.nb_locaux_commerciaux ?? 0) > 0
										? fmtNombre(b.nb_locaux_commerciaux)
										: '—'}</td
								>
							</tr>
						{/each}
						{#if hasOrphanLots}
							<tr>
								<td class="communs">Communs</td>
								<td>{fmtNombre(copropriete.nb_parkings_communs)}</td>
								<td>—</td>
								<td>—</td>
								<td>—</td>
							</tr>
						{/if}
					</tbody>
					<tfoot>
						<tr>
							<td>Total</td>
							<td>{totalParking > 0 ? totalParking : '—'}</td>
							<td>{totalCave > 0 ? totalCave : '—'}</td>
							<td>{totalAppart > 0 ? totalAppart : '—'}</td>
							<td>{totalLocaux > 0 ? totalLocaux : '—'}</td>
						</tr>
					</tfoot>
				</table>
			</div>
		</div>
	{/if}
</div>

<style>
	/* ── Infos résidence ────────────────────────────────────────── */
	.info-grid {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(min(220px, 100%), 1fr));
		gap: 0.6rem;
	}
	.info-item {
		display: flex;
		flex-direction: column;
		gap: 0.1rem;
	}

	/*  Les contrats : deux colonnes, séparés du bloc d'identité par un filet.
	    Le filet dit que ce sont deux natures d'information, là où un simple
	    espacement se lit comme un retour à la ligne de la même liste. */
	.contrats-grid {
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: 0.6rem 1.5rem;
		margin-top: 1rem;
		padding-top: 0.9rem;
		border-top: 1px solid var(--color-border);
	}
	@media (max-width: 767px) {
		.contrats-grid {
			grid-template-columns: 1fr;
		}
	}
	.info-label {
		font-size: var(--fs-2xs);
		color: var(--color-text-muted);
		text-transform: uppercase;
		letter-spacing: 0.04em;
		font-weight: 600;
	}
	.info-value {
		font-size: var(--fs-base);
		font-weight: 500;
	}
	.info-highlight {
		color: var(--color-primary);
		font-weight: 700;
	}
	/*  Un mandat échu n'est pas une information de plus : c'est une décision en
	    attente. La couleur d'alerte le sort de la lecture ordinaire. */
	.mandat-echu {
		color: var(--color-danger);
		font-weight: 600;
	}

	/* ── Tableau bâtiments ────────────────────────────────────────────── */
	.batiment-table {
		width: 100%;
		border-collapse: collapse;
		font-size: var(--fs-base);
		margin-top: 0.25rem;
	}
	.batiment-table th {
		text-align: left;
		padding: 0.4rem 0.75rem;
		font-size: var(--fs-2xs);
		text-transform: uppercase;
		letter-spacing: 0.04em;
		color: var(--color-text-muted);
		border-bottom: 2px solid var(--color-border);
		font-weight: 600;
	}
	.batiment-table td {
		padding: 0.4rem 0.75rem;
		border-bottom: 1px solid var(--color-border);
	}
	.batiment-table tfoot td {
		font-weight: 700;
		border-top: 2px solid var(--color-border);
		border-bottom: none;
	}
	.carte-fiche {
		padding: 1.25rem;
	}
	.bloc-adresse {
		margin-bottom: 1rem;
	}
	.valeur-adresse {
		margin-top: 0.25rem;
	}
	.bloc-composition {
		border-top: 1px solid var(--color-border);
		padding-top: 1rem;
	}
	.label-composition {
		margin-bottom: 0.6rem;
	}
	.batiment {
		font-weight: 600;
	}
	.communs {
		color: var(--color-text-muted);
		font-style: italic;
	}
</style>
