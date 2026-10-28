<!--
  « L'envoyer par courriel » — la SUITE du toast « Lien copié » (#1357).

  Option E des maquettes du 26/09/2026 : le clic sur 🔗 garde son effet (le lien
  est copié), et le message de confirmation propose l'envoi. Le lien d'abord,
  le champ ensuite : qui ne veut que copier ne voit rien de plus.

  Ce qui part est décidé par le serveur (`routers/partage`) : pour une affaire,
  son titre et son lien ; pour tout autre objet, ce qu'il est et son lien — le
  destinataire sans droits ne verra rien. Sous plafond. L'écran ne
  valide l'adresse que pour dire tout de suite ce qui manque.
-->
<script lang="ts">
	import { createEventDispatcher, tick } from 'svelte';
	import { partage as partageApi } from '#lib/api/index.ts';
	import type { CiblePartage } from '#lib/partage.ts';
	import { messageErreur } from '#lib/erreurs.ts';

	/** Ce qui est transmis — l'affaire, l'annonce, le sondage… (`cibleDuLien`). */
	export let cible: CiblePartage;
	/** Le bouton 🔗 qui a ouvert le message : Échap lui rend le focus. */
	export let retour: HTMLElement | null = null;

	const dispatch = createEventDispatcher<{ fermer: void }>();
	let ouvert = false;
	let email = '';
	let erreur = '';
	let envoye = '';
	let enCours = false;
	let champ: HTMLInputElement;

	const complete = (v: string) => /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(v.trim());

	async function ouvrir() {
		ouvert = true;
		await tick();
		champ?.focus();
	}

	async function envoyer() {
		if (!complete(email)) {
			erreur = 'Cette adresse n’est pas complète : il manque l’@ ou le domaine.';
			champ?.focus();
			return;
		}
		enCours = true;
		erreur = '';
		try {
			await partageApi.envoyer(cible.objet, cible.id, email.trim());
			envoye = `Envoyé à ${email.trim()}`;
		} catch (e) {
			erreur = messageErreur(e, 'L’envoi n’a pas abouti.');
		} finally {
			enCours = false;
		}
	}

	function clavier(e: KeyboardEvent) {
		if (e.key !== 'Escape') return;
		dispatch('fermer');
		retour?.focus();
	}
</script>

<div class="partage">
	{#if envoye}
		<p class="envoye" role="status">✓ {envoye}</p>
	{:else if !ouvert}
		<button
			type="button"
			class="btn btn-outline btn-sm envoyer"
			on:click={ouvrir}
			on:keydown={clavier}>✉️ L’envoyer par courriel</button
		>
	{:else}
		<form class="formulaire" on:submit|preventDefault={envoyer} novalidate>
			<!--  `.field` porte la peau du champ et son focus (`champs.css`). -->
			<div class="field">
				<input
					bind:this={champ}
					type="email"
					bind:value={email}
					on:input={() => (erreur = '')}
					placeholder="prenom.nom@exemple.fr"
					autocomplete="email"
					aria-label="Adresse du destinataire"
					aria-invalid={!!erreur}
					on:keydown={clavier}
				/>
			</div>
			<button type="submit" class="btn btn-primary btn-sm" disabled={enCours}>
				{enCours ? 'Envoi…' : 'Envoyer'}
			</button>
		</form>
		{#if erreur}<p class="erreur" role="alert">{erreur}</p>{/if}
	{/if}
</div>

<style>
	.partage {
		margin-top: 0.4rem;
	}
	/*  Un vrai bouton du site, sur UNE ligne : la bulle le rend hors de la carte
	    (`use:portail`), rien ne le comprime plus. La pression (0,97) vient de
	    `.btn` (`composants.css`). */
	.envoyer {
		width: 100%;
		white-space: nowrap;
	}
	.formulaire {
		display: flex;
		gap: 0.4rem;
	}
	.formulaire .field {
		flex: 1;
		min-width: 0;
		margin: 0;
	}
	.erreur {
		margin: 0.3rem 0 0;
		color: var(--color-danger);
	}
	.envoye {
		margin: 0.2rem 0 0;
		font-weight: 600;
	}
</style>
