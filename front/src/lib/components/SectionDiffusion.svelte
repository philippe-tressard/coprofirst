<!--
  **La section 9 — Diffusion** : qui verra cette entrée, et par quels canaux.

  Message interne · groupe WhatsApp / syndic / conseil syndical · adresse externe.

  ## Pourquoi ce composant (#498, 19/08/2026)

  Arbitré à l'écran : *« C'est une évolution sur l'objet Diffusion, qu'il soit
  positionné sur n'importe quel formulaire. »*

  La Diffusion est un **objet du site**, pas un bloc de formulaire : elle se rend
  partout pareil (R3 du cadre #430), et tout ce qu'on lui ajoute doit atteindre
  les neuf écrans qui la portent. Elle était écrite dans `EvolForm` d'un côté et
  dans `ChampsCommuns` de l'autre — deux écritures d'une même notion, donc deux
  valeurs libres de diverger, ce qui est exactement arrivé aux canaux avant que
  `CanauxNotification` ne les réunisse (08/08/2026).

  ⚠️ **`CanauxNotification` ne suffisait pas** : il porte les trois cases, pas la
  section qui les entoure — son titre, le message interne, l'adresse externe, et
  l'avertissement sur les fichiers WhatsApp. C'est ce reste-là qui divergeait.

  ## Ce que ce composant ne fait PAS

  Il ne décide pas de l'envoi et ne compose aucun message : il rend des cases.
  L'aperçu de ce qui partira vit dans `ApercuDiffusion.svelte`, et la composition
  côté serveur — un aperçu reconstruit ici mentirait à la première évolution d'un
  gabarit (`standards/04` §14).
-->
<script lang="ts">
	import { SECTIONS_LIBELLE } from '#lib/entites/types.ts';
	import SectionFormulaire from '#lib/components/SectionFormulaire.svelte';
	import CanauxNotification from '#lib/components/CanauxNotification.svelte';
	import ApercuDiffusionModale from '#lib/components/ApercuDiffusion.svelte';
	import { creerApercu } from '#lib/apercu.ts';
	import type { ApercuDiffusion } from '#lib/api/index.ts';
	import { createEventDispatcher } from 'svelte';

	const dispatch = createEventDispatcher<{ envoyer: void }>();

	/** Préfixe des `id` : plusieurs formulaires coexistent souvent à l'écran. */
	export let idPrefixe = 'diffusion';
	/** Les trois canaux — liés par l'appelant, qui seul sait ce qu'ils déclenchent. */
	export let whatsapp = false;
	export let syndic = false;
	export let cs = false;
	/**  « M'envoyer une copie » — la quatrième case de `CanauxNotification`, qui en
	 *   porte le pourquoi. Transmise, jamais décidée ici : cette section est un
	 *   relais, et c'est l'écran qui sait quoi en faire à l'envoi. */
	/**  🔴 UNE SEULE CHARGE UTILE POUR LES QUATRE CANAUX, dans l'écran appelant.
	 *
	 *   Les canaux voyagent souvent dans PLUSIEURS charges utiles d'un même
	 *   écran — l'aperçu, la création, la mise à jour. `FormulaireActualite` en
	 *   avait trois, et l'ajout de `envoyer_auteur` a dû être fait trois fois. Une
	 *   quatrième oubliée, et le canal s'affiche sans jamais partir : c'est le
	 *   défaut corrigé le 31/08/2026, sur cinq écrans à la fois.
	 *
	 *   Le remède tient en une ligne : un objet `canaux` réactif, répandu par
	 *   `...canaux` dans chaque charge utile.
	 *
	 *   ⚠️ Les canaux partent AUSSI à la mise à jour, et c'est voulu : le serveur
	 *   n'envoie que sur la TRANSITION décoché → coché, donc réenregistrer sans y
	 *   toucher ne rejoue rien. C'est ce qui rend l'édition sûre (cadre, 18/08). */
	export let auteur = false;
	/**  Le nom de l'auteur de l'objet, relayé jusqu'à la case « Envoyer une copie
	 *   à … ». Relais pur : ce composant ne sait pas non plus qui a écrit
	 *   l'objet — seul l'écran tient l'objet. */
	export let auteurNom = '';
	/** Afficher les trois cases de canal. */
	export let avecCanaux = false;
	/** Afficher le champ d'adresse externe (CS/admin). */
	export let avecEmailExterne = false;
	export let emailExterne = '';
	/**  Proposer « Message interne ». C'est une décision de DIFFUSION — qui voit
	     cette entrée —, donc elle est rendue ici, avec les canaux, et non au
	     milieu du commentaire comme le faisait le formulaire de réponse écrit à
	     la main de la fiche d'un ticket (#431). */
	export let avecInterne = false;
	export let interne = false;
	/**  Pièces jointes de l'entrée : sert uniquement à savoir s'il faut avertir
	     que WhatsApp ne les emporte pas. */
	export let fichiers: string[] = [];
	/** Infobulle propre au contexte, passée telle quelle à `CanauxNotification`. */
	export let aideWhatsapp = '';
	/**  Motif interdisant le groupe WhatsApp — relayé tel quel, la règle vit
	 *   dans `CanauxNotification` (voir sa documentation). */
	export let whatsappInterdit = '';

	/**  🔴 L'envoi que ce panneau NE COMMANDE PAS (#1147, 22/09/2026).
	 *
	 *   Une affaire notifie le conseil syndical à sa création, quelles que soient
	 *   les cases ci-dessous. Rien ne le disait, et un envoi qu'aucune case ne
	 *   montre est un envoi qu'on découvre dans sa boîte : signalé à l'écran
	 *   comme une anomalie, alors que le comportement était voulu depuis le
	 *   08/09/2026 (*« un conseiller qui n'ouvre pas le site ne voyait jamais
	 *   passer un signalement »*).
	 *
	 *   ⚠️ Ce n'est pas une case : il n'y a rien à régler ici. Le destinataire,
	 *   lui, le règle dans SON profil — c'est ce que la phrase dit. */
	export let avecNotificationCs = false;
	/** Rendu en version dense (fil d'évolution, devis). */
	export let compact = false;

	/**  🔴 L'APERÇU APPARTIENT À L'OBJET DIFFUSION (#498, 20/08/2026).
	 *
	 *   Question posée à l'écran : *« je ne comprends pas qu'une fonction dans un
	 *   objet ne soit pas accessible sur toutes ses implémentations »*. Elle était
	 *   fondée. L'aperçu existait — endpoint, composant, tests — mais il vivait
	 *   chez DEUX appelants (`FormulaireTicket`, `EvolForm`), écrit deux fois,
	 *   et zéro fois ici. Un écran qui posait cet objet obtenait trois cases et
	 *   rien d'autre : il n'y avait **rien à hériter**.
	 *
	 *   C'est la classe de défaut du cadre #430 appliquée à un GESTE plutôt qu'à
	 *   un champ — et le miroir de #505 : là un geste s'affichait sans exister,
	 *   ici il existait sans pouvoir se propager.
	 *
	 *   L'appelant fournit la FONCTION (chaque entité a son endpoint), l'objet
	 *   porte l'état, la modale et les trois sorties. Absente = pas d'aperçu, et
	 *   c'est le comportement des sept écrans qui n'en ont pas encore. */
	export let demanderApercu: (() => Promise<ApercuDiffusion>) | null = null;
	/** Passé à la modale : elle grise « Envoyer » pendant l'enregistrement. */
	export let envoiEnCours = false;

	//  Le store vit ICI, plus dans chaque formulaire. `#lib/apercu` était déjà
	//  partagé ; c'est son BRANCHEMENT qui était recopié.
	const apercu = creerApercu(() => {
		if (!demanderApercu) throw new Error('Aperçu non disponible sur cet écran.');
		return demanderApercu();
	});

	/**  Appelé par le formulaire au moment de soumettre. Rend `true` si l'aperçu
	 *   s'ouvre — le formulaire s'arrête alors et attend la confirmation.
	 *
	 *   ⚠️ L'aperçu s'intercale dans la SOUMISSION, il n'est pas un bouton à part :
	 *   c'est ce qui garantit qu'on ne peut pas diffuser sans avoir vu. Le geste
	 *   reste donc déclenché par le formulaire, l'objet ne fait que le porter.
	 *
	 *   Il ne s'interpose QUE si un canal est coché : sans canal il n'y a rien à
	 *   montrer, et une modale de plus serait une étape gratuite. « Un canal
	 *   est-il coché ? » se lit ICI, sur les cases que ce composant porte — les
	 *   trois formulaires hôtes le recalculaient chacun (26/09/2026, #1342). */
	export function ouvrirSiDiffusion(): boolean {
		if (!demanderApercu || !(avecCanaux && (whatsapp || syndic || cs))) return false;
		void apercu.ouvrir();
		return true;
	}

	/** Fermer depuis le parent (après enregistrement, ou sur annulation). */
	export function fermerApercu(): void {
		apercu.fermer();
	}

	$: visible = avecCanaux || avecEmailExterne || avecInterne;

	/** Repliée par défaut — la valeur vient de la déclaration (#1095). */
	export let pliable = false;

	/**  🔴 Le résumé dit ce qui PART, et « rien » quand rien ne part. C'est la
	 *   section la plus lourde de conséquences du formulaire : la replier sans
	 *   dire son état laisserait un envoi se préparer sans qu'on le voie. */
	$: nbCanaux = [whatsapp, syndic, cs, auteur].filter(Boolean).length;
	$: resume = nbCanaux === 0 ? "rien ne part à l'extérieur" : `${nbCanaux} envoi(s) prévu(s)`;
	/** Le motif d'extinction de la section, ou `''` (`inactivePour`, #1191). */
	export let inactive = '';
</script>

{#if $apercu.ouvert}
	<ApercuDiffusionModale
		apercu={$apercu.donnees}
		chargement={$apercu.chargement}
		envoi={envoiEnCours}
		on:envoyer={() => dispatch('envoyer')}
		on:retour={apercu.fermer}
		on:annuler={apercu.fermer}
	/>
{/if}

{#if visible}
	<!-- ── 9. Diffusion — EN DERNIER, après les pièces jointes ──────────────
	     L'avertissement sur les fichiers est rendu au CONTACT de la case WhatsApp
	     qu'il commente : sous le sélecteur de fichiers, il en était séparé par
	     toute la rubrique (#416). -->
	<SectionFormulaire
		titre={SECTIONS_LIBELLE.diffusion}
		{inactive}
		{pliable}
		{resume}
		valeurModifiee={nbCanaux > 0}
	>
		<!--  Les options propres à l'écran (épingler, brouillon, afficher au fil…)
		      passent AVANT les canaux : elles décident de ce qui est PUBLIÉ, les
		      canaux de qui en est prévenu. Ce slot existait dans la seconde
		      implémentation de cette section (`ChampsCommuns`) ; il rejoint l'objet
		      avec elle (#498). -->
		<slot name="options" />
		{#if avecInterne}
			<label class="case-interne">
				<input type="checkbox" bind:checked={interne} />
				<span>Message interne (visible par le conseil syndical uniquement)</span>
			</label>
		{/if}

		{#if avecCanaux}
			<CanauxNotification
				bind:whatsapp
				bind:syndic
				bind:cs
				bind:auteur
				{auteurNom}
				{compact}
				{aideWhatsapp}
				{whatsappInterdit}
			/>
			<!--  🔴 L'aide propre au contexte est AFFICHÉE, plus seulement en infobulle.
			      `CanauxNotification` en fait un `title=` — invisible au doigt, invisible
			      au lecteur d'écran tant qu'on ne survole pas. Or sur une actualité
			      confidentielle, elle dit « le message ne portera ni le titre ni le
			      contenu » : c'est une conséquence que l'auteur doit lire.
			      Deux poids deux mesures dans la même section, signalé à l'écran le
			      28/08/2026 — l'annonce de hall explique en clair, juste au-dessus.

			      ⚠️ Conditionnée à `whatsapp`, comme l'avertissement sur les fichiers
			      dix lignes plus bas : une aide qui décrit un envoi DÉCRIT UN ACTE, et
			      un acte qu'on n'a pas demandé n'a pas à être commenté. Ma première
			      version l'affichait toujours — signalé à l'écran le même jour, et le
			      motif était déjà là, chez le voisin. -->
			{#if whatsapp && aideWhatsapp}
				<p class="aide sous-case">{aideWhatsapp}</p>
			{/if}
			{#if whatsapp && fichiers.length > 0}
				<p class="aide sous-case">
					⚠️ Les fichiers ne sont pas envoyés via WhatsApp, uniquement le texte.
				</p>
			{/if}
		{/if}

		{#if avecNotificationCs}
			<p class="aide sous-case">
				ℹ️ En plus de ces cases, chacun est prévenu selon les réglages de son profil — dont le
				conseil syndical du périmètre pour chaque nouvelle affaire.
			</p>
		{/if}

		{#if avecEmailExterne}
			<div class="field champ-large">
				<label for="{idPrefixe}-email-ext">&#x1F4E7; Notifier une adresse email externe</label>
				<input
					id="{idPrefixe}-email-ext"
					type="email"
					bind:value={emailExterne}
					placeholder="contact@exemple.fr"
				/>
			</div>
		{/if}
	</SectionFormulaire>
{/if}

<style>
	/*  Définie ICI, avec le balisage qu'elle habille : `.checkbox-field` n'est pas
	    une classe d'`app.css` — chaque composant qui l'emploie la style lui-même,
	    et une classe seulement utilisée arrive nue à l'écran (v2.67.11). */
	.case-interne {
		display: flex;
		align-items: center;
		gap: 0.4rem;
		cursor: pointer;
		font-size: var(--fs-md);
		margin: 0 0 0.6rem;
	}
	.case-interne input[type='checkbox'] {
		width: auto;
		margin: 0;
		flex-shrink: 0;
	}
	/*  Sous 480 px, la cible tactile d'une case ne faisait que 16 à 18 px de haut
	    (socle 11 §10). */
	@media (max-width: 480px) {
		.case-interne {
			min-height: 44px;
		}
	}
</style>
