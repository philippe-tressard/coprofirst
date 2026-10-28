<!--
  Ma résidence › Règlement — poser une question au règlement de copropriété.

  Venu de l'Espace CS le 11/10/2026 : il s'ouvre aux copropriétaires quand
  l'administration le permet (la page masque l'onglet sinon, le serveur refuse).

  Trois blocs, dans l'ordre du geste :
  1. le TEXTE du règlement — ses fichiers pour l'admin, un lien pour les autres
     (`SectionTexteReglement`) ;
  2. la QUESTION — l'assistant répond en juriste, extraits à l'appui ;
  3. l'HISTORIQUE — une question déjà posée ne se repaie pas, et une réponse
     relue peut rejoindre la FAQ par le conseil (boîte ouverte dans la carte).
     Un copropriétaire n'y lit que SES questions : le serveur les filtre.

  L'état et les appels réseau vivent ici, la page ne garde que le choix de
  l'onglet (`svelte-patterns`, famille `Onglet<Nom>`). Le serveur décide si
  l'assistant peut répondre (`disponible`) : rien de sa configuration ne sort.
-->
<script lang="ts">
	import IconeIA from '#lib/components/IconeIA.svelte';
	import { onMount } from 'svelte';
	import CarteQuestionReglement from '#lib/components/CarteQuestionReglement.svelte';
	import EncartAvertissement from '#lib/components/EncartAvertissement.svelte';
	import EtatListe from '#lib/components/EtatListe.svelte';
	import EtoileRequis from '#lib/components/EtoileRequis.svelte';
	import FormulaireFaq from '#lib/components/FormulaireFaq.svelte';
	import SectionTexteReglement from '#lib/components/SectionTexteReglement.svelte';
	import { toast } from '#lib/components/Toast.svelte';
	import {
		faq as faqApi,
		reglement as reglementApi,
		type EtatReglement,
		type QuestionReglement,
	} from '#lib/api/index.ts';
	import { basculer } from '#lib/accordeon.ts';
	import { confirmer } from '#lib/confirmation.ts';
	import { cibleDuHash, revelerCible } from '#lib/deepLink.ts';
	import { messageErreur } from '#lib/erreurs.ts';
	import { categorieSaisie, saisieFaqVide, type SaisieFaq } from '#lib/faq.ts';
	import { richEmpty } from '#lib/publications.ts';
	import { isAdmin, isCS } from '#lib/stores/auth.ts';

	let etat: EtatReglement | null = null;
	let questions: QuestionReglement[] = [];
	let chargement = true;
	let erreur = '';

	let question = '';
	let envoi = false;

	let ouvert: number | null = null;
	let publication: number | null = null;
	let formFaq: SaisieFaq = saisieFaqVide();
	let categories: string[] = [];
	let erreurCategories = '';
	let enregistrementFaq = false;

	onMount(async () => {
		try {
			[etat, questions] = await Promise.all([reglementApi.etat(), reglementApi.questions()]);
		} catch (e) {
			erreur = messageErreur(e);
		} finally {
			chargement = false;
		}
		//  `#question-reglement-<id>` : une question dont on a copié le lien.
		const cible = cibleDuHash('question-reglement');
		if (cible !== null) {
			ouvert = cible;
			revelerCible(`question-reglement-${cible}`);
		}
	});

	async function recharger() {
		[etat, questions] = await Promise.all([reglementApi.etat(), reglementApi.questions()]);
	}

	async function poser() {
		if (!question.trim()) return;
		envoi = true;
		try {
			const q = await reglementApi.poser(question.trim());
			questions = [q, ...questions];
			ouvert = q.id;
			publication = null;
			question = '';
		} catch (e) {
			toast('error', messageErreur(e));
		} finally {
			envoi = false;
		}
	}

	async function supprimerQuestion(q: QuestionReglement) {
		const dansLaFaq = q.faq_item_id
			? " L'entrée de FAQ publiée à partir de cette réponse reste, et se retire depuis la FAQ."
			: '';
		if (
			!(await confirmer({
				titre: `Supprimer la question « ${q.question} » ?`,
				message: `La question et sa réponse sont effacées de l'historique, et une nouvelle question identique sera refacturée.${dansLaFaq}`,
				libelleConfirmer: 'Supprimer',
				danger: true,
			}))
		)
			return;
		try {
			await reglementApi.supprimerQuestion(q.id);
			questions = questions.filter((x) => x.id !== q.id);
			if (ouvert === q.id) ouvert = null;
			if (publication === q.id) publication = null;
			toast('success', 'Question supprimée.');
		} catch (e) {
			toast('error', messageErreur(e));
		}
	}

	async function ouvrirPublication(q: QuestionReglement) {
		if (publication === q.id) {
			publication = null;
			return;
		}
		formFaq = { ...saisieFaqVide(), question: q.question, reponse: q.reponse };
		publication = q.id;
		ouvert = null;
		erreurCategories = '';
		try {
			categories = await faqApi.categories();
		} catch (e) {
			erreurCategories = messageErreur(e);
		}
	}

	async function publier(q: QuestionReglement) {
		const categorie = categorieSaisie(formFaq);
		if (!formFaq.question.trim() || richEmpty(formFaq.reponse) || !categorie) {
			toast('error', 'Question, catégorie et réponse sont obligatoires.');
			return;
		}
		enregistrementFaq = true;
		try {
			const maj = await reglementApi.publierDansLaFaq(q.id, {
				categorie,
				question: formFaq.question.trim(),
				reponse: formFaq.reponse.trim(),
			});
			questions = questions.map((x) => (x.id === maj.id ? maj : x));
			publication = null;
			toast('success', 'Réponse publiée dans la FAQ.');
		} catch (e) {
			toast('error', messageErreur(e));
		} finally {
			enregistrementFaq = false;
		}
	}
