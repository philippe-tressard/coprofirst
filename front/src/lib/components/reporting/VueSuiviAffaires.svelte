<!--
  Reporting CS — **Suivi des affaires** (16/10/2026, maquette D2 choisie à l'écran).

  TOUTES les affaires ni résolues ni annulées — plus seulement celles suivies au
  kanban, comme le faisait l'ancien « Suivi des dossiers » qu'elle remplace —, la
  plus ancienne en tête : âge, date d'ouverture, titre et descriptif (dix lignes
  au plus), catégorie. Au-dessus, leur nombre, celles de plus de 90 jours et la
  répartition par catégorie ; puis, à la demande, la synthèse de l'assistant (✨).

  🔴 Le relevé est CALCULÉ au serveur (`GET /suivi-affaires`) : la règle d'entrée,
  l'ancienneté et ses seuils y vivent, et le PDF — rendu par le serveur, pas par
  l'impression du navigateur — lit le même. Cette vue ne fait que les montrer.

  Autonome comme la relance : elle charge ses données et rend compte à la barre
  d'outils du parent (`chargement`, `estVide`, `recharger`, `exporterPdf`).
-->
<script lang="ts">
	import { onMount } from 'svelte';
	import { messageErreur } from '$lib/erreurs';
	import {
		suiviAffaires as suiviApi,
		type AffaireOuverte,
		type SuiviAffaires,
		type SyntheseAffaires,
	} from '$lib/api';
	import { fmtDate } from '$lib/date';
	import { categorieTicketLabel, lienTicket } from '$lib/tickets';
	import { enregistrerFichier } from '$lib/fichiers';
	import { toast } from '$lib/components/Toast.svelte';
	import EtatListe from '$lib/components/EtatListe.svelte';
	import Badge from '$lib/components/Badge.svelte';
	import IconeAction from '$lib/components/IconeAction.svelte';

	/** La teinte de l'âge — la tranche vient du serveur, qui garde les seuils. */
	const TEINTE_AGE: Record<AffaireOuverte['anciennete'], string> = {
		ancienne: 'badge-red',
		moyenne: 'badge-orange',
		recente: 'badge-gray',
	};

	let suivi: SuiviAffaires | null = null;
	let enCours = false;
	let erreur = '';
	let synthese: SyntheseAffaires | null = null;
	let redaction = false;
	let exportEnCours = false;

	/** Lu par la barre d'outils du parent — ne pas écrire depuis l'extérieur. */
	export let chargement = false;
	/** Idem : « rien à exporter » se décide ici. */
	export let estVide = true;
	$: chargement = enCours || exportEnCours;
	$: estVide = !suivi || suivi.total === 0;

	$: plusGrand = Math.max(1, ...(suivi?.par_categorie ?? []).map((c) => c.nombre));

	async function charger() {
		enCours = true;
		erreur = '';
		try {
			suivi = await suiviApi.lire();
		} catch (e) {
			erreur = messageErreur(e, 'Chargement impossible');
		} finally {
			enCours = false;
		}
	}

	/** Rechargement demandé par la barre d'outils du parent. */
	export function recharger() {
		charger();
	}

	async function synthetiser() {
		redaction = true;
		try {
			synthese = await suiviApi.synthese();
		} catch (e) {
			toast('error', messageErreur(e, 'Synthèse impossible'));
		} finally {
			redaction = false;
		}
	}

	/** L'export, demandé par la barre d'outils : le PDF du serveur, synthèse comprise. */
	export async function exporterPdf() {
		exportEnCours = true;
		try {
			const pdf = await suiviApi.pdf(synthese);
			enregistrerFichier(pdf, `suivi-des-affaires-${suivi?.jour ?? ''}.pdf`);
		} catch (e) {
			toast('error', messageErreur(e, 'Export PDF impossible'));
		} finally {
			exportEnCours = false;
		}
	}

	onMount(charger);
</script>

