<script lang="ts">
	import ChargementDiffere from '$lib/components/ChargementDiffere.svelte';
	import EtoileRequis from '$lib/components/EtoileRequis.svelte';
	import { page } from '$app/stores';
	import { sondages as sondagesApi, type SondageDetail } from '$lib/api';
	import { confirmer, confirmerPuis, SUPPRESSION } from '$lib/confirmation';
	import { tenter, messageErreur } from '$lib/erreurs';
	import { signaler } from '$lib/signalements';
	import { currentUser, isAdmin, isCS, isGestionnaire, quandAuthResolue } from '$lib/stores/auth';
	import { refuserLaCommunaute } from '$lib/communaute';
	import { safeHtml } from '$lib/sanitize';
	import { siteNomStore } from '$lib/stores/pageConfig';
	import { toast } from '$lib/components/Toast.svelte';
	import FilAriane from '$lib/components/FilAriane.svelte';
	import Reponses from '$lib/components/Reponses.svelte';
	import { fmtDateShort } from '$lib/date';
	import EtatListe from '$lib/components/EtatListe.svelte';
	import { aboutirGeste, ouvrirGeste } from '$lib/aboutissement';
	import ResultatsSondage from '$lib/components/ResultatsSondage.svelte';

	let sondage: SondageDetail | null = null;
	let loading = true;
	let selectedOption: number | null = null;
	let voting = false;
	let respectEngagement = false;
	let commentaireVote = '';
	let reponseLibre = '';

	$: optionSelectionnee = sondage?.options?.find((o) => o.id === selectedOption);
	$: champLibreActif = !!optionSelectionnee?.champ_libre;

	//  🔴 La correction passe par `FormulaireSondage`, le SEUL formulaire du
	//  sondage (#1329). Cette fiche en avait un second (`ChampsEditionSondage`),
	//  rendu en bas de page, dans un autre ordre : deux rendus d'un même objet.
	//  La règle des libellés seuls (#467) vit dans `FormulaireSondage.corriger`.
	let edition = false;
	let deleting = false;

	$: sondageId = Number($page.params.id);
	$: peutModerer = $isCS;
	$: estAuteur = sondage && $currentUser?.id === sondage.auteur_id;
	$: peutGerer = estAuteur || $isAdmin;

	//  Pas `onMount` : il précède le layout qui charge l'utilisateur (#1486).
	quandAuthResolue(async () => {
		if ($isGestionnaire) {
			//  Le motif vient de l'API, le « qui » de `$isGestionnaire` : cet écran
			//  ne réécrit plus la règle d'accès — ce qu'il affirmait à tort (15/09).
			refuserLaCommunaute($currentUser);
			loading = false;
			return;
		}
		try {
			sondage = await sondagesApi.get(sondageId);
		} catch (e) {
			toast('error', messageErreur(e, 'Erreur de chargement'));
		} finally {
			loading = false;
		}
	});

	//  `nb_votes` est ABSENT quand les résultats sont masqués (l'API ne l'envoie
	//  pas, plutôt que d'envoyer 0 qui se lirait « personne n'a voté ») : sans ce
	//  repli la somme vaudrait NaN et les pourcentages aussi.
	$: totalVotes = sondage?.options?.reduce((sum, o) => sum + (o.nb_votes ?? 0), 0) ?? 0;

	async function voter() {
		if (!selectedOption) {
			toast('error', 'Sélectionnez une option');
			return;
		}
		if (champLibreActif && !reponseLibre.trim()) {
			toast('error', 'Merci de préciser votre réponse dans le champ prévu');
			return;
		}
		if (!respectEngagement) {
			toast('error', 'Vous devez accepter la charte de respect');
			return;
		}
		//  Capturée AVANT le rappel : TypeScript ne conserve pas dans une closure le
		//  fait que la garde ci-dessus a écarté `null`.
		const option = selectedOption;
		voting = true;
		await tenter(async () => {
			await sondagesApi.voter(
				sondageId,
				option,
				commentaireVote.trim() || undefined,
				reponseLibre.trim() || undefined,
			);
			aboutirGeste('sondage.voter');
			sondage = await sondagesApi.get(sondageId);
			commentaireVote = '';
			reponseLibre = '';
		}, 'Vote enregistré');
		voting = false;
	}

	async function supprimerCommentaire(commentaireId: number) {
		//  ⚠️ La confirmation est demandée par `Reponses`, qui porte le bouton :
		//  la redemander ici ferait deux fenêtres pour un geste.
		await tenter(async () => {
			await sondagesApi.supprimerCommentaire(sondageId, commentaireId);
			if (sondage)
				sondage = {
					...sondage,
					commentaires: sondage.commentaires.filter((c) => c.id !== commentaireId),
				};
		}, 'Commentaire supprimé');
	}

	async function repondreSondage(contenu: string) {
		const publie = await tenter(async () => {
			await sondagesApi.commenter(sondageId, contenu);
			sondage = await sondagesApi.get(sondageId);
		}, 'Commentaire publié');
		//  🔴 L'échec doit REMONTER : `Reponses` ne vide son champ que si la
		//  promesse aboutit. Avaler l'erreur ici effacerait un commentaire que
		//  personne n'a publié.
		if (!publie) throw new Error('Commentaire non publié');
	}

	async function corrige() {
		sondage = await sondagesApi.get(sondageId);
		edition = false;
	}

	async function stopperSondage() {
		await confirmerPuis(
			'Stopper ce sondage maintenant ? Les résultats seront visibles immédiatement.',
			'Sondage clôturé',
			async () => {
				await sondagesApi.cloturer(sondageId);
				if (sondage) sondage = { ...sondage, cloture: true, cloture_forcee: true };
			},
		);
	}

	async function supprimerSondage() {
		if (!(await confirmer(SUPPRESSION('Ce sondage')))) return;
		deleting = true;
		//  🔴 La navigation n'a lieu QUE si la suppression a abouti — quitter
		//  l'écran sur un échec laisserait croire le sondage supprimé.
		if (await tenter(() => sondagesApi.supprimer(sondageId), 'Sondage supprimé'))
			location.href = '/sondages';
		else deleting = false;
	}

	$: peutVoter = sondage && !sondage.cloture && sondage.mon_vote === null;
	$: if (peutVoter) ouvrirGeste('sondage.voter'); //  Le geste mesuré (#1633).
	//  Décision prise par l'API, pas recomposée ici. Cette ligne valait
	//  `resultats_publics || cloture || aVote` — et cinquante lignes plus bas un
	//  second `&& sondage.resultats_publics` écrasait le tout, rendant les deux
	//  dernières branches mortes : un sondage à case décochée ne montrait JAMAIS
	//  ses résultats, pas même une fois clôturé (#397).
	$: voirResultats = sondage?.resultats_visibles ?? false;
