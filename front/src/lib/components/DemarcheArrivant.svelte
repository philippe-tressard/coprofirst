<!--
  La démarche « Nouvel arrivant » du profil : le résident dit s'il emménage
  (interphone, boîte aux lettres…) ou s'il était déjà là. Elle ne s'affiche que
  tant qu'il n'a pas répondu.

  Extrait de `routes/(app)/profil/+page.svelte` le 29/09/2026 (#779,
  modularité) : état, gestes et rendu partent ensemble — la page ne s'en
  servait que pour décider d'afficher la section.
-->
<script lang="ts">
	import { auth as authApi, type User } from '#lib/api/index.ts';
	import { currentUser, setUser } from '#lib/stores/auth.ts';
	import { tenter } from '#lib/erreurs.ts';
	import { toast } from '#lib/components/Toast.svelte';
	import EncartAvertissement from '#lib/components/EncartAvertissement.svelte';

	export let batiments: { id: number; numero: string }[] = [];

	let choix: '' | 'nouvel_arrivant' | 'deja_resident' = '';
	let batimentNumero = '';
	let ancienResident = '';
	let ancienResidentInconnu = false;
	let enregistrement = false;

	//  Même déclencheur que les champs du profil : le STORE, pas le montage — le
	//  layout `(app)` le peuple après les `onMount` des enfants.
	let initialise = false;
	$: if ($currentUser && !initialise) {
		initialise = true;
		initialiserDepuis($currentUser);
	}

	function initialiserDepuis(u: User) {
		batimentNumero = u.batiment_nom?.replace(/[^0-9]/g, '') ?? '';
		// Démarche arrivant : lire depuis la base (fallback localStorage pour migration)
		if (u.demarche_arrivant === 'nouvel_arrivant' || u.demarche_arrivant === 'deja_resident') {
			choix = u.demarche_arrivant;
			return;
		}
		const savedChoix = localStorage.getItem(`profil_arrivant_choix_${u.id}`);
		if (savedChoix === 'nouvel_arrivant' || savedChoix === 'deja_resident') {
			choix = savedChoix;
			// Migrer vers la base
			authApi
				.updateMe({ demarche_arrivant: savedChoix })
				.then((updated) => setUser(updated))
				.catch(() => {});
		}
	}

	async function declarerNouvelArrivant() {
		if (!ancienResidentInconnu && !ancienResident.trim()) {
			toast('error', "Indiquez l'ancien résident ou cochez 'Je ne sais pas'.");
			return;
		}
		enregistrement = true;
		await tenter(async () => {
			const batimentFinal = batimentNumero
				? `Bât. ${batimentNumero}`
				: ($currentUser?.batiment_nom || '').trim() || null;
			await authApi.declarerNouvelArrivant({
				batiment: batimentFinal,
				ancien_resident: ancienResidentInconnu ? null : ancienResident.trim() || null,
				ancien_resident_inconnu: ancienResidentInconnu,
			});
			choix = 'nouvel_arrivant';
			// Rafraîchir le user en store (la base a été mise à jour côté serveur)
			authApi
				.me()
				.then((u) => setUser(u))
				.catch(() => {});
		}, 'Déclaration Nouvel Arrivant envoyée');
		enregistrement = false;
	}

	async function declarerDejaResident() {
		await tenter(async () => {
			const updated = await authApi.updateMe({ demarche_arrivant: 'deja_resident' });
			setUser(updated);
			choix = 'deja_resident';
		}, 'Choix enregistré : déjà résident (aucune démarche nouvel arrivant).');
	}
</script>

{#if !choix}
	<section class="card demarche">
		<h2 class="section-title">Démarche Nouvel Arrivant</h2>
		<p class="aide consigne">
			Ce choix vous appartient : vous êtes la meilleure personne pour savoir si vous venez d'arriver
			dans la résidence.
		</p>
		<div class="explication">
			<EncartAvertissement>
				Vous venez de créer un compte sur la plateforme.
				<br />
				<strong>Nouvel arrivant</strong> : vous emménagez réellement dans la résidence (Démarches
				nouvel arrivant : interphone, BAL, ...)
				<br />
				<strong>Déjà résident</strong> : vous venez de créer un compte mais vous étiez déjà résident (donc
				pas de démarche nouvel arrivant)
			</EncartAvertissement>
		</div>

		<!--  Les bâtiments viennent de la copropriété. Un repli « Bât. 1 à 4 » écrit
		      en dur les remplaçait quand la liste manquait : c'étaient ceux de CETTE
		      résidence (29/09/2026). La page dit déjà, par son bandeau, que la liste
		      n'a pas pu être chargée. -->
		<div class="field">
			<label for="arr-bat">Bâtiment concerné</label>
			<select id="arr-bat" bind:value={batimentNumero}>
				<option value="">— Sélectionner —</option>
				{#each batiments as bat (bat.numero)}
					<option value={String(bat.numero)}>{`Bât. ${bat.numero}`}</option>
				{/each}
			</select>
		</div>
		<div class="field">
			<label for="arr-ancien">Nom de l'ancien résident</label>
			<input
				id="arr-ancien"
				type="text"
				bind:value={ancienResident}
				disabled={ancienResidentInconnu}
				placeholder="Ex : Mme Dupont"
			/>
		</div>
		<label class="case-inconnu">
			<input type="checkbox" bind:checked={ancienResidentInconnu} />
			Je ne sais pas
		</label>
		<div class="form-actions">
			<button class="btn btn-primary" on:click={declarerNouvelArrivant} disabled={enregistrement}>
				{enregistrement ? 'Envoi…' : 'Je suis un nouvel arrivant'}
			</button>
			<button
				class="btn btn-arrivant-deja"
				type="button"
				on:click={declarerDejaResident}
				disabled={enregistrement}
			>
				Je suis déjà résident
			</button>
		</div>
	</section>
{/if}

<style>
	.demarche {
		margin-bottom: 1.5rem;
	}
	.consigne {
		margin-bottom: 0.6rem;
	}
	.explication {
		margin-bottom: 0.8rem;
	}
	.case-inconnu {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		margin-top: -0.35rem;
		margin-bottom: 0.7rem;
		font-size: var(--fs-base);
		color: var(--color-text-muted);
	}
	.btn-arrivant-deja {
		background: var(--color-success-plein);
		color: var(--color-sur-plein);
	}
	@media (hover: hover) and (pointer: fine) {
		.btn-arrivant-deja:hover:not(:disabled) {
			background: #256f47;
		}
	}
</style>
