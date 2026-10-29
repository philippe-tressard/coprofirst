<!--
  **Voir ce qui partira, avant de confirmer** — l'e-mail rendu dans son gabarit et
  le message WhatsApp tel qu'il sera composé.

  POURQUOI CE COMPOSANT (#498, 19/08/2026). Demandé à l'écran : *« avant la
  diffusion il faudrait voir le mail (aperçu) avant de confirmer son envoi »*,
  puis *« partout où l'objet diffusion par mail est concerné »*, puis *« l'aperçu
  peut-il aussi englober WhatsApp ? »*. Jusqu'ici on cochait une case et on
  découvrait le résultat en le recevant — quand on faisait partie des destinataires.

  🔴 **Rien n'est composé ici.** Le serveur rend le message avec les MÊMES
  fonctions que l'envoi (`composer_email`, `construire_message`) ; ce composant ne
  fait que l'afficher. Un aperçu reconstruit côté écran deviendrait faux à la
  première évolution d'un gabarit, et personne ne s'en apercevrait — puisque c'est
  justement l'aperçu qu'on regarderait pour le vérifier (`standards/04` §14).

  ## Trois issues, et « Retour au formulaire » n'est pas « Annuler »

  Arbitrage du 19/08 : *« si l'aperçu de ce qui sera expédié est correct alors
  envoi, sinon annulation ou retour au formulaire »*. Les deux sorties sont donc
  distinctes — revenir au formulaire **garde la saisie intacte**, annuler ferme
  tout. Un aperçu qui fait perdre le brouillon serait pire que pas d'aperçu.

  ## Ce que l'aperçu ne peut pas savoir, et qu'il DIT

  Le ticket n'existe pas encore : son **numéro** et son **lien permanent** sont
  attribués à la création. Ils sont nommés en pied de modale plutôt qu'inventés.
  Et sur WhatsApp, la ligne « 📷 Photos à voir sur le site » n'apparaît que si
  l'encodage de la photo échoue à l'envoi : l'aperçu montre *le message tel qu'il
  sera composé*, pas *ce que le groupe recevra à coup sûr*.
-->
<script lang="ts">
	import Modale from '#lib/components/Modale.svelte';
	import { createEventDispatcher } from 'svelte';
	import Icon from '#lib/components/Icon.svelte';
	import EncartAvertissement from '#lib/components/EncartAvertissement.svelte';
	import type { ApercuDiffusion } from '#lib/api/index.ts';

	export let apercu: ApercuDiffusion | null = null;
	/** Chargement en cours côté serveur. */
	export let chargement = false;
	/** L'envoi est en cours : le bouton principal se verrouille. */
	export let envoi = false;

	const dispatch = createEventDispatcher<{
		envoyer: void;
		retour: void;
		annuler: void;
	}>();

	$: canaux = apercu?.canaux ?? [];
	//  Un canal coché mais inactif est le cas qui justifie cet écran : le bridge
	//  est éteint, ou personne n'est joignable. On l'annonce avant l'envoi.
	$: inactifs = canaux.filter((c) => !c.actif);
	$: rienNePartira = canaux.length > 0 && inactifs.length === canaux.length;
</script>

<Modale
	titre="📤 Avant d'envoyer"
	styleBoite="max-width:720px;width:100%"
	on:fermer={() => dispatch('annuler')}
>
	<p class="apercu-intro">Voici ce qui partira, tel que les destinataires le recevront.</p>

	{#if chargement}
		<p class="apercu-attente">Composition du message…</p>
	{:else if canaux.length === 0}
		<div class="empty-state">
			<h3>Aucun canal de diffusion coché</h3>
			<p>L'affaire sera créée sans notification.</p>
		</div>
	{:else}
		{#each canaux as canal (canal.canal)}
			<section class="apercu-canal" class:apercu-canal-inactif={!canal.actif}>
				<h3 class="apercu-canal-titre">
					{#if canal.canal === 'whatsapp'}
						<Icon name="whatsapp" size={18} /> Groupe WhatsApp
					{:else}
						<span class="ico" aria-hidden="true">&#x2709;&#xFE0F;</span> E-mail
					{/if}
					{#if canal.actif}
						<span class="badge badge-green">Partira</span>
					{:else}
						<span class="badge badge-red">Ne partira pas</span>
					{/if}
				</h3>

				{#if !canal.actif}
					<p class="apercu-motif">{canal.inactif_motif}</p>
				{:else}
					<p class="apercu-destinataires">
						<strong>À :</strong>
						{canal.destinataires.join(' · ')}
					</p>
				{/if}

				<!--  Ceux que le canal visait et qui ne recevront rien, avec le motif
				      (#2006) : l'aperçu annonçait deux membres du conseil que l'envoi
				      écartait ensuite, sans un mot. -->
				{#if canal.ecartes?.length}
					<div class="apercu-ecartes">
						<EncartAvertissement role="note">
							<strong>Ne recevront rien :</strong>
							<ul>
								{#each canal.ecartes as ecarte, i (i)}
									<li>{ecarte.qui} — {ecarte.motif}</li>
								{/each}
							</ul>
						</EncartAvertissement>
					</div>
				{/if}

				{#if canal.actif}
					{#if canal.canal === 'email'}
						{#if canal.sujet}
							<p class="apercu-sujet"><strong>Objet :</strong> {canal.sujet}</p>
						{/if}
						<!--  🔴 Un IFRAME CLOISONNÉ, et non `{@html safeHtml(...)}` (#529).
							      Signalé à l'écran : *« le style de l'aperçu n'est pas celui du
							      mail, plus difficile à valider »*.

							      La cause : `safeHtml` fait son travail. Il retire `<style>`,
							      les attributs `style=`, et n'autorise ni `<table>` ni `<tr>` ni
							      `<td>` — or un e-mail est bâti ENTIÈREMENT de tables et de
							      styles en ligne, seule mise en forme que les clients de
							      messagerie honorent. L'aperçu montrait donc le texte du mail,
							      pas le mail.

							      ⚠️ Et un aperçu qui ne ressemble pas à ce qui partira ne
							      remplit pas son office : on le regarde POUR valider la mise en
							      forme. C'est la règle du projet — observer la chose, pas son
							      approximation (`standards/04` §14).

							      🔒 Le cloisonnement est PLUS strict qu'avant, pas moins :
							      `sandbox` sans `allow-scripts` interdit tout script (là où
							      DOMPurify se contentait de nettoyer), et sans
							      `allow-same-origin` le document n'a accès ni au DOM parent, ni
							      aux cookies, ni au stockage. Le `srcdoc` ne peut donc rien
							      faire d'autre que s'afficher. -->
						<iframe
							class="apercu-corps-cadre"
							title="Aperçu de l'e-mail"
							sandbox=""
							srcdoc={canal.corps_html ?? ''}
						></iframe>
					{:else}
						{#if canal.ampute}
							<p class="apercu-avertissement">
								&#x26A0;&#xFE0F; Ce message partira <strong>sans son contenu</strong> : le groupe est
								commun à toute la copropriété, et le périmètre visé ne s'adresse pas à tous ceux qui le
								liraient.
							</p>
						{/if}
						<pre class="apercu-whatsapp">{canal.texte}</pre>
						<p class="apercu-note">
							{#if canal.avec_photo}
								&#x1F4F7; La première photo accompagnera le message.
							{:else}
								Aucune photo ne partira avec ce message.
							{/if}
						</p>
					{/if}
				{/if}
			</section>
		{/each}

		{#if apercu?.attribues_a_la_creation?.length}
			<p class="apercu-note apercu-attribues">
				Attribués à la création, donc absents de cet aperçu :
				<strong>{apercu.attribues_a_la_creation.join(', ')}</strong>.
			</p>
		{/if}
	{/if}

	<div class="modal-footer">
		<button type="button" class="btn btn-outline" on:click={() => dispatch('annuler')}>
			Annuler
		</button>
		<button type="button" class="btn btn-outline" on:click={() => dispatch('retour')}>
			&#x2190; Retour au formulaire
		</button>
		<button
			type="button"
			class="btn btn-primary"
			disabled={envoi || chargement}
			on:click={() => dispatch('envoyer')}
		>
			{#if envoi}
				Envoi…
			{:else if rienNePartira}
				Créer sans notifier
			{:else}
				Confirmer et envoyer
			{/if}
		</button>
	</div>
</Modale>

<style>
	/*  Le style part avec le balisage : une classe posée ici et définie dans la
	    page hôte ne serait pas atteinte (panne des pastilles nues, v2.67.11), et
	    `npm run lint:classes-nues` le refuse. */
	.apercu-intro {
		font-size: var(--fs-base);
		color: var(--color-text-muted);
		margin: 0 0 1rem;
	}
	.apercu-attente {
		color: var(--color-text-muted);
		font-size: var(--fs-base);
	}
	/*  L'émoji d'en-tête d'un canal, aligné sur l'icône SVG du canal voisin.
	    Défini ICI : `.ico` n'est pas une classe d'`app.css`, et chaque composant
	    qui l'emploie la style lui-même — sinon elle arrive nue (v2.67.11). */
	.ico {
		font-size: 1.05rem;
		line-height: 1;
	}

	.apercu-canal {
		border: 1px solid var(--color-border);
		border-radius: var(--radius);
		padding: 0.85rem 1rem;
		margin-bottom: 0.85rem;
	}
	/*  Un canal qui ne partira pas se lit d'un coup d'œil, sans lire le badge. */
	.apercu-canal-inactif {
		border-left: 4px solid var(--color-danger);
		opacity: 0.9;
	}
	.apercu-canal-titre {
		display: flex;
		align-items: center;
		gap: 0.45rem;
		flex-wrap: wrap;
		font-size: var(--fs-lg);
		font-weight: 600;
		margin: 0 0 0.6rem;
	}
	.apercu-motif {
		font-size: var(--fs-md);
		color: var(--color-danger);
		margin: 0;
	}
	.apercu-destinataires,
	.apercu-sujet {
		font-size: var(--fs-md);
		color: var(--color-text-muted);
		margin: 0 0 0.4rem;
		overflow-wrap: anywhere;
	}
	/*  Le corps de l'e-mail est rendu dans un IFRAME cloisonné : il apporte ses
	    propres styles (tables, couleurs, marges), et c'est le but. La hauteur est
	    FIXE et non `max-height` : un iframe ne s'adapte pas à son contenu depuis
	    l'extérieur, et une hauteur trop courte transforme l'aperçu en fente. */
	.apercu-corps-cadre {
		width: 100%;
		height: 420px;
		display: block;
		border: 1px solid var(--color-border);
		border-radius: 6px;
		background: var(--color-surface);
	}
	/*  Le message WhatsApp se lit en chasse fixe et EN CONSERVANT ses sauts de
	    ligne : c'est exactement ce que le groupe verra, retours compris. */
	.apercu-whatsapp {
		white-space: pre-wrap;
		overflow-wrap: anywhere;
		font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
		font-size: var(--fs-md);
		line-height: 1.5;
		background: var(--color-bg);
		border: 1px solid var(--color-border);
		border-radius: 6px;
		padding: 0.6rem 0.7rem;
		margin: 0;
	}
	.apercu-ecartes {
		margin: 0 0 0.5rem;
	}
	.apercu-ecartes ul {
		margin: 0.2rem 0 0;
		padding-left: 1.2rem;
	}
	.apercu-avertissement {
		font-size: var(--fs-md);
		line-height: 1.5;
		margin: 0 0 0.5rem;
		padding: 0.5rem 0.6rem;
		border-radius: 6px;
		background: var(--color-orange-fond);
		color: var(--color-orange-texte);
	}
	.apercu-note {
		font-size: var(--fs-sm);
		color: var(--color-text-muted);
		margin: 0.4rem 0 0;
	}
	.apercu-attribues {
		margin-top: 0.8rem;
	}

	@media (max-width: 767px) {
		.apercu-corps-cadre {
			height: 300px;
		}
	}
</style>
