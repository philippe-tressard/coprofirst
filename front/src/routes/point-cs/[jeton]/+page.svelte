<!--
  Le LIEN DE VALIDATION d'un compte rendu de point CS / Syndic (#2042) — la page
  qu'ouvre un présent depuis le courriel.

  Publique : un membre du syndic n'a souvent pas de compte, le jeton seul
  l'identifie. 🔴 L'OUVRIR NE VALIDE RIEN (`standards/03` §5 bis) : les
  messageries ouvrent les liens avant leur destinataire. Seuls « Je valide » et
  l'envoi d'un commentaire agissent, par un geste.

  Le CR se lit tel que le serveur le sert — en entier, « CS et présents »
  compris (#2082) : les présents l'ont entendu. Chaque affaire porte « qui la lit »
  (le mot de la pastille de la page Affaires, #2089) et, après un renvoi, « Modifié en révision N ». Le texte riche
  passe par l'assainisseur.
-->
<script lang="ts">
	import { SEPARATEUR } from '#lib/separateurs.ts';
	import { onMount } from 'svelte';
	import { lieu } from '#lib/lieu.svelte.ts';
	import EtatListe from '#lib/components/EtatListe.svelte';
	import EnteteAuthentification from '#lib/components/EnteteAuthentification.svelte';
	import PiedFormulaire from '#lib/components/PiedFormulaire.svelte';
	import EtoileRequis from '#lib/components/EtoileRequis.svelte';
	import { toast } from '#lib/components/Toast.svelte';
	import { pointsConseil, type CompteRenduParLien } from '#lib/api/index.ts';
	import { fmtDate, fmtDatetime, fmtTime } from '#lib/date.ts';
	import { messageErreur } from '#lib/erreurs.ts';
	import { safeHtml } from '#lib/sanitize.ts';
	import { getSiteNom } from '#lib/stores/pageConfig.ts';
	import { LIBELLE_CS_ET_PRESENTS } from '#lib/points-conseil.ts';
	import Badge from '#lib/components/Badge.svelte';

	const siteNom = getSiteNom();
	$: jeton = $lieu.params.jeton ?? '';

	let cr: CompteRenduParLien | null = null;
	let chargement = true;
	let erreur = '';
	let enCours = false;
	let commentaireOuvert = false;
	let commentaire = '';
	let commente = false;

	async function geste(action: () => Promise<CompteRenduParLien>, succes: string) {
		enCours = true;
		try {
			cr = await action();
			toast('success', succes);
			return true;
		} catch (e) {
			toast('error', messageErreur(e, 'Envoi impossible'));
			return false;
		} finally {
			enCours = false;
		}
	}

	async function envoyerCommentaire() {
		if (!commentaire.trim()) return;
		const ok = await geste(
			() => pointsConseil.commenterParLien(jeton, commentaire.trim()),
			'Commentaire envoyé au conseil syndical',
		);
		if (ok) {
			commentaireOuvert = false;
			commentaire = '';
			commente = true;
		}
	}

	onMount(async () => {
		try {
			cr = await pointsConseil.lien(jeton);
		} catch (e) {
			erreur = messageErreur(e, 'Lien inconnu ou remplacé par un envoi plus récent');
		} finally {
			chargement = false;
		}
	});
</script>

<svelte:head><title>Compte rendu à valider — {siteNom}</title></svelte:head>

<div class="auth-page">
	<article class="card colonne-lecture lien-cr">
		<EnteteAuthentification sousTitre="Compte rendu du point CS / Syndic" />

		{#if chargement || erreur || !cr}
			<EtatListe {chargement} {erreur} titreErreur="Ce lien ne mène à aucun compte rendu" />
		{:else}
			<p class="quand">
				{fmtDatetime(cr.debut)}{#if cr.fin}{SEPARATEUR.fleche}{fmtTime(cr.fin)}{/if} · {cr.ou}
			</p>
			<p class="presents">Présents : {cr.presents.join(', ') || '—'}</p>
			{#if cr.revision > 1}
				<p class="muet">Révision {cr.revision} du compte rendu.</p>
			{/if}

			{#each cr.abordees as a (a.numero)}
				<section class="abordee">
					<h2>{a.numero} · {a.titre}</h2>
					<p class="marques">
						{#if a.lecture}<Badge teinte="badge-blue" compact title="Qui la lit">{a.lecture}</Badge
							>{/if}
						{#if a.conseil_seul}<Badge teinte="badge-purple" compact>{LIBELLE_CS_ET_PRESENTS}</Badge
							>{/if}
						{#if a.marque}<Badge teinte="badge-orange" compact>{a.marque}</Badge>{/if}
					</p>
					<div class="contenu">{@html safeHtml(a.contenu)}</div>
				</section>
			{:else}
				<p class="muet">Aucune affaire abordée.</p>
			{/each}
			{#if cr.non_traitees.length}
				<p class="muet">Non traitées : {cr.non_traitees.join(' · ')}</p>
			{/if}

			<div class="decision">
				{#if cr.etat === 'valide'}
					<p class="alert alert-success">Ce compte rendu est validé.</p>
				{:else if cr.deja_valide}
					<p class="alert alert-success">
						Merci : votre validation est enregistrée.
						{#if cr.echeance}Sans réponse des autres présents, le compte rendu sera validé le
							{fmtDate(cr.echeance)}.{/if}
					</p>
				{:else}
					{#if commente}
						<p class="alert alert-success">
							Votre commentaire est transmis au conseil syndical, qui corrigera le compte rendu
							avant de vous le renvoyer.
						</p>
					{:else if cr.echeance}
						<p class="muet">
							Sans réponse de votre part, le compte rendu sera validé le {fmtDate(cr.echeance)}.
						</p>
					{/if}
					{#if commentaireOuvert}
						<form on:submit|preventDefault={envoyerCommentaire}>
							<div class="field">
								<label for="commentaire-cr"
									>Votre commentaire<EtoileRequis vide={!commentaire.trim()} /></label
								>
								<textarea
									id="commentaire-cr"
									rows="5"
									maxlength="4000"
									placeholder="Ce qui est à corriger ou à compléter."
									bind:value={commentaire}></textarea>
							</div>
							<PiedFormulaire
								{enCours}
								desactive={!commentaire.trim()}
								on:annule={() => (commentaireOuvert = false)}
							/>
						</form>
					{:else}
						<div class="rangee-gestes">
							<button
								type="button"
								class="btn btn-outline"
								disabled={enCours}
								on:click={() => (commentaireOuvert = true)}>Envoyer un commentaire</button
							>
							<button
								type="button"
								class="btn btn-primary"
								disabled={enCours}
								on:click={() =>
									geste(() => pointsConseil.validerParLien(jeton), 'Validation enregistrée')}
								>Je valide</button
							>
						</div>
					{/if}
				{/if}
			</div>
		{/if}
	</article>
</div>

<style>
	.marques {
		display: flex;
		flex-wrap: wrap;
		gap: 0.3rem;
		margin: 0 0 0.35rem;
	}
	.lien-cr {
		padding: 1.5rem;
	}
	.quand,
	.presents {
		margin: 0 0 0.35rem;
		font-size: var(--fs-sm);
	}
	.abordee {
		padding: 0.6rem 0;
		border-top: 1px solid var(--color-border);
	}
	.abordee h2 {
		font-size: var(--fs-base);
		margin: 0 0 0.25rem;
		color: var(--color-primary);
	}
	.contenu {
		font-size: var(--fs-sm);
	}
	.muet {
		color: var(--color-text-muted);
		font-size: var(--fs-sm);
	}
	.decision {
		margin-top: 1rem;
		padding-top: 0.75rem;
		border-top: 1px solid var(--color-border);
	}
</style>
