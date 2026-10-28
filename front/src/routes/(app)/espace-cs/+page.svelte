<script lang="ts">
	import ChargementDiffere from '$lib/components/ChargementDiffere.svelte';
	import { lieu } from '$lib/lieu.svelte';
	import { nomAffiche } from '$lib/noms';
	import type { Inscrit, LigneImport, LotRapproche } from '$lib/annuaire-rapprochement';
	import type { User } from '$lib/api/types';
	import EntetePage from '$lib/components/EntetePage.svelte';
	//  ⏱ L'onglet Annuaire et la boîte de validation attendent un geste :
	//  chargés à leur affichage (#1844).
	import { validerCompte } from '$lib/comptes';
	import { messageErreur, tenter } from '$lib/erreurs';
	import ChargementPartiel from '$lib/components/ChargementPartiel.svelte';
	import { essayer, messagePartiel } from '$lib/chargement';
	import { isCS, authResolue, quandAuthResolue } from '$lib/stores/auth';
	import { goto } from '$app/navigation';
	import {
		admin as adminApi,
		auth as authApi,
		lots as lotsApi,
		type CommandeAccesEnAttente,
	} from '$lib/api';
	import { typeAccesLabel } from '$lib/types-acces';
	import { toast } from '$lib/components/Toast.svelte';
	import { getPageConfig, configStore, siteNomStore, defautsDePage } from '$lib/stores/pageConfig';
	import { fmtDateShort } from '$lib/date';
	import { marquerDonneesAffichees, trackTabView } from '$lib/telemetry';
	import BarreOnglets from '$lib/components/BarreOnglets.svelte';
	import { agitPourAutrui } from '$lib/roles';
	import { accepterCommandeAcces, refuserCommandeAcces } from '$lib/commandes-acces';
	import EtatListe from '$lib/components/EtatListe.svelte';

	$: _pc = getPageConfig($configStore, 'espace-cs', defautsDePage('espace-cs'));
	$: _siteNom = $siteNomStore;

	// -- Onglet -------------------------------------------------------------
	//  🔴 UNE SEULE LISTE, et elle est dans la TABLE (`$lib/pages.ts`, 05/09/2026).
	//  Elle a d'abord été écrite deux fois dans ce fichier (04/09), puis une fois
	//  ici et une fois dans la table — qui porte désormais aussi l'URL de chaque
	//  onglet. Une liste locale rouvrirait la divergence avec l'adresse.
	export let data: { onglet: string };
	$: onglet = data.onglet;
	/** Vue de reporting demandée par l'URL — c'est `OngletReporting` qui la valide.
	 *
	 * 🔴 DÉRIVÉE, et non posée dans `onMount` (18/09/2026). Svelte monte les
	 * ENFANTS avant le parent : `OngletReporting` lisait donc `vueInitiale` alors
	 * que le parent ne l'avait pas encore renseignée, et l'alerte « ticket syndic
	 * à relancer » du tableau de bord ouvrait le suivi des dossiers au lieu de la
	 * relance. Le lien était juste, l'ordre de montage le rendait sans effet.
	 */
	$: vueReporting = onglet === 'reporting' ? ($lieu.url.searchParams.get('vue') ?? null) : null;
	$: trackTabView(onglet);

	// -- Validations --------------------------------------------------------
	let batimentsMap: Record<number, string> = {};
	let comptesEnAttente: User[] = [];
	let commandesEnAttente: CommandeAccesEnAttente[] = [];
	let loading = true;
	$: nbComptes = comptesEnAttente.length;
	$: nbCommandes = commandesEnAttente.length;

	//  ⚠️ Les 31 symboles `ah*` vivent dans `OngletAnnoncesHall.svelte` depuis le
	//  20/08/2026 : ils ne servaient qu'à cet onglet, et l'onglet s'amorce seul.

	// -- Annuaire -----------------------------------------------------------
	//  L'onglet vit dans `AnnuaireConseil` et `AnnuaireSyndic` (#779, 29/09/2026),
	//  qui s'amorcent seuls. La page ne garde que les données de RÉFÉRENCE qu'elle
	//  charge de toute façon : elles servent aux deux à rapprocher un nom saisi
	//  d'un inscrit et d'un logement (`$lib/annuaire-rapprochement`).
	/** Non vide = une donnée de référence manque : l'écran est faux, pas vide. */
	let erreurBatiments = '';
	let erreurAnnuaire = '';
	$: erreurReference = messagePartiel(erreurBatiments, erreurAnnuaire);
	let allUsers: Inscrit[] = [];
	let allLots: LotRapproche[] = [];
	let lotImports: LigneImport[] = [];
	$: sources = { inscrits: allUsers, lots: allLots, imports: lotImports, batiments: batimentsMap };
	//  🔴 Refuser sur un « non » AVÉRÉ, jamais sur un « pas encore » : le pourquoi est dans `check-gardes-auth.mjs`.
	$: if ($authResolue && !$isCS) goto('/tableau-de-bord');
	quandAuthResolue(() => {
		if ($isCS) charger();
	});
	//  🔴 L'onglet Validations n'attend que SES lectures (#1843). Il attendait
	//  aussi les inscrits, les lots et les imports de lots, qui ne servent qu'à
	//  l'Annuaire — dont `/lots/admin/imports`, l'une des routes les plus lentes
	//  du serveur : +210 ms à chaque ouverture de l'Espace CS.
	async function charger() {
		try {
			const [comptes, commandes, [batList, eBat]] = await Promise.all([
				adminApi.comptesEnAttente(),
				adminApi.commandesAccesEnAttente(),
				essayer<{ id: number; numero: string }[]>(authApi.batiments(), []),
			]);
			erreurBatiments = eBat;
			comptesEnAttente = comptes;
			//  🔴 Le type du CLIENT, et non un type local (#1679) : `PendingAcces`
			//  lisait un demandeur et un lot que la route ne rendait pas, et une
			//  commande en attente faisait tomber le rendu de l'onglet. La route
			//  rend désormais `demandeur_nom`, `lot` et `batiment`.
			commandesEnAttente = commandes;
			batimentsMap = Object.fromEntries(batList.map((b) => [b.id, `Bât. ${b.numero}`]));
		} catch {
			toast('error', 'Erreur de chargement');
		} finally {
			loading = false;
			marquerDonneesAffichees();
		}
	}

	//  Les données de RÉFÉRENCE de l'Annuaire se lisent à l'ouverture de
	//  l'Annuaire, une fois (#1843) — et ses deux annuaires ne se montent qu'une
	//  fois LUES : une donnée « pas encore là » ne doit pas se lire « aucune
	//  correspondance » (#522).
	let referenceDemandee = false;
	let referenceLue = false;
	$: if (onglet === 'annuaire' && $authResolue && $isCS && !referenceDemandee) {
		referenceDemandee = true;
		chargerReference();
	}
	async function chargerReference() {
		//  🔴 Trois données de RÉFÉRENCE (#522) : elles ne s'affichent nulle
		//  part, elles garnissent les rapprochements d'un nom saisi avec un inscrit
		//  et un logement. Un échec ne vidait aucune liste — il rendait le
		//  rapprochement automatique muet, sans que rien ne distingue « aucune
		//  correspondance » de « je n'ai pas cherché ».
		const [[users, eUsers], [lotsData, eLots], [importsData, eImports]] = await Promise.all([
			essayer(adminApi.utilisateurs(), []),
			essayer(lotsApi.tous(), []),
			essayer(lotsApi.listImports(), []),
		]);
		erreurAnnuaire = messagePartiel(eUsers, eLots, eImports);
		allUsers = users.map((u) => ({
			id: u.id,
			prenom: u.prenom,
			nom: u.nom,
			email: u.email,
			telephone: u.telephone ?? null,
			batiment_id: u.batiment_id ?? null,
		}));
		allLots = lotsData as LotRapproche[];
		lotImports = importsData;
		referenceLue = true;
	}

	// -- Validations handlers -----------------------------------------------
	// Validation + Nouvel Arrivant
	let cvModal: User | null = null;
	let cvNewArrivant = false;
	let cvBatiment = '';
	let cvAncienResident = '';
	let cvSubmitting = false;

	function openCSValidation(user: User) {
		cvModal = user;
		cvNewArrivant = false;
		cvBatiment = user.batiment_id ? (batimentsMap[user.batiment_id] ?? '') : '';
		cvAncienResident = '';
	}

	//  🔴 Le geste vit dans `$lib/comptes` (12/09/2026). Cet écran en portait sa
	//  propre version, plus PAUVRE que celle de l'administration : le même
	//  endpoint rend `auto_match`, et le conseil syndical ne voyait ni les lots
	//  résolus, ni l'avertissement quand un copropriétaire aidé reste introuvable.
	//  `standards/02` §4 bis — entre deux implémentations, retenir LA PLUS DISANTE.
	async function confirmerCSValidation() {
		if (!cvModal) return;
		const u = cvModal;
		cvSubmitting = true;
		try {
			const annonces = await validerCompte(u, {
				nouvelArrivant: cvNewArrivant,
				batiment: cvBatiment,
				ancienResident: cvAncienResident,
			});
			comptesEnAttente = comptesEnAttente.filter((x) => x.id !== u.id);
			for (const a of annonces) toast(a.ton, a.texte);
			cvModal = null;
		} catch (e) {
			toast('error', messageErreur(e));
		} finally {
			cvSubmitting = false;
		}
	}

	async function traiterCompte(id: number, decision: 'approuver' | 'rejeter') {
		await tenter(
			async () => {
				await adminApi.traiterCompte(id, {
					action: decision === 'approuver' ? 'valider' : 'refuser',
				});
				comptesEnAttente = comptesEnAttente.filter((u) => u.id !== id);
			},
			decision === 'approuver' ? 'Compte approuvé' : 'Compte rejeté',
		);
	}
	async function traiterCommande(id: number, decision: 'approuver' | 'rejeter') {
		await tenter(
			async () => {
				if (decision === 'rejeter') await refuserCommandeAcces(id);
				else if (!(await accepterCommandeAcces(id))) return;
				commandesEnAttente = commandesEnAttente.filter((c) => c.id !== id);
			},
			decision === 'approuver' ? 'Commande approuvée' : 'Commande rejetée',
		);
	}
