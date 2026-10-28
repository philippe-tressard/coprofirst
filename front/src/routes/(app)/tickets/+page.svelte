<script lang="ts">
	import ChargementDiffere from '#lib/components/ChargementDiffere.svelte';
	import EntetePage from '#lib/components/EntetePage.svelte';
	import BoutonNouveau from '#lib/components/BoutonNouveau.svelte';
	import FiltresAffaires from '#lib/components/FiltresAffaires.svelte';
	import EtatListe from '#lib/components/EtatListe.svelte';
	import { onMount } from 'svelte';
	import { marquerDonneesAffichees } from '#lib/telemetry.ts';
	import { goto } from '$app/navigation';
	import BarreOnglets from '#lib/components/BarreOnglets.svelte';
	//  ⏱ Le Kanban attend le passage sur son onglet (#1844).
	import { routeOnglet } from '#lib/routes-onglets.ts';
	import { revelerCible } from '#lib/deepLink.ts';
	import { isAdmin, isCS } from '#lib/stores/auth.ts';
	import { writable } from 'svelte/store';
	import { tickets as ticketsApi, type Ticket } from '#lib/api/index.ts';
	import { messageErreur } from '#lib/erreurs.ts';
	import { affairesEnListe } from '#lib/affaires-en-liste.ts';
	import { TICKET } from '#lib/entites/ticket.ts';
	import { categorieDuLien } from '#lib/formulaire-affaire.ts';
	import {
		getPageConfig,
		configStore,
		siteNomStore,
		defautsDePage,
	} from '#lib/stores/pageConfig.ts';
	import ListeTickets from '#lib/components/ListeTickets.svelte';
	import ArchivesParAnnee from '#lib/components/ArchivesParAnnee.svelte';
	import { aboutirGeste, ouvrirGeste } from '#lib/aboutissement.ts';
	import AvertissementUrgence from '#lib/components/AvertissementUrgence.svelte';
	import { OPTIONS_FILTRE_NATURE, statutsPresents } from '#lib/tickets.ts';
	import { estArchive, filtrerAffaires, rechercheAffaires } from '#lib/recherche-affaires.ts';
	import { offrirLaPastille, selonPortee } from '#lib/me-concerne.ts';

	$: _pc = getPageConfig($configStore, 'mes-demandes', defautsDePage('mes-demandes'));
	$: _siteNom = $siteNomStore;

	const ticketList = writable<Ticket[]>([]);
	let loading = true;
	/** Message d'une panne de chargement, ou vide (#796). */
	let erreur = '';
	let filterStatut = '';
	//  La recherche libre a remplacé le filtre Catégorie (27/09/2026) : la
	//  règle est au serveur, `#lib/recherche-affaires` demande et filtre.
	let recherche = '';
	let inclureArchives = false;
	const moteur = rechercheAffaires();
	$: moteur.chercher(recherche);
	//  Actualité · Calendrier · Activité (#1092) — `?nature=` le pose depuis un
	//  lien, notamment les anciennes adresses `/actualites` et `/calendrier`.
	let filterNature = '';

	// Création : boîte dans la page, comme partout ailleurs sur le site (#367).
	// Ce fut le dernier écran à créer un objet par page dédiée — cf. l'en-tête de
	// FormulaireTicket.svelte.
	//  UN bouton, UN formulaire (23/09/2026) : « Actualité » y est la première
	//  catégorie, et c'est elle qui allume ce qu'une actualité a de propre.
	export let data: { onglet: string };
	$: onglet = data.onglet;
	//  L'onglet Archives n'a qu'un contenu : il l'ouvre (#1092).
	$: if (onglet === 'archives') historyExpanded = true;

	let showForm = false;
	//  La catégorie qu'un lien demande (`?categorie=`, #2075) — un bogue depuis l'avis.
	let categorieInitiale = '';
	$: if (showForm) ouvrirGeste('affaire.creer'); //  Le geste mesuré (#1633).

	function ticketCree(e: CustomEvent<Ticket>) {
		aboutirGeste('affaire.creer');
		$ticketList = [e.detail, ...$ticketList];
		showForm = false;
	}

	//  Ce que la page décide pour ses cartes — laquelle est dépliée, en
	//  correction, en attente d'une Suite — et les appels de chaque geste vivent
	//  dans `#lib/affaires-en-liste`, que le lien direct d'une affaire emploie
	//  aussi (15/10/2026). Le rendu vit dans `ListeTickets` → `CarteTicket`.
	const affaires = affairesEnListe(ticketList);
	const { etat: etatAffaires, gestes } = affaires;
	//  Les DEUX listes — actives et archives — reçoivent le même état : écrit une
	//  fois, il ne peut pas diverger de l'une à l'autre.
	$: etatListe = { ...$etatAffaires, peutAdministrer: $isAdmin };

	//  Badges, libellés, options du workflow ET catégories viennent de
	//  `#lib/tickets` : quatre listes de statuts avaient divergé (#415), et les
	//  catégories étaient à leur tour écrites en quatre endroits — dont ces six
	//  boutons de filtre, en dur dans le balisage (#431).

	//  « Ce qui me concerne » (#2215) : offerte s'il y a de quoi filtrer.
	let offrirMeConcerne = false;
	let portee = '';
	onMount(async () => {
		offrirMeConcerne = await offrirLaPastille();
	});

	onMount(async () => {
		try {
			$ticketList = await ticketsApi.list();
			const params = new URLSearchParams(window.location.search);
			// `?nouveau=1` ouvre directement la boîte de création. C'est ce qui
			// remplace l'ancienne page `/tickets/nouveau` : les liens qui menaient
			// à un écran de saisie doivent continuer à y mener, pas atterrir sur la
			// liste en laissant l'utilisateur chercher le bouton.
			if (params.get('nouveau')) {
				showForm = true;
				categorieInitiale = categorieDuLien(params);
			}
			filterNature = OPTIONS_FILTRE_NATURE.some((o) => o.val === params.get('nature'))
				? (params.get('nature') ?? '')
				: '';
			// Auto-ouverture depuis ?open=TK-XXXXX (lien profond depuis le tableau de bord)
			const openNum = params.get('open');
			if (openNum) {
				const target = $ticketList.find((t) => t.numero === openNum);
				if (target) {
					if (estArchive(target)) {
						historyExpanded = true;
						//  Une affaire archivée se montre dans SON onglet (#1092).
						if (onglet !== 'archives')
							await goto(routeOnglet('mes-demandes', 'archives') + location.search, {
								replaceState: true,
							});
						//  On DÉSIGNE l'année ; le composant l'ouvre. Cette page posait
						//  auparavant l'état interne du groupement, ce qui l'obligeait
						//  à en porter sa propre copie.
						anneeVisee = new Date(target.mis_a_jour_le ?? target.cree_le).getFullYear();
					}
					await affaires.deplier(target);
					revelerCible(`ticket-${target.id}`);
				}
			}
		} catch (e) {
			//  🔴 AUCUN `catch` ici jusqu'au 06/09/2026 : une panne de chargement
			//  affichait « Aucune demande » — annoncer une absence qu'on n'a pas constatée,
			//  c'est le défaut #519, corrigé sur les annonces et jamais ici (#796).
			erreur = messageErreur(e, 'Erreur de chargement');
		} finally {
			loading = false;
			marquerDonneesAffichees();
		}
	});

	//  La règle d'archivage n'est PAS ici : `estArchive` lit le champ calculé par
	//  le serveur (#515) — `#lib/recherche-affaires`, avec le filtre de la liste.

	//  Ce que la liste principale peut montrer, AVANT le filtre d'état : c'est
	//  cet ensemble-là qui donne les boutons du filtre. Le calculer après
	//  n'en laisserait qu'un seul, celui qu'on vient de choisir.
	$: affichables = $ticketList.filter((t) => !estArchive(t));
	$: optionsStatut = statutsPresents(affichables);
	//  ⚠️ Un filtre retenu sur un état qui vient de disparaître de la liste — le
	//  dernier ticket résolu bascule dans l'Historique — laisserait un écran vide
	//  ET plus aucun bouton pour en sortir. On retombe alors sur « Tous ».
	$: if (filterStatut && !optionsStatut.some((o) => o.value === filterStatut)) filterStatut = '';

	$: filtered = selonPortee(
		filtrerAffaires($ticketList, {
			resultats: $moteur.resultats,
			inclureArchives,
			statut: filterStatut,
			nature: filterNature,
			optionsStatut,
		}),
		portee,
	);
	$: correspondances = new Map(($moteur.resultats ?? []).map((r) => [r.ticket_id, r]));

	// Historique : tickets clôturés depuis plus de 7 jours, limité à 3 ans, groupés par année décroissante
	const THREE_YEARS_AGO = new Date();
	THREE_YEARS_AGO.setFullYear(THREE_YEARS_AGO.getFullYear() - 3);

	$: historyTickets = $ticketList
		.filter((t) => estArchive(t) && new Date(t.mis_a_jour_le ?? t.cree_le) >= THREE_YEARS_AGO)
		.sort(
			(a, b) =>
				new Date(b.mis_a_jour_le ?? b.cree_le).getTime() -
				new Date(a.mis_a_jour_le ?? a.cree_le).getTime(),
		);

	//  ⚠️ Le groupement par année vivait ici — troisième copie du même bloc,
	//  avec l'Espace CS et `ArchivesParAnnee` lui-même. Il est parti dans le
	//  composant ; ce qui reste est le FILTRE, propre à cet écran.
	let historyExpanded = false;
	/**  L'année à ouvrir, désignée par un lien profond `?open=TK-…`. C'est la
	 *   SEULE chose que cette page ait besoin de dire au groupement — et la
	 *   capacité qui lui manquait pour adopter le composant (#516). */
	let anneeVisee: number | null = null;
