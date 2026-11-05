<!--
  Classer un courriel qu'aucune affaire ne désigne (#2555) — sous sa ligne, dans
  Espace CS › Courriels.

  Le message est authentifié et vient d'un correspondant connu : il attend que le
  conseil le RATTACHE à une affaire ouverte, en CRÉE une, ou l'ÉCARTE. Les affaires
  suggérées (mots de l'objet, affaires de l'expéditeur) sont une proposition, jamais
  un choix fait : le serveur ne rattache rien de lui-même (`utils/courriel_a_classer`).

  Écarter efface le message gardé : il se confirme.
-->
<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import { courriels, type CourrielAClasser } from '#lib/api/index.ts';
	import { confirmer } from '#lib/confirmation.ts';
	import { messageErreur } from '#lib/erreurs.ts';
	import { toast } from '#lib/components/Toast.svelte';

	export let message: CourrielAClasser;

	const dispatch = createEventDispatcher<{ classe: void }>();

	let numero = '';
	let enCours = false;

	async function faire(geste: () => Promise<{ bilan: string }>) {
		enCours = true;
		try {
			const { bilan } = await geste();
			toast('success', bilan.charAt(0).toUpperCase() + bilan.slice(1) + '.');
			dispatch('classe');
		} catch (e) {
			toast('error', messageErreur(e));
		} finally {
			enCours = false;
		}
	}

	const rattacher = (n: string) => faire(() => courriels.rattacher(message.id, n));
	const creer = () => faire(() => courriels.creerAffaire(message.id));

	async function ecarter() {
		const ok = await confirmer({
			titre: 'Écarter le courriel',
			message:
				'Rien ne sera ajouté au site, et le message gardé sera effacé. Il reste dans la boîte de réception.',
			libelleConfirmer: 'Écarter',
		});
		if (ok) await faire(() => courriels.ecarter(message.id));
	}
</script>

<div class="classer" aria-busy={enCours}>
	{#if message.apercu}
		<blockquote class="apercu">{message.apercu}</blockquote>
	{/if}
	{#if message.suggestions.length}
		<p class="aide intitule">Affaires ouvertes proches</p>
		<ul class="suggestions">
			{#each message.suggestions as s (s.id)}
				<li>
					<button
						class="btn btn-outline btn-sm"
						type="button"
						disabled={enCours}
						on:click={() => rattacher(s.numero)}
						>Rattacher à #{s.numero}<span class="titre-suggestion">{s.titre}</span></button
					>
				</li>
			{/each}
		</ul>
	{/if}
	<!--  Pas un `<form>` : ce n'est pas un enregistrement (`lint:soumission`), c'est un
	      geste — Entrée dans le champ le lance aussi. -->
	<div class="autre">
		<label class="field champ-court">
			Autre affaire
			<input
				type="text"
				bind:value={numero}
				placeholder="TK-123456"
				autocomplete="off"
				on:keydown={(e) => e.key === 'Enter' && numero.trim() && rattacher(numero)}
			/>
		</label>
		<button
			class="btn btn-outline btn-sm"
			type="button"
			disabled={enCours || !numero.trim()}
			on:click={() => rattacher(numero)}>Rattacher</button
		>
	</div>
	<div class="gestes">
		<button class="btn btn-primary btn-sm" type="button" disabled={enCours} on:click={creer}
			>Créer une affaire</button
		>
		<button class="btn btn-outline btn-sm" type="button" disabled={enCours} on:click={ecarter}
			>Écarter</button
		>
	</div>
</div>

<style>
	.classer {
		margin-top: 0.6rem;
		padding-top: 0.6rem;
		border-top: 1px solid var(--color-border);
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
	}
	.apercu {
		margin: 0;
		padding: 0.4rem 0.6rem;
		border-left: 3px solid var(--color-border);
		color: var(--color-text-muted);
		font-size: var(--fs-sm);
	}
	.intitule {
		margin: 0;
	}
	.suggestions {
		display: flex;
		flex-direction: column;
		gap: 0.3rem;
		margin: 0;
		padding: 0;
		list-style: none;
	}
	.suggestions .btn {
		display: flex;
		flex-wrap: wrap;
		gap: 0 0.4rem;
		text-align: left;
		max-width: 100%;
	}
	.titre-suggestion {
		color: var(--color-text-muted);
		font-weight: normal;
	}
	.autre {
		display: flex;
		flex-wrap: wrap;
		align-items: flex-end;
		gap: 0.5rem;
	}
	/*  La marge basse d'un champ décalait le bouton sous la saisie : ils se
	    tiennent sur la même ligne de base. */
	.autre .field {
		margin-bottom: 0;
	}
	.autre .btn {
		min-height: 2.5rem;
	}
	.gestes {
		display: flex;
		flex-wrap: wrap;
		gap: 0.5rem;
	}
</style>
