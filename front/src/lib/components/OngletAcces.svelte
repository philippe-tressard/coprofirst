<!--
  **Les accès d'un résident** — badges Vigik, télécommandes, demandes et
  déclarations — rendus par SECTION.

  ## Pourquoi ce composant (12/09/2026, #928)

  Il était l'écran `/acces-securite` tout entier. Le regroupement demandé —
  *« Mes lots & accès », avec « Mes badges » et « Télécommandes » en
  sous-onglets* — impose qu'un autre écran puisse le monter : `routeInterne` sert
  **tous les onglets d'une page par un seul écran** (`lib/routes-onglets.ts`), et
  `/mon-lot/badges` est donc rendue par `mon-lot`, pas par cette route-ci.

  C'est le motif des dix-sept `Onglet*.svelte` de l'administration : l'écran
  porte la barre d'onglets, le composant porte le contenu.

  ## Ce que `section` découpe, et ce qu'elle ne découpe pas

  | `section` | Ce qui s'affiche |
  |---|---|
  | `badges` | les badges Vigik, puis les blocs communs |
  | `telecommandes` | les télécommandes, puis les blocs communs |
  | `tout` | les deux listes — l'ancienne page, préservée pour `/acces-securite` |

  🔴 **Les blocs communs ne se découpent pas** : demandes passées, accès confiés
  par le bailleur, vue par locataire, badges de la copropriété. Ils portent les
  DEUX types dans la même liste — les scinder demanderait de filtrer, donc de
  décider qu'une demande à deux lignes se lit en deux endroits. Ils restent
  entiers sous chaque onglet.

  ⚠️ Les deux gestes — « + Nouvel accès » et « Déclarer un accès » — ne sont plus
  des sections à faire défiler mais des boutons en TÊTE DE PAGE (demandé le
  12/09). Ils sont donc pilotés de l'extérieur, par `ouvrirDemande` et
  `ouvrirDeclaration`, que l'écran hôte lie à ses boutons.
