<!--
  BilanCarnet.svelte — 📊 le bilan d'un exercice du carnet d'entretien (#1645).

  Un argument chiffré pour l'assemblée générale : sur un exercice comptable
  (borné par le mois de début d'exercice de la fiche copropriété), par catégorie
  d'affaire du carnet — durée moyenne, temps moyen par étape du kanban, relances
  au syndic et délai de réaction, intervenants les plus lents.

  🔴 RÉSERVÉ au conseil syndical (arbitré le 04/10/2026). La page le monte sous
  `$isCS`, et le serveur refuse tout autre lecteur (`require_cs_or_admin`) :
  masquer répond à ce qui s'affiche, refuser à ce qui s'atteint.

  Monté par la page Résidence, à côté de `CarnetEntretien` et non dedans : le
  carnet est la lecture de tous les copropriétaires, le bilan celle du conseil.
  Replié à l'arrivée, il ne demande rien au serveur tant qu'on ne l'ouvre pas.
-->
<script lang="ts">
	import { carnet as carnetApi, type BilanCarnet } from '#lib/api/index.ts';
	import { essayer } from '#lib/chargement.ts';
	import { fmtDate } from '#lib/date.ts';
	import { fmtJours, libelleAffaires } from '#lib/synthese.ts';
	import { categorieTicketLabel } from '#lib/tickets.ts';
	import { fmtNombre, nombreOuNull } from '#lib/utils.ts';
	import ChoixPastilles from './ChoixPastilles.svelte';
	import EtatListe from './EtatListe.svelte';
	import MoyennesAffaires from './MoyennesAffaires.svelte';
	import SectionRepliee from './SectionRepliee.svelte';

	let ouvert = false;
	let bilan: BilanCarnet | null = null;
	let erreur = '';
	let chargement = false;
	/**  L'exercice choisi — l'année où il commence, en chaîne (`ChoixPastilles`).
	 *   Posé par le PREMIER chargement (l'exercice en cours, que le serveur
	 *   désigne), puis par la pastille. */
	let choisi = '';

	async function charger(exercice: number | null): Promise<BilanCarnet | null> {
		chargement = true;
		[bilan, erreur] = await essayer<BilanCarnet | null>(carnetApi.metriques(exercice), null);
		chargement = false;
		return bilan;
	}

	/**  Le dépliage : rien n'est demandé au serveur avant le premier. */
	async function basculer() {
		ouvert = !ouvert;
		if (!ouvert || bilan || chargement) return;
		const lu = await charger(null);
		if (lu) choisi = String(lu.exercice.annee);
	}

	/**  Une autre pastille : l'exercice qu'elle nomme, s'il n'est pas déjà affiché.
	 *   ⚠️ Ne dépend QUE du choix — la fonction ne le réécrit jamais, donc aucun
	 *   tour de réactivité ne la rappelle. */
	function choisir(valeur: string) {
		const annee = nombreOuNull(valeur);
		if (annee !== null && annee !== bilan?.exercice.annee && !chargement) charger(annee);
	}

	$: choisir(choisi);

	$: exercices = (bilan?.exercices ?? []).map((e) => ({ val: String(e.annee), label: e.libelle }));
</script>

<SectionRepliee
	titre="📊 Bilan de l'exercice — conseil syndical"
	{ouvert}
	surBascule={basculer}
	enSerie
>
	<div class="bilan">
		<p class="aide">
			Les affaires du carnet closes pendant l'exercice comptable, résolues ou annulées, mesurées
			comme leur synthèse. Les durées sont en jours ouvrés : de 9 h à 17 h, hors week-ends et jours
			fériés. Réservé au conseil syndical.
		</p>
		{#if exercices.length > 1}
			<ChoixPastilles
				options={exercices}
				bind:valeur={choisi}
				tous={false}
				libelle="Exercice"
				libelleDevant
			/>
		{/if}
		<EtatListe
			{chargement}
			{erreur}
			vide={!bilan?.categories.length}
			titreVide="Aucune affaire close"
			messageVide={bilan
				? `Aucune affaire du carnet n'a été close sur l'exercice ${bilan.exercice.libelle}.`
				: ''}
		>
			{#if bilan}
				<p class="bilan-periode">
					Exercice <strong>{bilan.exercice.libelle}</strong>, du {fmtDate(bilan.exercice.debut)} au
					{fmtDate(bilan.exercice.fin)} · {libelleAffaires({
						nombre: bilan.nombre,
						annulees: bilan.categories.reduce((n, c) => n + c.annulees, 0),
					})}
				</p>
				{#each bilan.categories as c (c.categorie)}
					<section class="bilan-categorie" aria-labelledby="bilan-{c.categorie}">
						<h3 class="bilan-titre" id="bilan-{c.categorie}">
							{categorieTicketLabel(c.categorie)}
							<span class="bilan-compte">{libelleAffaires(c)}</span>
						</h3>
						<MoyennesAffaires resume={c} libelle="Moyennes — {categorieTicketLabel(c.categorie)}" />
						{#if c.prestataires.length}
							<div class="table-wrap">
								<table class="table">
									<caption class="table-legende"
										>Intervenants les plus lents — étape « Chez le prestataire »</caption
									>
									<thead>
										<tr>
											<th scope="col">Intervenant</th>
											<th scope="col" class="nombre">Durée moyenne (jours ouvrés)</th>
											<th scope="col" class="nombre">Affaires</th>
										</tr>
									</thead>
									<tbody>
										{#each c.prestataires as p (p.prestataire_id)}
											<tr>
												<td>{p.nom}</td>
												<td class="nombre">{fmtJours(p.jours)}</td>
												<td class="nombre">{fmtNombre(p.nombre)}</td>
											</tr>
										{/each}
									</tbody>
								</table>
							</div>
						{/if}
					</section>
				{/each}
			{/if}
		</EtatListe>
	</div>
</SectionRepliee>

<style>
	.bilan {
		display: flex;
		flex-direction: column;
		gap: 1rem;
		/*  Le carnet suit : sans cet espace, son texte d'aide se lisait comme la
		    dernière ligne du bilan (relevé sur capture, 04/10/2026). */
		margin-bottom: 1.5rem;
	}
	.bilan-periode {
		margin: 0;
		font-size: var(--fs-md);
		color: var(--color-text-muted);
	}
	.bilan-categorie {
		display: flex;
		flex-direction: column;
		gap: 0.6rem;
		min-width: 0;
	}
	.bilan-titre {
		display: flex;
		flex-wrap: wrap;
		align-items: baseline;
		gap: 0.25rem 0.6rem;
		margin: 0;
		font-size: var(--fs-lg);
		color: var(--color-primary);
		border-bottom: 1px solid var(--color-border);
		padding-bottom: 0.35rem;
	}
	.bilan-compte {
		font-size: var(--fs-sm);
		font-weight: 400;
		color: var(--color-text-muted);
	}
</style>
