<script lang="ts">
	import ChargementDiffere from '$lib/components/ChargementDiffere.svelte';
	import EntetePage from '$lib/components/EntetePage.svelte';
	import BoutonNouveau from '$lib/components/BoutonNouveau.svelte';
	import FiltresAffaires from '$lib/components/FiltresAffaires.svelte';
	import EtatListe from '$lib/components/EtatListe.svelte';
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import BarreOnglets from '$lib/components/BarreOnglets.svelte';
	import VueKanbanAffaires from '$lib/components/VueKanbanAffaires.svelte';
	import { routeOnglet } from '$lib/routes-onglets';
	import { revelerCible } from '$lib/deepLink';
	import { isAdmin, isCS } from '$lib/stores/auth';
	import { tickets as ticketsApi, type Ticket, type TicketEvolution } from '$lib/api';
	import { messageErreur } from '$lib/erreurs';
	import { optionsRapides } from '$lib/options-rapides';
	import { ARCHIVAGE, SUPPRESSION, confirmerPuis } from '$lib/confirmation';
	import type { GestesTicket } from '$lib/tickets';
	import { TICKET } from '$lib/entites/ticket';
	import { getPageConfig, configStore, siteNomStore, defautsDePage } from '$lib/stores/pageConfig';
	import { toast } from '$lib/components/Toast.svelte';
	import ListeTickets from '$lib/components/ListeTickets.svelte';
	import ArchivesParAnnee from '$lib/components/ArchivesParAnnee.svelte';
	import { chargeCorrection, type ChargeUtileEvolution } from '$lib/evolutions';
	import { aboutirGeste, ouvrirGeste } from '$lib/aboutissement';
	import AvertissementUrgence from '$lib/components/AvertissementUrgence.svelte';
	import { OPTIONS_FILTRE_NATURE, estActualite, statutsPresents } from '$lib/tickets';
	import { estArchive, filtrerAffaires, rechercheAffaires } from '$lib/recherche-affaires';

	$: _pc = getPageConfig($configStore, 'mes-demandes', defautsDePage('mes-demandes'));
	$: _siteNom = $siteNomStore;

	let ticketList: Ticket[] = [];
	let loading = true;
	/** Message d'une panne de chargement, ou vide (#796). */
	let erreur = '';
	let filterStatut = '';
	//  La recherche libre a remplacé le filtre Catégorie (27/09/2026) : la
	//  règle est au serveur, `$lib/recherche-affaires` demande et filtre.
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
	$: if (showForm) ouvrirGeste('affaire.creer'); //  Le geste mesuré (#1633).

	function ticketCree(e: CustomEvent<Ticket>) {
		aboutirGeste('affaire.creer');
		ticketList = [e.detail, ...ticketList];
		showForm = false;
	}

	//  Ce que la page décide, et qu'elle est seule à savoir : quel ticket est
	//  déplié, lequel est ouvert en correction, lequel attend une entrée
	//  d'Historique. Le rendu, lui, vit dans `ListeTickets` → `CarteTicket`, et
	//  l'affichage suit la déclaration `TICKET` (`$lib/entites/ticket`).
	let expandedTickets = new Set<number>();
	// Évolutions par ticket (chargées à la demande)
	let evolsMap: Record<number, TicketEvolution[]> = {};
	let evolsLoaded = new Set<number>();
	let evolsErreurs: Record<number, string> = {};
	let showEvolForm: number | null = null;
	let editingTicket: number | null = null;
	let evolSaving = false;

	//  Badges, libellés, options du workflow ET catégories viennent de
	//  `$lib/tickets` : quatre listes de statuts avaient divergé (#415), et les
	//  catégories étaient à leur tour écrites en quatre endroits — dont ces six
	//  boutons de filtre, en dur dans le balisage (#431).

	onMount(async () => {
		try {
			ticketList = await ticketsApi.list();
			const params = new URLSearchParams(window.location.search);
			// `?nouveau=1` ouvre directement la boîte de création. C'est ce qui
			// remplace l'ancienne page `/tickets/nouveau` : les liens qui menaient
			// à un écran de saisie doivent continuer à y mener, pas atterrir sur la
			// liste en laissant l'utilisateur chercher le bouton.
			if (params.get('nouveau')) showForm = true;
			filterNature = OPTIONS_FILTRE_NATURE.some((o) => o.val === params.get('nature'))
				? (params.get('nature') ?? '')
				: '';
			// Auto-ouverture depuis ?open=TK-XXXXX (lien profond depuis le tableau de bord)
			const openNum = params.get('open');
			if (openNum) {
				const target = ticketList.find((t) => t.numero === openNum);
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
					await toggleTicket(target);
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
		}
	});

	//  La règle d'archivage n'est PAS ici : `estArchive` lit le champ calculé par
	//  le serveur (#515) — `$lib/recherche-affaires`, avec le filtre de la liste.

	//  Ce que la liste principale peut montrer, AVANT le filtre d'état : c'est
	//  cet ensemble-là qui donne les boutons du filtre. Le calculer après
	//  n'en laisserait qu'un seul, celui qu'on vient de choisir.
	$: affichables = ticketList.filter((t) => !estArchive(t));
	$: optionsStatut = statutsPresents(affichables);
	//  ⚠️ Un filtre retenu sur un état qui vient de disparaître de la liste — le
	//  dernier ticket résolu bascule dans l'Historique — laisserait un écran vide
	//  ET plus aucun bouton pour en sortir. On retombe alors sur « Tous ».
	$: if (filterStatut && !optionsStatut.some((o) => o.value === filterStatut)) filterStatut = '';

	$: filtered = filtrerAffaires(ticketList, {
		resultats: $moteur.resultats,
		inclureArchives,
		statut: filterStatut,
		nature: filterNature,
		optionsStatut,
	});
	$: correspondances = new Map(($moteur.resultats ?? []).map((r) => [r.ticket_id, r]));

	// Historique : tickets clôturés depuis plus de 7 jours, limité à 3 ans, groupés par année décroissante
	const THREE_YEARS_AGO = new Date();
	THREE_YEARS_AGO.setFullYear(THREE_YEARS_AGO.getFullYear() - 3);

	$: historyTickets = ticketList
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

	async function toggleTicket(t: Ticket) {
		if (expandedTickets.has(t.id)) {
			expandedTickets.delete(t.id);
			expandedTickets = new Set(expandedTickets);
			fermerFormulaires();
		} else {
			expandedTickets = new Set([t.id]);
			fermerFormulaires();
			if (!evolsLoaded.has(t.id)) await loadEvolutions(t.id);
		}
	}

	function fermerFormulaires() {
		showEvolForm = null;
		editingTicket = null;
	}

	async function loadEvolutions(id: number) {
		try {
			evolsMap[id] = await ticketsApi.evolutions(id);
			evolsLoaded = new Set([...evolsLoaded, id]);
			evolsMap = { ...evolsMap };
			evolsErreurs = { ...evolsErreurs, [id]: '' };
		} catch (e) {
			//  Dit, jamais avalé (29/09/2026) : avalé, un 403 rendait un fil VIDE (TK-124285).
			evolsErreurs = { ...evolsErreurs, [id]: messageErreur(e) };
		}
	}

	//  Ouvrir un formulaire déplie sa carte et referme l'autre : deux formulaires
	//  ouverts sur le même écran, c'est deux « Enregistrer » pour deux gestes
	//  différents à quelques centimètres.
	//  UN point d'entrée (#426) : le formulaire porte les DEUX gestes, et lequel a
	//  été fait se lit dans les pastilles — celle de l'état courant est active, la
	//  laisser telle quelle ne change rien.
	function openEvolForm(t: Ticket) {
		editingTicket = null;
		showEvolForm = t.id;
		expandedTickets = new Set([t.id]);
	}

	function openEditForm(t: Ticket) {
		showEvolForm = null;
		options.fermer();
		editingTicket = t.id;
		expandedTickets = new Set([t.id]);
	}

	//  ── Options rapides (12/09/2026) ────────────────────────────────────────
	//  Le crayon ouvre les huit sections ; dépingler n'en touche qu'une. L'état et
	//  le geste viennent de `$lib/options-rapides` — trois pages les répétaient.
	const options = optionsRapides<Ticket>();
	const { ouvertId: optionsTicketId, enCours: optionsTicketEnCours } = options;

	function openOptions(t: Ticket) {
		showEvolForm = null;
		editingTicket = null;
		options.ouvrir(t);
		expandedTickets = new Set([t.id]);
	}

	const enregistrerOptionsTicket = (t: Ticket, data: unknown) =>
		options.enregistrer(
			() => ticketsApi.update(t.id, data),
			(maj) => (ticketList = ticketList.map((x) => (x.id === maj.id ? { ...x, ...maj } : x))),
		);

	//  🔴 ÉCRIT UNE FOIS, passé aux DEUX listes — les tickets actifs et les
	//  archives. Les treize gestes et les huit états y étaient recopiés, et
	//  l'ajout du panneau d'options en aurait fait vingt-six lignes de plus, sur
	//  deux écritures libres de diverger (`ListeTickets` le prévenait lui-même).
	$: etatListe = {
		expandedIds: expandedTickets,
		evolsMap,
		evolsErreurs,
		ticketEnEdition: editingTicket,
		ticketEnOptions: $optionsTicketId,
		optionsRapidesEnCours: $optionsTicketEnCours,
		ticketEnEvolution: showEvolForm,
		evolutionEnCours: evolSaving,
		evolEnEdition,
		evolCorrectionEnCours,
		peutAdministrer: $isAdmin,
	};
	const gestes: GestesTicket = {
		basculer: toggleTicket,
		evoluerOuvrir: openEvolForm,
		modifier: openEditForm,
		optionsOuvrir: openOptions,
		optionsEnregistrer: enregistrerOptionsTicket,
		supprimer: deleteTicket,
		archiver: archiverTicket,
		evoluer: addEvolution,
		evolModifier: (id) => (evolEnEdition = id),
		evolCorriger: corrigerEvolution,
		evolSupprimer: supprimerEvolution,
		evolAnnuler: () => (evolEnEdition = null),
		modifie: ticketModifie,
		annuler: fermerFormulaires,
		filChange: (t) =>
			ticketsApi.get(t.id).then(ticketModifie, (e) => toast('error', messageErreur(e))),
	};

	//  🔴 Ce type était RÉÉCRIT ici, et il lui manquait `perimetre_cible` — alors
	//  que son commentaire affirmait « même contrat que la fiche détail ». Deux
	//  contrats d'accord sur le papier et divergents dans les faits : c'est le
	//  défaut de #415 (statuts) et #413 (champs), sur un troisième objet (#529).
	//  Il vit désormais dans `$lib/evolutions`, avec le reste du vocabulaire.

	//  ── Correction d'une entrée du fil ──────────────────────────────────────
	//  Le crayon existait dans `RubriqueHistorique` depuis #431 et servait la
	//  FICHE d'un ticket ; la liste ne le branchait pas. Même entité, deux
	//  rendus, une capacité sur deux — signalé à l'écran le 18/08/2026.
	let evolEnEdition: number | null = null;
	let evolCorrectionEnCours = false;

	//  🔴 Effacer une entrée du fil — ADMIN seulement, et le serveur le revérifie
	//  (`require_admin`). Une transition d'état est refusée côté serveur (422) et
	//  n'affiche pas de corbeille côté écran : l'écran dit la même chose que le
	//  serveur, ni plus ni moins.
	//
	//  ⚠️ Pas de confirmation : le geste est réservé à l'admin, porte une corbeille
	//  explicite, et le fil se recharge aussitôt — l'effet est immédiatement
	//  visible. Une modale de plus sur un geste déjà restreint et déjà rare
	//  ajouterait un clic sans ajouter de sécurité.
	async function supprimerEvolution({ ticket: t, evolId }: { ticket: Ticket; evolId: number }) {
		try {
			await ticketsApi.deleteEvolution(t.id, evolId);
			await loadEvolutions(t.id);
			toast('success', 'Entrée supprimée');
		} catch (e2) {
			toast('error', messageErreur(e2));
		}
	}

	async function corrigerEvolution(t: Ticket, brut: unknown) {
		if (evolEnEdition === null) return;
		evolCorrectionEnCours = true;
		try {
			//  🔄 TOUTES les sections d'une Suite se corrigent, Suivi compris
			//  (01/10/2026) : la charge vient de `chargeCorrection`, la même que la
			//  fiche. Ce relais énumérait quatre champs — chaque section ajoutée au
			//  formulaire y aurait été perdue en silence (#529).
			await ticketsApi.updateEvolution(
				t.id,
				evolEnEdition,
				chargeCorrection(brut as ChargeUtileEvolution),
			);
			await loadEvolutions(t.id);
			evolEnEdition = null;
			toast('success', 'Entrée corrigée');
		} catch (e2) {
			toast('error', messageErreur(e2));
		} finally {
			evolCorrectionEnCours = false;
		}
	}

	async function addEvolution(t: Ticket, brut: unknown) {
		const data = brut as ChargeUtileEvolution;
		evolSaving = true;
		try {
			//  🔴 La charge utile ENTIÈRE, comme la fiche (`HistoriqueTicket`). Ce
			//  relais énumérait ses champs, et jetait donc ce qu'il ne nommait pas :
			//  le périmètre resserré jusqu'au 20/08 (#529), puis les options, puis
			//  les destinataires d'une actualité (#1091). Plus rien à oublier.
			await ticketsApi.addEvolution(t.id, { ...data, contenu: data.contenu || undefined });
			if (data.type === 'etat') {
				ticketList = ticketList.map((x) =>
					x.id === t.id ? { ...x, statut: data.nouveau_statut ?? x.statut } : x,
				);
			}
			await loadEvolutions(t.id);
			showEvolForm = null;
			toast('success', data.type === 'etat' ? 'Statut mis à jour' : 'Commentaire ajouté');
		} catch (e2) {
			toast('error', messageErreur(e2));
		} finally {
			evolSaving = false;
		}
	}

	//  Une actualité n'affiche pas de numéro : on la nomme par son titre.
	const designation = (t: Ticket) =>
		estActualite(t) ? `L'actualité « ${t.titre} »` : `L'affaire ${t.numero}`;

	//  📦 Archiver, et non supprimer, depuis la liste (24/09/2026, `ux-patterns`
	//  §8) : le 🗑️ y effaçait une actualité entière, sans retour possible.
	async function archiverTicket(t: Ticket) {
		await confirmerPuis(ARCHIVAGE(designation(t)), 'Archivée', async () => {
			const maj = await ticketsApi.update(t.id, { archive_manuel: true });
			ticketList = ticketList.map((x) => (x.id === t.id ? { ...x, ...maj } : x));
		});
	}

	async function deleteTicket(t: Ticket) {
		await confirmerPuis(SUPPRESSION(designation(t)), 'Suppression effectuée', async () => {
			await ticketsApi.delete(t.id);
			ticketList = ticketList.filter((x) => x.id !== t.id);
		});
	}

	//  Le PATCH inscrit une CORRECTION dans le fil (« Correction : État … ») :
	//  sans ce rechargement, la carte affiche le ticket corrigé au-dessus d'un
	//  historique qui n'en dit rien.
	async function ticketModifie(maj: Ticket) {
		ticketList = ticketList.map((x) => (x.id === maj.id ? { ...x, ...maj } : x));
		await loadEvolutions(maj.id);
		editingTicket = null;
	}
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
		tickets={ticketList}
		affichees={filtered.length}
	/>
{/if}

<!--  Le formulaire s'ouvre APRÈS l'avertissement et les filtres : `ux-patterns`
      §0 ter, signalé ici le 12/09/2026. -->
{#if showForm}
	<ChargementDiffere charger={() => import('$lib/components/FormulaireTicket.svelte')}>
		{#snippet contenu(FormulaireTicket)}
			<FormulaireTicket cle="creation" on:cree={ticketCree} on:annule={() => (showForm = false)} />
		{/snippet}
	</ChargementDiffere>
{/if}

<!--  Les trois états par `EtatListe` (#796) — dont l'ERREUR, qui n'existait pas :
      une panne affichait « Aucune demande ». -->
{#if onglet === 'kanban'}
	<VueKanbanAffaires
		tickets={ticketList}
		peutDeplacer={$isCS}
		on:cree={async () => (ticketList = await ticketsApi.list())}
		on:deplace={(e) =>
			(ticketList = ticketList.map((x) =>
				x.id === e.detail.id ? { ...x, statut: e.detail.statut } : x,
			))}
	/>
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