{#if enCours || erreur || !suivi || suivi.total === 0}
	<EtatListe
		chargement={enCours}
		{erreur}
		vide={!suivi || suivi.total === 0}
		titreErreur="Impossible d’afficher le suivi des affaires"
		titreVide="Aucune affaire ouverte"
		messageVide="Toutes les affaires sont résolues ou annulées."
	/>
{:else}
	<div class="tete">
		<div class="chiffres">
			<div class="kpi-card">
				<div class="kpi-value">{suivi.total}</div>
				<div class="kpi-label">
					affaire{suivi.total > 1 ? 's' : ''} non fermée{suivi.total > 1 ? 's' : ''}
				</div>
			</div>
			<div class="kpi-card" class:kpi-alert={suivi.anciennes > 0}>
				<div class="kpi-value">{suivi.anciennes}</div>
				<div class="kpi-label">de plus de 90 jours</div>
			</div>
		</div>
		<section class="report-card" aria-labelledby="titre-repartition">
			<h3 id="titre-repartition" class="intitule">Par catégorie</h3>
			<ul class="barres">
				{#each suivi.par_categorie as c (c.categorie)}
					<li>
						<span>{categorieTicketLabel(c.categorie)}</span>
						<span class="piste" aria-hidden="true">
							<span class="barre" style="width:{(100 * c.nombre) / plusGrand}%"></span>
						</span>
						<span class="nombre">{c.nombre}</span>
					</li>
				{/each}
			</ul>
		</section>
	</div>

	{#if synthese || suivi.synthese_disponible}
		<section class="synthese" aria-labelledby="titre-synthese" aria-busy={redaction}>
			<div class="synthese-entete">
				<h3 id="titre-synthese" class="intitule">✨ Synthèse de l’assistant</h3>
				{#if suivi.synthese_disponible}
					<button
						type="button"
						class="btn btn-sm btn-outline"
						on:click={synthetiser}
						disabled={redaction}
					>
						<IconeAction icone="sparkles" />
						{redaction ? 'Rédaction…' : synthese ? 'Relancer' : 'Rédiger la synthèse'}
					</button>
				{/if}
			</div>
			{#if synthese}
				<p class="resume">{synthese.resume}</p>
				{#if synthese.points.length}
					<ul class="points">
						{#each synthese.points as p, i (i)}<li>{p}</li>{/each}
					</ul>
				{/if}
				<p class="a-relire">À relire : elle part dans le PDF exporté.</p>
			{:else}
				<p class="a-relire">
					L’assistant résume ce qui presse, ce qui attend une décision et ce qui traîne.
				</p>
			{/if}
		</section>
	{/if}

	<div class="report-card">
		<table class="report-table compact affaires">
			<thead>
				<tr><th>Âge</th><th>Ouverte le</th><th>Affaire</th><th>Catégorie</th></tr>
			</thead>
			<tbody>
				{#each suivi.affaires as a (a.id)}
					<tr>
						<td class="age">
							<Badge teinte={TEINTE_AGE[a.anciennete]} title="{a.age_jours} jours"
								>{a.age_jours} j</Badge
							>
						</td>
						<td class="date">{fmtDate(a.ouverte_le)}</td>
						<td class="affaire">
							<a href={lienTicket(a.id)} class="titre">{a.titre}</a>
							{#if a.descriptif}<p class="descriptif clamp-10">{a.descriptif}</p>{/if}
						</td>
						<td class="categorie">{categorieTicketLabel(a.categorie)}</td>
					</tr>
				{/each}
			</tbody>
		</table>
	</div>
{/if}

<style>
	/*  La tête de la maquette D2 : les deux chiffres à gauche, la répartition à
	    droite. Sous 768 px, ils s’empilent. */
	.tete {
		display: grid;
		grid-template-columns: minmax(9rem, auto) 1fr;
		gap: 0.75rem;
		margin-bottom: 0.75rem;
	}
	.chiffres {
		display: flex;
		flex-direction: column;
		gap: 0.75rem;
	}
	.chiffres .kpi-card {
		flex: none;
		padding: 0.6rem 1rem;
	}
	.intitule {
		font-size: var(--fs-xs);
		text-transform: uppercase;
		letter-spacing: 0.05em;
		color: var(--color-text-muted);
		margin: 0 0 0.5rem;
	}
	.barres {
		list-style: none;
		margin: 0;
		padding: 0;
		display: grid;
		grid-template-columns: max-content 1fr 2.5ch;
		gap: 0.4rem 0.6rem;
		align-items: center;
		font-size: var(--fs-sm);
	}
	.barres li {
		display: contents;
	}
	.piste {
		background: var(--color-neutre-fond);
		border-radius: var(--radius);
		height: 0.6rem;
		overflow: hidden;
	}
	.barre {
		display: block;
		height: 100%;
		background: var(--color-primary);
		border-radius: var(--radius);
	}
	.nombre {
		text-align: right;
		font-weight: 700;
	}
	.synthese {
		border: 1px solid var(--color-border);
		background: var(--color-violet-fond);
		border-radius: var(--radius);
		padding: 0.75rem 1rem;
		margin-bottom: 0.75rem;
	}
	.synthese-entete {
		display: flex;
		justify-content: space-between;
		align-items: center;
		gap: 0.5rem;
		flex-wrap: wrap;
	}
	.synthese-entete .intitule {
		color: var(--color-violet);
		margin: 0;
	}
	.resume {
		margin: 0.5rem 0 0.25rem;
	}
	.points {
		margin: 0.25rem 0 0;
		padding-left: 1.2rem;
	}
	.a-relire {
		margin: 0.4rem 0 0;
		font-size: var(--fs-xs);
		color: var(--color-text-muted);
	}
	.affaires .date,
	.affaires .categorie,
	.affaires .age {
		white-space: nowrap;
	}
	.affaires .date,
	.affaires .categorie {
		color: var(--color-text-muted);
	}
	.titre {
		font-weight: 700;
		color: var(--color-text);
	}
	.descriptif {
		margin: 0.2rem 0 0;
		white-space: pre-line;
	}

	/*  Au téléphone, chaque ligne devient une fiche : l'âge, la date et la
	    catégorie sur une ligne, puis le titre et le descriptif. */
	@media (max-width: 767px) {
		.tete {
			grid-template-columns: 1fr;
		}
		.chiffres {
			flex-direction: row;
		}
		.chiffres .kpi-card {
			flex: 1;
		}
		.affaires thead {
			display: none;
		}
		.affaires,
		.affaires tbody {
			display: block;
		}
		.affaires tr {
			display: flex;
			flex-wrap: wrap;
			gap: 0.25rem 0.6rem;
			align-items: center;
			padding: 0.6rem 0;
			border-bottom: 1px solid var(--color-border);
		}
		.affaires td {
			display: block;
			padding: 0;
			border: 0;
		}
		.affaires td.affaire {
			order: 4;
			flex-basis: 100%;
		}
	}
</style>
