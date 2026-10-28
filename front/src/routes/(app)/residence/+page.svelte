<script lang="ts">
	import { tenter, messageErreur } from '#lib/erreurs.ts';
	import AideSource from '#lib/components/AideSource.svelte';
	import BadgePerimetre from '#lib/components/BadgePerimetre.svelte';
	import BanniereResidence from '#lib/components/BanniereResidence.svelte';
	import SectionDiagnostics from '#lib/components/SectionDiagnostics.svelte';
	import EntetePage from '#lib/components/EntetePage.svelte';
	import FormulaireCreation from '#lib/components/FormulaireCreation.svelte';
	import PiedFormulaire from '#lib/components/PiedFormulaire.svelte';
	import ChampsIdentiteCopropriete, {
		chargeIdentite,
		identiteDepuis,
	} from '#lib/components/ChampsIdentiteCopropriete.svelte';
	import { tick } from 'svelte';
	import { browser } from '$app/env';
	import { marquerDonneesAffichees } from '#lib/telemetry.ts';
	import { afterNavigate } from '$app/navigation';
	import { isAdmin, isCS, isLocataire, isProprioOuCS, quandAuthResolue } from '#lib/stores/auth.ts';
	import {
		copropriete as coproprieteApi,
		documents as documentsApi,
		diagnostics as diagnosticsApi,
		reglement as reglementApi,
		type Batiment,
		type Copropriete,
		type DiagnosticType,
		type Document,
	} from '#lib/api/index.ts';
	import { toast } from '#lib/components/Toast.svelte';
	import { cibleDuHash, revelerCible } from '#lib/deepLink.ts';
	import {
		getPageConfig,
		configStore,
		siteNomStore,
		defautsDePage,
		nomResidenceEnregistre,
	} from '#lib/stores/pageConfig.ts';
	import BarreOnglets from '#lib/components/BarreOnglets.svelte';
	import SectionRegles, {
		lireRegles,
		type LectureRegles,
	} from '#lib/components/SectionRegles.svelte';
	//  ⏱ Le Carnet et son bilan attendent le passage sur leur onglet (#1844).
	import FicheResidence from '#lib/components/FicheResidence.svelte';
	import RubriqueDocuments from '#lib/components/RubriqueDocuments.svelte';
	import ChargementPartiel from '#lib/components/ChargementPartiel.svelte';
	import { essayer, messagePartiel } from '#lib/chargement.ts';
	import EtatListe from '#lib/components/EtatListe.svelte';
	import IconeAction from '#lib/components/IconeAction.svelte';
	import ChargementDiffere from '#lib/components/ChargementDiffere.svelte';

	/**  L'onglet vient du CHEMIN, résolu par `+page.ts` — jamais d'un `let`
	 *   qu'on affecte : une page qui écrit son propre onglet ne peut plus être
	 *   atteinte par son adresse (`ux-patterns` §4). */
	export let data: { onglet: string };
	$: onglet = data.onglet;

	$: _pc = getPageConfig($configStore, 'residence', defautsDePage('residence'));
	$: _siteNom = $siteNomStore;

	// ── State ──────────────────────────────────────────────────────────────────
	let copropriete: Copropriete | null = null;
	let batiments: Batiment[] = [];
	let plans: Document[] = [];
	let reglements: Document[] = [];
	let crAg: Document[] = [];
	let loading = true;
	//  🔴 Une erreur PAR liste, et non une pour la page (#522). Ces cinq
	//  rubriques se chargent indépendamment : dire « rien n'a marché » quand
	//  seuls les diagnostics ont échoué serait aussi faux que de ne rien dire.
	let ePlans = '',
		eReglements = '',
		eCrAg = '',
		eDiagnostics = '';
	//  Les bâtiments ne s'AFFICHENT pas : ils garnissent des menus déroulants et
	//  la correspondance « Bât. n ». Leur absence ne vide pas l'écran, elle le
	//  rend faux — d'où le bandeau plutôt qu'un état de liste.
	let eReference = '';

	let catIdPlan: number | null = null;
	let catIdReglement: number | null = null;
	let catIdCrAg: number | null = null;

	// Édition résidence
	let editing = false;
	let saving = false;
	let identite = identiteDepuis(null);

	//  Plans, règlement, CR d'AG : leur dépôt, leur correction et leur
	//  suppression vivent dans `RubriqueDocuments` (#779) — ils y étaient écrits
	//  trois fois, et la copie du plan liait son périmètre à celle de l'AG (#470).

	// Diagnostics réglementaires
	let diagnosticTypes: DiagnosticType[] = [];
	//  ⚠️ L'état du dépôt et de la correction d'un rapport vit dans
	//  `SectionDiagnostics` : il n'a d'objet que là où il est employé.

	// Règles & Recommandations

	// ── Derived ────────────────────────────────────────────────────────────────
	// Composition depuis les champs stockés sur Batiment et Copropriete

	//  Réactif : le tri des plans lit `batiments`, qui arrive après eux.
	$: trierPlans = (docs: Document[]) =>
		[...docs].sort((a, b) => {
			if (!a.batiment_id && b.batiment_id) return -1;
			if (a.batiment_id && !b.batiment_id) return 1;
			const bA = batiments.find((x) => x.id === a.batiment_id);
			const bB = batiments.find((x) => x.id === b.batiment_id);
			return (bA?.numero ?? '').localeCompare(bB?.numero ?? '');
		});
	const trierCrAg = (docs: Document[]) =>
		[...docs].sort((a, b) => {
			const anneeB = b.annee ?? 0;
			const anneeA = a.annee ?? 0;
			if (anneeB !== anneeA) return anneeB - anneeA;
			const dateB = b.date_ag ?? b.publie_le ?? '';
			const dateA = a.date_ag ?? a.publie_le ?? '';
			return dateB.localeCompare(dateA);
		});

	function batimentLabel(id: number | null | undefined): string {
		if (!id) return 'Résidence';
		const b = batiments.find((x) => x.id === id);
		return b ? `Bât. ${b.numero}` : 'Bât. ?';
	}

	//  ⚖️ L'onglet Règlement (11/10/2026) : réservé comme le carnet (`reserve` dans
	//  `pages.ts`), et MASQUÉ en plus quand l'administration ne l'a pas ouvert aux
	//  copropriétaires — le serveur seul le sait. `null` tant qu'il n'a pas
	//  répondu : l'onglet reste dans la rangée (sinon `BarreOnglets` renverrait sur
	//  la Fiche un lien reçu avant de savoir), son contenu attend. Une réponse en
	//  échec ne masque rien : l'onglet ouvert dira lui-même l'erreur.
	let accesReglement: boolean | null = null;
	$: masques = accesReglement === false ? ['reglement'] : [];
	quandAuthResolue(async () => {
		if (!$isProprioOuCS) return;
		const [r] = await essayer(reglementApi.acces(), null);
		accesReglement = r ? r.acces : true;
	});

	//  Lien profond depuis le fil d'activité, une notification ou l'onglet
	//  Règlement : `#doc-<id>` (plan, règlement, PV d'AG) ou `#diag-<id>`
	//  (rapport de diagnostic). La page est longue et découpée en sections — y
	//  arriver sans viser l'élément revient à faire chercher l'utilisateur.
	function revelerLienProfond() {
		const idDoc = cibleDuHash('doc');
		if (idDoc !== null) revelerCible(`doc-${idDoc}`);
		const idDiag = cibleDuHash('diag');
		if (idDiag !== null) revelerCible(`diag-${idDiag}`);
	}
	//  …et pas seulement à l'arrivée : un acte cité par l'onglet Règlement mène à
	//  `/residence#doc-N` SANS remonter la page (même composant, autre onglet).
	afterNavigate(({ type }) => {
		if (type !== 'enter' && !loading) revelerLienProfond();
	});

	// ── Chargement de la Fiche ─────────────────────────────────────────────────
	//  ⏱ UNE vague, et sur la Fiche seulement (#1841). Elle se chargeait en trois
	//  — les catégories, puis les trois rubriques par l'identifiant de leur
	//  catégorie, puis les règles au montage de leur section : +411 ms au lieu de
	//  +149 —, et ouverte sur le Carnet, la page lançait quand même ses huit
	//  appels. Les rubriques se demandent désormais par CODE ; l'identifiant, qui
	//  ne sert qu'au dépôt, arrive avec elles. Les règles partent aussi, et
	//  `SectionRegles` prend leur lecture à son montage.
	let ficheDemandee = false;
	let lectureRegles: LectureRegles | null = null;
	$: if (browser && onglet === 'fiche' && !ficheDemandee) {
		ficheDemandee = true;
		chargerFiche();
	}

	async function chargerFiche() {
		lectureRegles = lireRegles();
		try {
			const [
				[copro, eCopro],
				[bats, eBats],
				[cats, eCats],
				[p, ep],
				[r, er],
				[ag, eag],
				[diag, ediag],
			] = await Promise.all([
				essayer<Copropriete | null>(coproprieteApi.get(), null),
				essayer<Batiment[]>(coproprieteApi.batiments(), []),
				essayer(documentsApi.listCategories(), []),
				essayer<Document[]>(documentsApi.listParCode('plan_residence'), []),
				essayer<Document[]>(documentsApi.listParCode('reglement_copropriete'), []),
				essayer<Document[]>(documentsApi.listParCode('pv_ag'), []),
				essayer<DiagnosticType[]>(diagnosticsApi.listTypes(), []),
			]);
			copropriete = copro;
			batiments = bats;
			//  ⚠️ Sans les CATÉGORIES, `catIdPlan` & consorts valent `null` : les
			//  listes s'affichent (elles se lisent par code), mais le dépôt d'un
			//  document n'a plus de catégorie où ranger — d'où le bandeau.
			eReference = messagePartiel(eCopro, eBats, eCats);

			catIdPlan = cats.find((c) => c.code === 'plan_residence')?.id ?? null;
			catIdReglement = cats.find((c) => c.code === 'reglement_copropriete')?.id ?? null;
			catIdCrAg = cats.find((c) => c.code === 'pv_ag')?.id ?? null;

			plans = p;
			ePlans = ep;
			reglements = r;
			eReglements = er;
			crAg = ag;
			eCrAg = eag;
			diagnosticTypes = diag;
			eDiagnostics = ediag;
		} catch (e) {
			toast('error', messageErreur(e, 'Erreur de chargement'));
		} finally {
			loading = false;
		}
		//  Après le rendu de la Fiche : l'élément visé doit exister. Ouverte sur un
		//  autre onglet, la page n'est mesurée qu'au passage sur la Fiche.
		await tick();
		revelerLienProfond();
		marquerDonneesAffichees();
	}

	// ── Édition résidence ──────────────────────────────────────────────────────
	function startEdit() {
		if (!copropriete) return;
		identite = identiteDepuis(copropriete);
		editing = true;
	}

	async function saveEdit() {
		saving = true;
		await tenter(async () => {
			copropriete = await coproprieteApi.update(chargeIdentite(identite));
			nomResidenceEnregistre(copropriete.nom);
			editing = false;
		}, 'Résidence mise à jour');
		saving = false;
	}
