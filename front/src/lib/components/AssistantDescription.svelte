<!--
  L'assistant IA de la section Description (#985, 17/09/2026) — retravailler
  le titre et le texte saisis, selon le prompt réglé dans Admin → Assistant IA.

  ## Le geste

  Une icône ✨ **dans la barre de l'éditeur, à droite** (`BoutonAssistant`) ouvre
  ce panneau : un prompt facultatif (« plus court », « plus formel »), le bouton
  qui sollicite, et la PROPOSITION avec « Appliquer » et « Ignorer ». Le
  formulaire ne change qu'à l'application, et rien n'est enregistré tant que
  l'auteur n'enregistre pas. Le geste se rejoue à volonté, chaque appel partant
  du texte COURANT.

  🔴 **Le panneau était ouvert en permanence** jusqu'au 22/09/2026 : deux lignes
  sous l'éditeur, sur les six formulaires qui portent la section Description, pour
  un geste qu'on fait rarement. Signalé à l'écran, capture à l'appui.

  ⚠️ L'état `ouvert` vit ICI et se lie (`bind:`) à `SectionDescription`, qui
  place le bouton dans le slot de l'éditeur. Deux emplacements dans l'arbre, un
  seul état — c'est le minimum de plomberie possible, et c'est pourquoi le
  bouton ne porte QUE la bascule : tout ce qui décide (peut-on solliciter ? que
  répond le serveur ?) reste dans ce fichier.

  ## Ce que l'écran dit, et ce qu'il ne décide pas

  - Il SIGNALE ce qui change (« Titre modifié », « Description modifiée ») pour
    que l'auteur pense à relire — c'est le SERVEUR qui l'a calculé, sur du
    texte normalisé ; comparer du HTML ici dirait « modifié » à chaque espace.
  - Il ne se montre qu'au conseil syndical et à l'administration (`$isCS`), et
    seulement si le serveur dit l'usage disponible (`stores/assistant`). Le
    droit, lui, est tenu par la route : l'icône masquée n'est qu'un confort.
  - Le titre et la description sont LIÉS (`bind:`) : la section Description
    ne connaît pas le titre, c'est le formulaire qui le lui prête pour ce
    geste — et qui le reçoit corrigé par le même lien.
  - `assiste` passe à vrai à l'application : c'est ce que le formulaire envoie
    en `assiste_ia`, et ce que la carte rend ensuite par `MarqueIA`.
