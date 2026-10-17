<!--
  Reporting CS — **Suivi des affaires** (16/10/2026, maquette D2 choisie à l'écran).

  Les affaires que la relance du syndic retient — plus seulement celles suivies
  au kanban, comme le faisait l'ancien « Suivi des dossiers » qu'elle remplace —,
  la plus ancienne en tête : âge, date d'ouverture, titre, périmètre et aperçu
  (cinq lignes au plus : le résumé de l'assistant, sinon le descriptif),
  catégorie. Au-dessus, leur nombre, celles de plus de 90 jours et les deux
  répartitions croisées, par catégorie et par bâtiment (#2043).

  ## Trois modes (#2035, #2043)

  - **Suivi affaires** — la maquette D2.
  - **Suivi entretiens périodiques** — les affaires d'entretien périodique non
    closes, sous le bilan des visites de l'année (`BilanVisites`) ; l'état de
    chaque visite à la place de la catégorie, et pas de résumé de l'assistant.
    Les visites déjà réalisées se listent avant le point (`VisitesRealisees`) :
    le tableau, qui ne garde que les non closes, ne les montre plus.
    Il remplace la vue « Entretien périodique » du reporting (`?vue=periodique`
    y mène).
  - **Relancer le syndic** — la liste du Suivi affaires, avec de quoi composer
    la relance (`RelanceSyndic`).

  Le sélecteur reste visible quand un mode est vide : sinon on ne pourrait plus
  en changer.

  ## Le résumé de chaque affaire, pas une synthèse d'ensemble

  « ✨ Résumer les affaires » fait rédiger, pour chacune, une ou deux phrases
  tirées de toute sa matière (fil compris), gardées au serveur et montrées sous
  son titre. La synthèse d'ENSEMBLE de #2034 a été retirée le jour même : ce
  qui sert, au conseil comme au syndic, est l'état de chaque affaire.

  🔴 Le relevé est CALCULÉ au serveur (`GET /suivi-affaires?mode=`) : la règle
  d'entrée, l'ancienneté et ses seuils, les répartitions y vivent, et le PDF —
  rendu par le serveur — lit le même. Cette vue ne fait que les montrer.

  ## Le point CS / Syndic (#2041, #2042)

  Dans les deux modes de suivi, un point s'ouvre au-dessus du tableau
  (`PointConseil`, un par mode) ; chaque affaire offre la saisie de son compte
  rendu (`SaisieCrAffaire`, dans le tableau), et le CR global se lit dessous
  (`CrGlobal`).

  Autonome : elle charge ses données et rend compte à la barre d'outils du parent
  (`chargement`, `estVide`, `recharger`, `exporterPdf`).
-->
<script lang="ts">
	import { messageErreur } from '$lib/erreurs';
	import {
		suiviAffaires as suiviApi,
		type CompteRenduPoint,
		type CrAffaire,
		type ModeReleve,
		type SuiviAffaires,
		type VisitePeriodique,
	} from '$lib/api';
	import { enregistrerFichier } from '$lib/fichiers';
	import { teinteBatiment, teinteCategorie } from '$lib/repartition';
	import { toast } from '$lib/components/Toast.svelte';
	import EtatListe from '$lib/components/EtatListe.svelte';
	import IconeIA from '$lib/components/IconeIA.svelte';
	import SelecteurMode from '$lib/components/SelecteurMode.svelte';
	import TableauAffaires from './TableauAffaires.svelte';
	import RelanceSyndic from './RelanceSyndic.svelte';
	import PointConseil from './PointConseil.svelte';
	import SaisieCrAffaire from './SaisieCrAffaire.svelte';
	import CrGlobal from './CrGlobal.svelte';
	import BarresCroisees from './BarresCroisees.svelte';
	import BilanVisites from './BilanVisites.svelte';
	import VisitesRealisees from './VisitesRealisees.svelte';

	const MODES = [
		{ valeur: 'suivi', libelle: 'Suivi affaires' },
		{ valeur: 'entretien', libelle: 'Suivi entretiens périodiques' },
		{ valeur: 'relance', libelle: 'Relancer le syndic' },
	];
	/**  `suivi`, `entretien` ou `relance` — `?vue=relance` (l'alerte du tableau de
	 *   bord) ouvre le troisième, `?vue=periodique` le deuxième. */
	export let mode = 'suivi';

	/** Le relevé que le mode lit : la relance lit celui du Suivi affaires. */
	$: releve = (mode === 'entretien' ? 'entretien' : 'affaires') as ModeReleve;
	$: entretien = releve === 'entretien';

	let suivi: SuiviAffaires | null = null;
	/** Les visites de l'année, lues par le bilan — le mode entretien les liste. */
	let visites: VisitePeriodique[] = [];
	let enCours = false;
	let erreur = '';
	let redaction = false;
	let exportEnCours = false;
	/** Le point CS / Syndic du mode, et l'affaire dont le CR est en saisie. */
	let compteRendu: CompteRenduPoint | null = null;
	let crOuvert: number | null = null;
	//  Les CR du point, quel que soit son état : terminé, un CR saisi se corrige
	//  encore (#2042) ; seul un point en cours en accepte un nouveau (`ajout`).
	$: crs = compteRendu
		? new Map<number, CrAffaire>(compteRendu.abordees.map((a) => [a.affaire.id, a.cr]))
		: null;

	/** Lu par la barre d'outils du parent — ne pas écrire depuis l'extérieur. */
	export let chargement = false;
	/** Idem : « rien à exporter » se décide ici. */
	export let estVide = true;
	$: chargement = enCours || exportEnCours;
	$: estVide = !suivi || suivi.total === 0;

	$: ordreBatiments = (suivi?.par_batiment ?? []).map((b) => b.cle);
	/** Les affaires nouvelles ou qui ont évolué depuis leur résumé — le serveur le dit (#2044). */
	$: aResumer = (suivi?.affaires ?? []).filter((a) => a.a_evolue).length;

	async function charger(m: ModeReleve) {
		enCours = true;
		erreur = '';
		compteRendu = null;
		crOuvert = null;
		try {
			suivi = await suiviApi.lire(m);
		} catch (e) {
			erreur = messageErreur(e, 'Chargement impossible');
		} finally {
			enCours = false;
		}
	}
	//  Un relevé par mode : passer du Suivi affaires aux entretiens le recharge,
	//  passer à la relance non (elle lit le même).
	$: charger(releve);

	/** Rechargement demandé par la barre d'outils du parent. */
	export function recharger() {
		charger(releve);
	}

	/**  Relire le relevé SANS repasser par l'état « chargement » : après un envoi
	 *   de relance, ou pour montrer les résumés que l'assistant vient d'écrire. */
	async function relire() {
		try {
			suivi = await suiviApi.lire(releve);
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
			const pdf = await suiviApi.pdf(releve);
			const nom = entretien ? 'suivi-des-entretiens-periodiques' : 'suivi-des-affaires';
			enregistrerFichier(pdf, `${nom}-${suivi?.jour ?? ''}.pdf`);
		} catch (e) {
			toast('error', messageErreur(e, 'Export PDF impossible'));
		} finally {
			exportEnCours = false;
		}
	}
</script>

<div class="mode">
	<!--  « Résumer » ne paraît que s'il y a du nouveau, et ne résume que lui (#2044). -->
	{#if suivi?.resumes_disponibles && !entretien && aResumer > 0}
		<button
			type="button"
			class="btn btn-sm btn-outline"
			on:click={resumer}
			disabled={redaction}
			aria-busy={redaction}
			title="L’assistant résume en une ou deux phrases chaque affaire nouvelle ou qui a évolué depuis son dernier résumé"
		>
			<IconeIA enCours={redaction} />
			{redaction ? 'Rédaction…' : `Résumer ${aResumer} affaire${aResumer > 1 ? 's' : ''}`}
		</button>
	{/if}
	<SelecteurMode libelle="Mode du suivi des affaires" options={MODES} bind:valeur={mode} />
</div>

{#if entretien}
	<BilanVisites bind:visites />
{/if}

{#if enCours || erreur || !suivi || suivi.total === 0}
	<EtatListe
		chargement={enCours}
		{erreur}
		vide={!suivi || suivi.total === 0}
		titreErreur="Impossible d’afficher le suivi"
		titreVide={entretien ? 'Aucun entretien périodique en cours' : 'Aucune affaire ouverte'}
		messageVide={entretien
			? 'Toutes les visites d’entretien sont faites ou annulées.'
			: 'Toutes les affaires sont résolues ou annulées.'}
	/>
	{#if entretien && !enCours}
		<VisitesRealisees {visites} />
	{/if}
{:else}
	<div class="tete">
		<div class="chiffres">
			<div class="kpi-card">
				<div class="kpi-value">{suivi.total}</div>
				<div class="kpi-label">
					{entretien ? 'entretien' : 'affaire'}{suivi.total > 1 ? 's' : ''} non
					{entretien ? 'clos' : 'fermée'}{suivi.total > 1 ? 's' : ''}
				</div>
			</div>
			<div class="kpi-card" class:kpi-alert={suivi.anciennes > 0}>
				<div class="kpi-value">{suivi.anciennes}</div>
				<div class="kpi-label">de plus de 90 jours</div>
			</div>
		</div>
		<BarresCroisees
			titre="Par catégorie"
			barres={suivi.par_categorie}
			teinte={(cle) => teinteBatiment(cle, ordreBatiments)}
		/>
		<BarresCroisees titre="Par bâtiment" barres={suivi.par_batiment} teinte={teinteCategorie} />
	</div>

	{#if mode === 'relance'}
		<RelanceSyndic {suivi} onEnvoyee={relire} />
	{:else}
		{#if entretien}
			<VisitesRealisees {visites} />
		{/if}
		{#key releve}
			<PointConseil mode={releve} bind:compteRendu />
		{/key}
		<div class="report-card">
			<TableauAffaires
				affaires={suivi.affaires}
				visites={entretien}
				{crs}
				ajout={compteRendu?.point.etat === 'en_cours'}
				bind:ouverte={crOuvert}
			>
				<svelte:fragment slot="saisie" let:affaire let:cr>
					{#if compteRendu}
						<SaisieCrAffaire
							pointId={compteRendu.point.id}
							{affaire}
							{cr}
							brouillonAuto={compteRendu.point.etat === 'en_cours'}
							onCompteRendu={(nouveau) => (compteRendu = nouveau)}
							onFerme={() => (crOuvert = null)}
						/>
					{/if}
				</svelte:fragment>
			</TableauAffaires>
		</div>
		{#if compteRendu}
			<CrGlobal {compteRendu} />
		{/if}
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
	/*  La tête : les deux chiffres à gauche, puis les deux répartitions côte à
	    côte, chacune la moitié de la place restante, à la même hauteur (#2043).
	    Sous 768 px, elles s'empilent. */
	.tete {
		display: grid;
		grid-template-columns: minmax(9rem, auto) minmax(0, 1fr) minmax(0, 1fr);
		align-items: stretch;
		gap: 0.75rem;
		margin-bottom: 0.75rem;
	}
	.chiffres {
		display: flex;
		flex-direction: column;
		gap: 0.75rem;
	}
	.chiffres .kpi-card {
		flex: 1;
		padding: 0.6rem 1rem;
	}
	/*  Au téléphone, les deux chiffres passent côte à côte au-dessus des
	    répartitions ; le tableau devient une suite de fiches (`TableauAffaires`). */
	@media (max-width: 767px) {
		.tete {
			grid-template-columns: minmax(0, 1fr);
		}
		.chiffres {
			flex-direction: row;
		}
	}
</style>