</script>

<svelte:head><title>{_pc.titre} · {_siteNom}</title></svelte:head>

<EntetePage titre={_pc.titre} descriptif={_pc.descriptif} icone={_pc.icone || 'shield-half'} />

<ChargementPartiel
	erreur={erreurReference}
	consequence="Les numéros de bâtiment peuvent s'afficher « Bât. ? », et le rapprochement automatique des lots ne trouvera rien — faute d'avoir pu chercher."
/>

<!-- Onglets -->
<BarreOnglets
	pageId="espace-cs"
	actif={onglet}
	comptes={{ validations: nbComptes + nbCommandes }}
/>

{#if onglet === 'validations'}
	{#if loading}
		<EtatListe chargement />
	{:else}
		<!-- KPI Cards -->
		<div class="kpi-row kpi-espaces">
			<div class="kpi-card" class:kpi-alert={nbComptes > 0}>
				<div class="kpi-value">{nbComptes}</div>
				<div class="kpi-label">Compte(s) à valider</div>
			</div>
			<div class="kpi-card" class:kpi-alert={nbCommandes > 0}>
				<div class="kpi-value">{nbCommandes}</div>
				<div class="kpi-label">Demande(s) d'accès</div>
			</div>
		</div>

		<!-- Comptes en attente -->
		<section class="largeur-saisie section-file">
			<h2 class="titre-file">Comptes en attente de validation</h2>
			{#if comptesEnAttente.length === 0}
				<p class="text-muted-sm">Aucun compte en attente.</p>
			{:else}
				{#each comptesEnAttente as user (user.id)}
					<div class="pending-row card" class:pending-row--edition={cvModal?.id === user.id}>
						<div class="pending-info">
							<strong>{nomAffiche(user)}</strong>
							<span class="text-muted-sm">
								{user.statut?.replace(/_/g, ' ') ?? '…'}{user.batiment_id
									? ` — ${batimentsMap[user.batiment_id] ?? `Bât. #${user.batiment_id}`}`
									: ''}
							</span>
							{#if agitPourAutrui(user) && user.nom_aide}
								<span class="text-muted-sm"
									>👤 Aidé : {nomAffiche(user.prenom_aide, user.nom_aide)}</span
								>
							{/if}
							<span class="text-muted-sm">{fmtDateShort(user.cree_le)}</span>
						</div>
						{#if cvModal?.id !== user.id}
							<div class="pending-actions">
								<button
									class="btn btn-sm btn-success"
									aria-pressed="false"
									on:click={() => openCSValidation(user)}>✓ Approuver</button
								>
								<button
									class="btn btn-sm btn-danger"
									on:click={() => traiterCompte(user.id, 'rejeter')}>✗ Rejeter</button
								>
							</div>
						{/if}
					</div>
					<!--  🔴 Le formulaire s'ouvre SOUS la ligne du compte, pas dans une
					      fenêtre (#889, arbitrage du 11/09/2026 : « les gestes courts dans
					      la carte »). Il est identique à celui de l'administration —
					      littéralement le même composant, et non plus une copie qui
					      dérive. -->
					{#if cvModal?.id === user.id}
						<div class="pending-form">
							<ChargementDiffere charger={() => import('$lib/components/ValidationCompte.svelte')}>
								{#snippet contenu(ValidationCompte)}
									<ValidationCompte
										utilisateur={user}
										enCours={cvSubmitting}
										bind:nouvelArrivant={cvNewArrivant}
										bind:batiment={cvBatiment}
										bind:ancienResident={cvAncienResident}
										onAnnuler={() => (cvModal = null)}
										onValider={confirmerCSValidation}
									/>
								{/snippet}
							</ChargementDiffere>
						</div>
					{/if}
				{/each}
			{/if}
		</section>

		<!-- Commandes d'accès -->
		<section class="largeur-saisie">
			<h2 class="titre-file">Demandes d'accès (badges / télécommandes)</h2>
			{#if commandesEnAttente.length === 0}
				<p class="text-muted-sm">Aucune demande en attente.</p>
			{:else}
				{#each commandesEnAttente as cmd (cmd.id)}
					<div class="pending-row card">
						<div class="pending-info">
							<strong>{cmd.demandeur_nom}</strong>
							<span class="text-muted-sm">
								{cmd.batiment ? `${cmd.batiment} · ` : ''}{cmd.lot} ·
								{typeAccesLabel(cmd.type)} · {cmd.quantite}
							</span>
							<span class="text-muted-sm">{fmtDateShort(cmd.cree_le)}</span>
						</div>
						<div class="pending-actions">
							<button
								class="btn btn-sm btn-success"
								on:click={() => traiterCommande(cmd.id, 'approuver')}>✓ Approuver</button
							>
							<button
								class="btn btn-sm btn-danger"
								on:click={() => traiterCommande(cmd.id, 'rejeter')}>✗ Rejeter</button
							>
						</div>
					</div>
				{/each}
			{/if}
		</section>
	{/if}
{:else if onglet === 'badges'}
	<!--  Le parc de badges a quitté « Mes lots & accès » (12/09/2026) : motif dans `pages.ts`. -->
	<ChargementDiffere charger={() => import('$lib/components/BadgesCopropriete.svelte')}>
		{#snippet contenu(BadgesCopropriete)}
			<BadgesCopropriete />
		{/snippet}
	</ChargementDiffere>
{:else if onglet === 'reporting'}
	<ChargementDiffere charger={() => import('$lib/components/reporting/OngletReporting.svelte')}>
		{#snippet contenu(OngletReporting)}
			<OngletReporting
				titreOnglet={_pc.onglets?.reporting?.label ?? 'Reporting'}
				vueInitiale={vueReporting}
			/>
		{/snippet}
	</ChargementDiffere>
{:else if onglet === 'annonces-hall'}
	<!-- Aucune prop de plafond : l'affiche a la sienne (`$lib/annonces`, #651). -->
	<ChargementDiffere charger={() => import('$lib/components/OngletAnnoncesHall.svelte')}>
		{#snippet contenu(OngletAnnoncesHall)}
			<OngletAnnoncesHall />
		{/snippet}
	</ChargementDiffere>
{:else if onglet === 'courriels'}
	<ChargementDiffere charger={() => import('$lib/components/OngletCourriels.svelte')}>
		{#snippet contenu(OngletCourriels)}
			<OngletCourriels />
		{/snippet}
	</ChargementDiffere>
{:else if onglet === 'annuaire'}
	<ChargementDiffere charger={() => import('$lib/components/OngletAnnuaireCS.svelte')}>
		{#snippet contenu(OngletAnnuaireCS)}
			<OngletAnnuaireCS {referenceLue} {sources} />
		{/snippet}
	</ChargementDiffere>
{/if}

<style>
	/*  `.tabs`, `.tab-btn` et ses deux états : copies au caractère près de
	    `styles/ecrans.css`, donc inertes. Retirées le 28/08/2026. */
	/*  `.badge-count` retirée : portée par `Onglet.svelte`, avec son balisage. */

	/* KPI */

	/* Validations */
	/*  La ligne d'un compte en cours de validation : son formulaire s'ouvre juste
	    dessous, les deux ne doivent pas se lire comme deux objets. */
	.pending-row--edition {
		border-bottom-left-radius: 0;
		border-bottom-right-radius: 0;
		margin-bottom: 0;
	}
	.pending-form {
		margin-bottom: 0.6rem;
	}
	.pending-row {
		display: flex;
		justify-content: space-between;
		align-items: center;
		gap: 1rem;
		margin-bottom: 0.5rem;
		flex-wrap: wrap;
	}
	.pending-info {
		display: flex;
		flex-direction: column;
		gap: 0.15rem;
	}
	.pending-actions {
		display: flex;
		gap: 0.5rem;
		flex-shrink: 0;
	}
	.btn-success {
		background: var(--color-success-plein);
		color: var(--color-sur-plein);
		border: none;
	}
	@media (hover: hover) and (pointer: fine) {
		.btn-success:hover:not(:disabled) {
			background: var(--color-success);
		}
	}
	.btn-danger {
		border: none;
	} /* fond et couleur : charte (#607) */
	@media (hover: hover) and (pointer: fine) {
		.btn-danger:hover:not(:disabled) {
			background: var(--color-danger);
		}
	}

	/*  Les sections de l'annuaire et leur style : `OngletAnnuaireCS` (#1844). */
	/*  🔴 Les vingt-huit règles de l'onglet « Tickets résidence » sont parties
	    avec lui le 28/08/2026 : `.tk-*`, `.context-chip`, `.rich-content`,
	    `.evol-form` et `.history-item` n'habillaient que ce balisage-là. Cette
	    page ne rend plus aucun ticket — `/tickets` le fait, avec `CarteTicket`. */
	/*  `.field label` et `.field textarea` : morts, retirés le 18/08/2026.
	    `.field select` : il repeignait la règle du même nom de `composants.css`,
	    et gagnait par la classe de portée de Svelte — retiré le 28/08 (#593). */
	/*  Trois couleurs de badge réécrites ici en `:global(…)`, donc pour tout le
	    site une fois cette feuille chargée. Retirées (#562) : la charte de
	    `styles/composants.css` les porte déjà. */

	/* Reporting */
	/*  Les trente-six règles `.ah-*` sont parties avec `OngletAnnoncesHall` :
	    Svelte scope les styles au composant qui rend le balisage, et les laisser
	    ici aurait livré l'onglet entièrement NU (v2.67.11). */
	.kpi-espaces {
		margin-bottom: 1.5rem;
	}
	.section-file {
		margin-bottom: 2rem;
	}
	.titre-file {
		font-size: 1rem;
		font-weight: 600;
		margin-bottom: 0.75rem;
	}
</style>