-->
<script lang="ts">
	import { isCS, quandAuthResolue } from '#lib/stores/auth.ts';
	import { assistantStore, chargerAssistant } from '#lib/stores/assistant.ts';
	import { assistant as assistantApi, type PropositionDescription } from '#lib/api/index.ts';
	import { messageErreur } from '#lib/erreurs.ts';
	import { safeRichContent } from '#lib/sanitize.ts';
	import { ENTITE_COMMENTAIRE, peutSolliciter, type ContexteAssistant } from '#lib/assistant.ts';
	import { toast } from '#lib/components/Toast.svelte';
	import IconeIA from '#lib/components/IconeIA.svelte';

	/** L'entité et son contexte — composés par le formulaire (`#lib/assistant`). */
	export let contexte: ContexteAssistant;
	/** Préfixe des `id` : plusieurs sections Description coexistent à l'écran. */
	export let idPrefixe: string;
	/** Le titre de l'objet, prêté par le formulaire. Ignoré si `avecTitre` est faux. */
	export let titre = '';
	export let description = '';
	/** Faux sur une entrée de fil : un commentaire n'a pas de titre à proposer. */
	export let avecTitre = true;
	/** Devient vrai quand une proposition est appliquée — lu par le formulaire. */
	export let assiste = false;

	/**  Le panneau est-il déplié ? Lié (`bind:`) à `SectionDescription`, qui pose
	 *   le déclencheur dans la barre de l'éditeur — un autre endroit de l'arbre. */
	export let ouvert = false;
	/**  L'assistant a-t-il lieu d'être ? Calculé ici (rôle + réponse du serveur) et
	 *   RENDU à l'appelant : sans lui, l'icône s'afficherait pour tout le monde et
	 *   n'ouvrirait rien. Sortant seulement — personne ne l'écrit d'en haut. */
	export let visible = false;
	/** Vrai pendant l'appel : l'icône le dit aussi, l'attente ne doit pas être muette. */
	export let enCours = false;

	/** L'`id` du panneau, pour la liaison `aria-controls` du déclencheur. */
	$: idPanneau = `${idPrefixe}-assistant-panneau`;

	let precision = '';

	/**
	 *  Ce que l'auteur peut demander, dans les mots du champ.
	 *
	 *  Sur un COMMENTAIRE, le prompt sait produire une phrase de rappel de
	 *  l'affaire — mais seulement si on la demande. Une capacite qu'aucune
	 *  invite n'annonce n'est employee par personne : l'auteur ne devine pas
	 *  ce qu'un champ libre accepte.
	 */
	$: invitePrecision =
		contexte.entite === ENTITE_COMMENTAIRE
			? 'rappeler le contexte, plus court…'
			: 'plus court, plus formel…';
	let proposition: PropositionDescription | null = null;

	//  🔴 Visible pour le CS seulement, et seulement si le serveur dit oui. Le
	//  store n'est interrogé QUE pour le CS : la route refuse aux autres.
	$: visible = $isCS && $assistantStore?.description === true;
	$: solliciteable = peutSolliciter(avecTitre ? titre : '', description) && !enCours;
	$: rienChange =
		proposition !== null && !proposition.titre_modifie && !proposition.description_modifiee;

	//  Pas `onMount` : il précède le layout qui charge l'utilisateur (#1486).
	quandAuthResolue(() => {
		if ($isCS && $assistantStore === null) void chargerAssistant();
	});

	async function solliciter() {
		if (!solliciteable) return;
		enCours = true;
		try {
			proposition = await assistantApi.description({
				entite: contexte.entite,
				titre: avecTitre ? titre : null,
				description,
				contexte: contexte.contexte,
				precision: precision.trim() || null,
				avec_titre: avecTitre,
			});
		} catch (e) {
			toast('error', messageErreur(e, 'L’assistant n’a pas répondu.'));
		} finally {
			enCours = false;
		}
	}

	function appliquer() {
		if (!proposition) return;
		if (avecTitre && proposition.titre_modifie && proposition.titre) titre = proposition.titre;
		if (proposition.description_modifiee) description = proposition.description;
		if (proposition.titre_modifie || proposition.description_modifiee) assiste = true;
		proposition = null;
	}

	function ignorer() {
		proposition = null;
	}
</script>

