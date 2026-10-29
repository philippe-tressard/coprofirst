<!--
  Reporting CS — la FRISE des échéances de contrats de l'année.

  Extrait de `VueRenouvellements.svelte` le 27/08/2026 (#453) : ce fichier portait
  456 lignes et DEUX sections indépendantes — la frise des contrats et les
  diagnostics réglementaires — qui ne partageaient que la carte qui les entoure.
  Une fois reformaté, il en faisait 700, largement au-dessus du seuil de
  modularité (rang 1).

  ⚠️ Les règles `.frise-*` ne servent qu'ici et voyagent avec ce balisage,
  variantes d'impression comprises. C'est la panne des pastilles nues (v2.67.11)
  qu'on évite, et que `npm run lint:classes-nues` refuse depuis.
-->
<script lang="ts">
	//  ⚠️ Cet écran affichait la valeur BRUTE — `chauffage_collectif` — parce que
	//  la table des libellés vivait dans `prestataires/+page.svelte` et qu'il n'y
	//  avait pas accès. Une table qui vit dans UN écran, les autres s'en passent.
	import { equipLabel } from '#lib/prestataires.ts';
	import { relire } from '#lib/utils.ts';
	import { fmtDate } from '#lib/date.ts';
	import NoteEtoiles from '#lib/components/NoteEtoiles.svelte';
	import {
		MOIS_LABELS,
		PREAVIS_MOIS,
		anneeCourante,
		contratsAvecEcheance,
		type ReportContrat,
		type ReportPrestataire,
	} from '#lib/reporting.ts';

	export let reportContrats: ReportContrat[] = [];
	export let reportPrestataires: ReportPrestataire[] = [];
	/** Note moyenne et nombre d'avis par prestataire, calculés une fois en amont. */
	export let reportNoteMoyParPrest: Map<number, { moy: number; nb: number }> = new Map();

	//  🔴 Relue à chaque rafraîchissement des DONNÉES — c'est `anneeDeReference`
	//  qui porte le pourquoi. Cette ligne était `anneeCourante()` seule : un `$:`
	//  sans variable réactive citée ne se réexécute jamais, et le commentaire
	//  d'alors décrivait un remède qui n'avait pas lieu (#549, 29/08/2026).
	$: ANNEE_COURANTE = relire(reportContrats, anneeCourante);

	//  La dérivation vit dans `#lib/reporting.ts` : le parent en a besoin pour ses
	//  compteurs, ce composant pour sa frise. La recopier serait la duplication
	//  que ce découpage existe pour retirer.
	$: contratsAvecFin = contratsAvecEcheance(
		reportContrats,
		reportPrestataires,
		reportNoteMoyParPrest,
	);

	$: contratsAnneeCourante = contratsAvecFin.filter((c) => {
		if (!c.dateFin) return false;
		// Inclure si la fin OU le préavis tombe dans l'année courante
		if (c.dateFin.getFullYear() === ANNEE_COURANTE) return true;
		if (c.datePreavis && c.datePreavis.getFullYear() === ANNEE_COURANTE) return true;
		return false;
	});

	$: contratsFuturs = contratsAvecFin.filter(
		(c) => c.dateFin && c.urgence === 'futur' && !contratsAnneeCourante.includes(c),
	);
	$: contratsInconnus = contratsAvecFin.filter((c) => c.urgence === 'inconnu');
</script>

<!-- Section 1 : Frise contrats -->
<section class="report-card carte-espacee">
	<h3>📋 Contrats prestataires — échéances {ANNEE_COURANTE}</h3>
	<p class="report-intro">
		Contrats dont la fin ou le préavis tombe en {ANNEE_COURANTE}. La zone hachurée indique la
		période de préavis ({PREAVIS_MOIS} mois).
	</p>

	{#if contratsAnneeCourante.length === 0}
		<div class="empty-state"><h3>Aucune échéance de contrat en {ANNEE_COURANTE}</h3></div>
	{:else}
		<div class="frise-container">
			<div class="frise-months">
				{#each MOIS_LABELS as m (m)}<div class="frise-month-label">{m}</div>{/each}
			</div>
			{#each contratsAnneeCourante.filter((x): x is typeof x & { dateFin: Date } => !!x.dateFin) as c (c.id)}
				{@const finDansAnnee = c.dateFin.getFullYear() === ANNEE_COURANTE}
				{@const moisFin = finDansAnnee ? c.dateFin.getMonth() : 11.9}
				{@const moisPreavis =
					c.datePreavis && c.datePreavis.getFullYear() < ANNEE_COURANTE
						? 0
						: (c.datePreavis?.getMonth() ?? 0)}
				{@const barStart = Math.max(0, moisPreavis)}
				{@const barEnd = moisFin}
				{@const preavisWidth = ((barEnd - barStart) / 12) * 100}
				{@const finPos = finDansAnnee ? ((moisFin + 0.5) / 12) * 100 : 99}
				{@const friseStyle = c.reconduit ? 'reconduit' : c.urgence}
				<!--  🔴 Les `class:` ci-dessous remplacent `frise-urgence-{friseStyle}`
					      et `frise-marker-{friseStyle}` (#810). Devant une classe
					      interpolée, Svelte cesse de déclarer les sélecteurs inutilisés
					      pour TOUT le fichier — celui-ci porte deux cents lignes de style
					      de frise, et l'aveuglement y masquait dix sélecteurs.

					      ⚠️ Les cinq valeurs sont celles d'`urgence`, plus `reconduit`.
					      Une sixième ajoutée en amont ne recevrait pas son style ici — et
					      c'est justement ce que `svelte-check` dira désormais, en
					      signalant le sélecteur devenu orphelin. Avant, il se taisait. -->
				<div class="frise-row-v2">
					<div class="frise-row-header">
						<div class="frise-row-title">
							<strong>{c.libelle}</strong>
							<span class="text-muted-sm">{c.prestataireNom}</span>
							<span class="text-muted-sm">· {equipLabel(c.type_equipement)}</span>
							{#if c.numero_contrat}<span class="text-muted-sm">· N° {c.numero_contrat}</span>{/if}
							<NoteEtoiles note={c.noteMoy} nbAvis={c.nbNotations} />
						</div>
						<div class="frise-row-badges">
							{#if c.urgence === 'preavis'}<span class="badge badge-orange">Préavis en cours</span>
							{:else}<span class="badge badge-blue">Actif</span>
							{/if}
							{#if c.reconduit}<span class="badge badge-purple">♻ Reconduit</span>{/if}
							<span class="frise-row-dates">
								{fmtDate(c.date_debut)} → {fmtDate(c.dateFin.toISOString())}
								{#if c.datePreavis}· préavis dès {fmtDate(c.datePreavis.toISOString())}{/if}
							</span>
						</div>
					</div>
					<div class="frise-bar-track">
						{#if preavisWidth > 0}
							<div
								class="frise-preavis-zone"
								class:frise-urgence-preavis={friseStyle === 'preavis'}
								class:frise-urgence-inconnu={friseStyle === 'inconnu'}
								class:frise-urgence-annee={friseStyle === 'annee'}
								class:frise-urgence-futur={friseStyle === 'futur'}
								class:frise-urgence-reconduit={friseStyle === 'reconduit'}
								style="left:{(barStart / 12) * 100}%;width:{preavisWidth}%"
							></div>
						{/if}
						{#if finDansAnnee}
							<div
								class="frise-marker"
								class:frise-marker-preavis={friseStyle === 'preavis'}
								class:frise-marker-inconnu={friseStyle === 'inconnu'}
								class:frise-marker-annee={friseStyle === 'annee'}
								class:frise-marker-futur={friseStyle === 'futur'}
								class:frise-marker-reconduit={friseStyle === 'reconduit'}
								style="left:{finPos}%"
								title="Fin : {fmtDate(c.dateFin.toISOString())}"
							>
								<span class="frise-marker-label"
									>{c.dateFin.getDate()}/{c.dateFin.getMonth() + 1}</span
								>
							</div>
						{:else}
							<div
								class="frise-marker marqueur-fin"
								class:frise-marker-preavis={friseStyle === 'preavis'}
								class:frise-marker-inconnu={friseStyle === 'inconnu'}
								class:frise-marker-annee={friseStyle === 'annee'}
								class:frise-marker-futur={friseStyle === 'futur'}
								class:frise-marker-reconduit={friseStyle === 'reconduit'}
								title="Fin : {fmtDate(c.dateFin.toISOString())} ({c.dateFin.getFullYear()})"
							>
								<span class="frise-marker-label">→ {c.dateFin.getFullYear()}</span>
							</div>
						{/if}
					</div>
				</div>
			{/each}
			<div class="frise-legend">
				<span><span class="frise-legend-dot point-preavis"></span> Préavis en cours</span>
				<span><span class="frise-legend-dot point-annee"></span> Expire cette année</span>
				<span><span class="frise-legend-dot point-reconduit"></span> Reconduit tacitement</span>
				<span class="frise-legend-hatch">▧ Zone de préavis</span>
				<span class="legende-fin">→ Fin en {ANNEE_COURANTE + 1}</span>
			</div>
		</div>
	{/if}

	<!-- Contrats futurs (hors exercice courant) -->
	{#if contratsFuturs.length > 0}
		<div class="bloc-suivant">
			<h4 class="titre-bloc">
				📅 Échéances futures ({contratsFuturs.length})
			</h4>
			<div class="frise-compact-list">
				{#each contratsFuturs as c (c.id)}
					<div class="frise-compact-item">
						<div class="frise-compact-info">
							<strong>{c.libelle}</strong>
							<span class="text-muted-sm">{c.prestataireNom} · {equipLabel(c.type_equipement)}</span
							>
						</div>
						<div class="frise-compact-meta">
							<NoteEtoiles note={c.noteMoy} />
							<span>Fin : {c.dateFin ? fmtDate(c.dateFin.toISOString()) : 'N/A'}</span>
							<span>Préavis : {c.datePreavis ? fmtDate(c.datePreavis.toISOString()) : 'N/A'}</span>
							{#if c.reconduit}<span class="badge badge-purple">♻ Reconduit</span>{/if}
						</div>
					</div>
				{/each}
			</div>
		</div>
	{/if}

	<!-- Contrats sans dates -->
	{#if contratsInconnus.length > 0}
		<div class="bloc-suivant">
			<h4 class="titre-bloc">
				⚠️ Dates manquantes ({contratsInconnus.length})
			</h4>
			<div class="frise-compact-list">
				{#each contratsInconnus as c (c.id)}
					<div class="frise-compact-item">
						<div class="frise-compact-info">
							<strong>{c.libelle}</strong>
							<span class="text-muted-sm"
								>{c.prestataireNom} · {equipLabel(c.type_equipement)}{#if c.numero_contrat}
									· N° {c.numero_contrat}{/if}</span
							>
						</div>
						<div class="frise-compact-meta">
							<NoteEtoiles note={c.noteMoy} />
							<span>Début : {c.date_debut ? fmtDate(c.date_debut) : 'N/A'}</span>
							<span class="badge badge-gray">Durée non renseignée</span>
						</div>
					</div>
				{/each}
			</div>
		</div>
	{/if}
</section>

<style>
	/* ── Renouvellements : frise contrats ─────────────────────────── */
	.frise-container {
		margin-top: 0.5rem;
	}
	.frise-months {
		display: grid;
		grid-template-columns: repeat(12, 1fr);
		font-size: var(--fs-2xs);
		color: var(--color-text-muted);
		text-transform: uppercase;
		letter-spacing: 0.03em;
		margin-bottom: 0.35rem;
		text-align: center;
		border-bottom: 1px solid var(--color-border);
		padding-bottom: 0.3rem;
	}
	.frise-row-v2 {
		padding: 0.5rem 0 1.2rem;
		border-bottom: 1px solid color-mix(in srgb, var(--color-border) 50%, transparent);
	}
	.frise-row-header {
		display: flex;
		justify-content: space-between;
		align-items: baseline;
		flex-wrap: wrap;
		gap: 0.15rem 0.8rem;
		margin-bottom: 0.3rem;
	}
	.frise-row-title {
		display: flex;
		align-items: baseline;
		gap: 0.4rem;
		font-size: var(--fs-md);
		min-width: 0;
		flex-wrap: wrap;
	}
	.frise-row-badges {
		display: flex;
		align-items: center;
		gap: 0.4rem;
		flex-wrap: wrap;
	}
	.frise-row-dates {
		font-size: var(--fs-2xs);
		color: var(--color-text-muted);
		white-space: nowrap;
	}
	.frise-bar-track {
		position: relative;
		height: 28px;
		background: repeating-linear-gradient(
			90deg,
			transparent,
			transparent calc(100% / 12 - 1px),
			var(--color-border) calc(100% / 12 - 1px),
			var(--color-border) calc(100% / 12)
		);
		border-radius: 4px;
	}

	/* Compact list for future/unknown contracts */
	.frise-compact-list {
		display: flex;
		flex-direction: column;
		gap: 0.4rem;
	}
	.frise-compact-item {
		display: flex;
		justify-content: space-between;
		align-items: center;
		gap: 0.5rem;
		padding: 0.4rem 0.6rem;
		border-radius: 6px;
		font-size: var(--fs-md);
		background: color-mix(in srgb, var(--color-surface) 90%, var(--color-border));
		flex-wrap: wrap;
	}
	.frise-compact-info {
		display: flex;
		align-items: baseline;
		gap: 0.4rem;
		min-width: 0;
		flex-wrap: wrap;
	}
	.frise-compact-meta {
		display: flex;
		align-items: center;
		gap: 0.6rem;
		font-size: var(--fs-xs);
		color: var(--color-text-muted);
		flex-wrap: wrap;
	}

	.frise-preavis-zone {
		position: absolute;
		top: 2px;
		bottom: 2px;
		border-radius: 3px;
		opacity: 0.35;
		background: repeating-linear-gradient(
			-45deg,
			transparent,
			transparent 4px,
			currentColor 4px,
			currentColor 6px
		);
	}
	.frise-preavis-zone.frise-urgence-preavis {
		color: var(--color-danger);
	}
	.frise-preavis-zone.frise-urgence-annee {
		color: var(--color-warning-texte);
	}
	.frise-preavis-zone.frise-urgence-futur {
		color: var(--color-info);
	}
	.frise-preavis-zone.frise-urgence-reconduit {
		color: var(--color-violet);
	}
	/*  🔴 `inconnu` — une date de fin qu'on n'a pas. Elle N'AVAIT AUCUN STYLE, et
	    personne ne le voyait : l'ancienne écriture `frise-urgence-{friseStyle}`
	    produisait la classe sans que rien ne vérifie qu'elle existe. La frise
	    s'affichait donc en `currentColor` hérité, c'est-à-dire au hasard.

	    Trouvé en convertissant l'interpolation en `class:` (#810) : le typage a
	    d'abord refusé `expire`, qui n'est PAS une valeur d'`urgence` — cinq
	    sélecteurs étaient écrits pour une valeur qui n'existe pas — puis
	    `lint:classes-nues` a réclamé `inconnu`, qui existe et n'avait rien.

	    Gris : on ne sait pas, et l'écran doit le dire sans alarmer. */
	.frise-preavis-zone.frise-urgence-inconnu {
		color: var(--color-text-muted);
	}

	.frise-marker {
		position: absolute;
		top: 0;
		bottom: 0;
		width: 3px;
		transform: translateX(-50%);
		border-radius: 2px;
	}
	.frise-marker-preavis {
		background: var(--color-danger);
	}
	.frise-marker-annee {
		background: var(--color-warning);
	}
	.frise-marker-futur {
		background: var(--color-info);
	}
	.frise-marker-reconduit {
		background: var(--color-violet);
	}
	/*  Même raison que `frise-urgence-inconnu` ci-dessus. */
	.frise-marker-inconnu {
		background: var(--color-text-muted);
	}

	.frise-marker-label {
		position: absolute;
		bottom: -16px;
		left: 50%;
		transform: translateX(-50%);
		font-size: var(--fs-2xs);
		color: var(--color-text-muted);
		white-space: nowrap;
	}
	.frise-legend {
		display: flex;
		gap: 1.2rem;
		font-size: var(--fs-sm);
		color: var(--color-text-muted);
		margin-top: 1.2rem;
		flex-wrap: wrap;
	}
	.frise-legend span {
		display: flex;
		align-items: center;
		gap: 0.35rem;
	}
	.frise-legend-dot {
		display: inline-block;
		width: 10px;
		height: 10px;
		border-radius: 2px;
	}
	.frise-legend-hatch {
		font-style: italic;
	}

	@media (max-width: 767px) {
		.frise-row-header {
			flex-direction: column;
		}
		.frise-bar-track {
			min-height: 24px;
		}
		.frise-months {
			font-size: 0.6rem;
		}
		.frise-compact-item {
			flex-direction: column;
			align-items: flex-start;
		}
	}

	@media print {
		.frise-container {
			break-inside: auto;
		}
		.frise-row-v2 {
			break-inside: avoid;
		}
		/*  ⚠️ Pas de règle `.report-table` ici : cette section n'en contient AUCUN,
		    elle rend une frise. Les deux lignes reprises du fichier d'origine y
		    étaient inertes, et `svelte-check` l'a dit dès la séparation — un
		    sélecteur orphelin que le fichier unique masquait. */
	}
	.carte-espacee {
		margin-bottom: 1.5rem;
	}
	.marqueur-fin {
		left: 98%;
		opacity: 0.7;
	}
	.point-preavis {
		background: var(--color-danger);
	}
	.point-annee {
		background: var(--color-warning);
	}
	.point-reconduit {
		background: var(--color-violet);
	}
	.legende-fin {
		font-size: var(--fs-xs);
		color: var(--color-text-muted);
	}
	.bloc-suivant {
		margin-top: 1.2rem;
	}
	.titre-bloc {
		font-size: var(--fs-base);
		font-weight: 600;
		margin: 0 0 0.5rem;
		color: var(--color-text-muted);
	}
</style>
