<!--
  EvolForm.svelte — Formulaire partagé d'ajout/édition d'évolution
  Utilisé par : tickets/[id], tickets (liste), actualites, espace-cs

  ## Il suit l'ORDRE et les SECTIONS communes (`ux-patterns` §9 sexies et septies)

  Ce composant est antérieur aux règles posées les 15-17/08/2026, et n'avait été
  repris par aucun des lots qui les ont établies (#416) : la **Diffusion** était
  rendue AVANT les pièces jointes, aucune section n'était nommée, et le bouton de
  soumission disait « Valider » en création contre « Enregistrer » en édition —
  le même geste, deux libellés, dans la même ligne de code.

  L'ordre est désormais celui de tout le site — Workflow, Description, Photos,
  Documents, Diffusion en dernier. La liste n’est pas recopiée ici : elle vit
  dans `ux-patterns` §9 sexies, et deux versions divergeraient au premier lot.

  ## UN SEUL POINT D'ENTRÉE, ET LE GESTE SE LIT DANS LES PASTILLES (#426)

  Ce formulaire commençait par une rangée de deux pastilles — « 💬 Commentaire »
  et « 🔄 Changement d'état » — au-dessus d'un formulaire ouvert par un bouton
  💬 : l'utilisateur avait **déjà dit** ce qu'il voulait faire en cliquant, et la
  première pastille était un choix sans objet.

  > « le bouton commentaire n'a pas lieu d'être — il est présent sur le fil
  >   principal pour ouvrir un *nouveau commentaire* » (17/08/2026)

  Première tentative (18/08, matin) : deux boutons sur la carte, le geste figé
  par l'appelant. **Refusée à l'écran** — *« il manque le principal, la section
  Workflow avec les différentes pastilles »*.

  La forme retenue est plus simple, et c'est **UN** point d'entrée : le bouton 🔄
  ouvre le formulaire, dont la **section Workflow** porte les états en pastilles,
  **celle de l'état courant active**. Laisser la pastille telle quelle ne change
  rien : l'entrée est alors un commentaire. En choisir une autre fait avancer le
  suivi. Le même formulaire sert les deux gestes sans jamais les redemander, parce
  que **la réponse est déjà visible à l'écran**.

  C'est aussi ce qui supprime la question « et si je veux commenter ET changer
  l'état ? » : c'était déjà possible, mais il fallait le deviner.

  Les pièces jointes sont DEUX sections, jamais une (#433) : le mode unifié
  (`separatePhotosAndDocs`) a disparu le 18/08/2026 avec son dernier appelant.

  ✅ **Gouverné par la déclaration d'entité** (02/09/2026, #463) : il REÇOIT
  l'entité, et la règle qui en tire les sections vit dans `#lib/evolutions`
  (`sectionsDeLaSuite`, 25/09/2026). Les cinq écrans ne décident plus des
  sections — seulement des DROITS de leur lecteur, et de ce que l'objet EST.

  ✅ **L'écart d'intitulé est levé (02/09/2026)** — arbitré : *« oui, unifier à
  commentaire »*. La description basculait « Commentaire » / « Contenu » selon le
  mode, là où R3 demande le MÊME libellé d'un formulaire à l'autre.

  ✅ **`SectionFormulaire` n'est plus employé ici** (02/09/2026, #463) : les
  sections 4, 6, 7-8 et 9 passent par les composants du cadre. L'ordre et les
  intitulés ne sont plus tenus par recopie. La raison invoquée jusqu'ici —
  « l'intitulé de `ChampsCommuns` est figé à Description » — était tombée le
  matin même.

  Les props sont documentées UNE fois, chacune à sa déclaration : cette liste-ci
  les recopiait, et deux listes divergent au premier ajout.

  Événements :
    submit(data)  – une `ChargeUtileEvolution` (`#lib/evolutions`, seule écriture de ses champs)
    cancel        – fermer le formulaire sans sauvegarder
-->
<script lang="ts">
	import SectionWorkflow from '#lib/components/SectionWorkflow.svelte';
	import SectionDescription from '#lib/components/SectionDescription.svelte';
	import { createEventDispatcher } from 'svelte';
	import { writable } from 'svelte/store';
	import SectionDiffusion from '#lib/components/SectionDiffusion.svelte';
	import {
		typeDeLEntree,
		entreeEnregistrable,
		etatInitialEntree,
		sectionsDeLaSuite,
		type ChargeUtileEvolution,
	} from '#lib/evolutions.ts';
	import SectionsPiecesJointes from '#lib/components/SectionsPiecesJointes.svelte';
	import SectionAffairesLiees from '#lib/components/SectionAffairesLiees.svelte';
	import FormulaireCreation from '#lib/components/FormulaireCreation.svelte';
	import SectionsCiblageEvolution from '#lib/components/SectionsCiblageEvolution.svelte';
	import type { ConditionInactive, EntiteDeclaree } from '#lib/entites/types.ts';
	import { pliageDe } from '#lib/pliage.ts';
	import { SUITE } from '#lib/gestes.ts';
	import type { AffaireLiee, ApercuDiffusion } from '#lib/api/index.ts';
	import { perimetreEntree } from '#lib/perimetres/index.ts';
	import PiedFormulaire from '#lib/components/PiedFormulaire.svelte';
	import { avecNouvelEtat, type ContexteAssistant } from '#lib/assistant.ts';

	// ── Props ─────────────────────────────────────────────────────────────────
	/** Préfixe des `id` des champs. Plusieurs formulaires d'évolution coexistent à
	    l'écran — le formulaire d'ajout d'une carte et l'édition d'une évolution du
	    même fil —, et deux `<label for="…">` pointant le même id ne désignent plus
	    rien. Même contrat que `ChampsCommuns`. */
	export let idPrefixe = 'evol';
	/**  CE QUE L'ON EST EN TRAIN DE FAIRE, écrit en toutes lettres (18/08/2026).
	 *
	 *   Ce formulaire était le SEUL du site sans en-tête : `FormulaireTicket` et
	 *   `FormulaireActualite` passent par `FormulaireCreation`, qui leur donne un
	 *   titre. Ici, le mode devait se deviner à partir de l'icône cliquée trois
	 *   secondes plus tôt — signalé à l'écran : *« on ne sait pas si on est en
	 *   mode édition, en mode suivi »*. R1 dit que le squelette porte
	 *   *en-tête · corps · pied* : un formulaire sans nom viole le cadre. */
	export let titre = SUITE.libelle;
	/** Options affichées dans le select "Nouvel état" */
	export let statutOptions: { value: string; label: string }[] = [];
	/** Map value→label pour afficher le statut actuel */
	export let statutLabels: Record<string, string> = {};
	/** Statut actuel de l'objet parent (badge à droite de l'intitulé) */
	export let currentStatut = '';
	/**  🔴 L'ENTITÉ dont ce fil est le quatrième état (#463) : c'est ELLE qui dit
	 *   quelles sections existent, plus les cinq écrans chacun de son côté (trois
	 *   recopiaient `sectionPresente(TICKET, 'evolution', …)`, deux passaient `true`
	 *   en dur — les valeurs coïncidaient, d'où l'invisibilité de la divergence).
	 *
	 *   ⚠️ La déclaration dit ce qui EXISTE, jamais ce que CET utilisateur a le
	 *   droit de faire : les trois props ci-dessous portent cela et restent chez
	 *   l'appelant, seul à connaître le lecteur. Les mêler aurait fait décider d'un
	 *   droit par une déclaration de forme. */
	export let entite: EntiteDeclaree;
	/**  Ce que l'objet EST et qui éteint une section — `sectionDeLaSuite`. */
	export let conditions: ConditionInactive[] = [];
	/**  Trois DROITS, pas des sections — `$isCS` sur la fiche, l'auteur sur sa carte —,
	 *   à défaut FERMÉ (#2142) : « Répondre » ne les passait pas et montrait ce
	 *   qu'aucune route n'emporte. Périmètre et Destinataires disent qui lit l'objet. */
	export let peutDiffuser = false;
	export let peutPreciserPerimetre = false;
	export let peutCibler = false;
	/**  Une variante du GESTE, pas de la section — R4 ne sait pas la déclarer
	 *   (#436) : faux sur une note interne, ligne de suivi et non signalement. */
	export let avecPiecesJointes = true;
	export let affaireLiable: number | null = null; // l'affaire à LIER depuis une Suite (#1342)
	/**  L'hôte a-t-il quelque chose à poser AVANT le Suivi (l'Équipement, #1326) ?
	 *   Un créneau déclaré mais vide ôterait au Suivi son rang de première section. */
	export let avantSuivi = true;
	/**  L'état que les TROIS créneaux partagent : l'Équipement (avant le Suivi)
	 *   propose l'Intervenant (après) — `#lib/suite-conseil`. */
	const partage = writable<Record<string, unknown>>({});
	/** Valeurs par défaut des notifications */
	export let defaultPartagerWhatsapp = false;
	export let defaultEnvoyerSyndic = false;
	export let defaultEnvoyerCs = false;
	/** Afficher le champ email externe */
	export let showEmail = false;
	/**  Proposer « Message interne ». C'est une décision de DIFFUSION — qui voit
	     cette entrée —, donc elle est rendue en section 9, avec les canaux, et
	     non au milieu du commentaire comme le faisait le formulaire de réponse
	     écrit à la main de la fiche d'un ticket (#431). */
	export let avecInterne = false;
	/** Lié par le parent : lui seul sait ce qu'une entrée interne change chez lui. */
	export let interne = false;
	/** CORRECTION d'une entrée : toutes les sections, sans Diffusion (`sectionsDeLaSuite`). */
	export let editMode = false;
	/** L'état qu'elle avait enregistré ; `currentStatut` est alors celui d'AVANT elle. */
	export let initialStatut = '';
	/** Contenu initial (mode édition) */
	export let initialContenu = '';
	/** Fichiers initiaux (mode édition) */
	export let initialFichiers: { url: string; nom: string; type?: string }[] = [];

	/**  Le périmètre que l'entrée AVAIT déclaré, en correction. Vide si elle n'en
	 *   déclarait aucun — le sélecteur part alors de l'hérité, comme en saisie. */
	export let initialPerimetre: string[] = [];
	/** Le ciblage en vigueur et son aide — voir `SectionsCiblageEvolution`. */
	export let initialDestinataires: string[] = [];
	export let destinatairesParDefaut: ((statut: string) => string[]) | null = null; // selon l'état (#1343)
	export let confidentiel = false; // « Résident concerné », lié à l'hôte (#1321)
	export let aidePerimetre = '';
	/**  Le périmètre de l’objet, et l’historique déjà écrit : ensemble ils donnent
	 *   celui dont cette entrée HÉRITE (`perimetreHerite`) — badge et point de
	 *   départ du sélecteur, calculés une seule fois pour ne pas en montrer deux. */
	export let perimetreCourant: string[] = [];
	export let entrees: { perimetre_cible?: string[] | null }[] = [];
	/**  Comment demander l'aperçu de ce qui partira — `null` = pas d'aperçu ici.
	 *
	 *   🔴 Fournie par l'APPELANT, jamais codée ici : ce formulaire sert quatre
	 *   écrans (ticket, actualité, calendrier, espace CS), et chacun compose son
	 *   message avec ses propres modèles. Un aperçu écrit ici ne pourrait montrer
	 *   qu'un seul des quatre — donc mentir sur les trois autres.
	 *
	 *   ⚠️ AJOUTÉ le 19/08/2026 après un signalement : l'aperçu n'existait qu'à la
	 *   création d'un ticket, et l'utilisateur l'a découvert en COMMENTANT — case
	 *   « envoyer au syndic » cochée, rien ne s'est ouvert. Une fonctionnalité
	 *   livrée à moitié ne se lit pas « la suite arrive », elle se lit « cassée »,
	 *   et c'est la lecture juste du côté de l'écran. */
	export let demanderApercu:
		| ((saisie: {
				contenu: string;
				fichiers_urls: string[];
				whatsapp: boolean;
				syndic: boolean;
				cs: boolean;
		  }) => Promise<ApercuDiffusion>)
		| null = null;
	/**  Le nom de l'auteur de l'OBJET commenté, jamais celui du commentaire —
	 *   la règle vit dans `CanauxNotification.svelte`. */
	export let auteurNom = '';
	/** Contrôlé par le parent : la sauvegarde API est-elle en cours ? */
	export let saving = false;

	/**  L'assistant IA du Commentaire (#985) : le contexte de l'objet PORTEUR, composé
	 *   par l'appelant, seul à tenir l'objet (`contexteCommentaire`). `null` = aucun. */
	export let assistant: ContexteAssistant | null = null;

	// ── Events ────────────────────────────────────────────────────────────────
	//  🔴 UNE écriture de la charge utile, `#lib/evolutions` — il y en avait deux (17/09/2026).
	const dispatch = createEventDispatcher<{ submit: ChargeUtileEvolution; cancel: void }>();

	// ── State ─────────────────────────────────────────────────────────────────
	let contenu = initialContenu;
	let assisteIA = false; // une proposition de l'assistant a été appliquée (#985)
	let nouveauStatut = initialStatut;
	let evolType: 'commentaire' | 'etat' = 'commentaire';
	let partagerWhatsapp = defaultPartagerWhatsapp;
	let envoyerSyndic = defaultEnvoyerSyndic;
	let envoyerCs = defaultEnvoyerCs;
	let envoyerAuteur = false;
	let emailExterne = '';
	let affairesLiees: AffaireLiee[] = [];
	//  L'état INITIAL d'une entrée (périmètre, destinataires, pièces) : `#lib/evolutions` (17/09/2026).
	let {
		perimetre,
		destinataires,
		photos,
		documents: docs,
	} = etatInitialEntree(
		editMode,
		initialPerimetre,
		perimetreCourant,
		entrees,
		initialDestinataires,
		initialFichiers,
		destinatairesParDefaut !== null,
	);

	// ── Helpers ───────────────────────────────────────────────────────────────

	$: allFichiersUrls = [...photos, ...docs];

	//  Sections visibles. La PREMIÈRE section rendue ne porte pas de filet
	//  au-dessus : un trait avant le premier groupe le séparerait du titre du
	//  formulaire, qui joue déjà ce rôle (`SectionFormulaire`).
	//  La section Workflow n'existe que pour le geste qui la concerne, et
	//  seulement s'il y a un état à proposer : un choix à un seul choix n'est pas
	//  un choix. Elle ne porte plus la NATURE de l'entrée — c'est l'appelant qui
	//  la décide (#426).
	//  🔄 Le Suivi se corrige aussi (01/10/2026) : `app/utils/suivi_fil.py`.
	$: sectionWorkflow = statutOptions.length > 0;
	//  Ce que la Suite offre — la déclaration ET le droit : `#lib/evolutions`.
	$: sections = sectionsDeLaSuite(entite, conditions, {
		perimetre: peutPreciserPerimetre,
		destinataires: peutCibler,
		piecesJointes: avecPiecesJointes,
		affairesLiees: affaireLiable !== null,
		diffusion: peutDiffuser,
		correction: editMode,
		creneaux: {
			avant_suivi: !!$$slots.avant_suivi && avantSuivi,
			specifiques: !!$$slots.specifiques,
			mise_en_avant: !!$$slots.mise_en_avant,
		},
	});
	$: avantPerimetre = sectionWorkflow || sections.specifiques || sections.avantSuivi;

	//  L'état actuel se lit en BADGE à droite de l'intitulé, pas en ligne de texte
	//  sous lui (`ux-patterns` §9 quater) — c'est la forme qu'a déjà la carte du
	//  ticket, deux centimètres plus haut.
	$: libelleStatutActuel = currentStatut ? statutLabels[currentStatut] || currentStatut : '';

	//  Le périmètre COURANT en badge, même forme que l'état courant deux lignes
	//  plus haut : on voit d'où l'on part avant de préciser. `ChampsCommuns`
	//  n'affiche le badge que sur le périmètre par défaut, parce que le sélecteur
	//  montre déjà la sélection ; ici le sélecteur part vide, donc le badge est le
	//  SEUL endroit où l'on lit le périmètre actuel — il est toujours affiché.
	//
	//  Le calcul lui-même vit dans `#lib/perimetres` : il parle de périmètre, pas
	//  de formulaire (extrait le 31/08/2026, sur refus de modularité).
	//  ⚠️ Des affectations plutôt qu'une déstructuration réactive : ESLint 10
	//  plante sur `$: ({a, b} = f())` (@typescript-eslint/no-unused-vars). Le
	//  contournement est ici, pas dans une règle désactivée.
	$: entreePerimetre = perimetreEntree(perimetreCourant, entrees, perimetre, sections.perimetre);
	$: perimetreDeclare = entreePerimetre.declare;
	$: libellePerimetreActuel = entreePerimetre.libelleActuel;

	//  🔴 L'INTITULÉ NE BASCULE PLUS (voir l'en-tête). « Commentaire » et non
	//  « Description » : c'est le mot d'un auteur sur un fil, pas le corps d'un objet.
	const titreContenu = 'Commentaire';
	//  Les trois règles du fil vivent dans `#lib/evolutions` depuis le 05/09/2026 :
	//  « quel geste ? », « le texte est-il requis ? », « y a-t-il quelque chose à
	//  enregistrer ? » se posent pareil sur les trois entités qui portent un fil.
	$: evolType = typeDeLEntree(nouveauStatut, currentStatut);
	//  Le commentaire est REQUIS quand l'entrée n'apporte que lui : sans texte ni
	//  changement d'état, l'entrée ne dirait rien. Pas de mention « (optionnel) » :
	//  l'absence d'astérisque suffit (`ux-patterns` §9).
	$: contenuRequis = !editMode && evolType === 'commentaire';
	//  Le NOUVEL état complète le contexte de l'assistant — seul ce formulaire le connaît (#985).
	$: assistantEffectif = avecNouvelEtat(assistant, evolType, nouveauStatut, statutLabels);
	$: canSubmit = !saving && entreeEnregistrable(evolType, contenu, allFichiersUrls.length);

	// ── Aperçu avant diffusion (#498) ─────────────────────────────────────────
	//  🔴 La saisie est PASSÉE à l'appelant, elle n'est pas lue depuis l'extérieur.
	//  Ce formulaire tient son état ; une fermeture posée chez l'appelant lirait
	//  des valeurs vides — première tentative, corrigée avant d'être livrée.
	//  L'état et la modale vivent dans `SectionDiffusion` depuis le 20/08/2026 :
	//  l'aperçu appartient à l'objet Diffusion, pas à ses appelants (#498). Ne
	//  reste ici que la SAISIE à transmettre — ce formulaire seul la connaît.
	/**  Motif interdisant le groupe WhatsApp, relayé à `SectionDiffusion` — il
	 *   vaut aussi pour une Suite : un ticket réservé au conseil le reste quand on
	 *   le commente. 🔴 Il était REÇU sans être relayé jusqu'au 26/09/2026 : la
	 *   case restait cochable, et promettait un envoi que le serveur refuse. */
	export let whatsappInterdit = '';

	let refDiffusion: SectionDiffusion;
	//  Transmise seulement si `demanderApercu` existe ; le refus vit dans `SectionDiffusion`.
	const brouillonApercu = () =>
		demanderApercu!({
			contenu,
			fichiers_urls: allFichiersUrls,
			whatsapp: partagerWhatsapp,
			syndic: envoyerSyndic,
			cs: envoyerCs,
		});

	// ── Submit ────────────────────────────────────────────────────────────────
	function soumettre() {
		if (!canSubmit) return;
		if (refDiffusion?.ouvrirSiDiffusion()) return;
		handleSubmit();
	}

	function handleSubmit() {
		if (!canSubmit) return;
		refDiffusion?.fermerApercu();
		dispatch('submit', {
			type: evolType,
			contenu,
			nouveau_statut: evolType === 'etat' ? nouveauStatut : undefined,
			corrige_suivi: editMode && sectionWorkflow ? true : undefined,
			fichiers_urls: allFichiersUrls,
			affaires_liees: affairesLiees.length ? affairesLiees.map((a) => a.id) : undefined,
			partager_whatsapp: sections.diffusion ? partagerWhatsapp : undefined,
			envoyer_syndic: sections.diffusion ? envoyerSyndic : undefined,
			envoyer_cs: sections.diffusion ? envoyerCs : undefined,
			envoyer_auteur: sections.diffusion ? envoyerAuteur : undefined,
			email_externe: showEmail ? emailExterne.trim() || undefined : undefined,
			interne: avecInterne ? interne : undefined,
			perimetre_cible: perimetreDeclare,
			public_cible: sections.destinataires ? destinataires : undefined, // affichée, donc émise (#1091)
			assiste_ia: assisteIA || undefined, // seulement quand c'est vrai : « je n'en dis rien » sinon
		});
	}
</script>

<!--  Même largeur de saisie que partout ailleurs (`ux-patterns` §9) : le
      formulaire s'étalait sur toute la carte, alors que le même geste sur une
      page dédiée s'arrête à 720 px. -->
<!--  Pas de cadre : ce formulaire s'ouvre DÉJÀ dans une carte, et deux bordures
      imbriquées pour un seul objet est le défaut signalé sur #425. Le titre,
      lui, reste — c'est lui qui dit ce qu'on fait. -->
<FormulaireCreation {titre} encadre={false}>
	<!--  🔴 L'ORDRE EST CELUI DE `SECTIONS_ORDRE`, comme dans l'édition (#1326) :
	      les trois créneaux de l'hôte se rendent à LEUR rang (`creneauDe`,
	      `#lib/evolutions`) — Équipement avant le Suivi, Quand et Intervenant
	      après, Mise en avant après les Destinataires. -->
	{#if sections.avantSuivi}
		<!-- eslint-disable-next-line svelte/require-store-reactive-access -- le MAGASIN, pas sa valeur : les créneaux l'écrivent -->
		<slot name="avant_suivi" premiere={true} {partage} />
	{/if}

	{#if sectionWorkflow}
		<!--  Suivi : l'état COURANT actif à l'ouverture ; le garder tel quel fait
		      de l'entrée un simple commentaire (R3, #423 · §9 septies et quater). -->
		<SectionWorkflow
			premiere={!sections.avantSuivi}
			pliable={pliageDe(entite, 'suivi')}
			idTitre="{idPrefixe}-workflow-titre"
			options={statutOptions}
			valeur={nouveauStatut || currentStatut}
			badge={editMode ? '' : libelleStatutActuel}
			on:choisir={(e) => (nouveauStatut = e.detail)}
		/>
	{/if}

	{#if sections.specifiques}
		<!-- eslint-disable-next-line svelte/require-store-reactive-access -- le MAGASIN, pas sa valeur : les créneaux l'écrivent -->
		<slot name="specifiques" premiere={!sectionWorkflow && !sections.avantSuivi} {partage} />
	{/if}

	<!--  Périmètre — les Destinataires viennent APRÈS les pièces jointes (#1326). -->
	<SectionsCiblageEvolution
		{idPrefixe}
		{entite}
		premiere={!avantPerimetre}
		avecPerimetre={sections.perimetre}
		bind:perimetre
		perimetreBadge={libellePerimetreActuel}
		{aidePerimetre}
	/>

	<SectionDescription
		{idPrefixe}
		idChamp="contenu"
		pliable={pliageDe(entite, 'description')}
		premiere={!avantPerimetre && !sections.perimetre}
		titre={titreContenu}
		requis={contenuRequis}
		placeholder={editMode
			? 'Modifier le commentaire…'
			: evolType === 'etat'
				? 'Précisions sur ce changement…'
				: 'Ajoutez un commentaire de suivi…'}
		bind:valeur={contenu}
		assistant={assistantEffectif}
		assistantAvecTitre={false}
		bind:assisteIA
	/>

	<!--  Pièces jointes — `SectionsPiecesJointes`, commun à `ChampsCommuns`. Elles ne
	      dépendent PAS du geste (18/08/2026) : une photo justifie souvent un
	      passage à « Résolu ». -->
	<SectionsPiecesJointes
		{idPrefixe}
		pliable={pliageDe(entite, 'pieces_jointes')}
		avecPhotos={sections.piecesJointes}
		bind:photos
		avecDocuments={sections.piecesJointes}
		bind:documents={docs}
		idDocuments="docs"
	/>

	{#if sections.affairesLiees}
		<SectionAffairesLiees
			{idPrefixe}
			bind:liees={affairesLiees}
			exclure={affaireLiable}
			pliable={pliageDe(entite, 'affaires_liees')}
		/>
	{/if}

	<!--  Destinataires, puis Mise en avant — « à qui l'on parle, puis comment on
	      le met en avant » (#1096), dans l'ordre de l'édition (#1326). -->
	<SectionsCiblageEvolution
		{idPrefixe}
		{entite}
		avecDestinataires={sections.destinataires}
		bind:destinataires
		destinatairesParDefaut={destinatairesParDefaut?.(nouveauStatut || currentStatut) ?? null}
		bind:confidentiel
	/>
	{#if sections.miseEnAvant}
		<!-- eslint-disable-next-line svelte/require-store-reactive-access -- le MAGASIN, pas sa valeur : les créneaux l'écrivent -->
		<slot name="mise_en_avant" premiere={false} {partage} />
	{/if}

	<SectionDiffusion
		bind:this={refDiffusion}
		demanderApercu={demanderApercu ? brouillonApercu : null}
		envoiEnCours={saving}
		on:envoyer={handleSubmit}
		{idPrefixe}
		pliable={pliageDe(entite, 'diffusion')}
		avecCanaux={sections.diffusion}
		bind:whatsapp={partagerWhatsapp}
		{whatsappInterdit}
		bind:syndic={envoyerSyndic}
		bind:cs={envoyerCs}
		bind:auteur={envoyerAuteur}
		{auteurNom}
		avecEmailExterne={showEmail}
		bind:emailExterne
		{avecInterne}
		bind:interne
		fichiers={allFichiersUrls}
		compact
	/>

	<!-- ── Actions ──────────────────────────────────────────────────────────
	     `.form-actions` vient d'app.css : la disposition était recomposée ici en
	     ligne, aux mêmes valeurs, donc libre de diverger (`ux-patterns` §9
	     quinquies). Le verbe est GÉNÉRIQUE dans les deux modes — « Valider » /
	     « Envoi… » en création contre « Enregistrer » / « Enregistrement… » en
	     édition, c'était le même geste sous deux libellés (§9 quinquies bis). -->
	<!--  ⚠️ `petit` : ce formulaire vit DANS une carte de ticket, où des boutons
	      pleine taille écraseraient le fil autour. Et `cancel` était la TROISIÈME
	      orthographe de l'annulation, après `annule` et `annuler` (#822). -->
	<PiedFormulaire
		petit
		enCours={saving}
		desactive={!canSubmit}
		soumission={false}
		on:annule={() => dispatch('cancel')}
		on:enregistre={soumettre}
	/>
</FormulaireCreation>

<!--  Aucun `<style>` : tout le rendu vient des composants montés ci-dessus, et
      chaque règle voyage avec le balisage qu'elle habille (v2.67.11). Les notes
      qui expliquaient l'absence de `.aide-bloc`, `.case-interne` et de la rangée
      de pastilles sont désormais dans les trois composants qui les portent. -->
