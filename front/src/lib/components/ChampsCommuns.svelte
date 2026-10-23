<!--
  ChampsCommuns.svelte — les sections 3 à 10 de TOUT formulaire de création,
  écrites une fois, dans l'ordre, avec leurs intitulés.

  ## Pourquoi ce composant (16/08/2026)

  L'ordre des sections était posé (`ux-patterns` §9 sexies) et `SectionFormulaire`
  savait les séparer à l'écran — mais chaque formulaire recomposait la suite à la
  main. Le résultat était exactement celui que `standards/02` §2 décrit :

  > « Les objets ont l'air d'être dupliqués, pas instanciés, car ils diffèrent
  >   selon les pages où ils sont implémentés. Il ne devrait pas y avoir de
  >   différence sur les objets Périmètre, Destinataires, Description, Photos,
  >   Fichiers et Diffusion — mais chaque page a des différences ! »

  Relevé avant correction, sur six écrans :

  | Notion       | Ce qui divergeait |
  |--------------|-------------------|
  | Description  | « Description » / « Description * » / « Notes » ; hauteur 60, 80, 90, 100 ou 120 px |
  | Photos       | `FichiersUpload` ici, absent là |
  | Documents    | `FichiersUpload` sur les tickets et le calendrier, `<input type="file">` nu sur les actualités et les prestations |
  | Diffusion    | aucune section nommée sur 4 écrans sur 6 |
  | Ordre        | Périmètre au milieu de la grille des champs spécifiques (prestations) ; Kanban rangé dans la diffusion (calendrier) |

  Aucune de ces différences n'était voulue. Elles sont le produit mécanique de
  six recopies : la seule façon de ne pas les voir revenir est qu'il n'y ait plus
  qu'UN endroit qui les écrive.

  ## Ce que ce composant décide, et ce qu'il ne décide pas

  Il décide **l'ordre, les intitulés et les séparations** des sections 3 à 10. Il
  ne décide RIEN du contenu métier : les sections 1 et 2 (Titre, champs
  spécifiques) restent dans l'écran, qui seul sait ce qu'elles portent.

  ## 🔴 Les sections 3 et 4 l'ont rejoint le 12/09/2026, et voici pourquoi

  Signalé à l'écran : *« la section Options de publication n'est pas ordonnée de
  la même façon entre Actualité et Tickets »*, et *« dans le calendrier,
  “Épingler dans le fil” est dans Diffusion alors qu'ailleurs c'est dans Options
  de publication »*.

  Les deux écarts ont la même cause : **l'ordre était écrit dans une
  documentation et respecté à la main.** Chaque écran posait sa section Options
  et sa section Workflow où il voulait, et rien ne pouvait le contredire — c'est
  très exactement le défaut que ce composant existait pour supprimer sur les
  sections 4 à 9, laissé en place sur les deux précédentes.

  L'ordre arbitré vit dans `SECTIONS_ORDRE` (voir plus bas) — la table qui
  était recopiée ici s'était arrêtée à dix sections, et a été retirée.

  ⚠️ Le Workflow reste un `slot` : son CONTENU est propre à l'objet (les six
  colonnes du Kanban, les états d'un ticket). Ce composant en impose le rang, le
  titre et le filet — pas ce qu'il y a dedans.

  Une section n'apparaît que si l'écran la déclare (`avecPerimetre`, `avecPhotos`…).
  Un sondage n'a pas de pièces jointes, une annonce n'a pas de diffusion : le
  contrat n'est pas « tous les écrans ont tout », c'est « quand un écran a une de
  ces notions, elle est à la même place et a la même tête ».

  ## L'ordre — il ne se discute pas par écran

  Il se lit dans `SECTIONS_ORDRE` (`$lib/entites/types`), tenu par
  `lint:ordre-sections`. Ce bloc en portait une copie — neuf sections, quand le
  cadre en comptait davantage : une liste recopiée ment dès le lot suivant.