</script>

<!--  Deux lecteurs, deux phrases. Celle du copropriétaire est arbitrée mot pour mot
      le 11/10/2026 : le conseil ne répond pas à sa place, un juriste ou le syndic si. -->
<EncartAvertissement>
	{#if $isCS}
		Les réponses sont un <strong>avis indicatif</strong>, rédigé par l'assistant d'après le texte de
		travail joint ici : il ne se substitue pas aux actes authentiques, qui seuls font foi.
		Relisez-le — et vérifiez les extraits signalés ⚠️ — avant de le relayer.
	{:else}
		Les réponses sont un <strong>avis indicatif</strong> : seuls les actes authentiques font foi. En cas
		de doute, interrogez un juriste ou le syndic.
	{/if}
</EncartAvertissement>

<EtatListe {chargement} {erreur}>
	{#if etat}
		<SectionTexteReglement {etat} onRecharger={recharger} />

		<section class="card config-section">
			<h3 class="config-section-title">Votre question</h3>
			<form on:submit|preventDefault={poser}>
				<label class="field"
					><span>Question<EtoileRequis vide={!question.trim()} /></span><textarea
						rows="3"
						maxlength="2000"
						bind:value={question}
						placeholder="Ex. : Un copropriétaire peut-il installer une climatisation sur son balcon ?"
					></textarea></label
				>
				{#if !etat.disponible}
					<EncartAvertissement compact>
						{#if $isCS}
							L'assistant n'est pas activé pour cet usage : Admin › Assistant IA › « Question au
							règlement de copropriété ».
						{:else}
							L'assistant ne répond pas pour le moment : réessayez plus tard.
						{/if}
					</EncartAvertissement>
				{:else if !etat.texte_disponible}
					<EncartAvertissement compact>
						{#if $isAdmin}
							Aucun fichier Markdown n'est joint : joignez le texte du règlement ci-dessus.
						{:else}
							Le texte du règlement n'est pas encore à la disposition de l'assistant.
						{/if}
					</EncartAvertissement>
				{/if}
				<div class="form-actions">
					<button
						type="submit"
						class="btn btn-primary"
						disabled={envoi || !question.trim() || !etat.disponible || !etat.texte_disponible}
						aria-busy={envoi}
						><IconeIA enCours={envoi} />
						{envoi ? 'Lecture du règlement…' : 'Poser la question'}</button
					>
				</div>
				{#if envoi}
					<p class="aide">
						L'assistant lit tout le règlement avant de répondre : comptez jusqu'à deux minutes.
					</p>
				{/if}
			</form>
		</section>
	{/if}

	<h3 class="titre-historique">{$isCS ? 'Questions posées' : 'Vos questions'}</h3>
	<EtatListe
		vide={questions.length === 0}
		titreVide="Aucune question posée"
		messageVide={$isCS
			? "Les réponses de l'assistant s'afficheront ici."
			: "Les réponses de l'assistant s'afficheront ici. Vous seul et le conseil syndical les lisez."}
	>
		{#each questions as q (q.id)}
			<CarteQuestionReglement
				{q}
				ouvert={ouvert === q.id}
				publication={publication === q.id}
				on:basculer={() => {
					publication = null;
					ouvert = basculer(ouvert, q.id);
				}}
				on:publier={() => ouvrirPublication(q)}
				on:supprimer={() => supprimerQuestion(q)}
			>
				<svelte:fragment slot="formulaire">
					<!--  Une entrée de FAQ ne porte aucun auteur ; la question, elle, peut
					      le désigner (11/10/2026 — « en anonymisant l'auteur »). -->
					<p class="aide">
						Retirez de la question et de la réponse tout ce qui désignerait qui l'a posée : nom,
						lot, étage, situation personnelle.
					</p>
					<FormulaireFaq
						bind:form={formFaq}
						{categories}
						{erreurCategories}
						enregistrement={enregistrementFaq}
						onEnregistrer={() => publier(q)}
						on:annule={() => (publication = null)}
					/>
				</svelte:fragment>
			</CarteQuestionReglement>
		{/each}
	</EtatListe>
</EtatListe>

<style>
	.titre-historique {
		margin: 1.5rem 0 0.6rem;
		font-size: var(--fs-md);
	}
</style>
