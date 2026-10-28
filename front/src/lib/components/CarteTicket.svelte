<!--
  CarteTicket.svelte — la carte d'un ticket dans une liste, dépliable, et ses
  trois modes : lecture, correction (édition), nouvelle entrée (évolution).

  ## Pourquoi ce composant (17/08/2026, #431)

  `tickets/+page.svelte` rendait cette carte DEUX FOIS — une fois pour la liste
  active, une fois pour la section des tickets clos —, soit **115 lignes
  recopiées**, fil de suivi compris. Les deux copies avaient déjà divergé de trois
  façons, toutes invisibles à la relecture :

    • le badge NEW n'existait que sur la première ;
    • le bouton ✏️ *Modifier* n'existait que sur la première, sans que rien ne
      dise pourquoi un administrateur le perdrait au bout de sept jours ;
    • le fil de suivi y était réécrit intégralement, deux fois.

  Une carte, un fichier. La seule différence retenue est l'**allure d'archive**
  (`archive`) : la carte s'atténue. Elle est portée en prop jusqu'à `CarteListe`,
  qui la rend comme toute carte archivée du site — une classe posée par la page
  sur le balisage d'un composant enfant ne serait **pas atteinte** par le
  `<style>` de la page (panne des pastilles nues, v2.67.11). Elle avait son
  propre rendu (`.history-item` : liseré gris, sans le filet de `.carte-liste`)
  jusqu'au 10/10/2026.

  ## Les formulaires vivent ICI, et pas dans un slot

  Première écriture, la carte exposait un slot `formulaire` et la page y branchait
  `FormulaireTicket` et `EvolForm`. Ce câblage-là aurait été recopié deux fois —
  la duplication supprimée d'un côté serait revenue de l'autre, en plus discret.
  La carte porte donc ses trois modes ; la page ne garde que la décision (*quel
  ticket, quel mode*) et les appels d'API.

  📦 Depuis le 12/10/2026 (#1860), ce qui ne s'affiche qu'une fois la carte
  DÉPLIÉE — la fiche de lecture, le fil, les trois panneaux — vit dans
  `CorpsCarteTicket`, chargé au geste et préchargé à l'approche de la main :
  la page Affaires ne le télécharge plus à l'ouverture.

  ## L'affichage passe par le squelette de lecture

  Le corps déplié (`CorpsCarteTicket`) n'écrit plus l'ordre de ses notions : `FicheLecture` le lit dans
  la déclaration `TICKET` (`#lib/entites/ticket`). La carte affichait
  *description → photos → périmètre* ; les deux formulaires demandent
  *périmètre → description → photos → documents*. C'est R2, et elle vaut aussi
  pour l'affichage.
-->
<script lang="ts">
	import ChargementDiffere from '#lib/components/ChargementDiffere.svelte';
	import CarteListe from '#lib/components/CarteListe.svelte';
	import BadgeNouveau from '#lib/components/BadgeNouveau.svelte';
	import ApercuTicket from './ApercuTicket.svelte';
	import ExtraitRecherche from './ExtraitRecherche.svelte';
	import EnteteCarte from './EnteteCarte.svelte';
	import PastillesAffaire from './PastillesAffaire.svelte';
	import ActionsTicket from './ActionsTicket.svelte';
	import { currentUser, isAdmin, isCS } from '#lib/stores/auth.ts';
	import { peutCommenter as peutCommenterCe, peutEditer } from '#lib/droits.ts';
	import {
		ticketUrgent,
		attributsNature,
		gouttiereAffaire,
		type GestesTicket,
	} from '#lib/tickets.ts';
	import { type CorrespondanceAffaire, type Ticket, type TicketEvolution } from '#lib/api/index.ts';
	import { nomProprietaire } from '#lib/saisi-pour.ts';

	export let ticket: Ticket;
	//  À QUI l'affaire appartient — le « Saisi pour » s'il existe, l'auteur
	//  sinon. Réactif : la carte se rafraîchit quand le ticket change.
	$: proprietaireNom = nomProprietaire(ticket);
	export let evolutions: TicketEvolution[] = [];
	/** Le fil n'a pas pu être chargé : on le DIT, au lieu d'un fil vide. */
	export let erreurSuivi = '';
	/** Ce qui l'a fait trouver, quand la liste est une recherche (27/09/2026). */
	export let correspondance: CorrespondanceAffaire | null = null;
	export let expanded = false;
	/** Allure d'archive : le ticket est clos depuis plus du délai de grâce. */
	export let archive = false;
	/** Le lecteur peut-il commenter / changer l'état ? (conseil syndical) */
	/** Le lecteur peut-il corriger ou supprimer ? (administrateur) */
	export let peutAdministrer = false;
	/**  Ce que le corps de la carte montre. La page en est propriétaire : elle
	     seule sait qu'un seul formulaire doit être ouvert à la fois.
	     ⚠️ UN seul mode d'évolution (#426) : le geste ne se déclare plus au clic,
	     il se lit dans les pastilles de la section Workflow, celle de l'état
	     courant étant active. */
	/**  `options` : le panneau qui change les SEULES options, sans ouvrir les huit
	 *   sections du formulaire (12/09/2026, demandé à l'écran). Un quatrième mode
	 *   et non un état à part : deux formulaires ouverts en même temps sur la même
	 *   carte n'auraient aucun sens, et `mode` porte déjà cette exclusion. */
	export let mode: 'lecture' | 'edition' | 'evolution' | 'options' = 'lecture';
	/** Le panneau d'options rapides attend-il le serveur ? */
	export let optionsRapidesEnCours = false;

	/** Enregistrement d'une évolution en cours — porté par la page (appel d'API). */
	export let evolutionEnCours = false;
	/**  L'entrée du fil en cours de CORRECTION, `null` si aucune. Portée par la
	 *   page : une seule entrée s'édite à la fois sur tout l'écran, sans quoi
	 *   deux formulaires ouverts ne diraient pas lequel enregistre quoi. */
	export let evolEnEdition: number | null = null;
	/** La correction est-elle en cours d'enregistrement ? */
	export let evolCorrectionEnCours = false;

	//  🔴 Les deux droits, calculés SUR CE TICKET — l'appelant ne peut pas les
	//  fournir : ils dépendent de qui l'a déposé, et une liste en affiche vingt.
	//
	//  Avant, le crayon n'apparaissait JAMAIS à l'auteur ni au « saisi pour »,
	//  que le serveur accepte depuis la v2.85.0.
	//
	//  ⚠️ `peutAdministrer` reste ce qu'il est pour la SUPPRESSION : effacer
	//  définitivement n'est pas éditer, et cela reste réservé à l'admin.
	$: peutEditerCeTicket = peutEditer(ticket, $currentUser?.id, $isAdmin);
	//  Une affaire absorbée n'a plus de Suite : son fil vit dans la principale (#1704).
	$: peutSuivreCeTicket =
		!ticket.fusionnee && peutCommenterCe(ticket, $currentUser?.id, $isAdmin, $isCS);

	/**  Les gestes de la page, en UN objet — le contrat d'`ActualiteEnListe`
	 *   (`GestesTicket`). La carte les relayait en dix-sept événements, que
	 *   `ListeTickets` réécrivait un à un : un oubli y rendait un bouton inerte
	 *   sans un mot (`evol_supprimer`, 18/08/2026). */
	export let gestes: GestesTicket;

	//  📦 Le corps déplié se charge au geste (#1860) : la MÊME fonction le précharge
	//  quand la main s'approche de la carte (`onApprocher`) et le charge au
	//  dépliage — `import()` ne télécharge qu'une fois, le second appel reprend
	//  la même promesse.
	const chargerCorps = () => import('#lib/components/CorpsCarteTicket.svelte');
</script>

<!--  QUAND puis QUOI, dans la colonne de gauche (maquette B, 10/10/2026) : la
      date n'est donc plus passée à l'en-tête — un seul fait, une place. -->
<CarteListe
	id="ticket-{ticket.id}"
	{...gouttiereAffaire(ticket)}
	{expanded}
	urgent={ticketUrgent(ticket)}
	{archive}
	onDeplier={() => gestes.basculer(ticket)}
	onApprocher={chargerCorps}
	{...attributsNature(ticket)}
>
	<!--  Le geste de dépliage vit dans `EnteteCarte` : le TITRE plie, avec un
	      survol qui le dit (18/08/2026). Le conteneur ne porte plus
	      `role="button"` — il interceptait la sélection de texte, et obligeait
	      chaque bouton d'action à un `stopPropagation` pour qu'un clic sur ✏️ ne
	      déplie pas la carte au même instant. -->
	<EnteteCarte titre={ticket.titre} basculable on:toggle={() => gestes.basculer(ticket)}>
		<svelte:fragment slot="titre-suffixe">
			<BadgeNouveau le={ticket.cree_le} />
		</svelte:fragment>
		<!--  🔴 L'EN-TÊTE PORTE LE PÉRIMÈTRE ET LE NUMÉRO (18/08/2026, signalé à
		      l'écran) : *« le périmètre devrait s'afficher dans l'état sous le titre
		      comme pour les actualités. Je ne comprends pas qu'il y ait une
		      différence de comportement, cela devrait être un squelette standard »*.

		      Le ticket était le SEUL des quatre écrans à cartes dépliables à ranger
		      son périmètre dans le corps : actualité, annonce et événement le
		      portaient déjà en tag. L'ordre des tags reprend celui de l'actualité —
		      état, puis 🔹 périmètre, puis les marqueurs, puis l'auteur — pour que
		      deux listes voisines se lisent de la même façon.

		      ⚠️ Le périmètre n'est donc PLUS passé à `FicheLecture` : il s'afficherait
		      deux fois sur la même carte. Le rendu de la section 4 en affichage, c'est
		      l'en-tête — et c'est vrai des quatre entités, ce qui referme l'écart que
		      le lot du calendrier avait laissé ouvert en le nommant.

		      Le NUMÉRO monte aussi : il n'était lisible qu'une fois la carte dépliée,
		      dans son pied, alors que c'est la référence qu'on cite au syndic. -->
		<svelte:fragment slot="tags">
			<!--  La dernière ligne vit dans `PastillesAffaire` (27/09/2026) : c'est la
			      norme, que le fil et l'actualité rendent à l'identique. -->
			<PastillesAffaire affaire={ticket} auteur={proprietaireNom} />
		</svelte:fragment>
		<svelte:fragment slot="actions">
			<ActionsTicket
				{ticket}
				{mode}
				peutSuivre={peutSuivreCeTicket}
				peutEditer={peutEditerCeTicket}
				{peutAdministrer}
				{archive}
				on:repondre={() => gestes.repondre(ticket)}
				on:evoluer_ouvrir={() => gestes.evoluerOuvrir(ticket)}
				on:modifier={() => gestes.modifier(ticket)}
				on:options_ouvrir={() => gestes.optionsOuvrir(ticket)}
				on:supprimer={() => gestes.supprimer(ticket)}
				on:archiver={() => gestes.archiver(ticket)}
			/>
		</svelte:fragment>
		<!--  🔴 L'aperçu passe par l'EN-TÊTE (18/09/2026) : c'est ce qui permet aux
		      pastilles de descendre en dernière ligne, comme sur le fil d'activité.
		      Rendu après `</EnteteCarte>`, il était le FRÈRE de l'en-tête — aucun
		      ordre CSS ne fait passer un élément sous le frère d'un autre parent. -->
		<svelte:fragment slot="apercu">
			{#if !expanded}
				<ApercuTicket {ticket} dansLigne />
				{#if correspondance}
					<ExtraitRecherche {correspondance} archivee={ticket.archivee} />
				{/if}
			{/if}
		</svelte:fragment>
	</EnteteCarte>

	{#if expanded}
		<!--  Le corps ne replie pas la carte : on y saisit, on y clique des
		      vignettes. `role="presentation"` dit que ce conteneur n'est qu'un
		      relais — l'élément interactif, c'est la carte. -->
		<div
			class="carte-corps tk-body"
			role="presentation"
			on:click|stopPropagation
			on:keydown|stopPropagation
		>
			<!--  Le CONTENU seul est différé : le conteneur reste ici, et avec lui le
			      fondu d'entrée de `.carte-corps` — pas de corps qui surgit plein. -->
			<ChargementDiffere charger={chargerCorps}>
				{#snippet contenu(CorpsCarteTicket)}
					<CorpsCarteTicket
						{ticket}
						{evolutions}
						{erreurSuivi}
						{mode}
						{optionsRapidesEnCours}
						{evolutionEnCours}
						{evolEnEdition}
						{evolCorrectionEnCours}
						peutSuivre={peutSuivreCeTicket}
						{gestes}
					/>
				{/snippet}
			</ChargementDiffere>
		</div>
	{/if}
</CarteListe>

<style>
	/*  Conteneur, survol, `expanded` et `urgent` viennent de `.carte-liste`
	    (app.css) : ne vivent ici que ce qui est propre à la carte d'un ticket.

	    ⚠️ `tk-expand` a été RETIRÉE du balisage (#431). Elle y était depuis
	    toujours, sur les deux cartes, et n'était définie NULLE PART qui l'atteigne :
	    sa seule définition vit dans le `<style>` d'`espace-cs`, donc scopée à cet
	    écran-là. Une classe utilisée et jamais définie n'échoue à aucun contrôle —
	    `svelte-check` sait dire qu'un sélecteur défini n'est pas utilisé, pas
	    l'inverse. La retirer ne change rien à l'écran : c'est bien la preuve
	    qu'elle ne faisait rien. */
	/*  L'en-tête vit dans `EnteteCarte` — titre, tags, date, actions et leur repli.
	    Ne reste ici que ce qui est propre à un ticket. */

	.tk-body {
		padding: 0.75rem 1rem 1rem;
		border-top: 1px solid var(--color-border);
	}
</style>
