<!--
  L'AIGUILLAGE de l'hôte commun d'une installation à plusieurs copropriétés (#1894).

  Sur l'hôte commun, l'écran de connexion demande d'abord À QUELLE copropriété on
  veut se connecter : code postal + nom (arbitrage du 17/10/2026). Le serveur
  renvoie l'adresse de la copropriété, et le navigateur y part — c'est là qu'on se
  connecte : l'hôte commun ne fait que rediriger (spec §4.1 bis).

  Ce que l'écran ne fait PAS, exprès (règle 5, pas d'énumération) : aucune liste,
  aucune suggestion, aucune complétion — ni du serveur, ni du navigateur
  (`autocomplete="off"` sur le nom). Un échec affiche le message du serveur, le
  même dans tous les cas ; le serveur plafonne les tentatives.

  `echec` : un message à afficher d'emblée — la route `/<alias>` le passe quand
  l'alias de l'adresse n'a mené nulle part.
-->
<script lang="ts">
	import { aiguillage } from '#lib/api/index.ts';
	import { messageErreur } from '#lib/erreurs.ts';
	import EtoileRequis from '#lib/components/EtoileRequis.svelte';

	export let echec = '';

	let codePostal = '';
	let nom = '';
	let envoi = false;

	async function aller() {
		echec = '';
		envoi = true;
		try {
			const { destination } = await aiguillage.aller({ code_postal: codePostal, nom });
			window.location.assign(destination);
		} catch (e) {
			echec = messageErreur(e);
			envoi = false;
		}
	}
</script>

<p class="aiguillage-consigne">
	Ce serveur héberge plusieurs copropriétés. Indiquez la vôtre pour rejoindre son espace.
</p>

{#if echec}
	<div class="alert alert-error" role="alert">{echec}</div>
{/if}

<form on:submit|preventDefault={aller}>
	<div class="field">
		<label for="aiguillage-cp">Code postal<EtoileRequis vide={!codePostal} /></label>
		<input
			id="aiguillage-cp"
			type="text"
			inputmode="numeric"
			pattern={'\\d{5}'}
			maxlength="5"
			autocomplete="postal-code"
			bind:value={codePostal}
			required
		/>
	</div>

	<div class="field">
		<label for="aiguillage-nom">Nom de la copropriété<EtoileRequis vide={!nom} /></label>
		<input
			id="aiguillage-nom"
			type="text"
			maxlength="120"
			autocomplete="off"
			spellcheck="false"
			bind:value={nom}
			required
		/>
	</div>

	<div class="btn-wrapper">
		<button class="btn btn-primary" type="submit" disabled={envoi}>
			{envoi ? 'Recherche…' : 'Continuer'}
		</button>
	</div>
</form>

<style>
	.aiguillage-consigne {
		margin: 0 0 1rem;
		text-align: center;
		color: var(--color-text-muted);
		font-size: var(--fs-base);
	}
</style>