-->
<script lang="ts">
	import type { ApercuDiffusion } from '$lib/api';
	import SectionDescription from '$lib/components/SectionDescription.svelte';
	import SectionQuand from '$lib/components/SectionQuand.svelte';
	import SectionsPiecesJointes from '$lib/components/SectionsPiecesJointes.svelte';
	import SectionFormulaire from './SectionFormulaire.svelte';
	import { SECTIONS_LIBELLE, type EntiteDeclaree, type IdSection } from '$lib/entites/types';
	import { pliageDe, requisDe } from '$lib/pliage';
	import { MAX_FICHIERS } from '$lib/fichiers';
	import SectionDiffusion from './SectionDiffusion.svelte';
	import SectionOptionsPublication from './SectionOptionsPublication.svelte';
	import SectionPerimetre from './SectionPerimetre.svelte';
	import SectionDestinataires from './SectionDestinataires.svelte';
	import ChampSaisiPour from '$lib/components/ChampSaisiPour.svelte';
	import { nomCopie, saisieDepuis } from '$lib/saisi-pour';
	import type { SaisieSaisiPour } from '$lib/saisi-pour';
	import type { CleOptionPublication } from '$lib/options-publication';
	import type { ContexteAssistant } from '$lib/assistant';
	import type { NatureLue } from '$lib/lecture-ticket';

	/** Préfixe des `id` des champs — deux formulaires peuvent coexister à l'écran,
	    et deux `<label for="…">` pointant le même id ne désignent plus rien. */
	export let idPrefixe: string;

	/**
	 * L'entité rendue — elle sert à lire le PLIAGE déclaré (#1095).
	 *
	 * 🔴 Une prop plutôt qu'un booléen par section : le pliage se LIT dans la
	 * déclaration, il ne se décide pas ici — ni par chaque écran.
	 *
	 * ⚠️ Absente, rien n'est plié : ce composant sert aussi des écrans qui ne
	 * sont pas encore au cadre, et leur imposer un pliage qu'aucune déclaration
	 * ne gouverne serait pire que pas de pliage.
	 */
	export let entite: EntiteDeclaree | null = null;

	const plie = (id: IdSection) => pliageDe(entite, id);
	//  L'astérisque vient de la DÉCLARATION, comme le pliage — et pour la même
	//  raison : les deux doivent s'accorder, et un composant qui écrirait l'un
	//  sans que la table sache l'autre rouvre la divergence (22/09/2026).
	const exige = (id: IdSection) => requisDe(entite, id);

	//  ── 2. Saisi pour ─────────────────────────────────────────────────────────
	//
	//  🔴 Section à part entière depuis le 15/09/2026, sur arbitrage :
	//
	//  > « j'ai sorti la section Saisi pour de Champs spécifiques (enregistre le
	//  >   nouveau standard des sections) »
	//
	//  Elle vivait DANS les champs spécifiques du ticket, ce qui la rendait
	//  invisible aux autres écrans : l'étendre aux actualités et aux événements
	//  l'aurait recopiée deux fois de plus. Elle est ici, donc son rang ne se
	//  négocie plus par écran — comme les options, pour la même raison, depuis le
	//  12/09.
	//
	//  ⚠️ `FormulaireTicket` continue de la poser lui-même, et c'est DÉCLARÉ :
	//  ses options dépendent du rôle et sont rendues avant `ChampsCommuns`, si
	//  bien que passer par ici les intercalerait dans le mauvais ordre.
	//  `lint:ordre-sections` vérifie que sa rangée reste juste.
	export let avecSaisiPour = false;
	/** Les résidents proposables — chargés par l'appelant, qui connaît ses droits. */
	export let residentsSaisiPour: {
		id: number;
		prenom: string;
		nom: string;
		email: string;
	}[] = [];
	export let erreurResidents = '';
	export let saisiPour: SaisieSaisiPour = saisieDepuis(null);

	//  ── 3. Options de publication ─────────────────────────────────────────────
	//  🔴 Le rang de cette section ne se négocie plus par écran (12/09/2026) :
	//  elle était posée par l'actualité, par le ticket et par l'événement, chacun
	//  à sa place. Le CONTENU, lui, reste déclaré — un ticket n'en rend pas les
	//  mêmes qu'une actualité.
	export let avecOptions = false;
	/** Les options rendues, dans l'ordre de la table `$lib/options-publication`. */
	export let optionsRendues: CleOptionPublication[] = ['epingle', 'urgente', 'brouillon'];
	/** Le nom de l'objet décrit — il entre dans les libellés qui le nomment.
	 *  Le mot d'ÉCRAN, jamais celui du modèle : `PUBLICATION.libelle` dit
	 *  « Actualité » (#1107). */
	export let objet = 'actualité';
	export let epingle = false;
	export let urgente = false;
	export let brouillon = false;
	/** L'objet édité était-il DÉJÀ épinglé ? (évite un double comptage) */
	export let dejaEpingle = false;
	/** 🔒 Motif pour lequel l'épinglage est impossible — relayé tel quel. */
	export let epingleInterdit = '';

	//  ── 4. Suivi ──────────────────────────────────────────────────────────────
	//  🔴 Plus rendu ici (#1329) : le créneau `workflow` n'avait AUCUN appelant ;
	//  le Suivi est `SectionWorkflow`, rendu par l'hôte avant ce composant.

	//  ── 5. Périmètre ──────────────────────────────────────────────────────────
	export let avecPerimetre = false;

	/**  Section « Quand » (#1092) — la date qui fait paraître l'objet au
	 *   calendrier. Elle est ce qui permet au Calendrier de cesser d'être un
	 *   objet pour devenir une vue. */
	export let avecQuand = false;

	export let debut = '';
	export let fin = '';
	export let quandAutreValeur = false; // le créneau « quand » porte une valeur
	export let perimetre: string[] = [];
	/**  Les sections ÉTEINTES par la nature de l'affaire, avec leur motif
	 *   (formulaire unique, 23/09/2026) : rendues grisées, sans champ. */
	export let inactives: Partial<Record<IdSection, string>> = {};
	/** 🔒 « Réservé au périmètre sélectionné », en tête de la section (25/09/2026). */
	export let avecReservePerimetre = false;
	export let reservePerimetre = false;
	/**  La pastille de lecture (25/09/2026), `null` sinon : « Confidentielle » (`brouillon`,
	 *   qui écrit `confidentiel`) ouvre Destinataires ; une affaire a la réserve d'office. */
	export let lecture: NatureLue | null = null;
	/**  `single` : un seul code retenu. Le rendu est le MÊME (des pastilles) —
	     seule la sélection change. Utilisé par les prestations, dont la colonne
	     `perimetre` ne porte qu'un code ; les passer au tableau demande une
	     migration, suivie à part. */
	export let perimetreMode: 'multi' | 'single' = 'multi';
	//  Périmètre obligatoire : lu dans la DÉCLARATION (`exige`), jamais posé ici —
	//  pourquoi, voir `requisDe` (#1186). Une évolution, sans entité, n'en a pas (#497).
	/**  Le badge de la section. `null` = calculé (le périmètre par défaut, quand
	 *   c'est lui). Une évolution y met le périmètre COURANT de l'objet porteur —
	 *   on voit d'où l'on part, ce qu'aucun calcul local ne peut deviner. */
	export let perimetreBadge: string | null = null;

	//  ── 6. Destinataires ──────────────────────────────────────────────────────
	export let avecDestinataires = false;
	/**  Ce bloc ouvre-t-il le formulaire ? Une section n'affiche son filet que si
	 *   quelque chose la précède — sinon il double celui du cadre, et c'est le
	 *   « double trait » signalé à l'écran le 05/09/2026. */
	export let premiere = false;
	export let destinataires: string[] = ['résidents'];
	/** Ceux d'une affaire sans choix, quand l'écran n'a pas de `lecture` — une Suite (#1343). */
	export let destinatairesParDefaut: string[] | null = null;

	//  ── 7. Description ────────────────────────────────────────────────────────
	export let avecDescription = false;
	export let description = '';
	/**  L'intitulé de la section — « Description » par défaut.
	 *
	 *   🔴 Il était FIGÉ : `EvolForm`, qui parle de « Commentaire » (#463), ne
	 *   pouvait pas hériter de ce composant et recopiait l'ordre et les intitulés.
	 *
	 *   ⚠️ Ce n'est pas une porte ouverte à un libellé par écran : **R3** demande
	 *   le même mot d'un formulaire à l'autre pour la même notion. Le paramètre
	 *   existe pour les objets dont la section n'est PAS une description — et
	 *   aujourd'hui il n'y en a qu'un. */
	export let descriptionTitre = 'Description';
	export let descriptionRequise = false;
	export let descriptionPlaceholder = '';
	/**  Hauteur minimale de l'éditeur. Elle valait 60, 80, 90, 100 ou 120 px selon
	     l'écran, sans qu'aucune de ces valeurs ait de raison : 120 px est retenu
	     comme défaut — c'est celui des deux écrans les plus utilisés (actualités,
	     tickets). Ne la surcharger que pour une vraie contrainte de place. */
	export let descriptionHauteur = '120px';
	/**  L'assistant IA de la section (#985) : l'entité et son contexte, composés
	 *   par l'écran (`$lib/assistant`). `null` = pas d'assistant. */
	export let assistant: ContexteAssistant | null = null;
	/**  Le titre de l'OBJET, prêté par l'écran pour que l'assistant puisse le
	 *   retravailler — LIÉ dans les deux sens. Ce composant ne rend pas la
	 *   section 1, il ne fait que relayer ce lien jusqu'à la Description. */
	export let titreObjet = '';
	/** Vrai dès qu'une proposition a été appliquée — l'écran l'envoie en `assiste_ia`. */
	export let assisteIA = false;

	//  ── 8. Photos ─────────────────────────────────────────────────────────────
	export let avecPhotos = false;
	export let photos: string[] = [];

	//  ── 9. Documents ──────────────────────────────────────────────────────────
	export let avecDocuments = false;
	export let documents: string[] = [];
	/**  Mode différé de TOUTE la section Pièces jointes, et son plafond : voir
	     `SectionsPiecesJointes` (#1186) et l'en-tête de `FichiersUpload`. */
	export let differes = false;
	export let fichiersDifferes: File[] = [];
	export let piecesMax: number = MAX_FICHIERS;
	/**  Qui rend le CONTRÔLE des documents. `interne` (défaut) : `FichiersUpload`,
	     comme partout. `slot` : l'écran fournit le sien — les documents d'une
	     publication sont des entités `Document` avec un identifiant, qu'on ajoute
	     et retire à l'unité. **La SECTION reste ici** dans les deux cas : son rang,
	     son intitulé et sa séparation ne se négocient pas, seul le contrôle change.
	     C'est le même contrat que la Diffusion, dont les actualités rendent déjà
	     les canaux elles-mêmes. */
	export let documentsControle: 'interne' | 'slot' = 'interne';

	//  ── 10. Diffusion ─────────────────────────────────────────────────────────
	export let avecDiffusion = false;
	/**  Les trois canaux (WhatsApp, syndic, CS). Un écran peut avoir une section
	     Diffusion SANS canaux — les actualités les rendent elles-mêmes, à travers
	     `OptionsPublication`, qui porte en plus le confidentiel et l'affiche de hall. */
	export let avecCanaux = true;

	/**  L'affaire notifie le conseil du périmètre à sa création, quelles que soient
	 *   les cases de Diffusion (#1147). Réservé à l'AFFAIRE : c'est
	 *   `tickets/arrivee.py` qui porte cet envoi, et lui seul. */
	export let avecNotificationCs = false;
	export let whatsapp = false;
	export let syndic = false;
	export let cs = false;
	/** « M'envoyer une copie » — relayée telle quelle (voir `CanauxNotification`). */
	export let auteur = false;
	/**  Le nom de l'auteur de l'objet, relayé jusqu'à la case « Envoyer une copie
	 *   à … ». Relais pur : ce composant ne sait pas non plus qui a écrit
	 *   l'objet — seul l'écran tient l'objet. */
	export let auteurNom = '';
	//  🔴 Le nom annoncé par « Envoyer une copie à … » doit dire ce qui PARTIRA,
	//  pas ce qui était enregistré. Ce composant a tout sous la main : il rend la
	//  section « Saisi pour » ET la case de diffusion. Le faire composer par les
	//  trois formulaires l'aurait écrit trois fois — et deux d'entre eux sont au
	//  plafond de modularité.
	//
	//  ⚠️ Signalé à l'écran le 15/09/2026 : « quand on change Saisi pour avec une
	//  personne ayant un email, ça change envoyer une copie à X ». C'est le
	//  comportement VOULU (arbitré le 12/09) — mais les formulaires annonçaient
	//  l'auteur, là où `CarteTicket` annonçait le propriétaire. La même case
	//  disait deux noms selon l'écran.
	$: nomDeLaCopie = avecSaisiPour
		? nomCopie({ proprietaire_nom: auteurNom }, { ...saisiPour, residents: residentsSaisiPour })
		: auteurNom;
	export let aideWhatsapp = '';
	/** Motif interdisant le groupe WhatsApp — relayé jusqu'à `CanauxNotification`. */
	export let whatsappInterdit = '';
	/**  La fonction d'aperçu de l'écran — transmise TELLE QUELLE à l'objet
	 *   Diffusion, qui porte l'état et la modale (#498). Absente = pas d'aperçu,
	 *   ce qui est le cas des écrans sans endpoint. */
	export let demanderApercu: (() => Promise<ApercuDiffusion>) | null = null;
	//  Exposé au parent : c'est LUI qui déclenche l'aperçu au moment de soumettre.
	export let refDiffusion: SectionDiffusion | null = null;
	export let envoiEnCours = false;

	//  🔴 Les badges d'état vivaient ICI, avec les deux sections écrites en
	//  ligne. Ils sont partis AVEC elles (`SectionPerimetre`,
	//  `SectionDestinataires`, 22/09/2026) : un badge calculé loin de la section
	//  qu'il décore est la première étape vers deux calculs qui divergent.

	//  Le filet du haut n'appartient pas au Périmètre : il appartient à la
	//  PREMIÈRE section rendue, quelle qu'elle soit. Sans ce calcul, ouvrir un
	//  formulaire par les options doublait le trait du cadre — le « double trait »
	//  signalé à l'écran le 05/09/2026, une section plus haut.
	//  ⚠️ « Saisi pour » entre dans ce calcul comme les autres : le filet du haut
	//  appartient à la première section RENDUE, et elle passe avant les options.
	//  L'oublier redonnerait le « double trait » du 05/09.
	$: premiereWorkflow = premiere && !avecSaisiPour && !avecOptions;
	$: premiereQuand = premiereWorkflow;
	$: premierePerimetre = premiereQuand && !avecQuand;
