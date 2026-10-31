<!--
  SyntheseAffaire.svelte — la Suite « Synthèse de l'affaire » (#1643).

  Une affaire du carnet close reçoit, trente minutes plus tard, une synthèse
  rédigée par l'assistant à partir de son fil et des métriques que le serveur
  calcule. Ce composant la rend, dans cet ordre (arbitré) :

    1. les cinq graphiques — M2 tuiles, M1 frise, M3 chronologie, M4 face à la
       moyenne, M5 rythme ;
    2. le texte : synthèse, difficultés, amélioration suggérée.

  En BROUILLON, seuls le conseil et l'administration la voient — le serveur ne
  l'envoie à personne d'autre — avec un bandeau, et cinq gestes : Modifier ·
  Relancer · Recommencer · Valider · Supprimer. Validée, elle garde Modifier et
  Supprimer (07/10/2026, demandé à l'écran : une synthèse validée ne se
  corrigeait ni ne s'effaçait). Les métriques ne s'éditent pas.

  Il sert la fiche de l'affaire (dans le fil) ET le carnet d'entretien (partie
  pliée de la ligne, en lecture) : une entité, un rendu.
-->
<script lang="ts">
	import Icon from '#lib/components/Icon.svelte';
	import IconeAction from '#lib/components/IconeAction.svelte';
	import IconeIA from '#lib/components/IconeIA.svelte';
	import { createEventDispatcher } from 'svelte';
	import { syntheses, type PropositionSynthese, type SyntheseAffaire } from '#lib/api/index.ts';
	import { confirmer } from '#lib/confirmation.ts';
	import { demander } from '#lib/saisie.ts';
	import { fmtDatetime } from '#lib/date.ts';
	import { messageErreur } from '#lib/erreurs.ts';
	import { safeDescription } from '#lib/sanitize.ts';
	import EncartAvertissement from './EncartAvertissement.svelte';
	import FormulaireCreation from './FormulaireCreation.svelte';
	import PiedFormulaire from './PiedFormulaire.svelte';
	import RichEditor from './RichEditor.svelte';
	import SyntheseChronologie from './SyntheseChronologie.svelte';
	import SyntheseFrise from './SyntheseFrise.svelte';
	import SyntheseMoyenne from './SyntheseMoyenne.svelte';
	import SyntheseRecidive from './SyntheseRecidive.svelte';
	import SyntheseRythme from './SyntheseRythme.svelte';
	import SyntheseTuiles from './SyntheseTuiles.svelte';
	import { toast } from './Toast.svelte';
	import { SEPARATEUR } from '#lib/separateurs.ts';

	export let synthese: SyntheseAffaire;
	/** Le conseil : les gestes d'un brouillon. Le serveur refait le contrôle. */
	export let gestes = false;
	/** L'intitulé « La synthèse ». Absent dans la carte d'une affaire, où l'encart
	    de sa rubrique le porte déjà (`RubriqueEtape`, maquette G du 16/10/2026) :
	    il s'y lisait deux fois, puis une troisième dans « La synthèse — ce qui
	    s'est passé ». */
	export let titre = true;

	const dispatch = createEventDispatcher<{ change: SyntheseAffaire }>();

	$: brouillon = synthese.statut === 'brouillon';
	$: vide = !synthese.synthese;
	$: m = synthese.metriques;

	let edition = false;
	let enCours = false;
	let texte = { synthese: '', difficultes: '', amelioration: '' };

	function ouvrirEdition() {
		texte = {
			synthese: synthese.synthese ?? '',
			difficultes: synthese.difficultes ?? '',
			amelioration: synthese.amelioration ?? '',
		};
		edition = !edition;
	}

	async function geste(appel: () => Promise<SyntheseAffaire>, succes: string) {
		enCours = true;
		try {
			synthese = await appel();
			edition = false;
			dispatch('change', synthese);
			toast('success', succes);
		} catch (e) {
			toast('error', messageErreur(e));
		} finally {
			enCours = false;
		}
	}

	//  🔴 Relancer et Recommencer PROPOSENT (03/10/2026, demandé à l'écran : « il
	//  manque une option Annuler si on veut sortir sans sauvegarder ») : le texte
	//  relu reste en place, la rédaction neuve s'affiche à part, et le conseil
	//  l'applique ou l'annule. Les métriques, recalculées, valent tout de suite.
	let proposition: PropositionSynthese | null = null;
	/** Le geste qui a sollicité l'assistant : SON ✨ devient ⏳ (`IconeIA`). */
	let sollicite: 'relancer' | 'recommencer' | null = null;

	async function proposer(
		geste: 'relancer' | 'recommencer',
		appel: () => Promise<PropositionSynthese>,
	) {
		enCours = true;
		sollicite = geste;
		try {
			proposition = await appel();
			synthese = proposition.actuelle;
			toast('success', 'Proposition de l’assistant : à appliquer ou annuler');
		} catch (e) {
			toast('error', messageErreur(e));
		} finally {
			enCours = false;
			sollicite = null;
		}
	}

	async function appliquer() {
		if (!proposition) return;
		const id = proposition.tentative_id;
		await geste(() => syntheses.appliquer(synthese.ticket_id, id), 'Proposition appliquée');
		proposition = null;
	}

	const enregistrer = () =>
		geste(() => syntheses.modifier(synthese.ticket_id, texte), 'Synthèse enregistrée');

	async function relancer() {
		const complement = await demander({
			titre: 'Relancer la synthèse',
			message:
				"L'assistant propose une nouvelle rédaction, que vous appliquerez ou annulerez. Votre consigne s'ajoute au prompt de l'usage ; appliquée, elle est gardée pour la prochaine relance.",
			libelle: 'Consigne complémentaire',
			placeholder: 'Plus court, insister sur les relances restées sans réponse…',
			libelleValider: 'Relancer',
		});
		if (complement === null) return;
		await proposer('relancer', () => syntheses.relancer(synthese.ticket_id, complement));
	}

	async function recommencer() {
		const ok = await confirmer({
			titre: 'Recommencer la synthèse',
			message:
				"L'assistant propose une nouvelle rédaction, sans consigne complémentaire — appliquée, celle-ci est effacée. Les rédactions précédentes restent dans l'historique.",
			libelleConfirmer: 'Recommencer',
		});
		if (ok) await proposer('recommencer', () => syntheses.recommencer(synthese.ticket_id));
	}

	async function supprimer() {
		const ok = await confirmer({
			titre: 'Supprimer la synthèse',
			message:
				"La synthèse et son entrée de l'historique sont retirées, y compris du carnet d'entretien. Vous pourrez en produire une nouvelle.",
			libelleConfirmer: 'Supprimer',
		});
		if (!ok) return;
		enCours = true;
		try {
			await syntheses.supprimer(synthese.ticket_id);
			dispatch('change', synthese);
			toast('success', 'Synthèse supprimée');
		} catch (e) {
			toast('error', messageErreur(e));
		} finally {
			enCours = false;
		}
	}

	async function valider() {
		const ok = await confirmer({
			titre: 'Valider la synthèse',
			message:
				"Validée, la synthèse est lue par tous ceux qui lisent l'affaire, et versée au carnet d'entretien. Le conseil peut encore la corriger ou la supprimer.",
			libelleConfirmer: 'Valider',
		});
		if (ok) await geste(() => syntheses.valider(synthese.ticket_id), 'Synthèse validée');
	}
</script>

<section class="synthese" aria-label="Synthèse de l'affaire">
	<!--  L'EN-TÊTE porte l'intitulé, la validation et les gestes de l'objet —
	      crayon puis corbeille, à droite, comme l'en-tête d'une carte (maquette A,
	      15/10/2026). Ils étaient sous les graphiques, loin de ce qu'ils touchent.
	      Dans la carte d'une affaire, l'intitulé est celui de l'encart : il ne
	      reste ici que la validation et les gestes, en tête du contenu déplié
	      (maquette G, 16/10/2026). -->
	{#if titre || gestes || synthese.validee_le}
		<div class="tete">
			{#if titre}
				<h4 class="intertitre titre"><Icon name="file-text" size={15} />La synthèse</h4>
			{:else}
				<span class="titre"></span>
			{/if}
			{#if synthese.statut === 'validee' && synthese.validee_le}
				<span class="validee"
					>Validée le {fmtDatetime(synthese.validee_le)}{synthese.validee_par_nom
						? ` par ${synthese.validee_par_nom}`
						: ''}</span
				>
			{/if}
			{#if gestes}
				<!--  Le mode se lit sur l'icône qui a ouvert le formulaire (`aria-pressed`,
			      ux-patterns §13 bis). La corbeille en dernier, irréversible. -->
				<span class="actions">
					<button
						type="button"
						class="btn-icon btn-icon-edit"
						aria-pressed={edition}
						aria-label="Modifier la synthèse"
						title="Modifier"
						disabled={enCours || !!proposition}
						on:click={ouvrirEdition}><IconeAction icone="pencil" /></button
					>
					<button
						type="button"
						class="btn-icon-danger"
						aria-label="Supprimer la synthèse"
						title="Supprimer la synthèse"
						disabled={enCours || edition || !!proposition}
						on:click={supprimer}><IconeAction icone="trash-2" /></button
					>
				</span>
			{/if}
		</div>
	{/if}
	{#if synthese.assiste_ia}
		<!--  Le préambule choisi par l'utilisateur le 03/10/2026, parmi quatre : il
		      remplace la seule marque ✨, trop discrète pour un texte qui sera lu
		      en assemblée générale. -->
		<p class="aide">
			✨ Ce texte a été produit par une intelligence artificielle et peut comporter des imprécisions
			: seul le fil de l’affaire fait foi.
		</p>
	{/if}

	{#if brouillon}
		<EncartAvertissement role="status" compact>
			{#if vide}
				<strong>Synthèse à rédiger</strong>{SEPARATEUR.tiret}{synthese.motif_vide ??
					"l'assistant n'a rien rédigé"}. Brouillon visible du conseil syndical seulement.
			{:else}
				<strong>Brouillon</strong>, visible du conseil syndical seulement : à relire, puis valider.
			{/if}
		</EncartAvertissement>
	{/if}

	<!--  🔴 LE TEXTE D'ABORD, puis les chiffres (maquette A, 15/10/2026) : on lit ce
	      qui s'est passé avant de le mesurer. La maquette du 03/10 mettait les
	      graphiques en tête — c'est la lecture dans une carte qui l'a renversée. -->
	{#if edition}
		<FormulaireCreation titre="Modifier la synthèse" encadre={false}>
			<form class="edition" on:submit|preventDefault={enregistrer}>
				<div class="field">
					<span id="synthese-texte-{synthese.id}">Synthèse</span>
					<RichEditor bind:value={texte.synthese} ariaLabelledby="synthese-texte-{synthese.id}" />
				</div>
				<div class="field">
					<span id="synthese-difficultes-{synthese.id}">Difficultés</span>
					<RichEditor
						bind:value={texte.difficultes}
						minHeight="80px"
						ariaLabelledby="synthese-difficultes-{synthese.id}"
					/>
				</div>
				<div class="field">
					<span id="synthese-amelioration-{synthese.id}">Amélioration suggérée</span>
					<RichEditor
						bind:value={texte.amelioration}
						minHeight="80px"
						ariaLabelledby="synthese-amelioration-{synthese.id}"
					/>
				</div>
				<PiedFormulaire {enCours} on:annule={() => (edition = false)} />
			</form>
		</FormulaireCreation>
	{:else if synthese.synthese}
		<section class="bloc">
			<h5 class="bloc-titre">Ce qui s'est passé</h5>
			<div class="rich-content texte">{@html safeDescription(synthese.synthese)}</div>
		</section>
	{/if}

	{#if m}
		<!--  Chaque bloc a son sous-titre, d'après la maquette arbitrée le
		      03/10/2026 — sans son repère de travail (M1…M5). -->
		<section class="bloc">
			<h5 class="bloc-titre">Les chiffres{SEPARATEUR.tiret}durée, étapes, suites et relances</h5>
			<SyntheseTuiles metriques={m} />
		</section>
		<section class="bloc">
			<h5 class="bloc-titre">La frise{SEPARATEUR.tiret}jours ouvrés passés à chaque étape</h5>
			<SyntheseFrise metriques={m} />
		</section>
		{#if m.comparaison}
			<section class="bloc">
				<h5 class="bloc-titre">
					Face à la moyenne{SEPARATEUR.tiret}les affaires de même catégorie sur l'exercice
				</h5>
				<SyntheseMoyenne metriques={m} />
			</section>
		{/if}
		<section class="bloc">
			<h5 class="bloc-titre">Le rythme{SEPARATEUR.tiret}suites par semaine, semaines muettes</h5>
			<SyntheseRythme metriques={m} />
		</section>
		<!--  La chronologie redit la frise date par date, la récidive ne concerne
		      qu'un équipement déjà réparé : PLIÉES (maquette A, 15/10/2026). Un
		      `<details>` : l'accordéon du site le ferme quand un autre s'ouvre. -->
		<details class="bloc plies">
			<summary class="bloc-titre">
				{m.recidive ? 'La récidive et la chronologie' : 'La chronologie'}
			</summary>
			{#if m.recidive}
				<h5 class="bloc-titre">La récidive{SEPARATEUR.tiret}le même équipement, déjà réparé</h5>
				<SyntheseRecidive metriques={m} />
			{/if}
			<h5 class="bloc-titre">
				La chronologie{SEPARATEUR.tiret}états datés, relances et réouverture
			</h5>
			<SyntheseChronologie metriques={m} />
		</details>
	{/if}

	{#if !edition}
		{#if synthese.difficultes}
			<section class="bloc">
				<h5 class="bloc-titre">Les difficultés{SEPARATEUR.tiret}ce qui a ralenti l'affaire</h5>
				<div class="rich-content texte">{@html safeDescription(synthese.difficultes)}</div>
			</section>
		{/if}
		{#if synthese.amelioration}
			<section class="bloc">
				<h5 class="bloc-titre">
					L'amélioration suggérée{SEPARATEUR.tiret}pour la prochaine affaire
				</h5>
				<div class="rich-content texte">{@html safeDescription(synthese.amelioration)}</div>
			</section>
		{/if}
	{/if}

	{#if proposition}
		<section class="bloc proposition" aria-label="Proposition de l'assistant">
			<h5 class="bloc-titre">Proposition de l’assistant{SEPARATEUR.tiret}à appliquer ou annuler</h5>
			<div class="rich-content texte">{@html safeDescription(proposition.synthese)}</div>
			{#if proposition.difficultes}
				<h6 class="proposition-titre">Difficultés</h6>
				<div class="rich-content texte">{@html safeDescription(proposition.difficultes)}</div>
			{/if}
			{#if proposition.amelioration}
				<h6 class="proposition-titre">Amélioration suggérée</h6>
				<div class="rich-content texte">{@html safeDescription(proposition.amelioration)}</div>
			{/if}
			<!--  Le motif de l'assistant des descriptions (`AssistantDescription`) : deux
			      gestes, pas un formulaire — rien n'est saisi ici. -->
			<div class="gestes">
				<button
					class="btn btn-outline btn-sm"
					type="button"
					disabled={enCours}
					on:click={() => (proposition = null)}>Annuler</button
				>
				<button class="btn btn-primary btn-sm" type="button" disabled={enCours} on:click={appliquer}
					>Appliquer</button
				>
			</div>
		</section>
	{/if}

	{#if gestes && brouillon}
		<!--  Les gestes d'un BROUILLON : relancer, recommencer, valider. -->
		<div class="gestes">
			<button
				type="button"
				class="btn btn-outline btn-sm"
				disabled={enCours || edition || !!proposition}
				aria-busy={sollicite === 'relancer'}
				on:click={relancer}><IconeIA enCours={sollicite === 'relancer'} /> Relancer</button
			>
			<button
				type="button"
				class="btn btn-outline btn-sm"
				disabled={enCours || edition || !!proposition}
				aria-busy={sollicite === 'recommencer'}
				on:click={recommencer}><IconeIA enCours={sollicite === 'recommencer'} /> Recommencer</button
			>
			<button
				type="button"
				class="btn btn-primary btn-sm"
				disabled={enCours || edition || vide || !!proposition}
				title={vide ? 'Rédigez la synthèse avant de la valider' : undefined}
				on:click={valider}>✅ Valider</button
			>
		</div>
	{/if}
</section>

<style>
	.synthese {
		display: flex;
		flex-direction: column;
		gap: 0.75rem;
		margin-top: 0.2rem;
	}
	.tete {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.5rem;
	}
	.titre {
		flex: 1;
		margin: 0;
	}
	h4.titre {
		display: flex;
		align-items: center;
		gap: 0.4rem;
	}
	.validee {
		font-size: var(--fs-xs);
		color: var(--color-text-muted);
	}
	.actions {
		display: flex;
		gap: 0.3rem;
	}
	.plies summary {
		cursor: pointer;
	}
	/*  Un bloc par graphique et par texte : le cadre et le sous-titre de la
	    maquette (03/10/2026). */
	.bloc {
		display: flex;
		flex-direction: column;
		gap: 0.6rem;
		padding: 0.75rem 0.9rem;
		border: 1px solid var(--color-border);
		border-radius: var(--radius);
		background: var(--color-surface);
	}
	.bloc-titre {
		margin: 0;
		font-size: var(--fs-base);
		font-weight: 500;
		color: var(--color-text);
	}
	.texte {
		color: var(--color-text);
		line-height: 1.6;
		font-size: var(--fs-md);
	}
	.texte :global(p) {
		margin: 0 0 0.4em;
	}
	/*  La proposition se distingue du texte relu : bordure de l'accent. */
	.proposition {
		border-color: var(--color-primary);
	}
	.proposition-titre {
		margin: 0;
		font-size: var(--fs-sm);
		font-weight: 600;
		color: var(--color-text);
	}
	.edition {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
	}
	.gestes {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.4rem;
		justify-content: flex-end;
	}
</style>
