<!--
  PageCommunaute.svelte — l'écran **Communauté** : sondages, boîte à idées et
  petites annonces.

  ## Pourquoi ce n'est plus une route (05/09/2026)

  Les trois rubriques ont désormais chacune leur adresse — `/sondages`, `/idees`,
  `/annonces` — parce qu'un onglet qui n'a pas d'URL ne peut pas s'envoyer. Trois
  routes, un seul écran : le contenu vit donc ici, et les trois `+page.svelte` ne
  font que le monter avec l'onglet que leur `load` a résolu.

  ⚠️ L'onglet est une PROPRIÉTÉ, jamais un état local : c'est le chemin qui décide.
  Le basculement d'onglet est une navigation (`<a href>` dans `BarreOnglets`), pas
  une affectation — sans quoi la barre d'adresse mentirait sur ce qu'on regarde,
  ce qui était exactement le défaut d'origine.
-->
<script lang="ts">
	import ChargementDiffere from '$lib/components/ChargementDiffere.svelte';
	import EntetePage from '$lib/components/EntetePage.svelte';
	import { IDEE_BADGE } from '$lib/idees';
	import OngletAnnonces from '$lib/components/OngletAnnonces.svelte';
	import { goto } from '$app/navigation';
	import {
		sondages as sondagesApi,
		idees as ideesApi,
		annonces as annoncesApi,
		signalements as signalementsApi,
		type Idee,
		type PetiteAnnonce,
		type Signalement,
		type Sondage,
		type SondageDetail,
	} from '$lib/api';
	import { currentUser, isAdmin, isCS, isGestionnaire, quandAuthResolue } from '$lib/stores/auth';
	import { refuserLaCommunaute } from '$lib/communaute';
	import { toast } from '$lib/components/Toast.svelte';
	import { getPageConfig, configStore, siteNomStore, defautsDePage } from '$lib/stores/pageConfig';
	import { messageErreur, tenter } from '$lib/erreurs';
	import { confirmerPuis, SUPPRESSION } from '$lib/confirmation';
	import { signaler as signalerContenu } from '$lib/signalements';
	import EtatListe from '$lib/components/EtatListe.svelte';
	import { essayer } from '$lib/chargement';
	import ListeSondages from '$lib/components/ListeSondages.svelte';
	import ListeEtArchives from '$lib/components/ListeEtArchives.svelte';
	import OngletIdees from '$lib/components/OngletIdees.svelte';
	import { trackTabView } from '$lib/telemetry';
	import { cibleDuHash, revelerCible } from '$lib/deepLink';
	import BarreOnglets from '$lib/components/BarreOnglets.svelte';
	import PanneauModeration from '$lib/components/PanneauModeration.svelte';
	import { routeOnglet } from '$lib/routes-onglets';

	$: _pc = getPageConfig($configStore, 'communaute', defautsDePage('communaute'));
	$: _siteNom = $siteNomStore;

	/**  L'onglet à rendre, résolu par le `load` de la route depuis le chemin. Il
	 *   n'est pas modifiable ici : on change d'onglet en NAVIGUANT. */
	export let onglet: string;
	$: trackTabView(onglet);

	// Ban communauté
	let banMessage = '';
	//  Vide = chargé sans encombre. Non vide = on n'a PAS pu regarder, et l'écran
	//  doit le dire au lieu d'annoncer « aucun » (#519).
	let erreurSondages = '';
	let erreurIdees = '';
	let erreurAnnonces = '';

	// Sondages — l'état de SAISIE vit dans `FormulaireSondage.svelte` : le ciblage
	// (périmètre, destinataires), les options et les canaux y sont désormais, avec
	// le reste des formulaires du site. Ne restent ici que la LISTE et ses actions.
	let sondages: Sondage[] = [];

	//  🔴 La partition courants / Archives est portée par `ListeEtArchives`, sur
	//  le `s.archivee` que le SERVEUR calcule (`app/utils/archivage.py`, #515) :
	//  30 jours après la date de clôture, délai réglable en administration. La
	//  recalculer ici en ferait une seconde règle — c'est exactement ce que #468 a
	//  retiré pour `cloture`, que la liste comparait à l'heure LOCALE du navigateur
	//  quand le serveur date en UTC.
	let sondagesLoading = true;
	let showFormSondage = false;

	//  « Ce sondage est-il clos ? » n'est PLUS calculé ici : le serveur le dit dans
	//  `s.cloture`, par la même `sondage_clos()` que la fiche, le vote et le fil
	//  (#468). La règle locale comparait `cloture_le` à l'heure LOCALE du
	//  navigateur quand le serveur date en UTC — un sondage clôturant à minuit
	//  était clos ou non selon le fuseau du lecteur. Un écran ne tranche pas ce
	//  genre de question (`ux-patterns` §16).

	//  La correction d'un sondage (#783). L'état vit ICI, pas dans
	//  `ListeSondages` : celui-ci est rendu DEUX fois (courants et Archives), et
	//  l'y mettre en aurait monté deux exemplaires sur le même sondage.
	//
	//  🔴 Une FICHE (`SondageDetail`), jamais la ligne de la liste (#1661) : la liste
	//  (`GET /sondages`) ne porte pas les options, et le formulaire les corrige par
	//  leur `id`. Ouvert avec la ligne de la liste, il montrait deux champs vides, et
	//  ce qu'on y tapait était ignoré — l'enregistrement ne renvoie que les options
	//  qui ont un `id`.
	let editSondage: SondageDetail | null = null;

	async function modifierSondage(s: Sondage, e: Event) {
		//  Le `preventDefault` date du temps où la carte ÉTAIT un lien : il ne sert
		//  plus (#1329, lien étiré sous des boutons qui ne sont plus dedans), et il
		//  est sans effet sur un bouton.
		e.preventDefault();
		if (editSondage?.id === s.id) {
			editSondage = null;
			return;
		}
		try {
			editSondage = await sondagesApi.get(s.id);
		} catch (err) {
			toast('error', messageErreur(err, 'Impossible de charger le sondage'));
		}
	}

	async function arreterSondage(s: Sondage, e: Event) {
		e.preventDefault();
		await confirmerPuis(
			`Stopper le sondage « ${s.question} » maintenant ?`,
			'Sondage stoppé',
			async () => {
				await sondagesApi.cloturer(s.id);
				//  `cloture` AUSSI : c'est lui que l'affichage lit désormais. Ne poser que
				//  `cloture_forcee` laisserait la carte inchangée jusqu'au rechargement.
				sondages = sondages.map((x) =>
					x.id === s.id ? { ...x, cloture_forcee: true, cloture: true } : x,
				);
			},
		);
	}

	async function supprimerSondage(s: Sondage, e: Event) {
		e.preventDefault();
		await confirmerPuis(
			SUPPRESSION(`Le sondage « ${s.question} »`),
			'Sondage supprimé',
			async () => {
				await sondagesApi.supprimer(s.id);
				sondages = sondages.filter((x) => x.id !== s.id);
			},
		);
	}

	// Idées
	let idees: Idee[] = [];
	let ideesLoading = true;
	let showFormIdee = false;
	let filtreStatut = '';

	//  Les annonces : la page les CHARGE (un seul `Promise.all` pour les trois
	//  rubriques) et les lie à `OngletAnnonces`, qui porte tout le reste — filtres,
	//  formulaires, gestes. `expandedAnnonce` reste ici parce qu'un lien profond
	//  (`#annonce-12`) la désigne avant que l'onglet ne soit monté.
	let annonces: PetiteAnnonce[] = [];
	let annoncesLoading = true;
	let showFormAnnonce = false;
	let expandedAnnonce: number | null = null;

	const statutClass = (s: string) => IDEE_BADGE[s] ?? 'badge-gray';

	$: filteredIdees = filtreStatut ? idees.filter((i) => i.statut === filtreStatut) : idees;
	$: sortedIdees = [...filteredIdees].sort((a, b) => b.nb_votes - a.nb_votes);

	function ideeCreee() {
		//  La liste est rechargée plutôt que complétée localement : le compteur de
		//  votes et le statut sont calculés par le serveur.
		ideesApi.list().then((l) => (idees = l));
		showFormIdee = false;
	}

	async function voter(id: number) {
		//  ⚠️ Le message de succès vient du SERVEUR (« vote retiré », « vote
		//  enregistré ») : il n'est connu qu'après l'appel, d'où le `toast` à
		//  l'intérieur plutôt qu'en second argument de `tenter`.
		await tenter(async () => {
			const res = await ideesApi.voter(id);
			idees = await ideesApi.list();
			toast('success', res.message ?? 'Vote enregistré');
		});
	}

	async function changeStatut(id: number, statut: string) {
		await tenter(async () => {
			await ideesApi.updateStatut(id, statut);
			idees = idees.map((i) => (i.id === id ? { ...i, statut } : i));
		}, 'Statut mis à jour');
	}

	async function deleteIdee(id: number) {
		await confirmerPuis(SUPPRESSION('Cette idée'), 'Idée supprimée', async () => {
			await ideesApi.delete(id);
			idees = idees.filter((i) => i.id !== id);
		});
	}

	// ── Réponses (idées + annonces) — composant partagé Reponses.svelte ──────────
	async function repondreIdee(id: number, contenu: string) {
		const publiee = await tenter(async () => {
			await ideesApi.repondre(id, contenu);
			idees = await ideesApi.list();
		}, 'Réponse publiée');
		//  🔴 L'échec doit REMONTER : `Reponses` ne vide son champ que si la
		//  promesse aboutit. L'avaler effacerait une réponse non publiée.
		if (!publiee) throw new Error('Réponse non publiée');
	}

	async function supprimerReponseIdee(ideeId: number, repId: number) {
		//  ⚠️ La confirmation est demandée par `Reponses`, qui porte le bouton.
		await tenter(async () => {
			await ideesApi.supprimerReponse(ideeId, repId);
			idees = await ideesApi.list();
		}, 'Réponse supprimée');
	}

	// ── Signalements / modération ────────────────────────────────────────────────
	//  Le dépliement du panneau est parti avec lui (`PanneauModeration`) : c'est son
	//  affaire, pas celle de l'écran.
	let signalements: Signalement[] = [];

	//  🔴 Un échec se dit au modérateur : taire la file lui fait croire qu'elle
	//  est vide (#1459).
	let erreurSignalements = '';
	//  🔴 Pas depuis `onMount` : il précède celui du layout, qui charge
	//  l'utilisateur. Sur un chargement direct, `$isCS` y était encore faux, et la
	//  file n'était JAMAIS demandée — le CS ne la voyait qu'après une navigation.
	quandAuthResolue(chargerSignalements);
	async function chargerSignalements() {
		if (!$isCS) return;
		[signalements, erreurSignalements] = await essayer(signalementsApi.liste('en_attente'), []);
	}

	//  Le geste lui-même vit dans `$lib/signalements` : il était écrit à
	//  l'identique ici et dans `sondages/[id]`. Ne reste que ce qui est PROPRE à
	//  cet écran — recharger la liste de modération quand on est au CS.
	const signaler = (cibleType: string, cibleId: number) =>
		signalerContenu(cibleType, cibleId, () => {
			if ($isCS) chargerSignalements();
		});

	async function resoudreSignalement(id: number, statut: 'traite' | 'rejete') {
		await tenter(
			async () => {
				await signalementsApi.resoudre(id, statut);
				signalements = signalements.filter((s) => s.id !== id);
			},
			statut === 'traite' ? 'Signalement traité' : 'Signalement ignoré',
		);
	}

	//  🔴 Le MOTIF vient de l'API (`communaute_motif_refus`), il ne se recalcule
	//  pas ici. Cet écran portait sa propre copie de la règle — statut, ban
	//  définitif, ban probatoire — avec un troisième libellé, différent de celui
	//  que l'API renvoie dans sa 403 et de celui que l'administration notifie
	//  (29/08/2026). L'API décide et FORMULE ; l'écran choisit le GESTE.

	// Garde réactive : redirige dès que le user est connu (garde contre la race condition async layout)
	$: if ($currentUser && $isGestionnaire) refuserLaCommunaute($currentUser);

	//  Pas `onMount` : il précède le layout qui charge l'utilisateur (#1486).
	quandAuthResolue(async () => {
		//  Un profil inadapté est déjà redirigé ci-dessus : ce qui reste ici est une
		//  suspension, qui s'affiche en bandeau plutôt qu'en redirection.
		if ($currentUser?.communaute_motif_refus) {
			banMessage = $currentUser.communaute_motif_refus;
			sondagesLoading = false;
			ideesLoading = false;
			annoncesLoading = false;
			return;
		}

		//  La liste des bâtiments n'est plus chargée ici : le sélecteur de périmètre
		//  lit l'arbre complet depuis son store, comme sur tous les autres écrans — un
		//  bâtiment n'est qu'un nœud parmi le parking, l'AFUL et les espaces.
		//  🔴 Un échec de chargement N'EST PAS une liste vide (19/08/2026).
		//
		//  Ces trois appels portaient `.catch(() => [])` : toute erreur — session
		//  expirée, 500, réseau — devenait un tableau vide, et l'écran affichait
		//  « Aucun sondage » / « Aucune annonce », c'est-à-dire EXACTEMENT le même
		//  rendu que s'il n'y avait rien. L'utilisateur a cru ses données perdues :
		//  deux sondages et trois annonces en cours dormaient en base pendant que
		//  l'écran affirmait le contraire.
		//
		//  C'est la règle 1 du projet, côté écran : une sortie vide n'est pas un
		//  constat (`standards/04`). On distingue donc les deux, et on le DIT.
		const [rS, rI, rA] = await Promise.allSettled([
			sondagesApi.list(),
			ideesApi.list(),
			annoncesApi.list(),
		]);
		if (rS.status === 'fulfilled') sondages = rS.value;
		else erreurSondages = messageErreur(rS.reason);
		if (rI.status === 'fulfilled') idees = rI.value;
		else erreurIdees = messageErreur(rI.reason);
		if (rA.status === 'fulfilled') annonces = rA.value;
		else erreurAnnonces = messageErreur(rA.reason);
		sondagesLoading = false;
		ideesLoading = false;
		annoncesLoading = false;

		// ── Lien profond ────────────────────────────────────────────────────────────
		//  L'ancre désigne un élément qui vit dans UNE rubrique précise. Sur la bonne
		//  route, on le révèle ; sur une autre, on navigue — sans cela « Voir
		//  l'annonce → » déposait le lecteur sur les sondages, où l'annonce n'est
		//  évidemment pas (bug signalé le 26/07/2026, et c'est le même défaut que
		//  l'onglet sans adresse : le lien connaissait la cible, pas l'écran).
		const idAnnonce = cibleDuHash('annonce');
		if (idAnnonce !== null) {
			expandedAnnonce = idAnnonce; // détails dépliés, comme après un dépôt
			if (onglet !== 'annonces') {
				goto(`${routeOnglet('communaute', 'annonces')}#annonce-${idAnnonce}`);
				return;
			}
			revelerCible(`annonce-${idAnnonce}`);
		}

		const idIdee = cibleDuHash('idee');
		if (idIdee !== null) {
			if (onglet !== 'idees') {
				goto(`${routeOnglet('communaute', 'idees')}#idee-${idIdee}`);
				return;
			}
			revelerCible(`idee-${idIdee}`);
		}
	});
