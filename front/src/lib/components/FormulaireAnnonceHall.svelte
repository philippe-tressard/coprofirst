<!--
  FormulaireAnnonceHall.svelte — la saisie d'une affiche de hall.

  ## Pourquoi ce composant (18/08/2026)

  Extrait d'`espace-cs/+page.svelte` — 3 341 lignes, le pire cas du dépôt (#453).
  Le garde-fou de modularité a refusé que le fichier grossisse pour recevoir deux
  commentaires d'exception, et il avait raison : **tous les autres formulaires du
  site sont des composants** (`FormulaireTicket`,
  `FormulaireSondage`, `FormulaireIdee`, `FormulaireAnnonce`). Celui-ci était le
  dernier écrit à même une page.

  ⚠️ La tentation était de raccourcir les commentaires jusqu'à repasser sous le
  seuil. C'est ce que la règle interdit explicitement — *raboter : ❌ jamais*. Le
  refus disait où le code devait aller, pas combien de lignes il pouvait faire.

  ## Ce qu'il décide, et ce qu'il ne décide pas

  Il rend la saisie et rien d'autre. La page garde l'état (`ahTitre`, `ahMessage`…),
  les appels d'API et la décision d'envoyer — c'est le **pattern A**, celui du
  formulaire d'événement (supprimé avec #1092) : l'état vit dans la page, le composant rend.

  ## L'ordre des sections, et sa seule exception

  Le cadre #430 : 1 titre · 2 format · 4 périmètre · 6 message · 7 photos. Cet
  écran rendait *titre → message → périmètre → format*, soit 1 → 6 → 4 → 2.

  🔴 **Une exception, demandée à l'écran** : « Pré-remplir depuis une actualité »
  reste **avant** le titre. Ce n'est pas une section du cadre — c'est un raccourci
  qui **remplit** le formulaire. Le placer après le titre reviendrait à proposer de
  réécrire ce qu'on vient de saisir.