-->
<script lang="ts">
	import Badge from '#lib/components/Badge.svelte';
	import { statutAccesBadge, statutAccesLabel } from '#lib/types-acces.ts';
	import FormulairesAcces from '#lib/components/FormulairesAcces.svelte';
	import {
		acces as accesApi,
		lots as lotsApi,
		bailleur as bailApi,
		type AccesBail,
		type AccesPorteur,
		type Bail,
		type MonLot,
	} from '#lib/api/index.ts';
	import { tenter, messageErreur } from '#lib/erreurs.ts';
	//  ⚠️ `confirmer` et `SUPPRESSION` sont partis avec la poubelle (15/09/2026) :
	//  il ne reste ici aucun geste irréversible à faire confirmer en rouge.
	import { confirmerPuis } from '#lib/confirmation.ts';
	import { toast } from '#lib/components/Toast.svelte';
	//  `isCS` n'est plus lu : il ne servait qu'à ouvrir la suppression au conseil
	//  syndical sur CET écran — un geste qui vit désormais chez l'administrateur,
	//  sur l'écran du parc.
	import { isBailleur, isLocataire, quandAuthResolue } from '#lib/stores/auth.ts';
	import MesAcces from '#lib/components/MesAcces.svelte';
	import AccesConnexes from '#lib/components/AccesConnexes.svelte';
	import { bailEnCours, nomLocataire } from '#lib/bail.ts';
	import EtatListe from '#lib/components/EtatListe.svelte';

	let vigiks: AccesPorteur[] = [];
	let telecommandes: AccesPorteur[] = [];
	let mesLots: MonLot[] = [];
	let accesRecus: AccesBail[] = [];
	let mesBaux: Bail[] = [];
	let loading = true;

	// Formulaire demande
	let formLotId = '';
	let formType = 'vigik';
	let formQuantite = 1;
	let formMotif = '';
	let submitting = false;

	//  Pas `onMount` : il précède le layout qui charge l'utilisateur (#1486).
	quandAuthResolue(async () => {
		try {
			//  ⚠️ `mesCommandes()` n'est plus appelée (12/09/2026) : la section
			//  Archives a quitté ces onglets, et charger une liste que rien
			//  n'affiche serait un aller-retour pour personne.
			//  Une liste par rôle, chacune à SA place : un locataire qui est aussi
			//  bailleur recevait ses accès reçus à la place de ses baux, les deux
			//  lisant le quatrième résultat.
			const [v, t, lots, recus, baux] = await Promise.all([
				accesApi.mesVigiks(),
				accesApi.mesTelecommandes(),
				lotsApi.mesList(),
				$isLocataire ? bailApi.mesAccesRecus() : null,
				$isBailleur ? bailApi.mesBaux() : null,
			]);
			[vigiks, telecommandes, mesLots] = [v, t, lots];
			if (recus) accesRecus = recus;
			if (baux) mesBaux = baux;
		} catch (e) {
			toast('error', messageErreur(e, 'Erreur de chargement'));
		} finally {
			loading = false;
		}
	});

	async function soumettreCommande() {
		if (!formLotId) {
			toast('error', 'Sélectionnez un lot');
			return;
		}
		submitting = true;
		await tenter(async () => {
			await accesApi.creerCommande({
				lot_id: Number(formLotId),
				type: formType,
				quantite: formQuantite,
				motif: formMotif || undefined,
			});
			showForm = false;
			formMotif = '';
		}, 'Demande envoyée au conseil syndical');
		submitting = false;
	}

	async function signalerPerdu(id: number, typeAcces: 'vigik' | 'tc') {
		await confirmerPuis('Signaler cet accès comme perdu ?', 'Signalement enregistré', async () => {
			if (typeAcces === 'vigik') {
				await accesApi.signalerVigiKPerdu(id);
				vigiks = vigiks.map((v) => (v.id === id ? { ...v, statut: 'perdu' } : v));
			} else {
				await accesApi.signalerTcPerdu(id);
				telecommandes = telecommandes.map((t) => (t.id === id ? { ...t, statut: 'perdu' } : t));
			}
		});
	}

	//  🔴 `supprimer()` A ÉTÉ RETIRÉ LE 15/09/2026, avec ses deux routes —
	//  demandé à l'écran : *« enlève la poubelle. Un résident ne peut pas
	//  supprimer un accès, il peut juste signaler qu'il a perdu »*.
	//
	//  Le commentaire qui l'accompagnait disait déjà la moitié du problème —
	//  « retirer un accès de SON compte n'est pas le détruire : le badge existe
	//  toujours » — et le geste le détruisait quand même. Le parc perdait alors la
	//  trace d'un objet qui circule, et l'import le reproposait à la résolution
	//  suivante.
	//
	//  Ce qui reste au porteur : **signaler une perte**. Ce qui reste à
	//  l'administrateur : la suppression définitive, sur l'écran du parc.

	// Déclaration d'accès existant
	let declareType = 'telecommande';
	let declareCode = '';
	let declaring = false;

	async function declarerBadge() {
		if (!declareCode.trim()) {
			toast('error', 'Saisissez un code');
			return;
		}
		declaring = true;
		//  ⚠️ Le message de succès dépend de la RÉPONSE (« import mis à jour ») :
		//  il n'est connu qu'après l'appel, d'où le `toast` à l'intérieur.
		await tenter(async () => {
			const r = await accesApi.declarerBadge({ type: declareType, code: declareCode.trim() });
			if (declareType === 'vigik') {
				vigiks = await accesApi.mesVigiks();
			} else {
				telecommandes = await accesApi.mesTelecommandes();
			}
			const msg = r.import_resolu ? ' (import mis à jour)' : '';
			toast('success', `Accès enregistré${msg}`);
			declareCode = '';
			showDeclareForm = false;
		});
		declaring = false;
	}

	// ── Bailleur : vue par locataire ─────────────────────────────────────────
	// Regroupement des vigiks/TCs confiés (chez_locataire) par locataire (email/nom)
	$: locatairesAcces = (() => {
		const bauxActifs = mesBaux.filter(bailEnCours);
		const all = [
			...vigiks.filter((v) => v.chez_locataire).map((v) => ({ ...v, typeAcces: 'vigik' as const })),
			...telecommandes
				.filter((t) => t.chez_locataire)
				.map((t) => ({ ...t, typeAcces: 'telecommande' as const })),
		];
		// Grouper par identité du locataire (email prioritaire, sinon nom+prénom)
		const groupMap = new Map<string, { baux: Bail[]; items: typeof all }>();
		for (const bail of bauxActifs) {
			const key =
				bail.locataire_email?.trim().toLowerCase() ||
				`${bail.locataire_prenom}|${bail.locataire_nom}`;
			if (!groupMap.has(key)) groupMap.set(key, { baux: [bail], items: [] });
			else groupMap.get(key)!.baux.push(bail);
		}
		for (const group of groupMap.values()) {
			const bailIds = new Set(group.baux.map((b) => b.id));
			group.items = all.filter((a) => a.bail_id != null && bailIds.has(a.bail_id));
		}
		return [...groupMap.values()];
	})();

	async function recupererTousLocataireAcces(bailIds: number[]) {
		await confirmerPuis(
			'Récupérer tous les accès confiés à ce locataire ?',
			'Accès récupérés',
			async () => {
				const updates = await Promise.all(bailIds.map((id) => bailApi.recupererAcces(id)));
				const ids = new Set(updates.flat().map((u) => `${u.type}:${u.id}`));
				vigiks = vigiks.map((v) =>
					ids.has(`vigik:${v.id}`) ? { ...v, chez_locataire: false, bail_id: null } : v,
				);
				telecommandes = telecommandes.map((t) =>
					ids.has(`telecommande:${t.id}`) ? { ...t, chez_locataire: false, bail_id: null } : t,
				);
			},
			'Erreur lors de la récupération',
		);
	}

	/**  Quelle liste d'accès cette instance montre. `tout` conserve l'ancienne
	 *   page — deux listes à la suite — pour `/acces-securite`. */
	export let section: 'badges' | 'telecommandes' | 'tout' = 'tout';

	/**  Les deux gestes sont OUVERTS depuis l'en-tête de page (#928) : l'écran
	 *   hôte porte les boutons, ce composant porte les formulaires. Les lier par
	 *   des props liées plutôt que par des événements évite à l'hôte de tenir un
	 *   second état qui pourrait se désaccorder de celui-ci. */
	export let showForm = false;
	export let showDeclareForm = false;