</script>

<svelte:head><title>{_pc.titre} — {_siteNom}</title></svelte:head>

<EntetePage titre={_pc.titre} descriptif={_pc.descriptif} icone={_pc.icone || 'building-2'} />

<!--  Cette page n'avait pas d'onglets avant le carnet d'entretien (10/09/2026).
      La rangée passe par `BarreOnglets`, qui lit la liste, l'ordre, les libellés
      et les routes dans `#lib/pages` — un `<div class="tabs">` local rouvrirait
      les cinq divergences que ce composant a fermées. -->
<BarreOnglets pageId="residence" actif={onglet} {masques} />

<!--  ⚠️ En HAUT, avant tout le reste : les bâtiments et les catégories de
      document garnissent les menus déroulants et la correspondance « Bât. n ».
      Leur absence ne vide pas l'écran, elle le rend faux — et un avertissement
      posé plus bas serait lu après ce qu'il devait qualifier (#522). -->
<ChargementPartiel
	erreur={eReference}
	consequence="Les numéros de bâtiment peuvent être absents, et l'ajout d'un document indisponible."
/>

<!--  Le carnet est une VUE de la résidence, pas un écran à part : il partage
      l'en-tête, la barre d'onglets et l'adresse de cette page. -->
{#if onglet === 'carnet'}
	<!--  📊 Le bilan de l'exercice (#1645) : le conseil syndical seul, replié à
	      l'arrivée. À côté du carnet et non dedans — le carnet est la lecture de
	      tous les copropriétaires, le bilan celle du conseil. -->
	{#if $isCS}
		<ChargementDiffere charger={() => import('#lib/components/BilanCarnet.svelte')}>
			{#snippet contenu(BilanCarnet)}
				<BilanCarnet />
			{/snippet}
		</ChargementDiffere>
	{/if}
	<ChargementDiffere charger={() => import('#lib/components/CarnetEntretien.svelte')}>
		{#snippet contenu(CarnetEntretien)}
			<CarnetEntretien />
		{/snippet}
	</ChargementDiffere>
{:else if onglet === 'reglement'}
	{#if accesReglement === null}
		<EtatListe chargement />
	{:else}
		<ChargementDiffere charger={() => import('#lib/components/OngletReglement.svelte')}>
			{#snippet contenu(OngletReglement)}
				<OngletReglement />
			{/snippet}
		</ChargementDiffere>
	{/if}
{:else if onglet === 'fiche' && loading}
	<EtatListe chargement />
{:else if onglet === 'fiche' && copropriete}
	<BanniereResidence bind:copropriete peutModifier={$isCS} />

	<!-- ── Section : Résidence ───────────────────────────────────────────── -->
	<section class="section-residence">
		<div class="section-header">
			<h2 class="section-title">Résidence : {copropriete.nom}</h2>
			<!--  La fiche s'écrit par `PATCH /copropriete`, réservé à l'administrateur : le
			      conseil syndical la lit, sans crayon qui finirait en 403 (#2096). -->
			{#if $isAdmin && !editing}
				<button
					class="btn-icon-edit"
					aria-label="Modifier la fiche de la résidence"
					title="Modifier"
					on:click={startEdit}><IconeAction icone="pencil" /></button
				>
			{/if}
		</div>

		{#if editing}
			<!--  Le cadre et le pied STANDARD (#1329) : une carte et une rangée de
			      boutons écrites à la main, « Annuler » en bouton plein. -->
			<FormulaireCreation titre="Modifier la fiche de la résidence" cle="fiche">
				<form on:submit|preventDefault={saveEdit}>
					<div class="form-grid">
						<ChampsIdentiteCopropriete bind:valeurs={identite} />
						<!--  🔴 Compagnie, n° de police et échéance ONT ÉTÉ RETIRÉS d'ici.
						      Depuis #490 la fiche les lit sur le CONTRAT d'assurance, et
						      `copropriete_lue` efface ces colonnes : les saisir ici
						      corrigeait donc une valeur que plus aucun écran n'affiche.
						      Trouvé le 29/08/2026 en instruisant la remarque sur la
						      reconduction tacite. C'est le défaut que `source_du_nom` a
						      fermé pour le nom du syndic (#535), sur trois champs cette
						      fois — un formulaire qui survit à sa source se lit comme une
						      commande, pas comme un vestige. -->
						<div class="field champ-large">
							<AideSource
								active
								origine="contrat d'assurance"
								ou="Prestataires → Contrats"
								repli=""
							/>
						</div>
					</div>
					<PiedFormulaire enCours={saving} on:annule={() => (editing = false)} />
				</form>
			</FormulaireCreation>
		{:else}
			<FicheResidence {copropriete} {batiments} />
		{/if}
	</section>

	<SectionRegles bind:lecture={lectureRegles} />

	<!-- ── Plans · Règlement · Comptes-rendus d'AG : une rubrique, trois usages ── -->
	<RubriqueDocuments
		mode="plan"
		titre="&#x1F5FA;️ Plans"
		categorieId={catIdPlan}
		bind:documents={plans}
		erreur={ePlans}
		trier={trierPlans}
		messageVide="Aucun plan ajouté."
		peutModifier={$isCS}
		intitule="Ajouter un plan"
		placeholderTitre="ex : Plan de masse résidence"
		placeholderDescription="Ce que ce plan montre, à quelle date il a été relevé…"
		avecPerimetre
		quoi="Ce plan"
		messageAjout="Plan ajouté"
	>
		<svelte:fragment slot="badges" let:doc>
			<!--  Une capsule NEUTRE : elle décrit, elle ne signale pas (la page
			      Affaires, standard du site depuis le 10/10/2026). -->
			<span class="badge badge-gray"
				>{doc.batiment_id ? batimentLabel(doc.batiment_id) : 'Copropriété'}</span
			>
		</svelte:fragment>
	</RubriqueDocuments>

	<RubriqueDocuments
		mode="reglement"
		titre="&#x1F4D6; Règlement de copropriété"
		categorieId={catIdReglement}
		bind:documents={reglements}
		erreur={eReglements}
		messageVide="Aucun règlement ajouté."
		peutModifier={$isCS}
		intitule="Ajouter un règlement"
		placeholderTitre="ex : Règlement de copropriété 2024"
		placeholderDescription="Ce qu'il remplace, ce qu'il ne couvre pas, où sont les annexes…"
		quoi="Ce règlement"
		messageAjout="Règlement ajouté"
	/>

	{#if !$isLocataire}
		<RubriqueDocuments
			mode="ag"
			titre="&#x1F4CB; Comptes-rendus d'AG"
			categorieId={catIdCrAg}
			bind:documents={crAg}
			erreur={eCrAg}
			trier={trierCrAg}
			messageVide="Aucun compte-rendu ajouté."
			peutModifier={$isCS}
			intitule="Ajouter un CR d'AG"
			placeholderTitre="ex : PV AG ordinaire 2025"
			placeholderDescription="Les points saillants, les résolutions votées, ce qui reste en suspens…"
			avecPerimetre
			quoi="Ce compte-rendu d'AG"
			messageAjout="CR d'AG ajouté"
		>
			<svelte:fragment slot="badges" let:doc>
				{#if doc.annee}<span class="badge badge-gray annee-ag">{doc.annee}</span>{/if}
				<!--  La date de l'assemblée est dans la GOUTTIÈRE, sous « AG »
				      (`RubriqueDocuments`) : une seule date par carte. -->
				<!--  🔴 `perimetreLabel` sur des CODES, plus `batimentLabel` sur des
			      identifiants (#470). Trois branches se sont réduites à une : le
			      libellé d'un périmètre se calcule, il ne se décide pas ici.
			      L'ancien rendu ne savait dire que « Bât. N » ou « Copropriété » ;
			      celui-ci nomme le parking, les caves, l'AFUL et les espaces —
			      et suit l'arbre quand un nœud est renommé. -->
				<!--  Neutre, comme tout ce qui DÉCRIT (10/10/2026) : la couleur propre
				      aux documents (`purple`) était l'écart que `BadgePerimetre`
				      rendait visible pour qu'on le tranche — la page Affaires l'a fait. -->
				<BadgePerimetre perimetre={doc.perimetre_cible}>
					<span class="badge badge-gray">Copropriété</span>
				</BadgePerimetre>
			</svelte:fragment>
		</RubriqueDocuments>
	{/if}

	<!-- ── Section : Diagnostics et Contrôles Réglementaires ────────────── -->
	<!--  🔴 UN COMPOSANT depuis le 08/09/2026 (#852). C'était la dernière
	      section de cet écran à vivre à même la page — onze variables d'état,
	      six gestes, cent quatre-vingts lignes de balisage — alors que les
	      trois autres partagent `SectionDocuments` depuis #522. Le garde-fou
	      de modularité l'a refusée quand les formulaires y sont rentrés. -->
	{#if !$isLocataire}
		<SectionDiagnostics bind:types={diagnosticTypes} erreur={eDiagnostics} peutModifier={$isCS} />
	{/if}
{:else}
	<div class="empty-state">
		<h3>Résidence non configurée</h3>
		<p>Les informations de la résidence ne sont pas encore disponibles.</p>
	</div>
{/if}

<style>
	/* ── Sections ───────────────────────────────────────────────── */
	/*  🔴 `.section-header` est remontée dans `styles/composants.css` le
	    06/09/2026 (#805) : elle était écrite trois fois à l'identique — ici, dans
	    `SectionDocuments` et dans `acces-securite` — et un quatrième écran qui
	    l'employait l'aurait rendue NUE. C'est `lint:classes-nues` qui l'a dit, et
	    c'est le moment où une copie devient une règle. */
	/*  Seul `margin: 0` differe : la charte pose `margin-bottom` (#607, 28/08/2026). */
	.section-title {
		margin: 0;
	}

	/* ── Bâtiments / lot counts ─────────────────────────────────── */

	/* ── Documents ──────────────────────────────────────────────── */
	/*  🔴 TOUTE la « ligne de document » vit dans `styles/composants.css` (#491) :
	    cette page l'emploie dans SON balisage, et trois blocs en sortaient NUS.
	    Le récit — et pourquoi `lint:classes-nues` ne le voyait pas — est là-bas. */

	/*  Trois couleurs de badge réécrites ici en `:global(…)`, donc pour tout le
	    site une fois cette feuille chargée — et `.badge-purple` y prenait encore
	    une quatrième valeur, différente de celle d'`espace-cs`. Retirées (#562) :
	    la charte de `styles/composants.css` les porte déjà. */

	/* ── Pills périmètre ────────────────────────────────────────── */
	/*  `.perimetre-pills` retirée (#561) : copie identique au caractère près de
	    celle de `styles/composants.css`, donc inerte — révélée en passant la
	    classe en PROP. Un composant partagé montre ce qu'une page gardait. */
	/*  🔴 `.pill`, `.pill:hover` et `.pill-active` retirées le 28/08/2026 (#491).
	    Cet écran portait SA variante — bordure 1px au lieu de 1.5px, fond
	    `surface` au lieu de `bg`, taille .8rem au lieu de .85rem — et elle
	    GAGNAIT, par la classe de portée que Svelte ajoute au sélecteur. Deux
	    styles de pastille coexistaient donc sciemment. `ecrans.css` portait
	    l'avertissement en toutes lettres : un commentaire n'est pas un
	    garde-fou. */

	/*  🔴 L'EN-TÊTE d'une modale ne s'écrit plus ici : `Modale.svelte` le rend, et
	    `styles/composants.css` le style (`.modal-titre`). #607 avait retiré
	    `.modal-header`, `.modal-close` et `.modal-footer` de ces trois écrans en
	    laissant `.modal-header h3` — la seule des quatre qui n'existait PAS en
	    global, donc la seule que le retrait ne pouvait pas solder. Elle a survécu
	    à l'identique dans les trois, et divergeait du `h2` de la charte. */

	/* ── Diagnostics ─────────────────────────────────────────────── */
	.section-residence {
		margin-bottom: 2.5rem;
	}
	.annee-ag {
		font-variant-numeric: tabular-nums;
	}
</style>