</script>

<svelte:head><title>{_pc.titre} — {_siteNom}</title></svelte:head>

<EntetePage
	titre={_pc.titre}
	descriptif={_pc.descriptif}
	icone={_pc.icone || 'message-square-text'}
>
	<!--  L'en-tête n'OUVRE que le formulaire : l'annulation vit à côté
	      d'« Enregistrer », dans le formulaire (18/08/2026). Le bouton s'efface
	      pendant la saisie — le laisser en « ✕ Annuler » ferait deux commandes
	      d'annulation pour un seul formulaire (#367).

	      🔴 La règle est PORTÉE par `BoutonNouveau` depuis le 12/09/2026. Elle
	      était écrite ici, dans `actualites` et dans le composant — et le
	      composant, seul, portait encore la version du 16/08 qu'elle remplace.
	      Trois écritures, dont une périmée : c'est ce qui a laissé Prestataires
	      afficher « ✕ Annuler » jusqu'à ce que l'utilisateur le signale. -->
	<BoutonNouveau
		ouvert={showForm}
		libelle={TICKET.libelleNouveau}
		on:basculer={() => (showForm = true)}
	/>
</EntetePage>

<!--  Liste · Kanban · Archives (#1092) — masquage et refus d'une route réservée :
      `BarreOnglets`, d'après `pages.ts`. -->
<BarreOnglets pageId="mes-demandes" actif={onglet} />

<AvertissementUrgence />

{#if onglet === 'liste'}
	<!--  Nature · Suivi · Catégorie : la barre et sa mise en page vivent dans
      `FiltresAffaires` ; la page ne garde que les valeurs retenues. -->
	<FiltresAffaires
		{optionsStatut}
		bind:nature={filterNature}
		bind:statut={filterStatut}
		bind:recherche
		bind:inclureArchives
		etat={$moteur}
		tickets={$ticketList}
		affichees={filtered.length}
		{offrirMeConcerne}
		bind:portee
	/>
{/if}

<!--  Le formulaire s'ouvre APRÈS l'avertissement et les filtres : `ux-patterns`
      §0 ter, signalé ici le 12/09/2026. -->
{#if showForm}
	<ChargementDiffere charger={() => import('#lib/components/FormulaireTicket.svelte')}>
		{#snippet contenu(FormulaireTicket)}
			<FormulaireTicket
				cle="creation"
				{categorieInitiale}
				on:cree={ticketCree}
				on:annule={() => (showForm = false)}
			/>
		{/snippet}
	</ChargementDiffere>
{/if}

<!--  Les trois états par `EtatListe` (#796) — dont l'ERREUR, qui n'existait pas :
      une panne affichait « Aucune demande ». -->
{#if onglet === 'kanban'}
	<ChargementDiffere charger={() => import('#lib/components/VueKanbanAffaires.svelte')}>
		{#snippet contenu(VueKanbanAffaires)}
			<VueKanbanAffaires
				tickets={$ticketList}
				peutDeplacer={$isCS}
				on:cree={async () => ($ticketList = await ticketsApi.list())}
				on:deplace={(e) =>
					($ticketList = $ticketList.map((x) =>
						x.id === e.detail.id ? { ...x, statut: e.detail.statut } : x,
					))}
			/>
		{/snippet}
	</ChargementDiffere>
{:else if onglet === 'liste'}
	<EtatListe
		chargement={loading}
		{erreur}
		vide={filtered.length === 0}
		titreErreur="Impossible d'afficher les demandes"
		titreVide={$moteur.terme ? 'Aucune affaire trouvée' : 'Aucune demande'}
		messageVide={$moteur.terme
			? 'Essayez un autre mot, ou incluez les Archives.'
			: 'Signalez un problème ou posez une question au conseil syndical.'}
	>
		<ListeTickets tickets={filtered} {correspondances} {...etatListe} {gestes} />
	</EtatListe>
{/if}

<!--  Section ARCHIVES — les tickets clos depuis plus du délai de grâce.
      ⚠️ Elle s'appelait « Historique », et ce mot est réservé au FIL d'évolutions
      d'un objet (cadre #430). Les deux acceptions coexistaient ici même, sur le
      même écran : le fil d'un ticket et l'archive de la liste. Départagé le
      20/08/2026 (#516).

      Bandeau et groupement par année : `ArchivesParAnnee`, qui ouvre aussi
      l'année désignée par un lien profond (`anneeVisee`). -->
{#if onglet === 'archives'}
	<EtatListe
		chargement={loading}
		{erreur}
		vide={historyTickets.length === 0}
		titreErreur="Impossible d'afficher les archives"
		titreVide="Aucune archive"
		messageVide="Les affaires closes et les actualités passées rejoignent cet onglet."
	>
		<ArchivesParAnnee
			items={historyTickets}
			dateDe={(t) => t.mis_a_jour_le ?? t.cree_le}
			compte={historyTickets.length}
			charge
			anneeOuverte={anneeVisee}
			bind:ouvert={historyExpanded}
			let:objet={ticketArchive}
		>
			<ListeTickets tickets={[ticketArchive]} archive {...etatListe} {gestes} />
		</ArchivesParAnnee>
	</EtatListe>
{/if}