-->
<script lang="ts">
	import SectionDiffusion from '#lib/components/SectionDiffusion.svelte';
	import { annoncesHall as annoncesHallApi } from '#lib/api/index.ts';
	import SectionDescription from '#lib/components/SectionDescription.svelte';
	import { contexteAssistant, perimetreContexte } from '#lib/assistant.ts';
	import Pastille from '#lib/components/Pastille.svelte';
	import SectionFormulaire from '#lib/components/SectionFormulaire.svelte';
	import SectionPerimetre from '#lib/components/SectionPerimetre.svelte';
	import FichiersUpload from '#lib/components/FichiersUpload.svelte';
	import { fmtDateShort } from '#lib/date.ts';
	import type { SourceAffiche } from '#lib/api/index.ts';
	import EtatListe from '#lib/components/EtatListe.svelte';

	type AhFormat = 'auto' | 'a4' | 'a5' | 'a6' | 'a7';

	//  Liés en deux sens : la page porte leur cycle de vie.
	export let titre = '';
	export let message = '';
	export let perimetre: string[] = [];
	export let format: AhFormat = 'auto';
	export let photos: string[] = [];
	/** Vrai dès qu'une proposition de l'assistant a été appliquée (#1089). */
	export let assisteIA = false;

	/**  Éléments du fil proposés au pré-remplissage — actualités, tickets ET
	 *   événements (10/09/2026). Vide : le bloc ne s'affiche pas. */
	export let pubs: SourceAffiche[] = [];
	export let erreurPubs = '';
	/** La CLÉ de la source (`ticket:12`), pas son id : trois familles, trois numérotations. */
	export let sourceId = '';
	export let formats: { val: AhFormat; label: string }[] = [];
	export let maxPhotos = 2;

	//  ⚠️ Calculs de PRÉSENTATION, remontés de la page (18/08/2026) : combien de
	//  caractères, et quel format en découle. Ils ne servent qu'à l'aide affichée
	//  sous les pastilles — la page, elle, garde la VALIDITÉ, qui commande son
	//  bouton. Le format retenu reste celui que l'API calcule ; ceci n'est qu'une
	//  prévision, et c'est écrit dans l'aide.
	//  🔴 MIROIR des seuils serveur (`app/utils/annonce_hall.py`), recalibrés le
	//  10/09/2026 sur une mesure du taux de remplissage — pas sur une intuition.
	//  Les deux contextes de build interdisent de partager le fichier
	//  (`project_partage_front_api_impossible`) : le seul motif viable est la
	//  copie PLUS un contrôle qui compare les deux.
	//  🔒 `npm run lint:seuils-affiche` échoue si elles divergent.
	const SEUILS: [string, number][] = [
		['A7', 420],
		['A6', 750],
		['A5', 1220],
	];
	//  Avec photo : la galerie prend la place d'une partie du texte, et l'affiche
	//  ne descend pas sous l'A6 (`SEUILS_FORMAT_AVEC_PHOTOS`, même contrôle).
	const SEUILS_AVEC_PHOTOS: [string, number][] = [
		['A6', 520],
		['A5', 860],
	];
	const formatMinPhotos = SEUILS_AVEC_PHOTOS[0][0];

	$: longueur = message.replace(/<[^>]*>/g, '').length + titre.trim().length;
	//  Sans texte, la photo fait l'affiche : elle s'ajuste dans toute la zone sous
	//  le titre (`annonce_hall_photos`, 24/10/2026). L'aide le dit, l'aperçu le montre.
	$: imageSeule = photos.length > 0 && message.replace(/<[^>]*>/g, '').trim().length === 0;
	$: formatPrevu = (() => {
		if (format !== 'auto') return format.toUpperCase();
		const seuils = photos.length ? SEUILS_AVEC_PHOTOS : SEUILS;
		const trouve = seuils.find(([, seuil]) => longueur <= seuil);
		return trouve ? trouve[0] : 'A4';
	})();

	/**  9. DIFFUSION — les TROIS canaux, comme partout ailleurs (#480).
	 *
	 *   🔴 Cet écran portait UNE case, au motif écrit ici même que « WhatsApp et le
	 *   syndic n'ont pas d'objet : une affiche s'imprime et se pose, le conseil
	 *   syndical est le seul destinataire qui en fasse quelque chose ».
	 *   L'arbitrage est renversé — *« Diffusion n'est pas standard : WhatsApp, CS,
	 *   syndic ⇒ utilise l'objet standard »*.
	 *
	 *   ⚠️ Le report était **légitime** : le cadre interdit d'ouvrir un champ que le
	 *   serveur ne consomme pas, et il n'en consommait qu'un sur trois. Les deux
	 *   autres sont consommés depuis le 01/09/2026 — c'est ce qui a permis de poser
	 *   l'objet.
	 *
	 *   Tous décochés par défaut : la valeur par défaut d'un envoi est « ne pas
	 *   envoyer ». */
	export let envoyerCs = false;
	export let envoyerSyndic = false;
	export let partagerWhatsapp = false;
	export let envoyerAuteur = false;
	/** Le nom de l'auteur de l'affiche — il nomme le destinataire de la copie. */
	export let auteurNom = '';

	//  L'APERÇU AVANT ENVOI (#498, branché ici le 01/09/2026).
	//
	//  🔴 Cet écran en était privé DÉLIBÉRÉMENT : tant que le serveur ne consommait
	//  qu'un canal sur trois, un aperçu y aurait montré un envoi qui n'a pas lieu —
	//  le mensonge même que #498 existe pour empêcher. Les trois canaux sont
	//  consommés depuis #480, et la condition est levée.
	//
	//  ⚠️ Brancher l'aperçu demande DEUX gestes, et le second est celui qu'on
	//  oublie : fournir `demanderApercu` NE SUFFIT PAS, il faut s'intercaler dans la
	//  soumission. Le 31/08, l'oubli du second a fait partir une actualité que
	//  personne n'a pu annuler — `npm run lint:apercu` le refuse depuis.
	let refDiffusion: SectionDiffusion | null = null;

	const brouillonApercu = () =>
		annoncesHallApi.apercuDiffusion({
			//  ⚠️ Plus de `publication_id` (23/09/2026) : `sourceId` est une CLÉ
			//  (`ticket:12`), jamais un nombre, et la ligne n'envoyait donc rien
			//  depuis le 10/09. La création ne transmet pas la source non plus :
			//  l'aperçu et l'envoi concordent — sans lien, tous les deux.
			titre: titre.trim(),
			message,
			perimetre_cible: perimetre,
			format_demande: format,
			images: photos,
			envoyer_cs: envoyerCs,
			envoyer_syndic: envoyerSyndic,
			partager_whatsapp: partagerWhatsapp,
			envoyer_auteur: envoyerAuteur,
		});

	/**  Aperçu d'abord si un canal est coché — même patron que `FormulaireActualite`.
	 *   `onCreer` reste l'unique chemin d'écriture. */
	function soumettre() {
		if (!valide) return;
		if (refDiffusion?.ouvrirSiDiffusion()) return;
		refDiffusion?.fermerApercu();
		onCreer();
	}

	export let valide = false;
	export let saving = false;
	export let apercuLoading = false;

	/** La page garde les appels d'API : le composant ne fait que les déclencher. */
	export let onPrefill: (cle: string) => void;
	export let onApercu: () => void;
	export let onCreer: () => void;
	export let onUpload: (f: File) => Promise<string>;
	export let onPhotosChange: () => void;
