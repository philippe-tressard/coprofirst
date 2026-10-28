<script lang="ts">
	import { lotTypeLabel } from '$lib/utils';
	import EntetePage from '$lib/components/EntetePage.svelte';
	import CaracteristiquesLot from '$lib/components/CaracteristiquesLot.svelte';
	import TableauCharges from '$lib/components/TableauCharges.svelte';
	import ChoixPastilles from '$lib/components/ChoixPastilles.svelte';
	import FormulaireCreation from '$lib/components/FormulaireCreation.svelte';
	import ChargementDiffere from '$lib/components/ChargementDiffere.svelte';
	import { onMount } from 'svelte';
	import { marquerDonneesAffichees } from '$lib/telemetry';
	import {
		lots as lotsApi,
		bailleur as bailApi,
		type Bail,
		type BailLocataire,
		type MonLot,
	} from '$lib/api';
	import { toast } from '$lib/components/Toast.svelte';
	import {
		isBailleur,
		isCS,
		isCoproprietaire,
		isLocataire,
		isResident,
		quandAuthResolue,
	} from '$lib/stores/auth';
	import { getPageConfig, configStore, siteNomStore, defautsDePage } from '$lib/stores/pageConfig';
	import { browser } from '$app/env';
	import { goto } from '$app/navigation';
	import BarreOnglets from '$lib/components/BarreOnglets.svelte';
	//  ⏱ Les onglets Accès et Location, la correction d'un bail et ses accès
	//  attendent un geste : chargés à leur affichage (#1844).
	import BoutonNouveau from '$lib/components/BoutonNouveau.svelte';
	import { messageErreur, tenter } from '$lib/erreurs';
	import { routeOnglet, routeSousOnglet } from '$lib/routes-onglets';
	import { bailEnCours, champsLocataire, nomLocataire } from '$lib/bail';
	import LotsBailleur from '$lib/components/LotsBailleur.svelte';
	import LotsLocataire from '$lib/components/LotsLocataire.svelte';
	import EtatListe from '$lib/components/EtatListe.svelte';

	$: _pc = getPageConfig($configStore, 'mon-lot', defautsDePage('mon-lot'));
	$: _siteNom = $siteNomStore;
	//  Deux lectures d'un même droit : le masquage dit ce qui s'AFFICHE, la
	//  redirection ce qui s'ATTEINT. Depuis que la gestion locative a une adresse,
	//  la seconde ne va plus de soi — un lien reçu par un locataire ouvrirait
	//  l'onglet que la barre lui cache.

	const ROUTE_BAUX_ACTIFS = routeSousOnglet('mon-lot', 'location', 'actif');

	// ── Onglet principal ───────────────────────────────────────────────────────
	//  L'onglet ET son sous-onglet viennent du CHEMIN — `/mon-lot/location/archives`
	//  est une adresse à part entière, qu'on peut envoyer. Le `load` les résout ;
	//  cet écran ne fait que les lire.
	export let data: { onglet: string; sous: string | null };
	$: mainTab = data.onglet;

	//  Les deux gestes d'accès (#928), refermés au changement d'onglet : un
	//  formulaire laissé derrière un onglet qu'on ne regarde plus est un
	//  formulaire qu'on croit avoir annulé.
	let accesDemande = false;
	let accesDeclare = false;
	$: if (mainTab) {
		accesDemande = false;
		accesDeclare = false;
	}
	$: bailTab = data.sous ?? 'actif';
	$: peutGererLocation = $isBailleur || $isCS || ($isResident && bauxTermines.length > 0);
	$: if (browser && !bauxLoading && mainTab === 'location' && !peutGererLocation) {
		goto(routeOnglet('mon-lot', 'lots'), { replaceState: true });
	}

	//  🔴 `Objet` est devenu `ObjetRemis`, dans `$lib/api` (#806) : c'est une
	//  réponse d'API, pas une notion de cet écran, et il était déclaré à
	//  l'identique ici et dans le composant qui le rend.

	// ── State (locataire bail) ────────────────────────────────────────────────
	let monBailData: BailLocataire | null = null;

	// ── State (lots) ──────────────────────────────────────────────────────────
	let lots: MonLot[] = [];
	let loading = true;
	/**  Non vide = on n'a PAS pu regarder. Distinct de « aucun lot associé ». */
	let erreurLots = '';
	/**  Le lot choisi, en valeur de pastille (`ChoixPastilles` parle en chaînes). */
	let lotChoisi = '';

	$: selectedLot = lots.find((l) => String(l.id) === lotChoisi) ?? null;
	$: optionsLots = lots.map((l) => ({
		val: String(l.id),
		label: `${l.batiment_nom ?? '—'} / ${lotTypeLabel(l.type)} - ${l.numero}`,
	}));
	$: bailAccesLot = bailAcces
		? (lots.find((l) => l.id === (bailAcces?.lot_id ?? -1)) ?? null)
		: null;

	// ── State (gestion locative) ──────────────────────────────────────────────
	let baux: Bail[] = [];
	let bauxLoading = true;

	//  La boîte de création s'ouvre depuis l'EN-TÊTE et depuis la vue bailleur
	//  (« + Créer un bail » sur un lot vacant) : c'est pourquoi ces deux états
	//  restent ici. Le reste de la saisie vit dans `OngletGestionLocative`.
	let showNewBail = false;
	let newBailLotIds = new Set<number>();

	// Edition locataire
	let bailEdite: Bail | null = null;
	let editLocataire = champsLocataire();
	let editLocataireId: number | null = null;

	// Gestion des accès (Vigik / TC) par bail
	let bailAcces: Bail | null = null;

	// ── Derived ────────────────────────────────────────────────────────────────
	$: bauxActifs = baux.filter(bailEnCours);
	$: bauxTermines = baux.filter((b) => b.statut === 'termine');

	// ── Init ───────────────────────────────────────────────────────────────────
	onMount(async () => {
		//  ⚠️ PAS `tenter` ici : ce `catch` fait plus que dire l'échec, il le
		//  MÉMORISE (`erreurLots`) pour que l'écran distingue « aucun lot » de
		//  « je n'ai pas pu regarder » (#816). `tenter` toaste et rend un booléen —
		//  il ne remplacerait pas cette nuance, il l'effacerait.
		try {
			lots = await lotsApi.mesList();
			if (lots.length > 0) lotChoisi = String(lots[0].id);
		} catch (e) {
			//  🔴 Sans cette variable, l'écran annonçait « Aucun lot associé » après
			//  un échec de chargement (#816) — et la page explique alors, en trois
			//  lignes, comment faire rattacher un lot qui EST peut-être déjà là.
			erreurLots = messageErreur(e, 'Impossible de charger vos lots');
			toast('error', erreurLots);
		} finally {
			loading = false;
			marquerDonneesAffichees();
		}
	});

	/**  Le locataire vient de dire ce qu'il loue : ses lots ont changé. */
	async function relireLots() {
		try {
			lots = await lotsApi.mesList();
		} catch (e) {
			toast('error', messageErreur(e, 'Impossible de relire vos lots'));
		}
	}

	/**  Les baux que CE compte gère : les siens (copropriétaire), tous (conseil),
	 *   aucun sinon. Écrit une fois — le chargement et l'affectation automatique
	 *   des accès le recopiaient (#779). */
	function lireBaux(): Promise<Bail[]> | null {
		if ($isCoproprietaire) return bailApi.mesBaux();
		if ($isCS) return bailApi.tousBaux();
		return null;
	}

	//  🔴 Ce qui dépend du RÔLE attend que le rôle soit connu (#779, 30/09/2026).
	//  C'était dans `onMount`, qui précède celui du layout qui charge l'utilisateur :
	//  sur un chargement direct ou un rechargement de la page, `$isCoproprietaire`
	//  et `$isLocataire` y valaient encore `false`. Un bailleur voyait alors TOUS
	//  ses lots « Vacant », avec « + Créer un bail » sur un lot loué ; un locataire
	//  ne voyait pas son bail. Seule une navigation interne rendait l'écran juste.
	quandAuthResolue(chargerSelonRole);
	async function chargerSelonRole() {
		if ($isLocataire) {
			try {
				monBailData = await bailApi.monBail();
			} catch (e) {
				//  « Pas de bail » est une réponse `null`, jamais une erreur (#1459).
				toast('error', messageErreur(e, 'Impossible de charger votre bail'));
			}
		}
		const lecture = lireBaux();
		if (lecture) {
			try {
				baux = await lecture;
			} catch (e) {
				toast('error', messageErreur(e, 'Erreur de chargement des baux'));
			}
		}
		bauxLoading = false;
	}

	function ouvrirEditionLocataire(bail: Bail) {
		bailEdite = bail;
		editLocataireId = bail.locataire_id ?? null;
		editLocataire = champsLocataire(bail);
		//  L'état de la recherche — compte associé, résultats, suggestions — vit
		//  dans `FormulaireBail` : il n'existe que pendant la saisie, et le
		//  formulaire est monté à l'ouverture, démonté à la fermeture.
	}

	async function sauvegarderLocataire() {
		if (!bailEdite) return;
		const cible = bailEdite;
		await tenter(async () => {
			const updated = await bailApi.updateBail(cible.id, {
				...editLocataire,
				date_sortie_prevue: editLocataire.date_sortie_prevue || null,
				locataire_id: editLocataireId ?? null,
			});
			baux = baux.map((b) => (b.id === updated.id ? { ...updated, objets: b.objets } : b));
			bailEdite = null;
		}, 'Informations mises à jour');
	}

	// ── Gestion accès ─────────────────────────────────────────────────────────

	//  🔴 L'ouverture ne fait plus QUE désigner le bail : le chargement des
	//  accès, la sélection et les deux gestes sont partis dans
	//  `ModaleAccesBail` (#779). La page n'en apprend rien — elle n'en avait
	//  besoin de rien.
	function ouvrirAccesBail(bail: Bail) {
		bailAcces = bail;
	}