</script>

{#if avecQuand}
	<!--  5. Quand — QUAND ÇA SE PASSE, et pour quand c'est attendu. Placée
	      avant le Périmètre : on sait ce qui arrive avant de dire où. -->
	<SectionQuand
		{idPrefixe}
		premiere={premiereQuand}
		pliable={plie('quand')}
		autreValeur={quandAutreValeur}
		inactive={inactives.quand ?? ''}
		bind:debut
		bind:fin
	>
		<slot name="quand" />
	</SectionQuand>
{/if}

<!--  6. L'INTERVENANT, à son rang : rendu par l'appelant (créneau), ou grisé
      avec son motif quand la déclaration l'éteint (#1092). -->
{#if inactives.intervenant}
	<SectionFormulaire
		titre={SECTIONS_LIBELLE.intervenant}
		pliable={plie('intervenant')}
		inactive={inactives.intervenant}
	/>
{:else}
	<slot name="intervenant" />
{/if}

{#if avecPerimetre}
	<SectionPerimetre
		{idPrefixe}
		premiere={premierePerimetre}
		pliable={plie('perimetre')}
		bind:perimetre
		mode={perimetreMode}
		requis={exige('perimetre')}
		badgeImpose={perimetreBadge}
		reservable={avecReservePerimetre}
		bind:reserve={reservePerimetre}
		reserveObjet={lecture && !lecture.actualite ? 'affaire' : 'actualité'}
		reserveSansObjet={lecture && brouillon ? 'Sans objet : elle est confidentielle.' : ''}
		inactive={inactives.perimetre ?? ''}
	>
		<slot name="aidePerimetre" slot="aidePerimetre" />
	</SectionPerimetre>
{/if}

{#if avecDescription}
	<SectionDescription
		{idPrefixe}
		pliable={plie('description')}
		titre={descriptionTitre}
		requis={descriptionRequise}
		placeholder={descriptionPlaceholder}
		hauteur={descriptionHauteur}
		bind:valeur={description}
		{assistant}
		bind:titreObjet
		bind:assisteIA
	/>
{/if}

<!--  7. Photos · 8. Documents — DEUX sections, écrites une seule fois pour ce
      composant ET `EvolForm`, qui les portait à l'identique (01/09/2026). -->
<SectionsPiecesJointes
	{idPrefixe}
	pliable={plie('pieces_jointes')}
	{avecPhotos}
	bind:photos
	{avecDocuments}
	{documentsControle}
	{differes}
	max={piecesMax}
	bind:documents
	bind:fichiersDifferes
>
	<svelte:fragment slot="documents"><slot name="documents" /></svelte:fragment>
</SectionsPiecesJointes>

<!--  Affaires liées (#1342) : un créneau, à son rang — seule l'affaire en porte. -->
<slot name="affairesLiees" />

{#if avecSaisiPour}
	<!--  2. Au nom de QUI l'entrée est ouverte. Le composant est celui des
	      tickets (`ChampSaisiPour`) : il portait déjà la saisie, il ne lui
	      manquait qu'un appelant de plus. -->
	<ChampSaisiPour
		pliable={plie('au_nom_de')}
		requis={exige('au_nom_de')}
		inactive={inactives.au_nom_de ?? ''}
		bind:mode={saisiPour.mode}
		bind:userId={saisiPour.userId}
		bind:nom={saisiPour.nom}
		bind:email={saisiPour.email}
		residents={residentsSaisiPour}
		{erreurResidents}
	/>
{/if}

{#if avecDestinataires || inactives.destinataires}
	<SectionDestinataires
		{idPrefixe}
		premiere={premiere && !avecPerimetre}
		pliable={plie('destinataires')}
		requis={exige('destinataires')}
		inactive={inactives.destinataires ?? ''}
		bind:destinataires
		{lecture}
		bind:confidentiel={brouillon}
		{perimetre}
		{reservePerimetre}
		parDefaut={destinatairesParDefaut}
		concerne={nomDeLaCopie}
	/>
{/if}

{#if avecOptions}
	<!--  3. Les options qui DÉCRIVENT l'objet — épinglage, urgence, brouillon.
	      La réserve au périmètre vit en tête du Périmètre. Toujours ici, jamais dans la Diffusion : elles se
	      corrigent, elles ne s'envoient pas. -->
	<SectionOptionsPublication
		{objet}
		{premiere}
		pliable={plie('mise_en_avant')}
		inactive={inactives.mise_en_avant ?? ''}
		options={optionsRendues}
		{dejaEpingle}
		{epingleInterdit}
		bind:epingle
		bind:urgente
		bind:brouillon
	/>
{/if}

<!--  🔴 La section 9 vient de `SectionDiffusion`, elle n'est plus réécrite ici
      (#498, 20/08/2026).

      L'objet Diffusion existait en DOUBLE : `SectionDiffusion.svelte` d'un côté,
      ces onze lignes de l'autre — et c'est la seconde que servaient les six
      formulaires de création. D'où la question posée à l'écran : « je ne
      comprends pas qu'une fonction dans un objet ne soit pas accessible sur
      toutes ses implémentations ». Réponse : il y avait deux objets, et l'aperçu
      n'avait été ajouté qu'à l'un des deux.

      ⚠️ `demanderApercu` n'est PAS transmis ici : aucun de ces six écrans n'a
      encore d'endpoint d'aperçu (seuls les tickets en ont un). L'objet le porte
      désormais — le jour où un écran fournit sa fonction, il obtient l'aperçu
      sans une ligne de plus. -->
{#if avecDiffusion}
	<SectionDiffusion
		pliable={plie('diffusion')}
		inactive={inactives.diffusion ?? ''}
		{avecCanaux}
		{avecNotificationCs}
		bind:whatsapp
		bind:syndic
		bind:cs
		bind:auteur
		auteurNom={nomDeLaCopie}
		{aideWhatsapp}
		{whatsappInterdit}
		bind:this={refDiffusion}
		{demanderApercu}
		{envoiEnCours}
		on:envoyer
	>
		<svelte:fragment slot="options"><slot name="diffusion" /></svelte:fragment>
	</SectionDiffusion>
{/if}
