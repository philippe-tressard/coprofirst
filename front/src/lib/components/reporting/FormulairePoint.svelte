<!--
  Le QUAND, le OÙ et le QUI d'un point CS / Syndic — maquette A1 (bandeau
  compact), arbitrée le 17/10/2026 (#2041). Sert l'ouverture et la correction.

  Finitions arbitrées sur maquette le 17/10/2026, après un premier usage :

  - **Quand / Où** : Début (requis), Fin, Moyen et Lieu, chacun son intitulé
    AU-DESSUS du champ, sur une même ligne — la bascule « Sur place | À
    distance » décalait l'intitulé du lieu.
  - **Moyen** : une liste (Sur place, Visioconférence, Téléphone, Sur place et
    à distance), lue au serveur (`participants.moyens`) ; le Lieu ne se saisit
    que si quelqu'un est sur place. Les lieux proposés — la copropriété, le
    cabinet du syndic, les derniers lieux — viennent de la base, en liste de
    suggestions : aucune adresse ne part à un service extérieur.
  - **Qui** : une rangée par population (`GROUPES_PRESENTS`), son intitulé en
    tête. Les invités en `PastilleRetirable` — la croix rouge des fichiers, pour
    un même geste « retirer » —, puis « Ajouter un invité » (`InvitePoint`) :
    autant qu'on veut.
-->
<script lang="ts">
	import Pastille from '#lib/components/Pastille.svelte';
	import PastilleRetirable from '#lib/components/PastilleRetirable.svelte';
	import EtoileRequis from '#lib/components/EtoileRequis.svelte';
	import IconeAction from '#lib/components/IconeAction.svelte';
	import PiedFormulaire from '#lib/components/PiedFormulaire.svelte';
	import InvitePoint from './InvitePoint.svelte';
	import type {
		MembrePoint,
		ParticipantsPoint,
		PointEntree,
		PresentEntree,
	} from '#lib/api/index.ts';
	import { depuisChampLocal, pourChampLocal } from '#lib/date.ts';
	import { GROUPES_PRESENTS, cleMembre, nomPresent } from '#lib/points-conseil.ts';

	export let idPrefixe: string;
	export let participants: ParticipantsPoint;
	/** Les valeurs de départ — le point corrigé, une reprise, ou le défaut. */
	export let initial: PointEntree;
	/** Ce que la reprise dit, s'il y en a une (« Repris du point … »). */
	export let reprise = '';
	export let enCours = false;
	export let onEnregistre: (entree: PointEntree) => void;
	export let onAnnule: () => void;

	let debut = pourChampLocal(initial.debut);
	let fin = pourChampLocal(initial.fin);
	let moyen = initial.moyen;
	let lieu = initial.lieu ?? '';
	let coches = new Set(
		initial.presents
			.filter((p) => p.nature !== 'invite')
			.map((p) => cleMembre(p.nature, p.membre_id)),
	);
	let invites: PresentEntree[] = initial.presents.filter((p) => p.nature === 'invite');
	let inviteOuvert = false;

	$: avecLieu = participants.moyens.find((m) => m.cle === moyen)?.avec_lieu ?? true;
	$: annuaire = { cs: participants.conseil, syndic: participants.syndic } as Record<
		string,
		MembrePoint[]
	>;

	function basculer(cle: string) {
		const s = new Set(coches);
		if (s.has(cle)) s.delete(cle);
		else s.add(cle);
		coches = s;
	}

	function membres(): PresentEntree[] {
		return (['cs', 'syndic'] as const).flatMap((nature) =>
			annuaire[nature]
				.filter((m) => coches.has(cleMembre(nature, m.id)))
				.map((m) => ({ nature, membre_id: m.id })),
		);
	}

	/** Ce qui précède le nom d'un invité, en gris : son entreprise, sinon « Invité ». */
	function prefixeInvite(inv: PresentEntree): string {
		return (inv.prenom || inv.nom) && inv.entreprise ? inv.entreprise : 'Invité';
	}

	function enregistrer() {
		const d = depuisChampLocal(debut);
		if (!d) return;
		onEnregistre({
			debut: d,
			fin: depuisChampLocal(fin),
			moyen,
			lieu: avecLieu ? lieu.trim() || null : null,
			presents: [...membres(), ...invites],
		});
	}
</script>

<form class="point-form" on:submit|preventDefault={enregistrer}>
	{#if reprise}
		<p class="aide reprise">{reprise}</p>
	{/if}
	<div class="quand-ou">
		<div class="field champ-en-ligne">
			<label for="{idPrefixe}-debut">Début<EtoileRequis vide={!debut} /></label>
			<input id="{idPrefixe}-debut" type="datetime-local" required bind:value={debut} />
		</div>
		<div class="field champ-en-ligne">
			<label for="{idPrefixe}-fin">Fin</label>
			<input id="{idPrefixe}-fin" type="datetime-local" bind:value={fin} />
		</div>
		<div class="field champ-en-ligne pleine">
			<label for="{idPrefixe}-moyen">Moyen</label>
			<select id="{idPrefixe}-moyen" bind:value={moyen}>
				{#each participants.moyens as m (m.cle)}
					<option value={m.cle}>{m.libelle}</option>
				{/each}
			</select>
		</div>
		{#if avecLieu}
			<div class="field champ-en-ligne pleine">
				<label for="{idPrefixe}-lieu">Lieu</label>
				<input
					id="{idPrefixe}-lieu"
					type="text"
					maxlength="120"
					list="{idPrefixe}-lieux"
					placeholder="Loge du gardien"
					bind:value={lieu}
				/>
				<datalist id="{idPrefixe}-lieux">
					{#each participants.lieux as l (l.adresse)}
						<option value={l.adresse}>{l.libelle}</option>
					{/each}
				</datalist>
			</div>
		{/if}
	</div>

	<div class="qui" role="group" aria-labelledby="{idPrefixe}-qui">
		<span class="libelle-groupe" id="{idPrefixe}-qui">Qui</span>
		{#each GROUPES_PRESENTS as g (g.nature)}
			<div class="population" role="group" aria-labelledby="{idPrefixe}-qui-{g.nature}">
				<span class="nom-population" id="{idPrefixe}-qui-{g.nature}">{g.libelle}</span>
				<div class="membres">
					{#if g.nature === 'invite'}
						{#each invites as inv, i (i)}
							<PastilleRetirable
								prefixe={prefixeInvite(inv)}
								nom={nomPresent(inv)}
								aideRetirer="Retirer cet invité"
								on:click={() => (invites = invites.filter((_, j) => j !== i))}
							/>
						{/each}
						{#if !inviteOuvert}
							<button
								type="button"
								class="btn btn-sm btn-outline"
								on:click={() => (inviteOuvert = true)}
							>
								<IconeAction icone="plus" /> Ajouter un invité
							</button>
						{/if}
					{:else if annuaire[g.nature].length}
						{#each annuaire[g.nature] as m (m.id)}
							<Pastille
								petite
								bascule
								active={coches.has(cleMembre(g.nature, m.id))}
								on:click={() => basculer(cleMembre(g.nature, m.id))}>{nomPresent(m)}</Pastille
							>
						{/each}
					{:else}
						<span class="aide">Aucun membre dans l’annuaire.</span>
					{/if}
				</div>
			</div>
		{/each}
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
	</div>

	<PiedFormulaire petit {enCours} desactive={!debut} on:annule={onAnnule} />
</form>

<style>
	.point-form {
		display: flex;
		flex-direction: column;
		gap: 0.75rem;
	}
	/*  Une même ligne d'intitulés : chaque champ porte le sien AU-DESSUS, et la
	    grille aligne les cellules en haut. Au téléphone, Début et Fin côte à
	    côte ; le moyen et le lieu, chacun sur sa ligne. */
	.quand-ou {
		display: grid;
		grid-template-columns: repeat(3, minmax(0, 12rem)) minmax(0, 1fr);
		align-items: start;
		gap: 0.75rem;
	}
	@media (max-width: 767px) {
		.quand-ou {
			grid-template-columns: repeat(2, minmax(0, 1fr));
		}
		.pleine {
			grid-column: 1 / -1;
		}
	}
	.qui {
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
		padding-top: 0.75rem;
		border-top: 1px solid var(--color-border);
	}
	/*  Une rangée par population : son nom à gauche, ses pastilles à droite ; au
	    téléphone, le nom passe au-dessus. */
	.population {
		display: grid;
		grid-template-columns: 9rem minmax(0, 1fr);
		align-items: start;
		gap: 0.5rem;
		padding: 0.4rem 0;
	}
	.population + .population {
		border-top: 1px dashed var(--color-border);
	}
	.nom-population {
		padding-top: 0.25rem;
		font-size: var(--fs-sm);
		color: var(--color-text-muted);
	}
	.membres {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.35rem;
		min-width: 0;
	}
	@media (max-width: 767px) {
		.population {
			grid-template-columns: minmax(0, 1fr);
			gap: 0.3rem;
		}
	}
	.reprise {
		margin: 0;
	}
</style>