</script>

<svelte:head><title>{_pc.titre} — {_siteNom}</title></svelte:head>

<!--  L'en-tête n'OUVRE plus : l'annulation vit à côté d'« Enregistrer » (norme du
      18/08/2026). Deux commandes pour un formulaire, c'est #367. -->
<EntetePage titre={_pc.titre} descriptif={_pc.descriptif} icone={_pc.icone || 'users-round'}>
	{#if onglet === 'sondages' && $isCS && !showFormSondage}
		<button class="btn btn-primary page-header-btn" on:click={() => (showFormSondage = true)}>
			+ Nouveau sondage
		</button>
	{:else if onglet === 'idees' && !showFormIdee}
		<button class="btn btn-primary page-header-btn" on:click={() => (showFormIdee = true)}>
			+ Nouvelle idée
		</button>
	{:else if onglet === 'annonces' && !showFormAnnonce}
		<button class="btn btn-primary page-header-btn" on:click={() => (showFormAnnonce = true)}>
			+ Déposer une annonce
		</button>
	{/if}
</EntetePage>

{#if banMessage}
	<div class="alert bannissement">
		⛔ {banMessage}
	</div>
{:else}
	<BarreOnglets pageId="communaute" actif={onglet} />

	{#if $isCS && erreurSignalements}
		<EtatListe compact erreur={erreurSignalements} />
	{:else if $isCS && signalements.length > 0}
		<PanneauModeration
			{signalements}
			on:resoudre={(e) => resoudreSignalement(e.detail.id, e.detail.decision)}
		/>
	{/if}

	{#if onglet === 'sondages'}
		{#if showFormSondage && $isCS}
			<ChargementDiffere charger={() => import('$lib/components/FormulaireSondage.svelte')}>
				{#snippet contenu(FormulaireSondage)}
					<FormulaireSondage
						on:cree={async () => {
							sondages = await sondagesApi.list();
							showFormSondage = false;
						}}
						on:annule={() => (showFormSondage = false)}
					/>
				{/snippet}
			</ChargementDiffere>
		{/if}

		<!--  La correction (#783), montée UNE seule fois et hors des deux listes —
		      `ListeSondages` est rendu deux fois (courants et Archives). `{#key}`
		      remonte le composant d'un sondage à l'autre : ses champs sont
		      initialisés une seule fois, à la construction.

		      ⚠️ ICI, ET NON DANS LA CARTE — contrairement aux annonces et aux idées,
		      dont le formulaire est passé dans le corps de la carte le 06/09/2026
		      (#787, « c'est tout en bas, et on ne voit pas »). Une carte de sondage
		      est un `<a>` vers sa fiche : y glisser un formulaire mettrait des
		      champs et des boutons **dans un lien**, ce qu'aucun navigateur ne rend
		      correctement et qu'aucun lecteur d'écran n'annonce.

		      Le formulaire est donc posé AU-DESSUS de la liste — le même endroit
		      que les actualités, et il reste sous les yeux. Ce n'est pas un oubli :
		      c'est la limite de ce que la carte-lien permet. -->
		{#if editSondage}
			{#key editSondage.id}
				<ChargementDiffere charger={() => import('$lib/components/FormulaireSondage.svelte')}>
					{#snippet contenu(FormulaireSondage)}
						<FormulaireSondage
							sondage={editSondage}
							on:modifie={async () => {
								sondages = await sondagesApi.list();
								editSondage = null;
							}}
							on:annule={() => (editSondage = null)}
						/>
					{/snippet}
				</ChargementDiffere>
			{/key}
		{/if}

		<EtatListe
			chargement={sondagesLoading}
			erreur={erreurSondages}
			vide={sondages.length === 0}
			titreErreur="Impossible d'afficher les sondages"
			titreVide="Aucun sondage"
			messageVide="Les sondages du conseil syndical apparaîtront ici."
		>
			<ListeEtArchives
				liste={sondages}
				titreVideCourant="Aucun sondage en cours"
				messageVideCourant="Les sondages clos sont rangés dans les Archives, ci-dessous."
			>
				<svelte:fragment let:items>
					<ListeSondages sondages={items} {arreterSondage} {supprimerSondage} {modifierSondage} />
				</svelte:fragment>
			</ListeEtArchives>
		</EtatListe>
	{/if}

	{#if onglet === 'idees'}
		<OngletIdees
			idees={sortedIdees}
			chargement={ideesLoading}
			erreur={erreurIdees}
			bind:filtreStatut
			showForm={showFormIdee}
			currentUserId={$currentUser?.id}
			estCS={$isCS}
			estAdmin={$isAdmin}
			{statutClass}
			onVoter={voter}
			onChangerStatut={changeStatut}
			onSupprimer={deleteIdee}
			onSignaler={signaler}
			onRepondre={repondreIdee}
			onSupprimerReponse={supprimerReponseIdee}
			on:cree={ideeCreee}
			on:annule={() => (showFormIdee = false)}
		/>
	{/if}

	{#if onglet === 'annonces'}
		<OngletAnnonces
			bind:annonces
			chargement={annoncesLoading}
			erreur={erreurAnnonces}
			bind:showForm={showFormAnnonce}
			bind:expandedAnnonce
			estCS={$isCS}
			estAdmin={$isAdmin}
			currentUserId={$currentUser?.id}
			onSignaler={signaler}
		/>
	{/if}
{/if}

<!-- /banMessage else -->

<style>
	.bannissement {
		margin: 2rem 0;
		padding: 1.5rem;
		border-radius: 10px;
		text-align: center;
		font-size: 1.1rem;
	}
</style>
