<!--
  ChoixAffaireAvis.svelte — l'affaire qu'un avis juge (15/11/2026).

  Deux groupes, dans cet ordre : les affaires où le prestataire est intervenant, puis
  les autres (servies déjà triées par `GET /prestataires/affaires-a-noter`). Une frappe
  filtre sur le numéro et le titre, tout de suite, ET lance la recherche DÉTAILLÉE de la
  page Affaires (`rechercheAffaires`, `GET /tickets/recherche`) : équipement, lieu,
  description, suites, messages, pièces jointes. Ce qu'elle trouve montre où
  (`ExtraitRecherche`) — rien n'est recherché ici avec une seconde règle.

  Pourquoi pas `ChoixAffaire` : il lit `GET /tickets/choix`, qui ne sait pas qui
  intervient, et sa recherche s'arrête au titre ; l'étendre aurait changé les cinq
  écrans qui l'emploient. Les gestes du champ (« # » d'un numéro, lien collé) sont
  les siens, par `termeAffaire` et `idAffaireDepuisLien`.
-->
<script lang="ts">
	import { onDestroy } from 'svelte';
	import type { AffaireAvis, CorrespondanceAffaire } from '#lib/api/index.ts';
	import { RECHERCHE_MIN, rechercheAffaires } from '#lib/recherche-affaires.ts';
	import { idAffaireDepuisLien, termeAffaire } from '#lib/tickets.ts';
	import ChampRecherche from './ChampRecherche.svelte';
	import ExtraitRecherche from './ExtraitRecherche.svelte';

	/** Toutes les affaires, celles du prestataire d'abord. */
	export let affaires: AffaireAvis[] = [];
	/** L'affaire retenue (son id en texte) ; vide = un avis général. Lié au parent. */
	export let affaireId = '';
	export let prestataireNom = '';
	export let id: string;

	/** Combien de propositions par groupe, sans recherche : au-delà, on cherche. */
	const PAR_GROUPE = 6;

	let recherche = '';
	const detail = rechercheAffaires();
	onDestroy(() => detail.chercher(''));

	$: detail.chercher(recherche);
	$: terme = termeAffaire(recherche).toLowerCase();
	$: idLien = idAffaireDepuisLien(recherche);
	$: actif = terme.length >= RECHERCHE_MIN || idLien !== null;
	$: choisie = affaires.find((a) => String(a.id) === affaireId) ?? null;

	/** Ce que la recherche détaillée a trouvé, par affaire : où, et le passage. */
	$: trouvees = new Map<number, CorrespondanceAffaire>(
		($detail.resultats ?? []).map((c) => [c.ticket_id, c]),
	);
	$: rang = new Map(($detail.resultats ?? []).map((c, i) => [c.ticket_id, i]));

	/** Les dépendances en ARGUMENTS : Svelte ne voit pas ce qu'une fonction lit en dedans,
	 *  et la liste ne se recalculerait pas à l'arrivée de la recherche détaillée. */
	function correspond(
		a: AffaireAvis,
		cherche: string,
		lien: number | null,
		detaillees: Map<number, CorrespondanceAffaire>,
	): boolean {
		if (lien !== null) return a.id === lien;
		return `${a.numero} ${a.titre}`.toLowerCase().includes(cherche) || detaillees.has(a.id);
	}

	//  Avec une recherche : le titre trouvé d'abord, puis la pertinence du serveur ; le
	//  groupe du prestataire reste devant. Sans : les plus récentes de chaque groupe.
	$: candidates = actif ? affaires.filter((a) => correspond(a, terme, idLien, trouvees)) : affaires;
	$: ordonnees = actif
		? [...candidates].sort(
				(x, y) =>
					Number(y.intervient) - Number(x.intervient) ||
					(rang.get(x.id) ?? -1) - (rang.get(y.id) ?? -1),
			)
		: candidates;
	$: siennes = ordonnees.filter((a) => a.intervient).slice(0, actif ? 20 : PAR_GROUPE);
	$: autres = ordonnees.filter((a) => !a.intervient).slice(0, actif ? 20 : PAR_GROUPE);
	$: groupes = [
		{ cle: 'siennes', titre: `Avec ${prestataireNom || 'ce prestataire'}`, liste: siennes },
		{ cle: 'autres', titre: 'Autres affaires', liste: autres },
	].filter((g) => g.liste.length > 0);

	$: aide = $detail.enCours
		? 'Recherche dans le suivi, les messages et les pièces jointes…'
		: actif && !groupes.length
			? 'Aucune affaire ne correspond.'
			: !actif
				? 'Sans affaire, l’avis porte sur le prestataire en général.'
				: '';

	function choisir(a: AffaireAvis) {
		affaireId = String(a.id);
		recherche = '';
	}
