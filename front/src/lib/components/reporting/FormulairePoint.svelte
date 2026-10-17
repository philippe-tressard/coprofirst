<!--
  Le QUAND, le OÙ et le QUI d'un point CS / Syndic — maquette A1 (bandeau
  compact), arbitrée le 17/10/2026 (#2041). Sert l'ouverture et la correction.

  - **Quand** : début (requis), fin facultative.
  - **Où** : Sur place | À distance, et un lieu. Les lieux proposés — la
    résidence, le cabinet du syndic, les derniers lieux — viennent de la base,
    en liste de suggestions du champ : aucune adresse ne part à un service
    extérieur.
  - **Qui** : une pastille par membre du CS et du syndic (bascule), les invités
    en pastilles, et « Ajouter un invité » (`InvitePoint`).
-->
<script lang="ts">
	import Pastille from '$lib/components/Pastille.svelte';
	import ChoixPastilles from '$lib/components/ChoixPastilles.svelte';
	import EtoileRequis from '$lib/components/EtoileRequis.svelte';
	import IconeAction from '$lib/components/IconeAction.svelte';
	import PiedFormulaire from '$lib/components/PiedFormulaire.svelte';
	import InvitePoint from './InvitePoint.svelte';
	import type { ParticipantsPoint, PointEntree, PresentEntree } from '$lib/api';
	import { depuisChampLocal, pourChampLocal } from '$lib/date';
	import { cleMembre, nomPresent } from '$lib/points-conseil';

	export let idPrefixe: string;
	export let participants: ParticipantsPoint;
	/** Les valeurs de départ — le point corrigé, une reprise, ou le défaut. */
	export let initial: PointEntree;
	/** Ce que la reprise dit, s'il y en a une (« Repris du point … »). */
	export let reprise = '';
	export let enCours = false;
	export let onEnregistre: (entree: PointEntree) => void;
	export let onAnnule: () => void;

	const OU = [
		{ val: 'place', label: 'Sur place' },
		{ val: 'distance', label: 'À distance' },
	];

	let debut = pourChampLocal(initial.debut);
	let fin = pourChampLocal(initial.fin);
	let ou = initial.a_distance ? 'distance' : 'place';
	let lieu = initial.lieu ?? '';
	let coches = new Set(
		initial.presents
			.filter((p) => p.nature !== 'invite')
			.map((p) => cleMembre(p.nature, p.membre_id)),
	);
	let invites: PresentEntree[] = initial.presents.filter((p) => p.nature === 'invite');
	let inviteOuvert = false;

	function basculer(cle: string) {
		const s = new Set(coches);
		if (s.has(cle)) s.delete(cle);
		else s.add(cle);
		coches = s;
	}

	function membres(): PresentEntree[] {
		return [
			...participants.conseil
				.filter((m) => coches.has(cleMembre('cs', m.id)))
				.map((m) => ({ nature: 'cs' as const, membre_id: m.id })),
			...participants.syndic
				.filter((m) => coches.has(cleMembre('syndic', m.id)))
				.map((m) => ({ nature: 'syndic' as const, membre_id: m.id })),
		];
	}

	function enregistrer() {
		const d = depuisChampLocal(debut);
		if (!d) return;
		onEnregistre({
			debut: d,
			fin: depuisChampLocal(fin),
			a_distance: ou === 'distance',
			lieu: lieu.trim() || null,
			presents: [...membres(), ...invites],
		});
	}
</script>

<form class="point-form" on:submit|preventDefault={enregistrer}>
	{#if reprise}
		<p class="aide reprise">{reprise}</p>
	{/if}
	<div class="ligne">
		<div class="field champ-en-ligne">
			<label for="{idPrefixe}-debut">Début<EtoileRequis vide={!debut} /></label>
			<input id="{idPrefixe}-debut" type="datetime-local" required bind:value={debut} />
		</div>
		<div class="field champ-en-ligne">
			<label for="{idPrefixe}-fin">Fin</label>
			<input id="{idPrefixe}-fin" type="datetime-local" bind:value={fin} />
		</div>
		<ChoixPastilles
			options={OU}
			bind:valeur={ou}
			tous={false}
			libelle="Où"
			libelleVisible
			radio="{idPrefixe}-ou"
			defilante={false}
		/>
		<div class="field champ-en-ligne lieu">
			<label for="{idPrefixe}-lieu">{ou === 'distance' ? 'Moyen' : 'Lieu'}</label>
			<input
				id="{idPrefixe}-lieu"
				type="text"
				maxlength="120"
				list="{idPrefixe}-lieux"
				placeholder={ou === 'distance' ? 'Visioconférence, téléphone…' : 'Loge du gardien'}
				bind:value={lieu}
			/>
			<datalist id="{idPrefixe}-lieux">
				{#each participants.lieux as l (l.adresse)}
					<option value={l.adresse}>{l.libelle}</option>
				{/each}
			</datalist>
		</div>
	</div>

	<div class="qui" role="group" aria-labelledby="{idPrefixe}-qui">
		<span class="intitule" id="{idPrefixe}-qui">Qui</span>
		{#if participants.conseil.length}
			<span class="groupe">CS</span>
			{#each participants.conseil as m (m.id)}
				<Pastille
					petite
					bascule
					active={coches.has(cleMembre('cs', m.id))}
					on:click={() => basculer(cleMembre('cs', m.id))}>{nomPresent(m)}</Pastille
				>
			{/each}
		{/if}
		{#if participants.syndic.length}
			<span class="groupe">Syndic</span>
			{#each participants.syndic as m (m.id)}
				<Pastille
					petite
					bascule
					active={coches.has(cleMembre('syndic', m.id))}
					on:click={() => basculer(cleMembre('syndic', m.id))}>{nomPresent(m)}</Pastille
				>
			{/each}
		{/if}
		{#if invites.length}
			<span class="groupe">Invités</span>
			{#each invites as inv, i (i)}
				<span class="invite">
					{nomPresent(inv)}{inv.entreprise && (inv.prenom || inv.nom) ? ` · ${inv.entreprise}` : ''}
					<button
						type="button"
						class="btn-icon"
						aria-label="Retirer l’invité"
						on:click={() => (invites = invites.filter((_, j) => j !== i))}
						><IconeAction icone="x" /></button
					>
				</span>
			{/each}
		{/if}
		{#if !inviteOuvert}
			<button type="button" class="btn btn-sm btn-outline" on:click={() => (inviteOuvert = true)}>
				<IconeAction icone="plus" /> Ajouter un invité
			</button>
		{/if}
	</div>
	{#if inviteOuvert}
		<InvitePoint
			{idPrefixe}
			onAjoute={(inv) => {
				invites = [...invites, inv];
				inviteOuvert = false;
			}}
			onAnnule={() => (inviteOuvert = false)}
		/>
	{/if}

	<PiedFormulaire petit {enCours} desactive={!debut} on:annule={onAnnule} />
</form>

<style>
	.point-form {
		display: flex;
		flex-direction: column;
		gap: 0.6rem;
	}
	.ligne {
		display: flex;
		flex-wrap: wrap;
		align-items: flex-end;
		gap: 0.5rem 1rem;
	}
	.lieu {
		flex: 1 1 14rem;
	}
	.qui {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.35rem 0.5rem;
	}
	.intitule {
		font-size: var(--fs-xs);
		text-transform: uppercase;
		letter-spacing: 0.05em;
		color: var(--color-text-muted);
		margin-right: 0.25rem;
	}
	.groupe {
		font-size: var(--fs-xs);
		color: var(--color-text-muted);
		margin-left: 0.25rem;
	}
	.invite {
		display: inline-flex;
		align-items: center;
		gap: 0.25rem;
		font-size: var(--fs-sm);
		padding: 0.1rem 0.25rem 0.1rem 0.6rem;
		border: 1px dashed var(--color-border);
		border-radius: 999px;
	}
	.reprise {
		margin: 0;
	}
</style>
