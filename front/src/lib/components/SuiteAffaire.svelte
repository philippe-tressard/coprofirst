<!--
  SuiteAffaire.svelte — la Suite 🔄 d'une affaire, et sa CORRECTION ✏️.

  ## Pourquoi un composant (01/10/2026)

  Demandé à l'écran : *« l'édition d'une suite doit permettre de modifier tous
  les sections éditables et surtout le suivi »*. La correction montait un
  `EvolForm` nu — ni Suivi, ni Équipement, ni Quand, ni Intervenant, ni
  Destinataires, ni Mise en avant — pendant que la Suite les rendait tous. Et
  chaque formulaire était monté DEUX fois, par la fiche (`HistoriqueTicket`) et
  par la liste (`CarteTicket`) : quatre montages, dont deux avaient déjà divergé
  (l'adresse externe n'était offerte que sur la fiche).

  Un seul montage désormais, pour les deux gestes et les trois cartes — fiche,
  liste, actualité (une actualité EST une affaire, #1091 : elle n'a ni Suivi ni
  aperçu, et sa Diffusion part par son module). Tout se
  DÉRIVE de l'affaire — l'hôte ne passe que ce qu'elle ne dit pas : l'entrée
  corrigée, le fil, le droit de suivre, l'attente du serveur.

  ## Ce que la correction garde de la Suite, et ce qu'elle n'a pas

  Toutes les sections, à leur rang, préremplies : l'entrée pour ce qu'elle porte
  (texte, pièces, périmètre, état), l'affaire pour le reste. Le Suivi part de
  l'état que la Suite avait enregistré ; revenir à l'état d'avant
  (`statut_avant`, calculé par le serveur) en refait un commentaire. Arbitré le
  01/10/2026 : **pas de Diffusion** — la Suite est déjà partie, et un
  destinataire ne reçoit jamais deux courriels pour un même fait.

  Événements : `submit` — la charge ENTIÈRE (`ChargeUtileEvolution`), options et
  planification comprises ; l'hôte la relaie (`chargeCorrection` pour un PATCH).
-->
<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import EvolForm from './EvolForm.svelte';
	import SectionsSuiteConseil from './SectionsSuiteConseil.svelte';
	import SuiteConseilEquipement from './SuiteConseilEquipement.svelte';
	import OptionsEvolutionTicket from './OptionsEvolutionTicket.svelte';
	import { tickets as ticketsApi, type Ticket, type TicketEvolution } from '$lib/api';
	import { contexteCommentaire } from '$lib/assistant';
	import { TICKET } from '$lib/entites/ticket';
	import type { ChargeUtileEvolution, EntreeCorrigee } from '$lib/evolutions';
	import { fichiersDepuisUrls } from '$lib/fichiers';
	import { conditionsDeLaSuite } from '$lib/formulaire-affaire';
	import { SUITE } from '$lib/gestes';
	import { destinatairesParDefautDuTicket, ticketLuDuSeulConseil } from '$lib/lecture-ticket';
	import { motifWhatsappInterdit } from '$lib/options-publication';
	import { reserveAuConseil } from '$lib/destinataires';
	import { nomCopie } from '$lib/saisi-pour';
	import { isCS } from '$lib/stores/auth';
	import { equipementDansLaSuite } from '$lib/suite-conseil';
	import { demanderFusion, SANS_FUSION } from '$lib/fusion-affaires';
	import {
		STATUT_TICKET_LABELS,
		estActualite,
		optionsDuTicket,
		optionsVersTicket,
	} from '$lib/tickets';
	import { etatDeLaSuite, etatsDeLaSuite } from '$lib/suivi-actualite';

	export let ticket: Ticket;
	/** L'entrée CORRIGÉE — `null` pour une Suite neuve. */
	export let evol: EntreeCorrigee | null = null;
	/** Le fil : il donne le périmètre dont une Suite neuve hérite. */
	export let entrees: TicketEvolution[] = [];
	/** Préciser le périmètre change qui verra l'affaire : un droit, calculé par l'hôte. */
	export let peutSuivre = false;
	export let saving = false;

	const dispatch = createEventDispatcher<{ submit: ChargeUtileEvolution; cancel: void }>();

	//  Une COPIE de l'état de l'affaire, reprise à chaque montage — l'hôte monte
	//  ce composant à l'ouverture : un formulaire abandonné ne laisse rien.
	let options = optionsDuTicket(ticket);

	$: correction = evol !== null;
	//  Ce qui distingue l'actualité, écrit ICI et nulle part ailleurs : pas de
	//  cycle, pas d'aperçu (son module compose son message), ses canaux par défaut,
	//  et le groupe fermé quand elle ne parle qu'au conseil. Son SUIVI, optionnel
	//  (10/10/2026), s'avance ici comme celui d'une affaire : `$lib/suivi-actualite`.
	$: actu = estActualite(ticket);
	$: etatCourant = etatDeLaSuite(ticket);
	$: whatsappInterdit = actu
		? motifWhatsappInterdit(reserveAuConseil(ticket.public_cible), 'actualité')
		: motifWhatsappInterdit(ticketLuDuSeulConseil(ticket), 'ticket');

	const apercu = (saisie: {
		contenu: string;
		fichiers_urls: string[];
		whatsapp: boolean;
		syndic: boolean;
		cs: boolean;
	}) =>
		ticketsApi.apercuDiffusion({
			ticket_id: ticket.id,
			commentaire: saisie.contenu,
			fichiers_urls: saisie.fichiers_urls,
			destinataire_syndic: saisie.syndic,
			destinataire_cs: saisie.cs,
			partager_whatsapp: saisie.whatsapp,
		});

	//  🔀 Une Suite qui CLÔT demande s'il faut absorber les affaires liées encore
	//  ouvertes (#1704) — jamais une correction : la clôture a déjà eu lieu.
	async function soumettre(charge: ChargeUtileEvolution) {
		//  Une actualité ne fusionne pas : son suivi est un repère, pas une clôture.
		const demande =
			correction || actu ? SANS_FUSION : await demanderFusion(ticket, charge.nouveau_statut);
		if (demande === null) return;
		dispatch('submit', demande.fusionner.length ? { ...charge, ...demande } : charge);
	}
