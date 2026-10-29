<!--
  **La vue locataire de « Mes lots »** — le lot loué, son bail et son
  propriétaire, puis les lots que le locataire possède en propre.

  Extraite de `mon-lot/+page.svelte` le 01/10/2026 (#779), en pendant de
  `LotsBailleur` : la page choisit la vue selon le rôle, chaque vue rend la
  sienne. Au passage, deux copies ont rejoint leur source :

  - le badge du bail était recomposé ici — « Bail actif », TOUJOURS vert, et
    `statut.replace('_', ' ')` sinon. Un bail en cours de sortie y serait sorti
    vert et mal libellé ; il passe par `BadgeStatutBail` (`lint:statut-recalcule`) ;
  - les caractéristiques du lot, écrites deux fois ici et une fois dans la
    page, passent par `CaracteristiquesLot` (`lint:caracteristiques-lot`).
-->
<script lang="ts">
	import BadgeStatutBail from '#lib/components/BadgeStatutBail.svelte';
	import CaracteristiquesLot from '#lib/components/CaracteristiquesLot.svelte';
	import TableauCharges from '#lib/components/TableauCharges.svelte';
	import QuestionsLocation from '#lib/components/QuestionsLocation.svelte';
	import type { BailLocataire, MonLot } from '#lib/api/index.ts';
	import { fmtDateShort as fmt } from '#lib/date.ts';
	import { nomAffiche } from '#lib/noms.ts';

	/** Le bail du locataire (`bailleur.monBail()`), ou `null` s'il n'en a pas. */
	export let bail: BailLocataire | null = null;
	/** Ses lots : ceux qu'il LOUE (`type_lien` locataire) et ceux qu'il possède. */
	export let lots: MonLot[] = [];
	/** Appelé quand il vient de dire ce qu'il loue : la page relit ses lots. */
	export let onRattache: () => void = () => {};

	//  Sans bail, un lot loué se lit sur son lien (04/10/2026) : le locataire
	//  l'a déclaré lui-même, d'après le fichier des lots (`QuestionsLocation`).
	$: loues = lots.filter((l) => l.type_lien === 'locataire');
	//  Une seule carte de lot pour les deux listes ; celle des lots loués se tait
	//  quand un bail les montre déjà.
	$: sections = [
		{ titre: '🏠 Lots loués', lots: bail ? [] : loues, enPropre: false },
		{
			titre: '🏢 Lots en propriété',
			lots: lots.filter((l) => l.type_lien !== 'locataire'),
			enPropre: true,
		},
	].filter((s) => s.lots.length > 0);
</script>

{#if bail}
	<div class="lots-section-label">🏠 Lot loué</div>
	<div class="card largeur-saisie carte-lot">
		<div class="carte-lot-entete">
			<span class="lbc-lot-badge">{bail.lot_batiment_nom ?? '—'} / {bail.lot_numero ?? '—'}</span>
			<BadgeStatutBail statut={bail.statut} compact />
		</div>
		<CaracteristiquesLot
			type={bail.lot_type}
			typeAppartement={bail.lot_type_appartement}
			etage={bail.lot_etage}
			superficie={bail.lot_superficie}
		>
			<svelte:fragment slot="avant">
				<dt>Bâtiment</dt>
				<dd>{bail.lot_batiment_nom ?? '—'}</dd>
			</svelte:fragment>
			<svelte:fragment slot="apres">
				<dt>Entrée</dt>
				<dd>{fmt(bail.date_entree)}</dd>
				{#if bail.date_sortie_prevue}
					<dt>Sortie prévue</dt>
					<dd>{fmt(bail.date_sortie_prevue)}</dd>
				{/if}
			</svelte:fragment>
		</CaracteristiquesLot>
		{#if bail.bailleur_nom || bail.bailleur_prenom}
			<div class="proprietaire">
				🏢 Propriétaire : <strong>{nomAffiche(bail.bailleur_prenom, bail.bailleur_nom)}</strong>
				{#if bail.bailleur_email}<br />📬
					<a href="mailto:{bail.bailleur_email}">{bail.bailleur_email}</a>{/if}
				{#if bail.bailleur_telephone}<br />📞 {bail.bailleur_telephone}{/if}
			</div>
		{/if}
	</div>
{:else if loues.length === 0}
	<QuestionsLocation {onRattache} />
{/if}

{#each sections as section (section.titre)}
	<div class="lots-section-label" class:lots-en-propre={section.enPropre}>
		{section.titre} ({section.lots.length})
	</div>
	<!--  Les charges des lots qu'il possède (#2251) — ceux qu'il loue n'en montrent aucune. -->
	{#if section.enPropre}<div class="largeur-saisie">
			<TableauCharges lots={section.lots} />
		</div>{/if}
	{#each section.lots as lot (lot.id)}
		<div class="card largeur-saisie carte-lot">
			<h2 class="carte-lot-titre">{lot.batiment_nom ?? '—'} / {lot.numero}</h2>
			<CaracteristiquesLot
				type={lot.type}
				typeAppartement={lot.type_appartement}
				etage={lot.etage}
				superficie={lot.superficie}
				designation={lot}
			/>
		</div>
	{/each}
{/each}

<style>
	.carte-lot {
		margin-bottom: 1.5rem;
	}
	.carte-lot-entete {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		margin-bottom: 0.75rem;
	}
	.carte-lot-titre {
		font-size: var(--fs-xl);
		font-weight: 600;
		margin-bottom: 0.75rem;
	}
	.lots-en-propre {
		margin-top: 1.5rem;
	}
	.proprietaire {
		margin-top: 0.75rem;
		font-size: var(--fs-md);
		color: var(--color-text-muted);
	}
	.proprietaire a {
		color: var(--color-primary);
	}
</style>