</script>

<svelte:head><title>{_pc.titre} — {_siteNom}</title></svelte:head>

<EntetePage titre={_pc.titre} descriptif={_pc.descriptif} icone={_pc.icone || 'key-round'}>
	{#if mainTab === 'location'}
		<BoutonNouveau
			ouvert={showNewBail}
			libelle="Nouveau bail"
			on:basculer={() => (showNewBail = true)}
		/>
	{/if}
	<!--  🔴 DEUX gestes en tête (#928) : ils étaient deux sections tout en bas de
	      l'ancien écran. ⚠️ Ils disent deux choses — « Nouvel accès » demande au
	      syndic ce qu'on n'a pas, « Déclarer » signale ce qu'on détient déjà. -->
	{#if mainTab === 'badges' || mainTab === 'telecommandes'}
		<BoutonNouveau
			ouvert={accesDemande}
			libelle="Nouvel accès"
			on:basculer={() => {
				accesDemande = true;
				accesDeclare = false;
			}}
		/>
		<BoutonNouveau
			ouvert={accesDeclare}
			libelle="Déclarer un accès"
			on:basculer={() => {
				accesDeclare = true;
				accesDemande = false;
			}}
		/>
	{/if}
</EntetePage>

<!--  🔴 Barre TOUJOURS rendue (#928) : trois onglets pour tout le monde depuis
      que la page porte les accès. ⚠️ `masques` plutôt qu'une condition autour
      d'elle — le « si concerné » porte sur UN onglet, pas sur la rangée. -->
<BarreOnglets pageId="mon-lot" actif={mainTab} masques={peutGererLocation ? [] : ['location']} />

<!-- ── Onglets : Mes badges (Vigik) · Télécommandes de parking ───────── -->
<!--  🔴 Le contenu vit dans `OngletAcces` (#928) : `routeInterne` sert tous les
      onglets d'une page par UN écran, donc `/mon-lot/badges` arrive ici. Motif
      des dix-sept `Onglet*.svelte` de l'administration. -->
{#if mainTab === 'badges' || mainTab === 'telecommandes'}
	<ChargementDiffere charger={() => import('$lib/components/OngletAcces.svelte')}>
		{#snippet contenu(OngletAcces)}
			<OngletAcces
				section={mainTab}
				bind:showForm={accesDemande}
				bind:showDeclareForm={accesDeclare}
			/>
		{/snippet}
	</ChargementDiffere>
{/if}

<!-- ── Onglet : Mes lots ────────────────────────────────────────────── -->
{#if mainTab === 'lots'}
	<!--  L'échec AVANT le vide : « aucun lot » est une affirmation, et on ne
	      l'a pas constatée (`EtatListe`). -->
	<EtatListe chargement={loading} erreur={erreurLots} titreErreur="Impossible d’afficher vos lots">
		{#if lots.length === 0 && !$isLocataire}
			<div class="empty-state">
				<h3>Aucun lot associé</h3>
				<p>Votre compte n'est pas encore lié à un lot.</p>
				<p class="aide-rattachement">
					Si votre compte vient d'être validé, la liaison se fait automatiquement.<br />
					Si aucun lot n'apparaît, contactez le gestionnaire du site ou
					<a href="/tickets?nouveau=1">faites une nouvelle demande</a>.
				</p>
			</div>
		{:else if $isLocataire}
			<!-- ── Vue locataire : lot loué via bail, et ses lots en propre ── -->
			<LotsLocataire bail={monBailData} {lots} onRattache={relireLots} />
		{:else if $isBailleur}
			<!-- ── Vue bailleur : lots possédés + locataires ── -->
			<LotsBailleur
				{lots}
				{bauxActifs}
				routeGestion={ROUTE_BAUX_ACTIFS}
				onCreerBail={(lotId) => {
					newBailLotIds = new Set([lotId]);
					showNewBail = true;
					goto(ROUTE_BAUX_ACTIFS);
				}}
				onAcces={ouvrirAccesBail}
				onModifierLocataire={ouvrirEditionLocataire}
			/>
		{:else}
			<!-- ── Vue standard (non bailleur) : sélecteur lot + carte ── -->
			{#if lots.length > 1}
				<ChoixPastilles
					options={optionsLots}
					bind:valeur={lotChoisi}
					tous={false}
					libelle="Lot affiché"
				/>
			{/if}

			<!--  Mes charges, lot par lot et au total (#2251, maquette A). -->
			<div class="largeur-saisie">
				<TableauCharges {lots} />
			</div>

			{#if selectedLot}
				<div class="card largeur-saisie carte-lot">
					<h2 class="carte-lot-titre">Caractéristiques</h2>
					<CaracteristiquesLot
						type={selectedLot.type}
						typeAppartement={selectedLot.type_appartement}
						etage={selectedLot.etage}
						superficie={selectedLot.superficie}
						designation={selectedLot}
					>
						<svelte:fragment slot="avant">
							<dt>Lot</dt>
							<dd>{selectedLot.numero}</dd>
							<dt>Bâtiment</dt>
							<dd>{selectedLot.batiment_nom ?? '—'}</dd>
						</svelte:fragment>
					</CaracteristiquesLot>
				</div>
			{/if}
		{/if}
	</EtatListe>
{/if}

<!-- ── Onglet : Gestion locative ────────────────────────────────────── -->
{#if mainTab === 'location'}
	<!--  Le contenu vit dans `OngletGestionLocative` (#928) : cette page a reçu les
	      deux sous-onglets d'accès, et le plafond de modularité a refusé — comme
	      l'audit de l'issue l'avait annoncé. La coupe suit la frontière que la
	      barre d'onglets dessine déjà. -->
	<ChargementDiffere charger={() => import('$lib/components/OngletGestionLocative.svelte')}>
		{#snippet contenu(OngletGestionLocative)}
			<OngletGestionLocative
				bind:baux
				{bauxActifs}
				{bauxTermines}
				{bauxLoading}
				{lots}
				{bailTab}
				bind:showNewBail
				bind:newBailLotIds
				{ouvrirEditionLocataire}
				{ouvrirAccesBail}
				{lireBaux}
			/>
		{/snippet}
	</ChargementDiffere>
{/if}

<!-- ── Correction d'un bail : LE MÊME formulaire, en modale ─────────── -->
<!--  Enveloppé pour sa `cle` : ce formulaire est rendu 240 lignes sous celui
      de création, donc en bas de page. Le motif est dans `FormulaireCreation`. -->
{#if bailEdite}
	<FormulaireCreation titre="Modifier les informations" cle={bailEdite.id}>
		<ChargementDiffere charger={() => import('$lib/components/FormulaireBail.svelte')}>
			{#snippet contenu(FormulaireBail)}
				<FormulaireBail
					edition
					intitule=""
					bind:bail={editLocataire}
					bind:locataireId={editLocataireId}
					on:annuler={() => (bailEdite = null)}
					on:enregistrer={sauvegarderLocataire}
				/>
			{/snippet}
		</ChargementDiffere>
	</FormulaireCreation>
{/if}

<!-- ── Modal : gestion des accès (Vigik / TC) ───────────────────────── -->
{#if bailAcces}
	<!--  Le bail fixé ici : le rétrécissement de `{#if}` ne traverse pas le snippet. -->
	{@const bail = bailAcces}
	<ChargementDiffere charger={() => import('$lib/components/ModaleAccesBail.svelte')}>
		{#snippet contenu(ModaleAccesBail)}
			<ModaleAccesBail
				bailId={bail.id}
				titre={`Accès — ${nomLocataire(bail)}`}
				typeLot={bailAccesLot?.type ?? null}
				on:fermer={() => (bailAcces = null)}
			/>
		{/snippet}
	</ChargementDiffere>
{/if}

<!-- ── Modal : retour objet ─────────────────────────────────────────── -->
<!--  🔴 La modale « Retour — … » A DÉMÉNAGÉ dans `InventaireBail` (#806) : elle
     porte sur un objet, pas sur un bail, et laisser son balisage ici pendant que
     le tableau qui l'ouvre est ailleurs aurait coupé un geste en deux fichiers. -->

<style>
	/*  Le sélecteur de lots est `ChoixPastilles` (#779, 01/10/2026) : `.lot-tabs`
	    repeignait des pastilles sous un autre nom, et la liste des
	    caractéristiques (`.details-grid`) est partie avec `CaracteristiquesLot`. */
	.carte-lot {
		margin-bottom: 1.5rem;
	}
	.carte-lot-titre {
		font-size: 1rem;
		font-weight: 600;
		margin-bottom: 1rem;
	}
	.aide-rattachement {
		font-size: var(--fs-md);
		color: var(--color-text-muted);
		margin-top: 0.5rem;
	}
	.aide-rattachement a {
		color: var(--color-primary);
	}
	/*  🔴 DIX règles orphelines ont été retirées d'ici le 06/09/2026 (#806), et la
	    façon dont elles sont apparues vaut d'être écrite.

	    Elles étaient mortes DEPUIS LONGTEMPS — restes d'un balisage parti, dont
	    `.search-locataire-row`, recopiée ici alors que `RechercheLocataire.svelte`
	    la porte avec son propre balisage. `lint:css-orphelin` n'en signalait
	    aucune.

	    ⚠️ La raison : le tableau d'inventaire contenait une classe INTERPOLÉE
	    (`class="badge {statutObjetBadge[objet.statut] ?? …}"`). Devant une classe
	    qu'il ne peut pas résoudre, le compilateur Svelte devient conservateur et
	    cesse de déclarer des sélecteurs inutilisés — POUR TOUT LE FICHIER. Une
	    seule interpolation aveuglait donc le contrôle sur 1 600 lignes.

	    Le tableau parti dans `InventaireBail`, l'aveuglement est parti avec lui, et
	    les dix restes sont devenus visibles. Un contrôle vert peut ne rien mesurer
	    (`standards/04`) : ici il ne le disait pas — il annonçait « 0 orphelin »,
	    pas « je n'ai pas pu regarder ». */

	/* Main tabs (like communauté) */
	/*  `.tabs` est partie avec les sous-onglets de la gestion locative
	    (12/09/2026, #928) : le style suit le balisage. */
	/* le reste vient de la charte (#607) */

	/* Bail sub-tabs */

	/* Lot multi-checklist */

	/*  🔴 L'EN-TÊTE d'une modale ne s'écrit plus ici : `Modale.svelte` le rend, et
	    `styles/composants.css` le style (`.modal-titre`). #607 avait retiré
	    `.modal-header`, `.modal-close` et `.modal-footer` de ces trois écrans en
	    laissant `.modal-header h3` — la seule des quatre qui n'existait PAS en
	    global, donc la seule que le retrait ne pouvait pas solder. Elle a survécu
	    à l'identique dans les trois, et divergeait du `h2` de la charte. */

	/* Bloc recherche locataire */
	/*  Le champ vit dans un `.field champ-en-ligne` depuis le 28/08/2026 : il
	    repeignait `.field input` et perdait le focus de la charte (#593, volet
	    C). Ne reste ici que la répartition, propre à cette rangée. */

	/*  🔴 `.chip-btn` retirée le 28/08/2026 (#491) : c'était la pastille de la
	    charte, sous un AUTRE NOM — donc invisible à toute recherche sur `pill`,
	    et libre de diverger sans que personne ne la rapproche de son modèle.
	    Elle avait déjà divergé : `.78rem`, `.2rem .55rem`, et un état actif en
	    teinte pâle là où la charte remplit la pastille. */
</style>