</script>

<EvolForm
	idPrefixe={evol ? `tk-evol-edit-${evol.id}` : `tk-evol-${ticket.id}`}
	auteurNom={nomCopie(ticket)}
	titre={correction ? SUITE.libelleModifier : SUITE.libelle}
	editMode={correction}
	initialContenu={evol?.contenu ?? ''}
	initialFichiers={fichiersDepuisUrls(evol?.fichiers_urls)}
	initialPerimetre={evol?.perimetre_cible ?? []}
	demanderApercu={correction || actu ? null : apercu}
	statutOptions={etatsDeLaSuite(ticket, $isCS)}
	statutLabels={STATUT_TICKET_LABELS}
	currentStatut={evol ? (evol.statut_avant ?? etatCourant) : etatCourant}
	initialStatut={evol?.type === 'etat' ? (evol.nouveau_statut ?? '') : ''}
	entite={TICKET}
	affaireLiable={$isCS ? ticket.id : null}
	initialDestinataires={ticket.public_cible ?? []}
	destinatairesParDefaut={actu ? null : destinatairesParDefautDuTicket(ticket)}
	defaultEnvoyerSyndic={actu && (ticket.destinataire_syndic ?? false)}
	defaultEnvoyerCs={actu && (ticket.destinataire_cs ?? false)}
	bind:confidentiel={options.brouillon}
	conditions={conditionsDeLaSuite(ticket)}
	assistant={actu
		? contexteCommentaire(ticket)
		: contexteCommentaire(ticket, STATUT_TICKET_LABELS[ticket.statut] ?? ticket.statut)}
	peutPreciserPerimetre={peutSuivre}
	perimetreCourant={ticket.perimetre_cible ?? []}
	aidePerimetre={actu
		? "Le périmètre en vigueur est repris tel quel : le corriger ici corrige l'actualité entière."
		: ''}
	{entrees}
	{whatsappInterdit}
	peutDiffuser={$isCS}
	peutCibler={$isCS}
	showEmail={$isCS && !correction}
	{saving}
	avantSuivi={equipementDansLaSuite(ticket, $isCS)}
	on:submit={(e) => soumettre({ ...e.detail, ...optionsVersTicket(options) })}
	on:cancel={() => dispatch('cancel')}
>
	<!--  Chaque section à son rang (#1326) : Équipement, puis Quand et
	      Intervenant, puis la Mise en avant. -->
	<svelte:fragment slot="avant_suivi" let:partage>
		<SuiteConseilEquipement {ticket} {partage} />
	</svelte:fragment>
	<svelte:fragment slot="specifiques" let:premiere let:partage>
		<SectionsSuiteConseil {ticket} {premiere} {partage} bind:options />
	</svelte:fragment>
	<svelte:fragment slot="mise_en_avant">
		<OptionsEvolutionTicket bind:options />
	</svelte:fragment>
</EvolForm>