{#if visible && ouvert}
	<div class="assistant" id={idPanneau}>
		<div class="assistant-commande">
			<button
				class="btn btn-outline btn-sm"
				type="button"
				disabled={!solliciteable}
				aria-busy={enCours}
				on:click={solliciter}
			>
				<IconeIA {enCours} />
				{enCours ? 'L’assistant travaille…' : 'Retravailler avec l’assistant'}
			</button>
			<!--  🔴 « Précision » ne disait pas ce qu'on attend (signalé à l'écran le
			      22/09/2026). Le champ ne complète pas le texte : il MODULE la réponse
			      de l'assistant — « plus court », « plus formel ». Un libellé qui nomme
			      la chose plutôt que sa place. -->
			<label class="field champ-en-ligne assistant-precision">
				Prompt pour moduler sa réponse
				<input
					id="{idPrefixe}-assistant-precision"
					type="text"
					bind:value={precision}
					maxlength="500"
					placeholder={invitePrecision}
					disabled={enCours}
				/>
			</label>
		</div>
		<p class="aide">
			{#if !solliciteable && !enCours}
				Saisissez un titre ou une description : l’assistant retravaille ce qui est écrit.
			{:else}
				L’assistant propose, vous relisez : rien ne change tant que vous n’appliquez pas. Vous
				pouvez le solliciter plusieurs fois.
			{/if}
		</p>

		{#if proposition}
			<section class="assistant-proposition" aria-label="Proposition de l’assistant">
				<h5 class="assistant-titre">
					Proposition de l’assistant
					{#if proposition.titre_modifie}<span class="badge badge-orange">Titre modifié</span>{/if}
					{#if proposition.description_modifiee}<span class="badge badge-orange"
							>Description modifiée</span
						>{/if}
				</h5>
				{#if rienChange}
					<p class="aide">L’assistant n’a rien changé au texte.</p>
				{:else}
					{#if avecTitre && proposition.titre_modifie && proposition.titre}
						<p class="assistant-titre-propose">{proposition.titre}</p>
					{/if}
					{#if proposition.description_modifiee}
						<!--  `safeRichContent`, pas `safeHtml` : le prompt de l'usage vit en
						      base et l'administrateur peut le réécrire. Le jour où il cesse
						      de demander du HTML, une proposition en texte simple arriverait
						      d'un seul bloc — `safeRichContent` rend ses retours à la ligne.
						      C'est l'assainisseur du cas « riche OU texte », déjà employé
						      partout où la forme n'est pas garantie. -->
						<div class="rich-content assistant-texte">
							{@html safeRichContent(proposition.description)}
						</div>
					{/if}
				{/if}
				<div class="assistant-actions">
					<button class="btn btn-outline btn-sm" type="button" on:click={ignorer}>Ignorer</button>
					{#if !rienChange}
						<button class="btn btn-primary btn-sm" type="button" on:click={appliquer}
							>Appliquer</button
						>
					{/if}
				</div>
			</section>
		{/if}
	</div>
{/if}

<style>
	.assistant {
		margin-top: 0.5rem;
	}
	.assistant-commande {
		display: flex;
		align-items: flex-end;
		gap: 0.6rem;
		flex-wrap: wrap;
	}
	/*  ⚠️ Le libellé est plus PETIT que le titre de section (0.72rem), et c'est
	    délibéré. `label.field` vaut 0.875rem partout : ici, il paraissait donc plus
	    important que « PÉRIMÈTRE » ou « DESCRIPTION » juste au-dessus, alors qu'il
	    nomme un réglage secondaire à l'intérieur d'une section. Signalé à l'écran
	    le 22/09/2026.

	    🔴 La règle générale n'est PAS touchée : un libellé de champ plus gros
	    qu'un titre de section est un défaut de toute la charte, pas de cet écran.
	    Le corriger vaut pour les quarante formulaires à la fois, devant l'écran —
	    c'est une décision d'interface, pas l'effet de bord d'un lot sur l'assistant.

	    La SAISIE, elle, garde sa taille : ce qu'on tape doit rester lisible. */
	.assistant-precision {
		flex: 1 1 14rem;
		margin: 0;
		font-size: var(--fs-2xs);
	}
	.assistant-precision input {
		font-size: var(--fs-base);
	}
	/*  La proposition se lit comme un encart : fond de surface, bordure fine,
	    jamais le fond de saisie — ce n'est pas un champ, on ne l'édite pas ici. */
	.assistant-proposition {
		margin-top: 0.6rem;
		padding: 0.7rem 0.85rem;
		border: 1px solid var(--color-border);
		border-radius: var(--radius);
		background: var(--color-surface);
	}
	.assistant-titre {
		display: flex;
		align-items: center;
		gap: 0.4rem;
		flex-wrap: wrap;
		margin: 0 0 0.5rem;
		font-size: var(--fs-sm);
		font-weight: 700;
	}
	.assistant-titre-propose {
		margin: 0 0 0.4rem;
		font-weight: 600;
	}
	.assistant-texte {
		font-size: var(--fs-base);
		line-height: 1.6;
	}
	.assistant-actions {
		display: flex;
		justify-content: flex-end;
		gap: 0.5rem;
		margin-top: 0.6rem;
	}
</style>