</script>

<!--  L'EXCEPTION : le pré-remplissage vient avant le titre. Voir l'en-tête. -->
{#if erreurPubs}
	<EtatListe compact erreur={erreurPubs} />
{:else if pubs.length}
	<div class="field">
		<label for="ah-source">Pré-remplir depuis le fil d'actualité</label>
		<select
			id="ah-source"
			value={sourceId}
			on:change={(e) => onPrefill((e.currentTarget as HTMLSelectElement).value)}
		>
			<option value="">— Saisie libre —</option>
			<!--  📌 sur les épinglées : sans lui, une actualité vieille de trois mois
			      apparaîtrait au milieu des récentes sans qu'on comprenne pourquoi —
			      elle est là PARCE QU'elle est épinglée, et ça se dit (10/09/2026). -->
			<!--  La FAMILLE est dite, parce que trois s'y mêlent désormais : un
			      titre seul ne dit pas si l'on reprend une actualité, un ticket ou
			      un événement — et on ne rédige pas une affiche pareil selon le cas. -->
			{#each pubs as source (source.cle)}
				<option value={source.cle}
					>{source.epingle ? '📌 ' : ''}{source.famille} · {fmtDateShort(source.date)} · {source.titre}</option
				>
			{/each}
		</select>
	</div>
	<p class="aide">
		Reprend le titre, le contenu et le périmètre de l'élément — et ses images s'il s'agit d'une
		actualité. Tout reste modifiable ci-dessous : l'affiche est indépendante de son origine. Toutes
		les <strong>actualités, affaires et événements</strong> encore au fil sont proposées, les
		<strong>épinglés</strong> (📌) en tête ; les archivés et les contenus confidentiels ne le sont pas.
	</p>
	<hr class="separateur-prefill" />
{/if}

<!--  1. Titre. `SectionFormulaire` porte le filet discret qui sépare les
      sections — celui de Tickets, demandé à l'écran le 18/08/2026. La section
      n'ayant qu'UN champ, son titre EST le libellé du champ (R3). -->
<SectionFormulaire premiere titre="Titre" requis rempli={!!titre?.trim()} pour="ah-titre">
	<div class="field champ-large">
		<input
			id="ah-titre"
			type="text"
			bind:value={titre}
			maxlength="120"
			placeholder="Ex : Coupure d'eau — mardi 4 août"
		/>
	</div>
</SectionFormulaire>

<!--  2. Champs spécifiques : le format de l'affiche. -->
<SectionFormulaire titre="Format">
	<!--  🔴 `Pastille`, PAS `<button class="pill">` (18/08/2026, signalé à l'écran :
	      « le format est illisible »). En sortant ce balisage de la page, j'y ai laissé
	      `.pill` et `.pill-active` : les pastilles sont parties NUES en production —
	      des rectangles collés, « Auto|A4|A5|A6 ».
	
	      C'est mot pour mot la régression v2.67.11, celle que ce dépôt cite dans une
	      dizaine de commentaires, et je l'ai commise en déplaçant du balisage. Écrire
	      la règle ne suffit pas : seul un composant qui porte son style AVEC son
	      balisage l'empêche, et c'est très exactement la raison d'être de `Pastille`. -->
	<div class="perimetre-pills">
		{#each formats as f (f.val)}
			<Pastille petite active={format === f.val} on:click={() => (format = f.val)}
				>{f.label}</Pastille
			>
		{/each}
	</div>
	<p class="aide">
		{#if format === 'auto'}
			Le plus petit format qui accueille le texte et les photos est retenu, pour occuper le moins de
			place possible dans l'afficheur du hall. Sous l'A4, des pointillés de découpe sont tracés sur
			l'affiche.
		{:else}
			Format imposé — le message sera mis en page en {format.toUpperCase()}.
		{/if}
		<strong>Prévu : {formatPrevu}</strong>
		{#if imageSeule}
			— photo seule, ajustée à la zone sous le titre.
		{:else}
			({longueur} caractère{longueur > 1 ? 's' : ''} — titre et message)
		{/if}
	</p>
</SectionFormulaire>

<!--  4. Périmètre — `SectionPerimetre`, la section de toutes les entités (#1329) :
      c'était une section SANS titre, et un sélecteur titré « Périmètre
      d'affichage » à la main. -->
<SectionPerimetre idPrefixe="ah" bind:perimetre>
	<!--  ⚠️ CETTE AIDE A MENTI DEUX FOIS EN UN JOUR, dans les deux sens, et c'est
	      instructif : elle annonçait d'abord un envoi automatique (vrai jusqu'au matin
	      du 18/08), puis « aucun message n'est envoyé » — écrit quand l'envoi a été
	      retiré, et devenu faux **quelques heures plus tard** avec la section
	      Diffusion.
	
	      Une aide qui décrit le COMPORTEMENT d'un autre champ vieillit à chaque fois
	      que ce champ bouge, sans que rien ne le signale. Elle ne dit donc plus que ce
	      dont elle répond : à quoi sert le périmètre. L'envoi se lit là où il se
	      décide — dans la section Diffusion, qui porte sa propre aide. -->
	<p class="aide" slot="aidePerimetre">Imprimé sur l'affiche : il dit où elle doit être posée.</p>
</SectionPerimetre>

<!--  6. Description — le texte affiché sur l'affiche (#1089, arbitré le 20/09/2026).
      Elle s'appelait « Message » et montait un éditeur à la main : c'était le seul
      formulaire à Description privé de l'assistant IA — celui d'une affiche lue par
      toute la résidence. Le champ garde son nom technique (`message`) côté API. -->
<SectionDescription
	idPrefixe="ah"
	requis={photos.length === 0}
	placeholder="Rédigez l'annonce telle qu'elle sera affichée…"
	bind:valeur={message}
	assistant={contexteAssistant('annonce de hall', { Périmètre: perimetreContexte(perimetre) })}
	bind:titreObjet={titre}
	bind:assisteIA
/>

<!--  « Pièces jointes », le nom de la section 8 depuis #1095 (#1329) : l'affiche
      n'accepte que des photos, et l'aide le dit. Écrit en clair, et non lu dans
      `SECTIONS_LIBELLE` : l'affiche est HORS cadre (`lint:intitules-section`),
      et lire la table la ferait juger comme une entité déclarée. -->
<SectionFormulaire titre="Pièces jointes" pour="ah-photos">
	<!--  7. Photos. Le champ n'écrit PAS son intitulé : la section le porte déjà,
	     et `FichiersUpload` en pose un par défaut (« Photos ») — on lisait donc le
	     mot deux fois, en deux typographies. C'est la règle que `SectionFormulaire`
	     écrit noir sur blanc depuis le 16/08 (une section à UN champ ne répète pas
	     son nom) ; seul cet écran l'avait manquée. Signalé par l'utilisateur. -->
	<FichiersUpload
		id="ah-photos"
		bind:urls={photos}
		max={maxPhotos}
		mode="photos"
		titre=""
		upload={onUpload}
		on:change={onPhotosChange}
	/>
	<p class="aide">
		Des photos, {maxPhotos} au maximum, entières (jamais rognées). Avec une description, elles se placent
		en pied d'affiche et le texte reste l'élément central ; sans description, elles occupent toute la
		zone sous le titre. Une affiche avec photo ne descend jamais sous l'{formatMinPhotos}.
	</p>
</SectionFormulaire>

<!--  ⚠️ PAS de `<SectionFormulaire titre="Diffusion">` autour : `SectionDiffusion`
      pose DÉJÀ sa propre section du même nom. L'envelopper affichait deux bandes
      « DIFFUSION » l'une sous l'autre — signalé à l'écran le 02/09/2026, capture à
      l'appui.

      🔴 TROISIÈME fois que ce défaut est signalé, et la PREMIÈRE depuis que
      `lint:titres` existe : son contrôle tenait la liste des composants porteurs
      À LA MAIN, et `SectionDiffusion` n'y était pas. Elle est calculée depuis. -->
<!--  🔴 L'OBJET DIFFUSION, et non trois cases écrites ici (#480).

      Cet écran portait UNE case. L'argument était réel — une affiche s'imprime
      et se pose — mais il décidait à la place du CS : rien n'empêche de vouloir
      prévenir le syndic, ou d'annoncer sur le groupe qu'une affiche est posée.

      ⚠️ Le lien envoyé sur WhatsApp pointe l'ACTUALITÉ dont l'affiche est
      tirée, quand il y en a une. Une affiche autonome part sans lien :
      l'historique des affiches est un écran d'administration, et y envoyer les
      résidents leur donnerait un 403. -->
<SectionDiffusion
	avecCanaux
	compact
	idPrefixe="ah-diffusion"
	bind:this={refDiffusion}
	bind:whatsapp={partagerWhatsapp}
	bind:syndic={envoyerSyndic}
	bind:cs={envoyerCs}
	bind:auteur={envoyerAuteur}
	{auteurNom}
	aideWhatsapp="Le groupe reçoit le titre, le message et un lien vers l'actualité d'origine — jamais le PDF."
	demanderApercu={brouillonApercu}
	envoiEnCours={saving}
	on:envoyer={() => onCreer()}
/>
<p class="aide">
	L'affiche est générée dans tous les cas et reste téléchargeable depuis l'historique. Le conseil
	syndical reçoit le PDF en pièce jointe, pour impression — et seuls les conseillers du périmètre
	visé sont prévenus.
</p>

<div class="form-actions">
	<button
		type="button"
		class="btn btn-outline"
		disabled={!valide || apercuLoading}
		on:click={onApercu}
	>
		{apercuLoading ? 'Génération…' : 'Aperçu'}
	</button>
	<!--  🔴 « Générer une affiche » (18/08/2026, demandé à l'écran : « Créer et
	      envoyer au CS me semble bizarre »). Le bouton nommait le DESTINATAIRE et le
	      transport ; ce qu'on fait ici, c'est PRODUIRE une affiche — l'envoi au CS
	      en est la conséquence, et l'aide du périmètre le dit déjà.

	      ⚠️ Exception assumée à « le bouton dit Enregistrer, partout »
	      (ux-patterns §9 quinquies bis) : cet écran ne crée pas un objet qu'on
	      retrouvera dans une liste, il FABRIQUE un document à imprimer. Même
	      famille que les imports, déjà hors périmètre de la règle. -->
	<button type="button" class="btn btn-primary" disabled={!valide || saving} on:click={soumettre}>
		{saving ? 'Génération…' : 'Générer une affiche'}
	</button>
</div>

<style>
	/*  Le balisage part avec ses styles : une classe posée ici et définie dans la
	    page ne serait pas atteinte (panne des pastilles nues, v2.67.11). */
	/*  ⚠️ Ces deux règles vivaient dans la page, sous `.ah-form label` et
	    `.ah-form input`. Elles sont parties avec le balisage qu'elles habillent :
	    `svelte-check` les a signalées orphelines dès l'extraction, ce qui a dit
	    exactement ce qui appartenait à ce composant. Sans ce déplacement, les
	    libellés seraient partis nus en production (v2.67.11).

	    ⚠️ NOMMÉES, jamais nues : `label { … }` a été refusé par `lint:styles`, et à
	    raison — il aurait atteint TOUS les `<label>` du composant, y compris ceux
	    d'un champ ajouté plus tard par quelqu'un qui ne lit pas ce bloc. C'est le
	    défaut qui avait étiré les cases à cocher du sondage (16/08/2026). */
	/*  `.ah-label-espace` a disparu : l'espacement entre sections est celui de
	    `SectionFormulaire`, une seule fois pour tout le site. */
	/*  Une case et son libellé. Le `width:auto` annule le `width:100%` des champs
	    de saisie — sans lui, la case s'étire et repousse son texte à l'autre bout
	    de la ligne (défaut signalé sur le sondage ET l'annonce, 16/08/2026). */
	/*  Le filet qui sépare le raccourci de pré-remplissage du formulaire lui-même.
	    Il était posé en `style=` en ligne — nommé ici, il cesse d'être à réécrire. */
</style>
