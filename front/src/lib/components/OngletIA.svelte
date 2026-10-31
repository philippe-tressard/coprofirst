<!--
  L'onglet **Assistant IA** de l'administration : le COMMUN — quel service,
  quelle clé, quelle adresse, quel délai — et un BLOC PAR USAGE, pliable, avec
  son modèle, son prompt, son plafond et son test (#984, 17/09/2026).

  Même geste et même forme qu'`OngletSmtp` : l'état et les appels réseau vivent
  ici, la page ne garde que le choix de l'onglet. Le champ secret passe par
  `ChampSecret`, extrait le même jour des deux écrans qui le portaient déjà.

  ## 🔴 La clé ne revient JAMAIS du serveur

  `llm_api_key` est déclarée dans `routers/config._SECRETS` : l'API rend un
  marqueur, jamais la valeur. L'écran sait seulement qu'une clé existe — et
  n'envoie la sienne que si elle est **non vide**, sinon un enregistrement
  ordinaire effacerait la clé posée.

  ## Ce que l'écran ne décide pas

  Ni la liste des fournisseurs, ni les modèles par défaut, ni les limites — tout
  cela vit dans `api/app/utils/llm.py`. Et depuis le 17/09/2026, **ni la liste
  des usages** : elle vient de `GET /config/llm-usages` (`llm_usages.py`), et
  l'écran rend un `BlocUsageIA` par entrée. Recopier l'une ou l'autre table ici
  la ferait diverger au premier ajout — c'est le défaut que ce dépôt connaît le
  mieux.

  ## Un seul « Enregistrer »

  Le commun et les usages s'enregistrent d'un geste : chaque bloc écrit ses clés
  dans `valeursSaisies`, et ce bouton envoie le tout. Un bouton par bloc ferait
  des enregistrements partiels — une clé posée sans son modèle, un modèle sans
  son activation.
-->
<script lang="ts">
	import EncartDemo from '#lib/components/EncartDemo.svelte';
	import { messageErreur } from '#lib/erreurs.ts';
	import { onMount } from 'svelte';
	import Icon from '#lib/components/Icon.svelte';
	import { config as configApi, type LimitesUsageIA, type UsageIA } from '#lib/api/index.ts';
	import { toast } from '#lib/components/Toast.svelte';
	import SectionFormulaire from '#lib/components/SectionFormulaire.svelte';
	import ChampSecret from '#lib/components/ChampSecret.svelte';
	import ChoixPastilles from '#lib/components/ChoixPastilles.svelte';
	import BlocUsageIA from '#lib/components/BlocUsageIA.svelte';
	import EtatService from '#lib/components/EtatService.svelte';
	import { oublierAssistant } from '#lib/stores/assistant.ts';
	import { SEPARATEUR } from '#lib/separateurs.ts';

	/** Valeurs lues au chargement par la page (`adminCfg`). */
	export let valeurs: Record<string, string> = {};

	//  ⚠️ Trois entrées : le seuil des listes courtes (≤ 6) impose des pastilles,
	//  pas un `<select>` (`ux-patterns`, `lint:seuil-listes`).
	const FOURNISSEURS = [
		{ val: 'openai', label: 'OpenAI', desc: 'api.openai.com — GPT' },
		{ val: 'anthropic', label: 'Claude', desc: 'api.anthropic.com — Anthropic' },
		{ val: 'azure_openai', label: 'Azure OpenAI', desc: 'votre point d’accès Azure' },
	];

	/** Repères de modèle pour la saisie libre — le champ reste libre, le catalogue vient du fournisseur. */
	const MODELES_REPERE: Record<string, string> = {
		openai: 'gpt-4o-mini',
		anthropic: 'claude-haiku-4-5-20251001',
		azure_openai: 'nom de votre déploiement',
	};

	//  Le COMMUN.
	let cfg = {
		actif: false,
		fournisseur: 'openai',
		base_url: '',
		api_version: '',
		delai_s: 45,
		envoi_document: true,
	};
	let cle = '';
	let clePosee = false;
	let enregistrement = false;

	//  Les USAGES — la liste vient de l'API, jamais d'ici.
	let usages: UsageIA[] = [];
	//  Les valeurs des usages, telles que les blocs les écrivent. Elles partent
	//  TOUTES à l'enregistrement, avec le commun.
	let valeursSaisies: Record<string, string> = {};
	//  L'ACCORDÉON (#987) : un seul usage déplié à la fois. Déplier l'un replie
	//  l'autre — demandé à l'écran le 17/09/2026, deux blocs ouverts faisaient une
	//  page longue. L'état vit ici : un bloc ne connaît pas ses voisins.
	//
	//  🔴 `null` à l'ouverture : TOUS les usages sont repliés, y compris ceux qui
	//  sont actifs (arbitré le 17/09/2026). Déplier le premier actif faisait de
	//  l'écran une page longue dès l'arrivée, alors qu'on y vient le plus souvent
	//  pour le bloc Commun — et la page ne choisit pas ce qu'on est venu lire.
	let usageOuvert: string | null = null;

	//  Où en est chaque usage — appels du mois, premier essai (04/10/2026). Une
	//  requête pour tous les blocs, rejouée après un enregistrement : un modèle
	//  ou un effort changé périme le premier essai. Son échec ne bloque rien,
	//  les blocs taisent alors la ligne.
	let limites: Record<string, LimitesUsageIA> = {};
	async function relireLimites() {
		try {
			const r = await configApi.llmConsommation();
			limites = Object.fromEntries(r.limites.map((l) => [l.usage, l]));
		} catch {
			limites = {};
		}
	}
	function basculerUsage(code: string, ouvert: boolean) {
		if (ouvert) usageOuvert = code;
		else if (usageOuvert === code) usageOuvert = null;
	}

	//  🔴 La liste des modèles vient du FOURNISSEUR, pas d'un catalogue écrit ici
	//  (11/09/2026 — « on peut choisir un modèle plus intelligent ? »). Un repère
	//  recopié propose ce que la clé ne peut pas appeler et cache ce qui est
	//  sorti depuis. Le catalogue est COMMUN : il dépend de la clé, pas de l'usage.
	//
	//  ⚠️ `catalogue.listable === false` n'est PAS une panne — Azure n'expose pas
	//  ses déploiements, et une clé peut très bien répondre sans avoir le droit
	//  de s'inventorier. On retombe alors sur la saisie libre, en disant pourquoi.
	let catalogue: {
		etat: 'aucun' | 'encours' | 'pret' | 'indisponible';
		motif: string;
		modeles: { id: string; libelle: string }[];
	} = { etat: 'aucun', motif: '', modeles: [] };

	$: azure = cfg.fournisseur === 'azure_openai';

	//  Le ✨ du tarif, à côté du modèle de CHAQUE bloc (30/09/2026) : il ne
	//  s'affiche que si l'usage « Tarif d'un modèle » est prêt — le commun activé,
	//  une clé, l'usage activé et doté d'un modèle. Lu sur l'écran, pas sur la
	//  base : un réglage non enregistré fait apparaître l'icône, et c'est alors le
	//  serveur qui dit ce qui manque (`ConfigLLM.verifier`).
	$: usageTarif = usages.find((u) => u.code === 'tarif_modele');
	$: tarifDisponible =
		!!usageTarif &&
		cfg.actif &&
		clePosee &&
		valeursSaisies[usageTarif.cles.actif] === '1' &&
		!!(valeursSaisies[usageTarif.cles.modele] ?? '').trim();

	$: if (valeurs && Object.keys(valeurs).length) hydrater(valeurs);

	let hydrate = false;
	function hydrater(lues: Record<string, string>) {
		if (hydrate) return;
		hydrate = true;
		cfg = {
			actif: lues['llm_actif'] === '1',
			fournisseur: lues['llm_fournisseur'] || 'openai',
			base_url: lues['llm_base_url'] || '',
			api_version: lues['llm_api_version'] || '',
			delai_s: Number(lues['llm_delai_s']) || 45,
			envoi_document: lues['llm_envoi_document'] !== '0',
		};
		clePosee = !!lues['llm_api_key'];
		//  Les blocs lisent et écrivent dans cette copie : la page garde la sienne.
		valeursSaisies = { ...lues };
	}

	onMount(async () => {
		try {
			usages = await configApi.llmUsages();
			relireLimites();
		} catch (e) {
			toast('error', messageErreur(e, 'Les usages de l’assistant n’ont pas pu être lus'));
		}
	});

	async function enregistrer() {
		enregistrement = true;
		try {
			//  L'activation n'y est pas : elle se coche dans Admin › Services, seule
			//  case qui l'écrit — la renvoyer rétablirait un service qu'on vient de couper.
			const charge: Record<string, string> = {
				llm_fournisseur: cfg.fournisseur,
				llm_base_url: cfg.base_url.trim(),
				llm_api_version: cfg.api_version.trim(),
				llm_delai_s: String(cfg.delai_s),
				llm_envoi_document: cfg.envoi_document ? '1' : '0',
			};
			//  Les clés de chaque usage, telles que son bloc les a posées. On
			//  n'envoie que les siennes : `valeursSaisies` porte toute la
			//  configuration du site, et la renvoyer entière réécrirait des clés
			//  que cet écran ne montre pas.
			for (const u of usages) {
				for (const cleUsage of Object.values(u.cles)) {
					if (cleUsage in valeursSaisies) charge[cleUsage] = valeursSaisies[cleUsage] ?? '';
				}
			}
			//  🔴 La clé n'est envoyée QUE si l'on en a saisi une. Une chaîne vide
			//  écraserait celle qui est enregistrée — et rien ne le dirait avant le
			//  prochain appel.
			if (cle) charge['llm_api_key'] = cle;
			await configApi.save(charge);
			if (cle) {
				clePosee = true;
				cle = '';
			}
			toast('success', 'Configuration enregistrée');
			relireLimites();
			//  Le fournisseur ou la clé viennent peut-être de changer : le
			//  catalogue précédent ne décrit plus ce qu'on peut appeler.
			catalogue = { etat: 'aucun', motif: '', modeles: [] };
			//  Et les formulaires relisent la disponibilité de l'assistant.
			oublierAssistant();
		} catch (e) {
			toast('error', messageErreur(e, 'Erreur à l’enregistrement'));
		} finally {
			enregistrement = false;
		}
	}

	async function chargerModeles() {
		catalogue = { etat: 'encours', motif: '', modeles: [] };
		try {
			const r = await configApi.llmModeles();
			catalogue = r.listable
				? { etat: 'pret', motif: '', modeles: r.modeles }
				: { etat: 'indisponible', motif: r.motif, modeles: [] };
		} catch (e) {
			catalogue = {
				etat: 'indisponible',
				motif: messageErreur(e, 'Liste indisponible'),
				modeles: [],
			};
		}
	}
</script>

<EncartDemo />
<div class="card">
	<h2 class="titre-onglet"><Icon name="zap" size={18} /> Assistant IA</h2>

	<SectionFormulaire premiere titre="Commun — le service">
		<EtatService actif={cfg.actif}>
			Coupé, aucune icône ✨ n’apparaît et aucun appel n’est facturé, quel que soit l’usage. Chaque
			usage a en plus sa propre activation, ci-dessous.
		</EtatService>

		<ChoixPastilles
			options={FOURNISSEURS}
			bind:valeur={cfg.fournisseur}
			tous={false}
			libelle="Fournisseur"
			libelleVisible
			requis
		/>

		<ChampSecret
			libelle="Clé d’API"
			requis
			rempli={clePosee || !!cle}
			bind:valeur={cle}
			pose={clePosee}
			placeholder="sk-…"
			aide="Elle n’est jamais renvoyée par le serveur, même à un administrateur. Une seule clé pour tous les usages."
		/>

		<div class="form-grid">
			<label class="field">
				Adresse du service {azure ? '*' : ''}
				<input
					type="url"
					bind:value={cfg.base_url}
					placeholder={azure ? 'https://mon-instance.openai.azure.com' : 'adresse par défaut'}
				/>
				<span class="aide">
					{azure
						? 'Obligatoire : Azure n’a pas d’adresse publique, chaque client a la sienne.'
						: 'À renseigner seulement pour passer par un relais compatible.'}
				</span>
			</label>
			{#if azure}
				<label class="field">
					Version d’API
					<input type="text" bind:value={cfg.api_version} placeholder="2024-06-01" />
					<span class="aide">La version indiquée dans votre portail Azure.</span>
				</label>
			{/if}
			<label class="field">
				Délai d’attente
				<input type="number" bind:value={cfg.delai_s} min="10" max="300" step="5" />
				<span class="aide">
					En secondes. Au-delà, on renonce et l’écran le dit{SEPARATEUR.tiret}le champ reste
					saisissable à la main.
				</span>
			</label>
		</div>
	</SectionFormulaire>

	<SectionFormulaire titre="Par usage">
		<p class="aide explication-usages">
			Chaque usage règle <strong>son modèle</strong>, <strong>son prompt</strong> et
			<strong>ses limites d’appels</strong>, et se teste séparément. Tout s’enregistre avec le
			bouton en bas de page.
		</p>
		{#if usages.length === 0}
			<p class="aide">Lecture des usages…</p>
		{/if}
		{#each usages as usage (usage.code)}
			<BlocUsageIA
				{usage}
				bind:valeurs={valeursSaisies}
				{catalogue}
				{clePosee}
				{azure}
				modeleRepere={MODELES_REPERE[cfg.fournisseur]}
				{chargerModeles}
				{tarifDisponible}
				limites={limites[usage.code]}
				{relireLimites}
				ouvert={usageOuvert === usage.code}
				on:basculer={(e) => basculerUsage(usage.code, e.detail)}
			>
				<!--  Le seul réglage propre à UN usage : ce que la synthèse envoie du
				      contrat. Il vit DANS son bloc (#1324), pas dans le commun — un autre
				      usage n'a pas de document à envoyer. -->
				<svelte:fragment slot="option">
					{#if usage.code === 'synthese_contrat'}
						<label class="field case option-usage">
							<input type="checkbox" bind:checked={cfg.envoi_document} />
							Envoyer le document du contrat au service
							<span class="aide">
								Sans lui, quatre sections de la synthèse sur sept restent vides : montants,
								prestations incluses et exclues ne vivent que dans le PDF. Sont transmis <strong
									>tous les documents du contrat</strong
								>{SEPARATEUR.tiret}l’initial, ses avenants, ses conditions générales : n’en lire
								qu’un rendrait les montants faux dès le premier avenant. Rien d’autre ne part : ni
								pièce jointe d’une affaire, ni document d’un autre contrat.
							</span>
						</label>
					{/if}
				</svelte:fragment>
			</BlocUsageIA>
		{/each}
	</SectionFormulaire>

	<div class="form-actions">
		<button class="btn btn-primary" type="button" on:click={enregistrer} disabled={enregistrement}>
			{enregistrement ? 'Enregistrement…' : 'Enregistrer'}
		</button>
	</div>
</div>

<style>
	.titre-onglet {
		display: flex;
		align-items: center;
		gap: 0.45rem;
		font-size: var(--fs-xl);
		font-weight: 700;
		margin: 0 0 0.9rem;
	}
	/*  Le réglage propre à un usage se lit sous son bloc, légèrement rentré. */
	.option-usage {
		margin-top: 0.6rem;
	}
	.explication-usages {
		margin-bottom: 0.4rem;
	}
</style>
