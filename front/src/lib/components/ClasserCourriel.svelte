<!--
  Classer un courriel qu'aucune affaire ne désigne (#2555) — sous sa ligne, dans
  Espace CS › Courriels.

  Le message est authentifié et vient d'un correspondant connu : il attend que le
  conseil le RATTACHE à une affaire ouverte, en CRÉE une, ou l'ÉCARTE. Les affaires
  suggérées (mots de l'objet, affaires de l'expéditeur) sont une proposition, jamais
  un choix fait : le serveur ne rattache rien de lui-même (`utils/courriel_a_classer`).

  🔴 UN seul bouton principal, qui nomme sa destination (12/11/2026, même leçon que
  `TransfertsVerses`). Toucher une proposition rattachait sur-le-champ, et « Créer une
  affaire » devenait le bouton plein quand rien n'était proposé : le geste qui crée
  une affaire à part se touchait comme le bon. Désormais une proposition ou un numéro
  tapé se CHOISIT (`aria-pressed`), et « Rattacher à #… » — inactif tant que rien
  n'est choisi — conclut. Créer et écarter sont secondaires, et se confirment.
-->
<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import { courriels, type CourrielAClasser } from '#lib/api/index.ts';
	import { confirmer } from '#lib/confirmation.ts';
	import { messageErreur } from '#lib/erreurs.ts';
	import { toast } from '#lib/components/Toast.svelte';
	import Icon from '#lib/components/Icon.svelte';
	import LibelleGroupe from '#lib/components/LibelleGroupe.svelte';
	import { SEPARATEUR } from '#lib/separateurs.ts';
	import { termeAffaire } from '#lib/tickets.ts';

	export let message: CourrielAClasser;

	const dispatch = createEventDispatcher<{ classe: void }>();

	/** La proposition retenue — ou rien, si un numéro est tapé. */
	let retenue: number | null = null;
	let numero = '';
	let enCours = false;

	//  Ce que le bouton principal rattachera : le numéro tapé l'emporte, sinon la
	//  proposition retenue. « #TK-… » se colle tel qu'il s'écrit à l'écran.
	$: tape = termeAffaire(numero);
	$: proposee = message.suggestions.find((s) => s.id === retenue) ?? null;
	$: cible = tape ? { numero: tape, titre: '' } : proposee;

	function retenir(id: number) {
		retenue = retenue === id ? null : id;
		numero = '';
	}

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

	function rattacher() {
		if (!cible || enCours) return;
		const n = cible.numero;
		void faire(() => courriels.rattacher(message.id, n));
	}

	async function creer() {
		const ok = await confirmer({
			titre: 'Créer une affaire',
			message:
				'Le courriel deviendra une affaire à part, décrite par son message. S’il concerne une affaire existante, rattachez-le plutôt.',
			libelleConfirmer: 'Créer',
			libelleAnnuler: 'Revenir',
		});
		if (ok) await faire(() => courriels.creerAffaire(message.id));
	}

	async function ecarter() {
		const ok = await confirmer({
			titre: 'Écarter le courriel',
			message:
				'Rien ne sera ajouté au site, et le message gardé sera effacé. Il reste dans la boîte de réception.',
			libelleConfirmer: 'Écarter',
			libelleAnnuler: 'Revenir',
		});
		if (ok) await faire(() => courriels.ecarter(message.id));
	}
</script>

<div class="classer" aria-busy={enCours}>
	{#if message.apercu}
		<blockquote class="apercu">{message.apercu}</blockquote>
	{/if}
	<!--  UN geste, deux façons de désigner l'affaire : une proposition, ou un numéro
	      tapé. Une seule colonne, un seul bord gauche et droit, une seule hauteur. -->
	<LibelleGroupe titre="Rattacher à une affaire" id="classer-{message.id}" classe="groupe">
		{#each message.suggestions as s (s.id)}
			<button
				class="btn btn-outline suggestion"
				type="button"
				aria-pressed={!tape && retenue === s.id}
				disabled={enCours}
				on:click={() => retenir(s.id)}
				><span class="coche" aria-hidden="true"><Icon name="check" size={16} /></span><span
					class="numero">#{s.numero}</span
				><span class="titre-suggestion">{s.titre}</span></button
			>
		{/each}
		<div class="field champ-en-ligne champ-numero">
			<label for="classer-{message.id}-numero" class="libelle-numero">
				{message.suggestions.length ? 'Autre affaire' : 'Numéro de l’affaire'}
			</label>
			<input
				id="classer-{message.id}-numero"
				type="text"
				bind:value={numero}
				placeholder="TK-123456"
				autocomplete="off"
				spellcheck="false"
				on:keydown={(e) => e.key === 'Enter' && tape && rattacher()}
			/>
		</div>
		<button
			class="btn btn-primary rattacher"
			type="button"
			disabled={enCours || !cible}
			on:click={rattacher}
		>
			{#if cible}
				<span
					>Rattacher à <span class="numero">#{cible.numero}</span
					>{#if cible.titre}{SEPARATEUR.point}<span class="titre-suggestion">{cible.titre}</span
						>{/if}</span
				>
			{:else}
				Rattacher à l’affaire choisie
			{/if}
		</button>
	</LibelleGroupe>
	<!--  Les autres issues, secondaires et confirmées : elles ne rattachent rien. -->
	<div class="autres-issues">
		<button class="btn btn-outline" type="button" disabled={enCours} on:click={creer}
			>Créer une affaire</button
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
	/*  Retenue : un contour plein et la coche — un changement de teinte seul ne
	    se distinguerait pas du survol. */
	.classer .suggestion[aria-pressed='true'] {
		border-color: var(--color-primary);
		box-shadow: inset 0 0 0 1px var(--color-primary);
	}
	.coche {
		display: inline-flex;
		visibility: hidden;
		color: var(--color-primary);
	}
	.suggestion[aria-pressed='true'] .coche {
		visibility: visible;
	}
	.numero {
		font-weight: 600;
		font-variant-numeric: tabular-nums;
	}
	/*  Le bouton qui conclut prend la colonne : il nomme l'affaire, titre compris. */
	.classer .rattacher {
		justify-content: flex-start;
		flex-wrap: wrap;
		width: 100%;
		margin-top: 0.25rem;
		text-align: left;
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
	.champ-numero input {
		width: 100%;
		min-height: var(--hauteur-geste);
		margin: 0.25rem 0 0;
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
