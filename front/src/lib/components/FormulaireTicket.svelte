<!--
  Le formulaire d'une AFFAIRE — actualités comprises —, celui qu'on remplit pour
  la CRÉER et celui qu'on rouvre pour la MODIFIER. Un seul fichier, deux gestes.

  ## 🔴 UN SEUL FORMULAIRE depuis le 23/09/2026 (arbitré à l'écran, maquette à l'appui)

  > « Sur la page, il y a deux nouveaux boutons : Affaires et Actualités. J'en veux
  >   qu'un seul “+ Nouvelle affaire” comprenant toutes les sections Affaires et
  >   Actualités, avec une nouvelle catégorie Actualité qui apparaît en premier.
  >   Selon le choix de la catégorie, les sections peuvent changer. Prévoir toutes
  >   les sections, grisées, pliées et inactives pour celles inappropriées. »

  `FormulaireActualite` a disparu dans celui-ci. « Actualité » est la première
  pastille de la catégorie (pleine ligne, puis un filet — variante A). La NATURE
  qu'elle décide — informer ou faire traiter — éteint des sections : Suivi,
  Équipement et Intervenant pour une actualité (Destinataires, éteinte pour une
  affaire, s'y rallume le 25/09/2026 : elle porte « Confidentielle »). Elles restent à leur rang, grisées, avec leur motif, et ce qu'elles
  portaient ne part pas. La règle vit dans `#lib/formulaire-affaire` (et le motif
  dans la déclaration `TICKET`), pas en `{#if}` ici : la même question se pose à
  l'affichage et à l'envoi.

  ## Pourquoi il sert aussi l'édition (17/08/2026, #425)

  « je préfère que tu rendes paramétrable avec les valeurs déjà saisies le formulaire
  d'édition plutôt que de le dupliquer » : la prop `ticket` (`null` = création, une
  affaire = correction). La catégorie s'y corrige aussi — c'est ainsi qu'une affaire
  devient une actualité ou l'inverse —, et ce qui s'efface est annoncé avant d'enregistrer.
  « Annuler » est À CÔTÉ d'« Enregistrer », dans les deux gestes (#367).

  ## Deux saisies, un formulaire (#2595)

  Essentielle ou Complète (`#lib/saisie-affaire`) : la première range les sections non
  essentielles dans « Plus de détails ».
