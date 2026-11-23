<!--
  MetriquesPrestataire.svelte — 📊 les affaires closes d'un prestataire, en chiffres (#1646).

  Celles où il était l'intervenant désigné, du carnet ou non (arbitré le
  04/10/2026) : combien, combien de temps « Chez le prestataire » (jours ouvrés),
  la durée totale, les relances au syndic — l'ensemble, puis chaque exercice
  comptable, le plus récent d'abord.

  🔴 RÉSERVÉ au conseil syndical, comme la notation de l'intervenant : la carte
  le monte sous `$estModerateur`, le serveur refuse tout autre lecteur
  (`require_cs_or_admin`).

  Monté dans le corps DÉPLIÉ de `CartePrestataire` : il ne demande rien au
  serveur tant qu'on n'a pas ouvert la fiche.
-->
<script lang="ts">
	import { onMount } from 'svelte';
	import { prestataires as prestApi, type MetriquesPrestataire } from '#lib/api/index.ts';
	import { essayer } from '#lib/chargement.ts';
	import {
		etapeMoyenne,
		fmtJours,
		libelleAffaires,
		libelleIssue,
		surAffaires,
	} from '#lib/synthese.ts';
	import { basculer } from '#lib/accordeon.ts';
	import { fmtDate } from '#lib/date.ts';
	import { fmtNombre } from '#lib/utils.ts';
	import EtatListe from './EtatListe.svelte';
	import MoyennesAffaires from './MoyennesAffaires.svelte';
	import { SEPARATEUR } from '#lib/separateurs.ts';

	export let prestataireId: number;

	/** L'étape qui mesure un intervenant (`agregats.ETAPE_PRESTATAIRE`). */
	const CHEZ_PRESTATAIRE = 'chez_prestataire';

	let donnees: MetriquesPrestataire | null = null;
	/** L'exercice déplié — un seul à la fois. */
	let ouvert: number | null = null;
	let erreur = '';
	let chargement = true;

	onMount(async () => {
		[donnees, erreur] = await essayer<MetriquesPrestataire | null>(
			prestApi.metriques(prestataireId),
			null,
		);
		chargement = false;
	});

	$: ensemble = donnees?.ensemble ?? null;
	$: chez = ensemble ? etapeMoyenne(ensemble, CHEZ_PRESTATAIRE) : null;
</script>

<section class="metriques-presta" aria-labelledby="metriques-presta-{prestataireId}">
	<span class="detail-label" id="metriques-presta-{prestataireId}">
		📊 Affaires traitées{SEPARATEUR.tiret}conseil syndical
	</span>
	<EtatListe
		{chargement}
		{erreur}
		vide={!ensemble?.nombre}
		compact
		messageVide="Aucune affaire close où ce prestataire était l'intervenant désigné."
	>
		{#if ensemble}
			<p class="metriques-resume">
				{libelleAffaires(ensemble)}.
				{#if chez}
					Étape « Chez le prestataire » : <strong>{fmtJours(chez.jours)}</strong> en moyenne (jours
					ouvrés), {surAffaires(chez.nombre)}.
				{:else}
					Aucune n'est passée par l'étape « Chez le prestataire ».
				{/if}
			</p>
			<MoyennesAffaires resume={ensemble} libelle="Moyennes des affaires du prestataire" />
			<ul class="exercices" role="list">
				{#each donnees?.exercices ?? [] as e (e.annee)}
					<li class="exercice">
						<button
							type="button"
							class="exercice-entete"
							aria-expanded={ouvert === e.annee}
							aria-controls="exercice-{prestataireId}-{e.annee}"
							on:click={() => (ouvert = basculer(ouvert, e.annee))}
						>
							<span class="chevron" aria-hidden="true">{ouvert === e.annee ? '▾' : '▸'}</span>
							<strong>{e.libelle}</strong>
							<span class="resume-exercice">
								{surAffaires(e.nombre)}{SEPARATEUR.point}chez le prestataire {fmtJours(
									etapeMoyenne(e, CHEZ_PRESTATAIRE)?.jours,
								)}{SEPARATEUR.point}durée totale {fmtJours(
									e.duree_totale,
								)}{SEPARATEUR.point}{fmtNombre(e.relances)} relance{e.relances > 1 ? 's' : ''}
							</span>
						</button>
						{#if ouvert === e.annee}
							<ul id="exercice-{prestataireId}-{e.annee}" class="affaires" role="list">
								{#each e.affaires as a (a.id)}
									<li class="affaire">
										<span class="affaire-titre">{a.titre}</span>
										<span class="affaire-date">{a.cloture ? fmtDate(a.cloture) : '—'}</span>
										<span class="affaire-issue">{libelleIssue(a.issue)}</span>
									</li>
								{:else}
									<li class="affaire">Aucune affaire.</li>
								{/each}
							</ul>
						{/if}
					</li>
				{/each}
			</ul>
		{/if}
	</EtatListe>
</section>

<style>
	.metriques-presta {
		display: flex;
		flex-direction: column;
		gap: 0.6rem;
		margin-top: 0.75rem;
		min-width: 0;
	}
	.exercices {
		list-style: none;
		margin: 0;
		padding: 0;
		display: flex;
		flex-direction: column;
		gap: 0.4rem;
	}
	.exercice {
		border: 1px solid var(--color-border);
		border-radius: 0.5rem;
		overflow: hidden;
	}
	.exercice-entete {
		width: 100%;
		display: flex;
		align-items: baseline;
		flex-wrap: wrap;
		gap: 0.5rem;
		padding: 0.6rem 0.75rem;
		min-height: 44px;
		border: 0;
		background: none;
		text-align: left;
		color: inherit;
		font: inherit;
		cursor: pointer;
	}
	.resume-exercice {
		color: var(--color-text-muted);
		font-size: var(--fs-sm);
	}
	.affaires {
		list-style: none;
		margin: 0;
		padding: 0 0.75rem 0.6rem;
		display: flex;
		flex-direction: column;
		gap: 0.3rem;
	}
	.affaire {
		display: flex;
		flex-wrap: wrap;
		gap: 0.5rem;
		font-size: var(--fs-md);
		border-top: 1px solid var(--color-border);
		padding-top: 0.3rem;
	}
	.affaire-titre {
		flex: 1 1 12rem;
		min-width: 0;
	}
	.affaire-date,
	.affaire-issue {
		color: var(--color-text-muted);
		font-size: var(--fs-sm);
	}
	.metriques-resume {
		margin: 0;
		font-size: var(--fs-md);
		color: var(--color-text-muted);
	}
</style>
