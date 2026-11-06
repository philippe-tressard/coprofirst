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
	import LibelleGroupe from '#lib/components/LibelleGroupe.svelte';

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
	<!--  UN geste, deux façons : une affaire proposée, ou un numéro tapé. Une seule
	      colonne, un seul bord gauche et droit, une seule hauteur de contrôle. -->
	<LibelleGroupe titre="Rattacher à une affaire" id="classer-{message.id}" classe="groupe">
		{#each message.suggestions as s, i (s.id)}
			<button
				class="btn suggestion"
				class:btn-primary={i === 0}
				class:btn-outline={i > 0}
				type="button"
				disabled={enCours}
				on:click={() => rattacher(s.numero)}
				><span class="numero">#{s.numero}</span><span class="titre-suggestion">{s.titre}</span
				></button
			>
		{/each}
		<div class="field champ-en-ligne champ-numero">
			<label for="classer-{message.id}-numero" class="libelle-numero">
				{message.suggestions.length ? 'Autre affaire' : 'Numéro de l’affaire'}
			</label>
			<div class="saisie-numero">
				<input
					id="classer-{message.id}-numero"
					type="text"
					bind:value={numero}
					placeholder="TK-123456"
					autocomplete="off"
					spellcheck="false"
					on:keydown={(e) => e.key === 'Enter' && numero.trim() && rattacher(numero)}
				/>
				<button
					class="btn btn-outline"
					type="button"
					disabled={enCours || !numero.trim()}
					on:click={() => rattacher(numero)}>Rattacher</button
				>
			</div>
		</div>
	</LibelleGroupe>
	<!--  Les autres issues, séparées : elles ne rattachent rien. -->
	<div class="autres-issues">
		<button
			class="btn"
			class:btn-primary={!message.suggestions.length}
			class:btn-outline={message.suggestions.length > 0}
			type="button"
			disabled={enCours}
			on:click={creer}>Créer une affaire</button
		>
		<button class="btn btn-outline" type="button" disabled={enCours} on:click={ecarter}
			>Écarter</button
		>
	</div>
</div>

<style>
	/*  Une seule hauteur pour tout ce qui se touche du doigt dans ce bloc : la
	    cible tactile de la charte (44 px au doigt, `composants.css`) en minimum,
	    et 2,5 rem à la souris — le champ s'aligne dessus par l'étirement. */
	.classer {
		--hauteur-geste: 2.5rem;
		margin-top: 0.6rem;
		padding-top: 0.75rem;
		border-top: 1px solid var(--color-border);
		display: flex;
		flex-direction: column;
		gap: 0.75rem;
	}
	/*  Le contenu tient dans une colonne lisible ; les filets, eux, vont d'un bord
	    à l'autre de la ligne, comme celui du journal au-dessus. */
	.apercu,
	.classer :global(.groupe) {
		max-width: 36rem;
	}
	.classer .btn {
		min-height: var(--hauteur-geste);
		justify-content: center;
	}
	.apercu {
		margin: 0;
		padding: 0.4rem 0.75rem;
		border-left: 3px solid var(--color-border);
		color: var(--color-text-muted);
		font-size: var(--fs-sm);
	}
	.classer :global(.groupe) {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
		margin-top: 0.4rem;
	}
	/*  Une proposition : numéro en tête, titre à la suite — le texte part du bord
	    gauche, comme une ligne de liste, et le bouton prend toute la colonne. */
	.classer .suggestion {
		justify-content: flex-start;
		flex-wrap: wrap;
		gap: 0 0.5rem;
		width: 100%;
		text-align: left;
	}
	.numero {
		font-weight: 600;
		font-variant-numeric: tabular-nums;
	}
	.titre-suggestion {
		font-weight: 400;
		opacity: 0.85;
	}
	/*  Un cran SOUS le titre du groupe : c'est une variante du même geste, pas un
	    second intitulé — en capitales, il pesait autant que « Rattacher à une affaire ». */
	.classer .libelle-numero {
		font-size: var(--fs-sm);
		font-weight: 400;
		text-transform: none;
		letter-spacing: 0;
		color: var(--color-text-muted);
	}
	/*  Plus d'air AU-DESSUS qu'entre le libellé et sa saisie : le libellé se lit
	    avec le champ qu'il nomme, pas avec la proposition qui le précède. */
	.champ-numero {
		margin-top: 0.5rem;
	}
	/*  Le champ et son bouton sont UNE commande : même rangée, même hauteur
	    (étirement), le bouton à sa largeur naturelle. */
	.saisie-numero {
		display: flex;
		align-items: stretch;
		gap: 0.5rem;
		margin-top: 0.25rem;
	}
	.saisie-numero input {
		flex: 1 1 auto;
		min-width: 0;
		min-height: var(--hauteur-geste);
		margin: 0;
	}
	.saisie-numero .btn {
		flex: 0 0 auto;
	}
	.autres-issues {
		display: flex;
		flex-wrap: wrap;
		gap: 0.5rem;
		padding-top: 0.75rem;
		border-top: 1px solid var(--color-border);
	}
	@media (pointer: coarse) {
		.classer {
			--hauteur-geste: 44px;
		}
	}
</style>