</script>

<div class="choix-affaire-avis">
	<span class="field-titre">Affaire concernée</span>
	{#if choisie}
		<div class="retenue">
			<span class="cav-numero">{choisie.numero}</span>
			<span class="cav-titre">{choisie.titre}</span>
			<button type="button" class="btn btn-sm btn-outline" on:click={() => (affaireId = '')}>
				Changer
			</button>
		</div>
	{:else}
		<ChampRecherche
			{id}
			bind:valeur={recherche}
			placeholder="Numéro, titre, équipement, mot du suivi…"
			dans="numéro, titre, lieu, équipement, description, suivi, messages, pièces jointes"
		/>
		{#if aide}<p class="aide">{aide}</p>{/if}
		{#each groupes as g (g.cle)}
			<p class="groupe">{g.titre}</p>
			<ul class="propositions" aria-label={g.titre}>
				{#each g.liste as a (a.id)}
					{@const trouvee = actif ? trouvees.get(a.id) : undefined}
					<li>
						<button type="button" class="proposition" on:click={() => choisir(a)}>
							<span class="ligne">
								<span class="cav-numero">{a.numero}</span>
								<span class="cav-titre">{a.titre}</span>
							</span>
							{#if !a.intervient && a.intervenants}
								<span class="intervenants">{a.intervenants}</span>
							{/if}
							{#if trouvee}<ExtraitRecherche correspondance={trouvee} />{/if}
						</button>
					</li>
				{/each}
			</ul>
		{/each}
	{/if}
</div>

<style>
	.choix-affaire-avis {
		display: flex;
		flex-direction: column;
		gap: 0.35rem;
	}
	.field-titre {
		font-weight: 600;
	}
	.retenue {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		flex-wrap: wrap;
		padding: 0.4rem 0.75rem;
		border: 1px solid var(--color-border);
		border-radius: var(--radius);
	}
	.retenue .cav-titre {
		flex: 1 1 10rem;
	}
	.groupe {
		margin: 0.4rem 0 0;
		font-weight: 600;
		color: var(--color-text-muted);
	}
	.propositions {
		list-style: none;
		margin: 0;
		padding: 0;
		border: 1px solid var(--color-border);
		border-radius: var(--radius);
		overflow: hidden;
	}
	.propositions li + li {
		border-top: 1px solid var(--color-border);
	}
	/*  Une ligne entière cliquable, à hauteur de pouce (`standards/11` §10). */
	.proposition {
		display: flex;
		flex-direction: column;
		gap: 0.15rem;
		width: 100%;
		min-height: 44px;
		padding: 0.5rem 0.75rem;
		border: none;
		background: var(--color-surface);
		text-align: left;
		cursor: pointer;
		font-family: inherit;
		color: inherit;
	}
	.proposition:focus-visible {
		outline: 2px solid var(--color-primary);
		outline-offset: -2px;
	}
	@media (hover: hover) and (pointer: fine) {
		.proposition:hover .cav-titre {
			color: var(--color-primary);
		}
	}
	.ligne {
		display: flex;
		gap: 0.5rem;
		align-items: baseline;
		min-width: 0;
	}
	.cav-numero {
		flex-shrink: 0;
		font-weight: 700;
		color: var(--color-text-muted);
	}
	.cav-titre {
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.intervenants {
		color: var(--color-text-muted);
	}
</style>