-->
<script lang="ts">
	import { messageErreur } from '#lib/erreurs.ts';
	import { pourChampLocal } from '#lib/date.ts';
	import { contexteAssistant, perimetreContexte } from '#lib/assistant.ts';
	import { createEventDispatcher } from 'svelte';
	import { perimetreDefautListe } from '#lib/perimetres/index.ts';
	import {
		tickets as ticketsApi,
		admin as adminApi,
		prestataires as prestatairesApi,
		type Ticket,
	} from '#lib/api/index.ts';
	import type SectionDiffusion from '#lib/components/SectionDiffusion.svelte';
	import { toast } from '#lib/components/Toast.svelte';
	import CadreFormulaire from '#lib/components/CadreFormulaire.svelte';
	import SectionTitre from '#lib/components/SectionTitre.svelte';
	import SectionsSpecifiquesTicket from '#lib/components/SectionsSpecifiquesTicket.svelte';
	import SectionsEquipementSuiviTicket from '#lib/components/SectionsEquipementSuiviTicket.svelte';
	import PhraseModeSaisie from '#lib/components/PhraseModeSaisie.svelte';
	import { estEssentielle, repartition } from '#lib/saisie-affaire.ts';
	import ChampsCommuns from '#lib/components/ChampsCommuns.svelte';
	import DiffusionPublication from '#lib/components/DiffusionPublication.svelte';
	import RepriseAnnonceHall from '#lib/components/RepriseAnnonceHall.svelte';
	import { lueDuSeulConseil, natureLue } from '#lib/lecture-ticket.ts';
	import SectionAffairesLiees from '#lib/components/SectionAffairesLiees.svelte';
	import SectionIntervenant from '#lib/components/SectionIntervenant.svelte';
	import { contratDeLaSaisie, type ContratEnCours } from '#lib/prestataires.ts';
	import ChampFrequence from '#lib/components/ChampFrequence.svelte';
	import { essayer } from '#lib/chargement.ts';
	import { pliageDe } from '#lib/pliage.ts';
	import type { PrefillActualite } from '#lib/actualite-prefill.ts';
	import { currentUser, estModerateur, quandAuthResolue } from '#lib/stores/auth.ts';
	import {
		CATEGORIE_ACTUALITE,
		OPTIONS_CATEGORIE,
		optionsCategorie,
		OPTIONS_TICKET,
		STATUT_TICKET_LABELS,
		optionsDuTicket,
	} from '#lib/tickets.ts';
	import type { Etat } from '#lib/entites/types.ts';
	import { sectionPresente } from '#lib/entites/types.ts';
	import { TICKET } from '#lib/entites/ticket.ts';
	import { PUBLICATION } from '#lib/entites/publication.ts';
	import { motifWhatsappInterdit } from '#lib/options-publication.ts';
	import { confirmer } from '#lib/confirmation.ts';
	import { demanderFusion, SANS_FUSION } from '#lib/fusion-affaires.ts';
	import {
		CATEGORIE_ENTRETIEN,
		chargeUtileAffaire,
		intervenantPropose,
		natureDe,
		alerteCorrection,
		sectionsInactives,
		chargeApercu,
		erreurDeSaisie,
		type SaisieAffaire,
	} from '#lib/formulaire-affaire.ts';
	import PiedFormulaire from '#lib/components/PiedFormulaire.svelte';
	import PropositionCroisee from '#lib/components/PropositionCroisee.svelte';
	import { comparerParNom, type Nommable } from '#lib/noms.ts';
	import { nomCopie, saisieDepuis, type ResidentProposable } from '#lib/saisi-pour.ts';
	import AlerteEnvoiUrgent from '#lib/components/AlerteEnvoiUrgent.svelte';

	/**  L'affaire à MODIFIER, avec ses valeurs déjà saisies. `null` (défaut) =
	 *   création. Le mode ne change pas pendant la vie du composant : l'appelant le
	 *   remonte à neuf (`{#key}`) quand il passe d'une affaire à l'autre. */
	export let ticket: Ticket | null = null;

	/**  Ce qui RAMÈNE le formulaire à l'écran quand il est rendu loin du geste
	 *   qui l'ouvre — relayé par `CadreFormulaire` jusqu'à `FormulaireCreation` (`check-geste-edition`,
	 *   règle F, 13/09/2026). */
	export let cle: unknown = undefined;
	/** La catégorie d'un dépôt ouvert par un lien (`lienNouvelleAffaire`, #2075). */
	export let categorieInitiale = '';

	const modeEdition = ticket !== null;

	/**  L'état du cadre #430 que ce formulaire rend : c'est LUI qui décide des
	 *   sections, via `sectionPresente(TICKET, etat, …)` — `lint:etats` refuse
	 *   qu'une condition en dur les gouverne. */
	const etat: Etat = modeEdition ? 'edition' : 'creation';

	const dispatch = createEventDispatcher<{ cree: Ticket; modifie: Ticket; annule: void }>();

	let titre = ticket?.titre ?? '';
	let description = ticket?.description ?? '';
	//  Section « Quand » (#1092) : une date fait paraître l'affaire au calendrier.
	let debut = pourChampLocal(ticket?.debut);
	let fin = pourChampLocal(ticket?.fin);
	//  Vrai dès qu'une proposition de l'assistant IA a été appliquée (#985).
	let assisteIA = false;
	//  🔴 AUCUNE catégorie présélectionnée (21/09/2026) : un défaut qui engage
	//  quelqu'un d'autre n'est pas un défaut, c'est une réponse qu'on n'a pas donnée.
	let categorie = ticket?.categorie ?? categorieInitiale;
	let statut = ticket?.statut ?? 'ouvert';
	//  Les options, reprises de l'affaire : le pont écran ⇄ objet vit dans
	//  `#lib/tickets` (`brouillon` écrit `confidentiel`, `urgente` la priorité).
	let options = optionsDuTicket(ticket);
	//  Copies défensives : une sélection abandonnée resterait visible sur la carte affichée.
	let perimetreCible: string[] = [...(ticket?.perimetre_cible ?? perimetreDefautListe())];
	//  À qui l'on parle — une actualité (#1091, #1096) comme une affaire (#1343) :
	//  vide, la règle de sa nature. Puis l'Accès 🔒 et l'affiche, d'une actualité.
	let publicCible: string[] = [...(ticket?.public_cible ?? [])];
	let reservePerimetre = ticket?.reserve_perimetre ?? false;
	let annonceHall = false;
	//  La DIFFUSION reprend les valeurs enregistrées ; seule la transition
	//  décoché → coché envoie, et c'est le serveur qui le décide (14/08/2026).
	let destinataireSyndic = ticket?.destinataire_syndic ?? false;
	let destinataireCs = ticket?.destinataire_cs ?? false;
	//  🔴 Une AFFAIRE neuve est adressée au conseil par défaut (03/10/2026) : la case décide du
	//  courriel « Nouvelle affaire ». Une actualité repart décochée ; en correction, la valeur
	//  enregistrée fait foi.
	$: if (!modeEdition) destinataireCs = !actualite;
	let envoyerAuteur = false;
	//  Un ACTE, pas une colonne : la case repart décochée à chaque ouverture.
	let partagerWhatsapp = false;
	//  Téléversés dès leur sélection (le courriel et l'affiche partent AVEC eux) ; rechargés
	//  en correction, car `PATCH` remplace la liste entière.
	let photosUrls: string[] = [...(ticket?.photos_urls ?? [])];
	let fichiersUrls: string[] = [...(ticket?.fichiers_urls ?? [])];
	let affairesLiees = [...(ticket?.affaires_liees ?? [])];
	let error = '';
	let loading = false;
	//  « Au nom de » (CS/admin) — la saisie vit dans `ChampSaisiPour`.
	let saisiPour = saisieDepuis(ticket);
	let usersActifs: (ResidentProposable & Nommable)[] = [];
	//  Section « Intervenant » et récurrence d'un Entretien (#1092, lot 5).
	let prestataireId: number | null = ticket?.prestataire_id ?? null;
	let contratId: number | null = ticket?.contrat_id ?? null; // le cadre (#1445)
	$: duContrat = contratDeLaSaisie(contrats, contratId, ticket?.contrat); // son rythme fait foi
	let equipement = ticket?.equipement ?? '';
	let contrats: ContratEnCours[] = [];
	let frequenceType = ticket?.frequence_type ?? '';
	let frequenceValeur: number | string | null = ticket?.frequence_valeur ?? null;
	let prestataires: { id: number; nom: string; actif?: boolean }[] = [];
	let erreurPrestataires = '';
	let erreurResidents = '';

	//  ── Ce que la NATURE décide (formulaire unique, 23/09/2026) ─────────────
	$: nature = natureDe(categorie);
	$: actualite = nature === 'actualite';
	$: inactives = sectionsInactives(etat, categorie, $estModerateur);
	//  La saisie ESSENTIELLE (#2595) : les sections rangées dans « Plus de détails », et celles
	//  qu'elle éteint, ni montrées ni rangées. Le mode est celui que l'API sert (`#lib/saisie-affaire`).
	$: essentielle = estEssentielle($currentUser?.saisie_affaire_effective);
	$: ({ replies, masquees, ouvert } = repartition(
		$currentUser?.saisie_affaire_effective,
		etat,
		categorie,
		$estModerateur,
		ticket,
	));
	//  Une correction ne cache jamais ce qui a été saisi : le groupe s'ouvre d'office, une fois.
	let [detailsOuverts, detailsVus] = [false, false];
	$: if (!detailsVus && replies.length) [detailsVus, detailsOuverts] = [true, ouvert];
	//  Réservée au conseil : « Confidentielle », Destinataires = CS seul, ou sa catégorie (#1436).
	$: reservee = $lueDuSeulConseil(categorie, statut, options.brouillon, publicCible);
	//  Une actualité réservée — au périmètre ou au conseil — n'a pas d'affiche.
	$: if ((reservePerimetre || reservee) && annonceHall) annonceHall = false;
	$: assistant = contexteAssistant(actualite ? 'actualité' : 'ticket', {
		Catégorie: OPTIONS_CATEGORIE.find((o) => o.val === categorie)?.label ?? categorie,
		Périmètre: $perimetreContexte(perimetreCible),
		...(actualite ? {} : { État: STATUT_TICKET_LABELS[statut] ?? statut }),
	});

	//  L'équipement PROPOSE l'intervenant sous contrat, et ce contrat (#1097, #1445),
	//  quand il vient de changer et qu'aucun n'est désigné — jamais un remplacement.
	let equipementVu = equipement;
	$: if (equipement !== equipementVu) {
		equipementVu = equipement;
		const propose = intervenantPropose(equipement, contrats, prestataireId);
		if (propose) ({ prestataireId, contratId } = propose);
	}

	//  Pas `onMount` : il précède le layout qui charge l'utilisateur (#1486).
	quandAuthResolue(async () => {
		if ($estModerateur && sectionPresente(TICKET, etat, 'intervenant')) {
			[prestataires, erreurPrestataires] = await essayer(prestatairesApi.list(), []);
			//  Pour PROPOSER l'intervenant sous contrat (#1097) — sans eux, rien n'est proposé.
			[contrats] = await essayer(prestatairesApi.contrats(), []);
		}
		if ($estModerateur && sectionPresente(TICKET, etat, 'au_nom_de')) {
			const [tous, e] = await essayer(adminApi.utilisateurs(), []);
			usersActifs = tous.filter((u) => u.actif).sort(comparerParNom);
			erreurResidents = e;
		}
	});

	//  Le pré-remplissage depuis une affiche de hall (#832) produit une actualité.
	//  Ce n'est pas une présélection (`lint:choix-requis`) : c'est la réponse au
	//  geste « reprendre cette affiche », que le conseil vient de faire.
	function appliquerReprise(p: PrefillActualite) {
		({ titre, description } = p);
		photosUrls = p.photos;
		perimetreCible = p.perimetreCible;
		categorie = CATEGORIE_ACTUALITE;
	}

	/** Tout ce qui a été saisi — la charge utile en est dérivée (`#lib/formulaire-affaire`). */
	$: saisie = {
		titre,
		description,
		assisteIA,
		categorie,
		statut,
		options,
		perimetreCible,
		publicCible,
		reservePerimetre,
		debut,
		fin,
		photosUrls,
		fichiersUrls,
		affairesLiees,
		destinataireSyndic,
		destinataireCs,
		partagerWhatsapp,
		envoyerAuteur,
		annonceHall,
		saisiPour,
		prestataireId,
		contratId,
		equipement,
		frequenceType,
		frequenceValeur,
	} satisfies SaisieAffaire;

	//  ── L'aperçu avant diffusion (#498), au gabarit de la NATURE (`publication_syndic`…).
	let refDiffusion: SectionDiffusion | null = null;
	const brouillonApercu = () => ticketsApi.apercuDiffusion(chargeApercu(saisie, ticket?.id));

	//  Le vocabulaire vient des DÉCLARATIONS (#1107). Une actualité n'affiche pas
	//  de numéro ; une affaire suivie le garde, c'est ce qui la distingue.
	$: titreBoite = !modeEdition
		? actualite
			? PUBLICATION.libelleNouveau
			: TICKET.libelleNouveau
		: estActualiteAvant
			? PUBLICATION.libelleModifier
			: `${TICKET.libelleModifier} #${ticket?.numero ?? ''}`;
	const estActualiteAvant = natureDe(ticket?.categorie ?? '') === 'actualite';
	//  « Actualité » est réservée au conseil. Son AUTEUR peut la corriger
	//  (`peut_editer`), mais pas la convertir : c'est un geste de modération, et
	//  une affaire suivie ouverte par lui repartirait sans état. Il ne voit donc
	//  que la sienne — la taire laisserait une catégorie cochée invisible.
	const optionsCat =
		!$estModerateur && estActualiteAvant
			? OPTIONS_CATEGORIE.filter((o) => o.val === 'actualite')
			: optionsCategorie($estModerateur);

	/** Contrôles de saisie — communs à la soumission directe et à l'aperçu. */
	function saisieValide(): boolean {
		error = erreurDeSaisie(saisie, $estModerateur);
		return !error;
	}

	/**  Le geste de soumission : aperçu d'abord si un canal est coché. `submit`
	 *   reste l'unique chemin d'enregistrement. */
	function soumettre() {
		if (!saisieValide()) return;
		if (!modeEdition && refDiffusion?.ouvrirSiDiffusion()) return;
		void submit();
	}

	async function submit() {
		if (!saisieValide()) return;
		refDiffusion?.fermerApercu();
		const contexte = { creation: !modeEdition, estCS: $estModerateur };
		//  🔴 Ce qu'une correction EFFACE (23/09/2026) et QUI LIRA l'affaire et tout
		//  son fil (29/09/2026) : dit avant, rien ne part sans accord.
		const alerte = ticket && (await alerteCorrection(ticket, saisie));
		if (alerte && !(await confirmer({ ...alerte, libelleConfirmer: 'Enregistrer' }))) return;
		const demande = ticket ? await demanderFusion(ticket, statut) : SANS_FUSION; // à la clôture (#1704)
		if (demande === null) return;
		loading = true;
		try {
			const charge = chargeUtileAffaire(saisie, contexte);
			if (ticket) {
				const maj = await ticketsApi.update(ticket.id, { ...charge, ...demande });
				toast('success', `${actualite ? PUBLICATION.libelle : TICKET.libelle} modifiée`);
				dispatch('modifie', maj);
				return;
			}
			const t = await ticketsApi.create(charge);
			toast(
				'success',
				actualite ? `${PUBLICATION.libelle} publiée` : `${TICKET.libelle} ${t.numero} créée`,
			);
			dispatch('cree', t);
		} catch (e) {
			error = messageErreur(
				e,
				modeEdition ? 'Erreur lors de l’enregistrement' : 'Erreur lors de la création',
			);
		} finally {
			loading = false;
		}
	}