</script>

{#if loading}
	<EtatListe chargement />
{:else}
	<!--  🔴 Les deux sections étaient écrites À L'IDENTIQUE, à quatre mots près
	      (#805). Quarante lignes en double — table, colonnes, boutons et leurs
	      conditions. Elles n'avaient pas encore divergé : c'est exactement le
	      moment où l'on factorise, avant d'avoir à décider laquelle a raison.

	      La condition d'affichage reste ici, pour les deux : un locataire sans
	      badge ne voit pas la section vide, un copropriétaire si — il peut en
	      déclarer un. Elle parle de la place de la section dans l'écran, pas du
	      tableau. -->
	{#if section !== 'telecommandes' && (vigiks.length > 0 || !$isLocataire)}
		<MesAcces
			titre="Badges d'accès (Vigik)"
			messageVide="Aucun badge enregistré."
			items={vigiks}
			onSignalerPerdu={(id) => signalerPerdu(id, 'vigik')}
		/>
	{/if}

	{#if section !== 'badges' && (telecommandes.length > 0 || !$isLocataire)}
		<MesAcces
			titre="Télécommandes de parking"
			messageVide="Aucune télécommande enregistrée."
			items={telecommandes}
			onSignalerPerdu={(id) => signalerPerdu(id, 'tc')}
		/>
	{/if}

	<!--  Les deux formulaires vivent dans `FormulairesAcces` (#928) : ce fichier
	      est né au-dessus du plafond en extrayant l'écran, et la coupe sépare ce
	      que je POSSÈDE de ce que je DEMANDE. Ils sont ouverts depuis l'en-tête
	      de page, d'où les deux props liées. -->
	<FormulairesAcces
		bind:showForm
		bind:showDeclareForm
		{mesLots}
		{soumettreCommande}
		{declarerBadge}
		bind:formLotId
		bind:formType
		bind:formQuantite
		bind:formMotif
		{submitting}
		{declaring}
		bind:declareType
		bind:declareCode
	/>

	<!-- Vue par locataire (bailleurs uniquement) -->
	{#if $isBailleur && mesBaux.length > 0}
		<section class="section card section-locataires">
			<div class="section-header">
				<h2 class="section-title">👥 Vue par locataire</h2>
			</div>
			{#if mesBaux.filter(bailEnCours).length === 0}
				<p class="text-muted-md">Aucun bail actif.</p>
			{:else}
				<p class="intro">Résumé des accès (Vigik / télécommandes) confiés à vos locataires.</p>
				{#each locatairesAcces as { baux, items } (baux[0]?.id ?? baux)}
					{@const premierBail = baux[0]}
					<div class="locataire-acces-row">
						<div class="lar-header">
							<div class="lar-tenant">
								<strong>{nomLocataire(premierBail)}</strong>
								{#if premierBail.locataire_email}<a
										href="mailto:{premierBail.locataire_email}"
										class="courriel">{premierBail.locataire_email}</a
									>{/if}
							</div>
							<div class="etat-locataire">
								{#if items.length > 0}
									<Badge teinte="badge-yellow" compact
										>{items.length} accès confié{items.length > 1 ? 's' : ''}</Badge
									>
									<button
										class="btn btn-sm btn-outline"
										on:click={() => recupererTousLocataireAcces(baux.map((b) => b.id))}
										>↩ Tout récupérer</button
									>
								{:else}
									<Badge teinte="badge-gray" compact>Aucun accès confié</Badge>
								{/if}
							</div>
						</div>
						{#if items.length > 0}
							<div class="lar-items">
								{#each items as item (item.id ?? item.code)}
									<div class="lar-item">
										<span class="code-acces">{item.code}</span>
										<Badge
											teinte={item.typeAcces === 'vigik' ? 'badge-blue' : 'badge-purple'}
											compact
										>
											{item.typeAcces === 'vigik' ? '🏷️ Vigik' : '📡 TC'}
										</Badge>
										<Badge teinte={statutAccesBadge(item.statut)} compact
											>{statutAccesLabel(item.statut)}</Badge
										>
									</div>
								{/each}
							</div>
						{/if}
					</div>
				{/each}
			{/if}
		</section>
	{/if}

	<!--  🔴 La vue d'ensemble du conseil syndical (#805). Elle vient APRÈS les
	      sections personnelles : cet écran est d'abord celui du résident — ses
	      badges, ses demandes — et le CS y ajoute un niveau de lecture, il ne le
	      remplace pas.
	
	      ⚠️ Réservée à `$isCS`, comme l'endpoint (`require_cs_or_admin`) : l'écran
	      dit ce que le serveur fait, ni plus ni moins (`ux-patterns` §15). -->

	<AccesConnexes {accesRecus} />
{/if}

<style>
	/*  ⚠️ `.section` est définie ICI **et** dans `AccesConnexes`, et ce n'est pas
	    une duplication à retirer : Svelte scope ses styles au FICHIER. Une classe
	    employée dans deux composants doit être définie dans les deux, sinon l'un
	    des deux écrans part nu — c'est ce que `lint:classes-nues` refuse. */
	.section {
		margin-bottom: 1.25rem;
	}
	/*  Seul `margin: 0` differe : la charte pose `margin-bottom` (#607, 28/08/2026). */
	.section-title {
		margin: 0;
	}
	/* Vue locataire bailleur */
	.locataire-acces-row {
		padding: 0.7rem 0;
		border-bottom: 1px solid var(--color-border);
	}
	.locataire-acces-row:last-child {
		border-bottom: none;
	}
	.lar-header {
		display: flex;
		justify-content: space-between;
		align-items: flex-start;
		gap: 0.75rem;
		flex-wrap: wrap;
		margin-bottom: 0.45rem;
	}
	.lar-tenant {
		display: flex;
		flex-direction: column;
		gap: 0.15rem;
	}
	.lar-items {
		display: flex;
		flex-wrap: wrap;
		gap: 0.4rem;
	}
	.lar-item {
		display: flex;
		align-items: center;
		gap: 0.3rem;
		background: var(--color-bg);
		border: 1px solid var(--color-border);
		border-radius: var(--radius);
		padding: 0.2rem 0.55rem;
		font-size: var(--fs-md);
	}
	.section-locataires {
		margin-top: 1rem;
		border-left: 3px solid var(--color-accent);
	}
	.intro {
		font-size: var(--fs-md);
		color: var(--color-text-muted);
		margin-bottom: 0.9rem;
	}
	.courriel {
		font-size: var(--fs-sm);
		color: var(--color-primary);
	}
	.etat-locataire {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		flex-wrap: wrap;
	}
	.code-acces {
		font-family: monospace;
		font-size: var(--fs-md);
	}
</style>
