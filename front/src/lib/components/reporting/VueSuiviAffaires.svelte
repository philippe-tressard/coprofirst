<!--
  Reporting CS — **Suivi des affaires** (16/10/2026, maquette D2 choisie à l'écran).

  Les affaires que la relance du syndic retient — plus seulement celles suivies
  au kanban, comme le faisait l'ancien « Suivi des dossiers » qu'elle remplace —,
  la plus ancienne en tête : âge, date d'ouverture, titre, périmètre et aperçu
  (cinq lignes au plus : le résumé de l'assistant, sinon le descriptif),
  catégorie. Au-dessus, leur nombre, celles de plus de 90 jours et la
  répartition par catégorie.

  ## Deux modes, une liste (#2035)

  « Suivre » est la maquette D2. « Relancer le syndic » remplace
  l'ancienne vue « Relance syndic » du reporting : la même liste, avec de quoi
  composer la relance (`RelanceSyndic`). L'ancienne vue en comptait cinq de
  moins, sous une autre règle — sur le même sujet, dans le même onglet.

  ## Le résumé de chaque affaire, pas une synthèse d'ensemble

  « ✨ Résumer les affaires » fait rédiger, pour chacune, une ou deux phrases
  tirées de toute sa matière (fil compris), gardées au serveur et montrées sous
  son titre. La synthèse d'ENSEMBLE de #2034 a été retirée le jour même : ce
  qui sert, au conseil comme au syndic, est l'état de chaque affaire.

  🔴 Le relevé est CALCULÉ au serveur (`GET /suivi-affaires`) : la règle d'entrée,
  l'ancienneté et ses seuils y vivent, et le PDF — rendu par le serveur, pas par
  l'impression du navigateur — lit le même. Cette vue ne fait que les montrer.

  Autonome : elle charge ses données et rend compte à la barre d'outils du parent
  (`chargement`, `estVide`, `recharger`, `exporterPdf`).
-->
<script lang="ts">
	import { onMount } from 'svelte';
	import { messageErreur } from '$lib/erreurs';
	import { suiviAffaires as suiviApi, type SuiviAffaires } from '$lib/api';
	import { categorieTicketLabel } from '$lib/tickets';
	import { enregistrerFichier } from '$lib/fichiers';
	import { toast } from '$lib/components/Toast.svelte';
	import EtatListe from '$lib/components/EtatListe.svelte';
	import IconeAction from '$lib/components/IconeAction.svelte';
	import SelecteurMode from '$lib/components/SelecteurMode.svelte';
	import TableauAffaires from './TableauAffaires.svelte';
	import RelanceSyndic from './RelanceSyndic.svelte';

	const MODES = [
		{ valeur: 'suivi', libelle: 'Suivre' },
		{ valeur: 'relance', libelle: 'Relancer le syndic' },
	];
	/** `suivi` ou `relance` — `?vue=relance` (l'alerte du tableau de bord) ouvre le second. */
	export let mode = 'suivi';

	let suivi: SuiviAffaires | null = null;
	let enCours = false;
	let erreur = '';
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

	/**  Relire le relevé SANS repasser par l'état « chargement » : après un envoi
	 *   de relance, ou pour montrer les résumés que l'assistant vient d'écrire. */
	async function relire() {
		try {
			suivi = await suiviApi.lire();
		} catch (e) {
			toast('error', messageErreur(e, 'Rechargement impossible'));
		}
	}

	async function resumer() {
		redaction = true;
		try {
			const { rediges } = await suiviApi.resumer();
			await relire();
			toast(
				'success',
				`✨ ${rediges} affaire${rediges > 1 ? 's' : ''} résumée${rediges > 1 ? 's' : ''}`,
			);
		} catch (e) {
			toast('error', messageErreur(e, 'Résumé impossible'));
		} finally {
			redaction = false;
		}
	}

	/** L'export, demandé par la barre d'outils : le PDF du serveur. */
	export async function exporterPdf() {
		exportEnCours = true;
		try {
			const pdf = await suiviApi.pdf();
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
	<div class="mode">
		{#if suivi.resumes_disponibles}
			<button
				type="button"
				class="btn btn-sm btn-outline"
				on:click={resumer}
				disabled={redaction}
				aria-busy={redaction}
				title="L’assistant résume chaque affaire en une ou deux phrases, à partir de toute sa matière"
			>
				<IconeAction icone="sparkles" />
				{redaction ? 'Rédaction…' : 'Résumer les affaires'}
			</button>
		{/if}
		<SelecteurMode libelle="Mode du suivi des affaires" options={MODES} bind:valeur={mode} />
	</div>

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

	{#if mode === 'relance'}
		<RelanceSyndic {suivi} onEnvoyee={relire} />
	{:else}
		<div class="report-card">
			<TableauAffaires affaires={suivi.affaires} />
		</div>
	{/if}
{/if}

<style>
	.mode {
		display: flex;
		justify-content: flex-end;
		align-items: center;
		flex-wrap: wrap;
		gap: 0.5rem 0.75rem;
		margin-bottom: 0.75rem;
	}
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
	/*  Au téléphone, les deux chiffres passent côte à côte au-dessus de la
	    répartition ; le tableau devient une suite de fiches (`TableauAffaires`). */
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
	}
</style>