</script>

<!--  Rendu en CRÉATION d'une affaire suivie seulement : c'est l'envoi qui notifie. -->
{#if !modeEdition && !actualite && options.urgente}
	<AlerteEnvoiUrgent />
{/if}

{#if error}
	<div class="alert alert-error largeur-saisie">{error}</div>
{/if}

<CadreFormulaire edition={modeEdition} titre={titreBoite} encadre={!modeEdition} {cle}>
	<form on:submit|preventDefault={soumettre}>
		<!--  Le pré-remplissage depuis une affiche vient AVANT le titre : c'est un
		      raccourci qui REMPLIT le formulaire, pas une section de l'entité. Il
		      produit une actualité — le conseil seul la publie. -->
		{#if $estModerateur}
			<RepriseAnnonceHall {modeEdition} on:reprise={(e) => appliquerReprise(e.detail)} />
		{/if}

		<PhraseModeSaisie />

		<SectionTitre
			id="titre"
			bind:valeur={titre}
			placeholder="Ex : Ascenseur bâtiment A en panne"
			maxlength={200}
		/>

		<!--  2 et 3 — Catégorie (« Actualité » en tête), Équipement, Suivi : ce
		      que l'affaire a de PROPRE. Les sections éteintes par la nature y sont
		      rendues grisées, à leur rang. -->
		<SectionsSpecifiquesTicket {etat} OPTIONS_CATEGORIE={optionsCat} bind:categorie />
		{#if !essentielle}
			<SectionsEquipementSuiviTicket
				{etat}
				{modeEdition}
				{inactives}
				bind:categorie
				bind:statut
				bind:options
				bind:equipement
			/>
		{/if}
		<PropositionCroisee bind:equipement bind:perimetreCible actif={!inactives.equipement} />

		<!--  4 à 13 : ordre, intitulés et séparations hérités de `ChampsCommuns`, gouvernés par
		      la DÉCLARATION (`lint:etats`) ; ce que la nature change se lit sur `actualite`. -->
		<ChampsCommuns
			entite={TICKET}
			{inactives}
			{replies}
			{masquees}
			bind:detailsOuverts
			bind:refDiffusion
			demanderApercu={brouillonApercu}
			envoiEnCours={loading}
			on:envoyer={() => void submit()}
			idPrefixe="ticket"
			avecSaisiPour={$estModerateur && sectionPresente(TICKET, etat, 'au_nom_de')}
			residentsSaisiPour={usersActifs}
			{erreurResidents}
			bind:saisiPour
			avecOptions={sectionPresente(TICKET, etat, 'mise_en_avant')}
			objet={actualite ? 'actualité' : 'ticket'}
			optionsRendues={!$estModerateur ? ['urgente'] : OPTIONS_TICKET}
			dejaEpingle={ticket?.epingle ?? false}
			bind:epingle={options.epingle}
			bind:urgente={options.urgente}
			bind:brouillon={options.brouillon}
			avecQuand={sectionPresente(TICKET, etat, 'quand')}
			bind:debut
			bind:fin
			quandAutreValeur={!!(frequenceType || duContrat?.frequence_type)}
			avecPerimetre={sectionPresente(TICKET, etat, 'perimetre')}
			bind:perimetre={perimetreCible}
			avecReservePerimetre={$estModerateur}
			lecture={$estModerateur ? natureLue({ categorie, statut }) : null}
			bind:reservePerimetre
			avecDestinataires={$estModerateur && sectionPresente(TICKET, etat, 'destinataires')}
			bind:destinataires={publicCible}
			avecDescription={sectionPresente(TICKET, etat, 'description')}
			avecNotificationCs
			descriptionRequise
			bind:description
			{assistant}
			bind:titreObjet={titre}
			bind:assisteIA
			descriptionPlaceholder={actualite
				? 'Contenu de l’actualité…'
				: 'Décrivez le problème avec le maximum de détails (localisation, depuis quand, fréquence…)'}
			avecPhotos={sectionPresente(TICKET, etat, 'pieces_jointes')}
			bind:photos={photosUrls}
			avecDocuments={sectionPresente(TICKET, etat, 'pieces_jointes')}
			bind:documents={fichiersUrls}
			avecDiffusion={$estModerateur && sectionPresente(TICKET, etat, 'diffusion')}
			bind:whatsapp={partagerWhatsapp}
			bind:syndic={destinataireSyndic}
			bind:cs={destinataireCs}
			bind:auteur={envoyerAuteur}
			auteurNom={nomCopie(ticket)}
			aideWhatsapp={reservePerimetre
				? 'Le groupe est commun à toute la copropriété : le message portera le titre et le périmètre, avec un lien vers l’application — jamais le contenu.'
				: 'Le message est publié sur le groupe WhatsApp ; les photos jointes partent avec.'}
			whatsappInterdit={motifWhatsappInterdit(reservee, actualite ? 'actualité' : 'ticket')}
		>
			<!--  L'affiche de hall n'est pas un canal : c'est l'option d'une ACTUALITÉ,
			      rendue dans le créneau de la Diffusion (#498). -->
			<!--  Les créneaux : Intervenant, récurrence (Quand), liens, Diffusion — rendus à LEUR rang
			      par `ChampsCommuns`, qui grise ce que la déclaration éteint ; `creneauRepliees`
			      pose Équipement et Suivi en tête de « Plus de détails » (saisie Essentielle). -->
			{#snippet creneauRepliees()}
				<SectionsEquipementSuiviTicket
					{etat}
					{modeEdition}
					{inactives}
					sections={replies}
					bind:categorie
					bind:statut
					bind:options
					bind:equipement
				/>
			{/snippet}
			{#snippet creneauIntervenant()}
				{#if sectionPresente(TICKET, etat, 'intervenant')}
					<SectionIntervenant
						idPrefixe="ticket"
						bind:prestataires
						{equipement}
						erreur={erreurPrestataires}
						pliable={pliageDe(TICKET, 'intervenant')}
						bind:prestataireId
						{contrats}
						bind:contratId
					/>
				{/if}
			{/snippet}
			{#snippet creneauAffairesLiees()}
				<SectionAffairesLiees
					bind:liees={affairesLiees}
					exclure={ticket?.id ?? null}
					affaire={ticket}
					on:fusionnee={(e) => dispatch('modifie', e.detail)}
					pliable={pliageDe(TICKET, 'affaires_liees')}
					inactive={inactives.affaires_liees ?? ''}
				/>
			{/snippet}
			{#snippet creneauQuand()}
				{#if $estModerateur && categorie === CATEGORIE_ENTRETIEN}
					<ChampFrequence
						idPrefixe="ticket-frequence"
						{duContrat}
						bind:frequenceType
						bind:frequenceValeur
					/>
				{/if}
			{/snippet}
			{#snippet creneauDiffusion()}
				{#if actualite}
					<DiffusionPublication reservee={reservePerimetre || reservee} bind:annonceHall />
				{/if}
			{/snippet}
		</ChampsCommuns>

		<PiedFormulaire enCours={loading} on:annule />
	</form>
</CadreFormulaire>
