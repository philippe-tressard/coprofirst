<!--
  **La section Archives d'un écran** — repliée, groupée par année, chaque année
  dépliable à son tour.

  ## Pourquoi ce composant (#516)

  Demandé à l'écran le 19/08/2026 : *« unifier sur chaque page la section
  d'historique / archivage, trouver le terme le plus juste et le standardiser…
  rends-la jolie (dépliable et par année) »*.

  Le motif existait **deux fois**, écrit différemment :
    - `HistoriqueActualites` — `SectionRepliee` + `grouperParAnnee`, chargement
      différé au premier dépliage, compteur `null` tant que rien n'est chargé ;
    - `calendrier/+page.svelte` — sa propre implémentation (`.archive-year-header`,
      `expandedArchiveYears`), avec un niveau de plus (année ▸ mois).

  Deux codes pour la même chose, donc deux aspects et deux comportements. Ce
  composant reprend le plus abouti des deux et le rend disponible aux écrans qui
  n'ont **aucune** section d'archives — ce qui devient nécessaire avec #515, où
  l'archivage automatique s'étend à sept objets : un objet archivé sans vue
  d'archives **disparaît du site**.

  ## 🔴 Le mot : « Archives », pas « Historique »

  `Historique` est déjà pris, et par une notion tranchée : le **fil d'un objet**
  (cadre #430 — `RubriqueHistorique`, « 📋 Historique »). Sur l'écran Tickets les
  deux coexistaient, sans rapport l'un avec l'autre.

  « Archives » dit ce que la section contient — des objets rangés, pas une action
  — et répond au geste existant **📦 Archiver**. C'est aussi le mot déjà employé
  par le Calendrier.

  ⚠️ « Archivage » a été envisagé et écarté : c'est l'**action**, pas le
  **contenu**. La section liste des objets.

  ## Le style voyage avec le balisage

  Les bandeaux d'année redéclarent leur chevron plutôt que d'emprunter
  celui de `SectionRepliee` — leur compteur, lui, est `Compte`, le même objet : Svelte scope les styles au composant qui
  rend le balisage, et compter sur celui d'un autre est exactement ce qui a fait
  partir les pastilles nues en production (v2.67.11).
-->
<script lang="ts" generics="T">
	import SectionRepliee from '#lib/components/SectionRepliee.svelte';
	import Compte from '#lib/components/Compte.svelte';
	import { TITRE_ARCHIVES } from '#lib/archives.ts';
	import { basculer } from '#lib/accordeon.ts';

	/** Les objets archivés. Vide tant que rien n'est chargé. */
	export let items: T[] = [];
	/** La date qui classe un objet — chaque type a la sienne (#515). */
	export let dateDe: (item: T) => string | Date | null | undefined;
	/** Lié : c'est lui qui déclenche le chargement différé chez l'appelant. */
	export let ouvert = false;
	/**  ⚠️ `null` tant que rien n'a été chargé : annoncer « 0 » se lirait
	 *   « il n'y a rien » alors qu'on n'a pas encore regardé. */
	export let compte: number | null = null;
	/**  Le titre vient de `#lib/archives` et non d'une chaîne écrite ici : cinq
	 *   écrans l'avaient en dur, et concordaient parce qu'on venait de les
	 *   aligner à la main (#516, point 4). */
	export let titre = TITRE_ARCHIVES;
	export let messageVide = 'Aucun élément archivé.';
	/** Affiche le message de vide : l'appelant sait s'il a fini de charger. */
	export let charge = false;

	//  UNE année dépliée à la fois (accordéon, 30/09/2026 — `#lib/accordeon`).
	//  C'était un `Set` : dix années ouvertes l'une après l'autre faisaient une
	//  page sans fin.
	let anneeDepliee: number | null = null;

	//  Groupement générique : le composant ne connaît aucun type d'objet, c'est
	//  l'appelant qui dit où lire la date. Une version par entité redonnerait la
	//  duplication que ce composant supprime.
	$: parAnnee = (() => {
		const groupes = new Map<number, T[]>();
		for (const it of items ?? []) {
			const d = dateDe(it);
			if (!d) continue;
			const annee = new Date(d).getFullYear();
			if (!Number.isFinite(annee)) continue;
			if (!groupes.has(annee)) groupes.set(annee, []);
			groupes.get(annee)!.push(it);
		}
		return [...groupes.entries()].sort(([a], [b]) => b - a);
	})();

	/**  L'année à ouvrir au premier dépliage, quand l'appelant en connaît une —
	 *   un lien profond vers un objet archivé, par exemple. `null` = la plus
	 *   récente.
	 *
	 *   ⚠️ Sans ce point d'entrée, l'écran Tickets ne pouvait pas adopter ce
	 *   composant : il ouvre l'année de l'objet visé, et son groupement par
	 *   année était donc réécrit à la main — la TROISIÈME copie du même bloc,
	 *   avec l'Espace CS. La capacité manquante était la vraie cause du doublon,
	 *   pas la paresse (#516). */
	export let anneeOuverte: number | null = null;

	//  La plus récente s'ouvre seule au premier dépliage : une section qui
	//  s'ouvre sur rien de visible donne l'impression d'être vide.
	let premierDepliage = true;
	$: if (ouvert && premierDepliage && parAnnee.length > 0) {
		const visee =
			anneeOuverte !== null && parAnnee.some(([a]) => a === anneeOuverte)
				? anneeOuverte
				: parAnnee[0][0];
		anneeDepliee = visee;
		derniereVisee = anneeOuverte;
		premierDepliage = false;
	}

	//  Une année désignée APRÈS le premier dépliage (second lien profond, sans
	//  rechargement de la page) doit s'ouvrir aussi — sinon le lien mène à une
	//  section ouverte sur une AUTRE année, ce qui se lit « l'objet n'existe
	//  plus ».
	//
	//  ⚠️ Sur un CHANGEMENT de l'année désignée seulement (`derniereVisee`) :
	//  comparer à l'année dépliée rouvrirait la désignée dès qu'on en déplie
	//  une autre — l'accordéon interdirait alors toute autre année.
	let derniereVisee: number | null = null;
	$: if (
		!premierDepliage &&
		anneeOuverte !== null &&
		anneeOuverte !== derniereVisee &&
		parAnnee.some(([a]) => a === anneeOuverte)
	) {
		anneeDepliee = anneeOuverte;
		derniereVisee = anneeOuverte;
	}
</script>

<SectionRepliee {titre} {compte} bind:ouvert>
	<div>
		{#if charge && parAnnee.length === 0}
			<p class="archives-vide">{messageVide}</p>
		{:else}
			{#each parAnnee as [annee, objets] (annee)}
				<div class="archives-annee">
					<button
						class="archives-annee-entete"
						on:click|stopPropagation={() => (anneeDepliee = basculer(anneeDepliee, annee))}
						aria-expanded={anneeDepliee === annee}
					>
						<span class="archives-annee-libelle">{annee}</span>
						<Compte n={objets.length} />
						<span class="archives-chevron">{anneeDepliee === annee ? '▲' : '▼'}</span>
					</button>
					{#if anneeDepliee === annee}
						{#each objets as objet (dateDe(objet))}
							<slot {objet} />
						{/each}
					{/if}
				</div>
			{/each}
		{/if}
	</div>
</SectionRepliee>

<style>
	.archives-vide {
		color: var(--color-text-muted);
		font-size: var(--fs-base);
		margin: 0.5rem 0 0;
	}
	.archives-chevron {
		font-size: var(--fs-sm);
		color: var(--color-text-muted);
		flex-shrink: 0;
	}
	.archives-annee {
		margin-bottom: 0.5rem;
	}
	.archives-annee-entete {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		width: 100%;
		background: var(--color-bg);
		border: 1px solid var(--color-border);
		border-radius: var(--radius);
		padding: 0.5rem 0.75rem;
		cursor: pointer;
		font-size: var(--fs-base);
		font-weight: 600;
		color: var(--color-text);
		margin-bottom: 0.3rem;
	}
	@media (hover: hover) and (pointer: fine) {
		.archives-annee-entete:hover {
			border-color: var(--color-primary);
			color: var(--color-primary);
		}
	}
	.archives-annee-libelle {
		flex: 1;
		text-align: left;
	}
</style>
