<!--
  Un USAGE de l'assistant IA dans l'administration (#984, 17/09/2026) : son
  activation, son modèle, son prompt, son plafond de jetons — et un bouton qui
  vérifie que CE modèle parle vraiment.

  ## Un bloc, N usages

  L'onglet rend ce composant une fois par entrée de `GET /config/llm-usages` :
  ajouter un usage côté API ajoute un bloc ici, sans une ligne d'écran. C'est
  la raison d'être de ce composant — deux blocs écrits à la main auraient
  divergé au premier réglage ajouté (le catalogue des modèles, par exemple).

  ## Ce que le bloc décide, et ce qu'il ne décide pas

  - Il ÉCRIT dans `valeurs` (lié) sous les clés que l'usage lui donne
    (`usage.cles`) : c'est l'onglet qui enregistre, en un seul geste, le commun
    et tous les usages. Un bouton par bloc ferait N enregistrements partiels.
  - Le catalogue des modèles est COMMUN (il dépend de la clé, pas de l'usage) :
    il est chargé par l'onglet et passé ici, chaque bloc y choisit le sien.
  - « Rétablir le prompt d'origine » VIDE la clé : le serveur retombe alors sur
    le prompt du code (`config_llm`), et le champ le montre. Écrire l'origine
    dans le champ reviendrait au même — mais la clé porterait une copie qui
    ne suivrait plus le code.
  - Pliable (`<details>`) : Philippe veut « un bloc pliable par usage, il y en a
    deux, peut-être plus à l'avenir ». Et UN SEUL déplié à la fois (#987,
    constaté à l'écran le 17/09/2026) : c'est l'onglet qui tient l'accordéon,
    ce bloc reçoit `ouvert` et signale `basculer`. À l'arrivée sur l'écran,
    **tous** sont repliés — la page ne choisit pas ce qu'on vient lire.
  - Le ✨ à côté du modèle (30/09/2026) cherche le prix du modèle ENREGISTRÉ
    de cet usage dans la grille de son fournisseur, le convertit au taux BCE
    et l'ENREGISTRE — c'est l'exception au « un seul Enregistrer » ci-dessus,
    demandée telle quelle. Les trois prix de « Coût et limites » reprennent
    alors ce que le serveur a écrit. Il ne s'affiche que si l'onglet dit l'usage
    « Tarif d'un modèle » prêt (`tarifDisponible`) — un usage coupé ne montre
    pas d'icône ✨, c'est la règle de tout le produit.
-->
<script lang="ts">
	import { messageErreur } from '#lib/erreurs.ts';
	import IconeIA from '#lib/components/IconeIA.svelte';
	import { createEventDispatcher } from 'svelte';
	import Icon from '#lib/components/Icon.svelte';
	import SectionFormulaire from '#lib/components/SectionFormulaire.svelte';
	import ChoixPastilles from '#lib/components/ChoixPastilles.svelte';
	import CoutUsageIA, { PRIX } from '#lib/components/CoutUsageIA.svelte';
	import EtoileRequis from '#lib/components/EtoileRequis.svelte';
	import {
		assistant as assistantApi,
		config as configApi,
		type LimitesUsageIA,
		type UsageIA,
	} from '#lib/api/index.ts';
	import { memePrompt } from '#lib/promptOrigine.ts';
	import { fmtNombre } from '#lib/utils.ts';
	import { SEPARATEUR } from '#lib/separateurs.ts';

	export let usage: UsageIA;
	/** Toutes les valeurs de configuration, liées : le bloc écrit les siennes. */
	export let valeurs: Record<string, string>;
	/** Le catalogue commun des modèles, chargé par l'onglet. */
	export let catalogue: {
		etat: 'aucun' | 'encours' | 'pret' | 'indisponible';
		motif: string;
		modeles: { id: string; libelle: string }[];
	};
	/** Une clé est-elle enregistrée ? Sans elle, ni catalogue ni test. */
	export let clePosee = false;
	/** Le fournisseur est-il Azure ? (pas de catalogue, un déploiement à nommer) */
	export let azure = false;
	/** Le repère de modèle du fournisseur, pour la saisie libre. */
	export let modeleRepere = '';
	/** L'onglet charge le catalogue ; le bloc ne fait que le demander. */
	export let chargerModeles: () => void;
	/**  Ce bloc est-il déplié ? Décidé par l'ONGLET, qui tient l'accordéon
	 *   (#987) : un seul usage déplié à la fois, et un bloc ne connaît pas ses
	 *   voisins. Le bloc annonce seulement qu'on l'a ouvert ou fermé (`basculer`). */
	export let ouvert = false;
	/**  L'usage « Tarif d'un modèle » est-il prêt ? Décidé par l'ONGLET, qui voit
	 *   le commun et tous les usages : sans lui, pas de ✨ à côté du modèle. */
	export let tarifDisponible = false;
	/**  Où en est l'usage — appels du mois, premier essai —, lu par l'ONGLET en une
	 *   requête pour tous les blocs ; `relireLimites` la rejoue quand un tarif
	 *   enregistré change le coût du premier essai. */
	export let limites: LimitesUsageIA | undefined = undefined;
	export let relireLimites: () => void = () => {};

	const dispatch = createEventDispatcher<{ basculer: boolean }>();

	$: cles = usage.cles;
	$: actif = valeurs[cles.actif] === '1';
	//  La case d'un usage qui peut s'ouvrir aux copropriétaires (11/10/2026) :
	//  l'usage la porte dans ses clés (`llm_usages.champs`), aucun autre ne l'a.
	$: cleCoproprietaires = cles.coproprietaires;
	$: modele = valeurs[cles.modele] ?? '';
	$: prompt = valeurs[cles.prompt] ?? '';
	//  ── Le prompt : trois états, pas deux (#994, 17/09/2026) ─────────────────
	//
	//  🔴 L'écran comparait la clé au VIDE, et disait « Prompt modifié » dès
	//  qu'elle portait quelque chose. Il ne regardait donc JAMAIS le texte livré :
	//  un prompt collé à l'identique s'annonçait modifié, et surtout une origine
	//  plus récente, arrivée avec un déploiement, ne se signalait pas.
	//
	//  | état | ce qui SERT | ce que l'écran en dit |
	//  |---|---|---|
	//  | clé vide | l'origine du code, et elle SUIT ses évolutions | « Prompt d'origine » |
	//  | clé = origine | ce texte, FIGÉ — il ne suivra plus le code | « Copie de l'origine » |
	//  | clé ≠ origine | ce texte | « Prompt modifié », et l'origine est proposée |
	//
	//  ⚠️ La deuxième ligne est celle qui n'était pas dite, et c'est la plus
	//  trompeuse : un copier-coller donne un texte juste AUJOURD'HUI, qui
	//  n'apprendra rien de la version suivante.
	$: promptOrigine = !prompt.trim();
	$: copieDeLOrigine = !promptOrigine && memePrompt(prompt, usage.prompt_defaut);
	$: promptDivergent = !promptOrigine && !copieDeLOrigine;
	$: maxJetons = Number(valeurs[cles.max_jetons]) || usage.max_jetons_defaut;
	//  Le modèle enregistré reste proposé même s'il n'est plus au catalogue :
	//  sinon la liste le remplacerait en silence par son premier élément, et un
	//  simple Enregistrer changerait le modèle sans que personne l'ait demandé.
	$: choixModeles =
		catalogue.etat === 'pret' && modele && !catalogue.modeles.some((m) => m.id === modele)
			? [{ id: modele, libelle: `${modele} (enregistré)` }, ...catalogue.modeles]
			: catalogue.modeles;

	function poser(cle: string, valeur: string) {
		valeurs = { ...valeurs, [cle]: valeur };
	}

	function retablirPrompt() {
		poser(cles.prompt, '');
	}

	//  Le ✨ du tarif. Les prix reviennent ENREGISTRÉS, en dollars comme la
	//  grille : ils s'écrivent tels quels dans `valeurs` — un « Enregistrer »
	//  ultérieur renverra la même chose. Un prix que la grille ne donne pas
	//  (`null`) laisse le champ comme il était.
	let tarif: { etat: 'aucun' | 'encours' | 'ok' | 'ko'; message: string } = {
		etat: 'aucun',
		message: '',
	};

	async function demanderTarif() {
		tarif = { etat: 'encours', message: '' };
		try {
			const r = await assistantApi.tarif(usage.code, modele);
			for (const { champ } of PRIX) {
				const prix = r[champ];
				if (prix !== null) poser(cles[champ], prix);
			}
			tarif = { etat: 'ok', message: r.remarque };
			relireLimites();
		} catch (e) {
			tarif = { etat: 'ko', message: messageErreur(e, 'La recherche du tarif a échoué') };
		}
	}

	let test: { etat: 'aucun' | 'encours' | 'ok' | 'ko'; message: string } = {
		etat: 'aucun',
		message: '',
	};

	async function tester() {
		test = { etat: 'encours', message: '' };
		try {
			const r = await configApi.llmTest(usage.code);
			test = {
				etat: 'ok',
				message: `${r.fournisseur} · ${r.modele} — réponse « ${r.reponse} » en ${r.duree_ms} ms`,
			};
		} catch (e) {
			test = { etat: 'ko', message: messageErreur(e, 'Le test a échoué') };
		}
	}
</script>

<details
	class="bloc-usage"
	open={ouvert}
	on:toggle={(e) => dispatch('basculer', e.currentTarget.open)}
>
	<summary class="bloc-usage-resume">
		<Icon name="zap" size={16} />
		<span class="bloc-usage-titre">{usage.libelle}</span>
		<span class="badge" class:badge-green={actif} class:badge-gray={!actif}
			>{actif ? 'Activé' : 'Désactivé'}</span
		>
	</summary>
	<p class="aide bloc-usage-description">{usage.description}</p>

	<SectionFormulaire premiere titre="Activation">
		<label class="field case">
			<input
				type="checkbox"
				checked={actif}
				on:change={(e) => poser(cles.actif, e.currentTarget.checked ? '1' : '0')}
			/>
			Activer cet usage
			<span class="aide">
				Désactivé, cet usage ne sert nulle part{SEPARATEUR.tiret}ni icône ✨, ni traitement
				automatique{SEPARATEUR.tiret}et aucun appel n’est facturé. L’activation globale, dans le
				bloc Commun, coupe tous les usages d’un geste.
			</span>
		</label>
		{#if cleCoproprietaires}
			<label class="field case">
				<input
					type="checkbox"
					checked={valeurs[cleCoproprietaires] === '1'}
					on:change={(e) => poser(cleCoproprietaires, e.currentTarget.checked ? '1' : '0')}
				/>
				Ouvert aux copropriétaires
				<span class="aide">
					Décochée, seuls le conseil syndical et l’administration s’en servent. Cochée, tous les
					copropriétaires aussi{SEPARATEUR.tiret}ni les locataires, ni les mandataires, ni le
					syndic. Les limites d’appels ci-dessous valent pour chacun. À décocher en cas d’abus : le
					conseil syndical garde l’accès.
				</span>
			</label>
		{/if}
		<!--  Le réglage propre à UN usage (la synthèse : envoyer le document). DANS le
		      bloc, pour qu'il se replie avec lui (#1324) : posé à côté du composant,
		      il restait visible sous le bloc replié. -->
		<slot name="option" />
	</SectionFormulaire>

	<SectionFormulaire titre="Modèle">
		<div class="form-grid">
			<label class="field">
				<span>Modèle<EtoileRequis vide={!modele} /></span>
				<div class="ligne-choix">
					{#if catalogue.etat === 'pret'}
						<select value={modele} on:change={(e) => poser(cles.modele, e.currentTarget.value)}>
							<option value="">— choisir un modèle —</option>
							{#each choixModeles as m (m.id)}
								<option value={m.id}>{m.libelle}</option>
							{/each}
						</select>
					{:else}
						<input
							type="text"
							value={modele}
							placeholder={modeleRepere}
							on:input={(e) => poser(cles.modele, e.currentTarget.value.trim())}
						/>
					{/if}
					{#if tarifDisponible}
						<button
							class="btn-icon"
							type="button"
							aria-label="Chercher et enregistrer le tarif de ce modèle"
							title="Chercher et enregistrer le tarif de ce modèle"
							aria-busy={tarif.etat === 'encours'}
							disabled={!modele || tarif.etat === 'encours'}
							on:click={demanderTarif}><IconeIA enCours={tarif.etat === 'encours'} /></button
						>
					{/if}
				</div>
				{#if tarif.etat === 'ko'}
					<!--  `aide` : dans le libellé du champ, un texte sans elle hériterait
					      de ses capitales (`champs.css`, #1315). -->
					<span class="aide verdict ko">⚠️ {tarif.message}</span>
				{/if}
				<div class="ligne-modele">
					{#if !azure}
						<button
							class="btn btn-outline btn-sm"
							type="button"
							disabled={catalogue.etat === 'encours' || !clePosee}
							on:click={chargerModeles}
						>
							{catalogue.etat === 'encours' ? 'Lecture…' : 'Voir les modèles disponibles'}
						</button>
					{/if}
				</div>
				<span class="aide">
					{#if catalogue.etat === 'pret'}
						{choixModeles.length} modèle{choixModeles.length > 1 ? 's' : ''} accessible{choixModeles.length >
						1
							? 's'
							: ''} avec cette clé, du plus récent au plus ancien. Chaque usage a SON modèle : un modèle
						plus capable rend un texte plus fidèle, et coûte plus cher par appel.
					{:else if catalogue.etat === 'indisponible'}
						{catalogue.motif} Saisissez l’<strong>identifiant d’API</strong> à la main{SEPARATEUR.tiret}pas
						le nom commercial.
					{:else if !clePosee}
						Enregistrez d’abord une clé dans le bloc Commun : la liste des modèles se lit avec elle.
					{:else}
						L’<strong>identifiant d’API</strong>, pas le nom commercial. Obligatoire : un usage sans
						modèle ne peut pas appeler.
						{azure
							? 'Sur Azure, indiquez le nom de votre déploiement.'
							: 'Le bouton ci-dessus demande au fournisseur ce que votre clé peut appeler.'}
					{/if}
				</span>
			</label>
			<!--  L'effort de raisonnement (30/09/2026). Lié à la valeur de CET usage :
			      l'onglet l'enregistre avec le reste. Les niveaux viennent du serveur
			      (`usage.efforts`) ; « Par défaut du modèle » n'envoie rien. -->
			<div class="field">
				<ChoixPastilles
					options={usage.efforts}
					bind:valeur={valeurs[cles.effort]}
					tous="Par défaut du modèle"
					libelle="Effort de raisonnement"
					libelleVisible
					defilante={false}
				/>
				<span class="aide">
					Un modèle qui raisonne pense avant d’écrire, et ces jetons se paient comme la réponse.
					Faible suffit pour mettre en forme ou reformuler ; moyen ou élevé pour lire et résumer un
					document. Un modèle qui ne raisonne pas ignore ce réglage.
				</span>
			</div>
			<label class="field">
				Longueur maximale de la réponse
				<input
					type="number"
					value={maxJetons}
					min="200"
					max="32000"
					step="500"
					on:input={(e) => poser(cles.max_jetons, e.currentTarget.value)}
				/>
				<span class="aide">
					En jetons, et c’est un plafond de <strong>coût</strong> autant que de longueur : seuls les
					jetons réellement produits sont facturés. Un modèle récent raisonne avant d’écrire, et ce
					raisonnement compte dans le plafond{SEPARATEUR.tiret}une réponse coupée vient de ce champ,
					pas du modèle. Valeur d’origine : {fmtNombre(usage.max_jetons_defaut)}.
				</span>
			</label>
		</div>
	</SectionFormulaire>

	<!--  Plafond et prix : `CoutUsageIA` (30/09/2026) — ce bloc franchissait 500
	      lignes en recevant l'effort de raisonnement. Le ✨ du tarif reste ICI,
	      à côté du modèle : il n'en passe que le compte rendu. -->
	<CoutUsageIA
		bind:valeurs
		{cles}
		{limites}
		gesteManuel={usage.geste_manuel}
		tarifEnregistre={tarif.etat === 'ok' ? tarif.message : ''}
	/>

	<SectionFormulaire titre="Prompt">
		<div class="field champ-large">
			<label for="prompt-{usage.code}">Consigne donnée au modèle</label>
			<textarea
				id="prompt-{usage.code}"
				rows="14"
				value={promptOrigine ? usage.prompt_defaut : prompt}
				on:input={(e) => poser(cles.prompt, e.currentTarget.value)}></textarea>
			<div class="ligne-modele">
				<button
					class="btn btn-outline btn-sm"
					type="button"
					disabled={promptOrigine}
					on:click={retablirPrompt}
				>
					Rétablir le prompt d’origine
				</button>
				{#if promptOrigine}
					<span class="badge badge-gray">Prompt d’origine</span>
				{:else if copieDeLOrigine}
					<span class="badge badge-gray">Copie de l’origine</span>
				{:else}
					<span class="badge badge-orange">Prompt modifié</span>
				{/if}
			</div>
			{#if copieDeLOrigine}
				<p class="aide">
					Ce texte est identique au prompt d’origine, mais il en est une <strong>copie</strong>
					: il ne suivra pas ses évolutions. « Rétablir le prompt d’origine » vide le champ, et c’est
					alors la version livrée par l’application qui sert{SEPARATEUR.tiret}celle-là se met à jour
					avec elle.
				</p>
			{:else if promptDivergent}
				<p class="aide">
					Ce texte <strong>diffère</strong> du prompt d’origine livré par cette version de l’application.
					C’est normal si vous l’avez adapté ; si vous attendiez une consigne plus récente, « Rétablir
					le prompt d’origine » la reprend.
				</p>
			{/if}
			<span class="aide">
				C’est le contexte que reçoit le modèle avant le texte à traiter : le ton, les interdits, la
				structure attendue. Vous pouvez y ajouter des consignes ou modifier le gabarit. La matière{SEPARATEUR.tiret}la
				fiche, les documents, la description saisie{SEPARATEUR.tiret}est ajoutée par l’application,
				et le <strong>format de réponse</strong> que l’application sait relire est imposé par elle : un
				prompt réécrit ne peut pas le casser.
			</span>
		</div>
	</SectionFormulaire>

	<SectionFormulaire titre="Vérification">
		<p class="aide explication-test">
			Ce test pose une vraie question au modèle de <strong>cet usage</strong> et attend sa réponse.
			⚠️ Il porte sur la configuration <strong>enregistrée</strong> : cliquez d’abord sur « Enregistrer
			» si vous venez de modifier un champ. L’usage n’a pas besoin d’être activé.
		</p>
		<div class="ligne-test">
			<button
				class="btn btn-outline"
				type="button"
				on:click={tester}
				disabled={test.etat === 'encours' || !clePosee}
			>
				{test.etat === 'encours' ? 'Test en cours…' : '🔌 Tester la connexion'}
			</button>
			{#if test.etat === 'ok'}
				<span class="verdict ok">✅ {test.message}</span>
			{:else if test.etat === 'ko'}
				<span class="verdict ko">⚠️ {test.message}</span>
			{/if}
		</div>
	</SectionFormulaire>
</details>

<style>
	/*  Le bloc pliable d'un usage : un cadre dans la carte de l'onglet, jamais une
	    seconde carte — deux bordures pleines pour un seul objet est le défaut
	    de #425. */
	.bloc-usage {
		border: 1px solid var(--color-border);
		border-radius: var(--radius);
		padding: 0.6rem 0.9rem;
		margin-top: 0.9rem;
	}
	.bloc-usage-resume {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		cursor: pointer;
		font-weight: 700;
		list-style: none;
	}
	.bloc-usage-resume::-webkit-details-marker {
		display: none;
	}
	.bloc-usage-resume::before {
		content: '›';
		display: inline-block;
		transition: transform var(--duree-geste) var(--ease-out);
		color: var(--color-text-muted);
	}
	.bloc-usage[open] > .bloc-usage-resume::before {
		transform: rotate(90deg);
	}
	.bloc-usage-titre {
		flex: 1;
	}
	.bloc-usage-description {
		margin: 0.5rem 0 0.9rem;
	}
	/*  La rangée qui porte un bouton sous son champ. Un `<div>` plutôt qu'un
	    frère du `<label>` : le bouton appartient au champ. */
	.ligne-modele {
		display: flex;
		align-items: center;
		gap: 0.6rem;
		margin-top: 0.35rem;
	}
	/*  Le modèle et son ✨ sur une ligne : le champ prend la place, l'icône se
	    tient à sa droite. */
	.ligne-choix {
		display: flex;
		align-items: center;
		gap: 0.4rem;
	}
	.ligne-choix > :is(select, input) {
		flex: 1;
		min-width: 0;
	}
	/*  44 px au doigt (`standards/11` §10) : l'icône seule en ferait 24. */
	.ligne-choix > .btn-icon {
		min-width: 2.75rem;
		min-height: 2.75rem;
	}
	.ligne-test {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		flex-wrap: wrap;
	}
	.verdict {
		font-size: var(--fs-base);
	}
	.verdict.ok {
		color: var(--color-success);
	}
	.verdict.ko {
		color: var(--color-danger);
	}
	.explication-test {
		margin-bottom: 0.6rem;
	}
</style>