</script>

<svelte:head><title>{sondage ? sondage.question : 'Sondage'} — {$siteNomStore}</title></svelte:head>

<FilAriane
	segments={[{ libelle: 'Communauté', href: '/sondages' }]}
	courant={sondage?.question ?? 'Sondage'}
/>

{#if loading}
	<EtatListe chargement />
{:else if !sondage}
	<EtatListe
		erreur="Ce sondage n’existe pas, ou vous n’y avez pas accès."
		titreErreur="Sondage introuvable"
	/>
{:else}
	<div class="sondage-page">
		<div class="sondage-entete">
			{#if sondage.cloture}
				<span class="badge badge-gray">Clôturé</span>
			{:else}
				<span class="badge badge-green">Ouvert</span>
			{/if}
			{#if sondage.cloture_le}
				<small class="muted">
					{sondage.cloture ? 'Clôturé' : 'Clôture'} le {fmtDateShort(sondage.cloture_le)}
				</small>
			{/if}
			{#if peutGerer}
				<div class="owner-actions">
					{#if !sondage.cloture}
						<button
							class="btn-icon-edit"
							aria-label="Modifier ce sondage"
							aria-pressed={edition}
							title="Modifier"
							on:click={() => (edition = !edition)}>&#x270F;&#xFE0F;</button
						>
						<button class="btn btn-outline btn-sm btn-stopper" on:click={stopperSondage}
							>⏹ Stopper</button
						>
					{/if}
					<button
						class="btn btn-outline btn-sm btn-supprimer"
						disabled={deleting}
						on:click={supprimerSondage}>&#x1F5D1; Supprimer</button
					>
				</div>
			{/if}
		</div>

		<!--  La correction s'ouvre SOUS l'en-tête, près du ✏️ qui l'ouvre — elle
		      était rendue en bas de page, après les résultats et les commentaires. -->
		{#if edition}
			<ChargementDiffere charger={() => import('$lib/components/FormulaireSondage.svelte')}>
				{#snippet contenu(FormulaireSondage)}
					<FormulaireSondage {sondage} on:modifie={corrige} on:annule={() => (edition = false)} />
				{/snippet}
			</ChargementDiffere>
		{/if}
		<h1 class="sondage-question">{sondage.question}</h1>
		{#if sondage.description}
			<div class="rich-content sondage-description">
				{@html safeHtml(sondage.description)}
			</div>
		{/if}

		<div class="sondage-corps">
			{#if totalVotes > 0}
				<p class="sondage-total">
					{totalVotes} vote{totalVotes > 1 ? 's' : ''}
				</p>
			{/if}

			{#if peutVoter}
				<!-- Mode vote -->
				<form on:submit|preventDefault={voter}>
					{#each sondage.options as opt (opt.id)}
						<label class="option-label" class:selected={selectedOption === opt.id}>
							<input
								type="radio"
								name="vote"
								value={opt.id}
								bind:group={selectedOption}
								on:change={() => (reponseLibre = '')}
							/>
							<span>{opt.libelle}</span>
							{#if opt.champ_libre}<span
									class="champ-libre-badge"
									title="Cette réponse inclut un champ de précision">✏️</span
								>{/if}
							{#if voirResultats}
								<span class="option-votes">{opt.nb_votes} vote{opt.nb_votes !== 1 ? 's' : ''}</span>
							{/if}
						</label>
					{/each}

					<!-- Champ libre conditionnel -->
					{#if champLibreActif}
						<!--  `.field` exigé par `lint:champs` dès le libellé associé (#561). -->
						<div class="champ-libre-box">
							<div class="field">
								<label for="sondage-reponse-libre" class="champ-libre-libelle">
									Précisez votre réponse<EtoileRequis vide={!reponseLibre.trim()} />
								</label>
								<textarea
									id="sondage-reponse-libre"
									bind:value={reponseLibre}
									placeholder="Décrivez votre réponse…"
									rows="3"
									class="champ-libre-texte"></textarea>
							</div>
						</div>
					{/if}

					<!-- Commentaire optionnel -->
					<div class="field sondage-commentaire">
						<label for="sondage-commentaire-vote">Commentaire</label>
						<textarea
							id="sondage-commentaire-vote"
							bind:value={commentaireVote}
							placeholder="Partagez votre point de vue…"
							rows="3"
							class="redimensionnable"></textarea>
					</div>

					<!-- Charte de respect -->
					<label class="respect-pledge">
						<input type="checkbox" bind:checked={respectEngagement} />
						<span>
							Je m'engage à rester respectueux envers tous les membres de la résidence. Tout propos
							irrespectueux pourra entraîner la suppression du commentaire et la suspension de mon
							compte.
						</span>
					</label>

					<button
						class="btn btn-primary sondage-voter"
						disabled={voting ||
							!selectedOption ||
							!respectEngagement ||
							(champLibreActif && !reponseLibre.trim())}
					>
						{voting ? 'Envoi…' : 'Voter'}
					</button>
				</form>
			{:else}
				<ResultatsSondage
					options={sondage.options}
					monVote={sondage.mon_vote}
					total={totalVotes}
					visibles={voirResultats}
				/>
			{/if}
		</div>

		<!-- ── Section commentaires ── -->
		<div class="comments-section">
			<h2 class="comments-title">&#x1F4AC; Commentaires ({(sondage.commentaires ?? []).length})</h2>
			<Reponses
				reponses={sondage.commentaires ?? []}
				currentUserId={$currentUser?.id}
				isCS={peutModerer}
				placeholder="Votre commentaire sur ce sondage…"
				expanded={true}
				onSubmit={repondreSondage}
				onDelete={supprimerCommentaire}
				onReport={(rid) => signaler('commentaire', rid)}
			/>
		</div>
	</div>
{/if}

<style>
	/*  `.back-link` est parti dans `FilAriane` (#365). Il disait « Communauté »
	    ici et « Retour aux tickets » sur la fiche de ticket : deux pages du même
	    site, deux conventions, aucune ne nommant la rubrique. */
	.option-label {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		padding: 0.75rem 1rem;
		border: 1px solid var(--color-border);
		border-radius: var(--radius);
		margin-bottom: 0.5rem;
		cursor: pointer;
		transition: border-color var(--duree-geste);
	}
	@media (hover: hover) and (pointer: fine) {
		.option-label:hover {
			border-color: var(--color-primary);
		}
	}
	.option-label.selected {
		border-color: var(--color-primary);
		background: var(--color-primary-light);
	}
	.option-label input {
		accent-color: var(--color-primary);
	}

	/* Charte de respect */
	.respect-pledge {
		display: flex;
		align-items: flex-start;
		gap: 0.6rem;
		margin-top: 0.85rem;
		padding: 0.75rem 1rem;
		background: var(--color-warning-fond);
		border: 1px solid #e8c87a;
		border-radius: var(--radius);
		font-size: var(--fs-md);
		color: #7a5a1a;
		cursor: pointer;
		line-height: 1.45;
	}
	.respect-pledge input {
		margin-top: 0.15rem;
		flex-shrink: 0;
		accent-color: var(--color-accent);
	}

	/* Champ libre */
	.champ-libre-box {
		margin-top: 0.75rem;
		padding: 0.75rem 1rem;
		border: 1px solid var(--color-primary);
		border-radius: var(--radius);
		background: var(--color-primary-light, #eff6ff);
	}

	/* Les styles en ligne de la page, rendus à la feuille (#1329, 28/09/2026). */
	.sondage-page {
		margin-top: 1.25rem;
	}
	.sondage-entete {
		display: flex;
		gap: 0.75rem;
		align-items: center;
		margin-bottom: 0.5rem;
		flex-wrap: wrap;
	}
	.btn-stopper {
		color: var(--color-warning-texte);
		border-color: var(--color-warning);
	}
	.btn-supprimer {
		color: var(--color-danger);
		border-color: var(--color-danger);
	}
	.sondage-question {
		font-size: 1.3rem;
		font-weight: 700;
		margin-bottom: 0.5rem;
	}
	.sondage-description {
		color: var(--color-text-muted);
		margin-bottom: 0.75rem;
	}
	.sondage-corps {
		margin-top: 1.5rem;
	}
	.sondage-total {
		font-size: var(--fs-md);
		color: var(--color-text-muted);
		margin-bottom: 1rem;
	}
	.option-votes {
		margin-left: auto;
		font-size: var(--fs-sm);
		color: var(--color-text-muted);
	}
	.champ-libre-libelle {
		font-weight: 600;
	}
	.champ-libre-texte {
		border-color: var(--color-primary);
		resize: vertical;
	}
	.sondage-commentaire {
		margin-top: 1rem;
	}
	.redimensionnable {
		resize: vertical;
	}
	.sondage-voter {
		margin-top: 1rem;
	}

	/* Commentaires (rendu par le composant partagé Reponses.svelte) */
	.comments-section {
		margin-top: 2rem;
		border-top: 1px solid var(--color-border);
		padding-top: 1.25rem;
	}
	.comments-title {
		font-size: 1rem;
		font-weight: 600;
		margin-bottom: 1rem;
	}

	/* Actions propriétaire */
	.owner-actions {
		display: flex;
		gap: 0.4rem;
		flex-wrap: wrap;
		margin-left: auto;
	}

	/* Modal */
</style>
