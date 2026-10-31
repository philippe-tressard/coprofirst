<!--
  DialogueFusion.svelte — « Fusionner les affaires liées ? », posé à la clôture (#1704).

  Arbitré le 05/10/2026 : clore une affaire peut ABSORBER ses affaires liées
  encore ouvertes — leurs suites rejoignent celle qu'on clôt, dans l'ordre
  chronologique, et elles sont closes en même temps. Le conseil juge du « même
  besoin, même périmètre » : la boîte le rappelle, elle ne le décide pas.

  🔒 Une affaire lue par moins de monde que celle qu'on clôt est montrée
  DÉSACTIVÉE, avec sa raison : la fusion rendrait ses suites lisibles à qui ne
  les lisait pas. Le serveur la refuse de toute façon (`utils/fusion_affaires`).
  Quand le conseil a une façon de l'autoriser (restreindre, élargir — l'inversion
  n'a pas lieu à la clôture), `ConciliationFusion` montre l'écart et les noms
  de ceux que la conciliation ferait lire autrement, à confirmer (27/10/2026).

  Rien n'est coché par défaut : une fusion ne se défait pas.

  ⚠️ S'emploie par `demanderFusion()` (`#lib/fusion-affaires`), jamais
  directement — comme `Confirmation` par `confirmer()`.
-->
<script lang="ts">
	import Modale from './Modale.svelte';
	import ConciliationFusion from './ConciliationFusion.svelte';
	import type { CandidateFusion } from '#lib/api/index.ts';
	import type { DemandeFusion } from '#lib/fusion-affaires.ts';
	import {
		choixPourServeur,
		conciliable,
		decisionIncomplete,
		decisionPrete,
		type Decisions,
	} from '#lib/fusion-conciliation.ts';
	import { SEPARATEUR } from '#lib/separateurs.ts';

	/** Le numéro de l'affaire qu'on clôt — celle qui absorbe. */
	export let numero: string;
	/** L'état de clôture, en toutes lettres (« Résolu », « Annulé »). */
	export let etat: string;
	export let candidates: CandidateFusion[];
	/** `null` : on renonce à clore ; sinon ce qu'on absorbe (rien, éventuellement) : on clôt. */
	export let onReponse: (r: DemandeFusion | null) => void;

	let cochees: number[] = [];
	let decisions: Decisions = {};

	function basculer(id: number, oui: boolean) {
		cochees = oui ? [...cochees, id] : cochees.filter((x) => x !== id);
	}

	/** Les refusées que le conseil a conciliées, noms confirmés. */
	$: conciliees = candidates.filter((c) => !c.fusionnable && decisionPrete(c, decisions[c.id]));
	/** Une option est choisie sans que ses noms soient confirmés : on ne clôt pas. */
	$: incomplet = candidates.some((c) => !c.fusionnable && decisionIncomplete(c, decisions[c.id]));
	$: total = cochees.length + conciliees.length;
	$: libelle = total ? `Clore et fusionner (${total})` : 'Clore sans fusionner';

	function clore() {
		onReponse({
			fusionner: [...cochees, ...conciliees.map((c) => c.id)],
			conciliations: choixPourServeur(candidates, decisions),
		});
	}
</script>

<Modale titre="Fusionner les affaires liées ?" on:fermer={() => onReponse(null)}>
	<div class="modal-body">
		<p class="fusion-message">
			Fusionnez seulement les affaires qui portent le <strong>même besoin</strong> sur le
			<strong>même périmètre</strong>. Leurs suites rejoindront {numero} dans l'ordre chronologique, elles
			seront closes en même temps ({etat}), et la synthèse de clôture les couvrira toutes. Une
			fusion ne se défait pas.
		</p>
		<ul class="fusion-liste">
			{#each candidates as c (c.id)}
				<li>
					<label class="case" class:attenue={!c.fusionnable}>
						<input
							type="checkbox"
							disabled={!c.fusionnable}
							checked={cochees.includes(c.id)}
							on:change={(e) => basculer(c.id, e.currentTarget.checked)}
						/>
						<span>{c.numero}{SEPARATEUR.tiret}{c.titre}</span>
					</label>
					{#if c.motif}
						<p class="aide sous-case">Impossible : {c.motif}.</p>
					{/if}
					{#if conciliable(c)}
						<ConciliationFusion
							candidate={c}
							numeroPrincipale={numero}
							bind:decision={decisions[c.id]}
						/>
					{/if}
				</li>
			{/each}
		</ul>
	</div>
	<!--  « Annuler » AVANT l'action, comme toute confirmation (`Confirmation.svelte`). -->
	<div class="modal-footer form-actions">
		<button type="button" class="btn btn-outline" on:click={() => onReponse(null)}>
			Annuler
		</button>
		<button type="button" class="btn btn-primary" disabled={incomplet} on:click={clore}>
			{libelle}
		</button>
	</div>
</Modale>

<style>
	.fusion-message {
		margin: 0 0 0.75rem;
		line-height: 1.5;
	}
	.fusion-liste {
		list-style: none;
		margin: 0;
		padding: 0;
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
	}
</style>
