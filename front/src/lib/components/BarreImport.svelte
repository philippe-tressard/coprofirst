<!--
  Les trois bandeaux d'un écran d'IMPORT : statistiques, téléversement, réglages
  du tableau (recherche et statut).

  ## Pourquoi ce composant existe (27/08/2026, #453)

  Les trois écrans d'import de l'administration — lots, télécommandes, badges
  Vigik — portaient ces trois blocs **à l'identique**, aux données près : mêmes
  classes, même structure, même bouton, même libellé « Importer un fichier
  Excel ». Soixante lignes de balisage recopiées trois fois.

  ⚠️ Les trois écrans ne sont PAS le même objet, et ce composant ne prétend pas
  le contraire. Les imports de télécommandes et de badges l'étaient (identiques à
  87 %, fusionnés en `OngletImportAcces`) ; celui des LOTS ne l'est qu'à 38 % — il
  a un tri, une action « auto-résoudre » de plus, et un compte rendu de
  téléversement bien plus riche. Forcer les trois dans un composant unique aurait
  produit une pièce à vingt propriétés, plus difficile à lire que les deux
  fichiers qu'elle remplace.

  Ce qu'on extrait, c'est donc **ce qui est réellement commun** — la mise en
  forme —, pas ce qui se ressemble. La différence n'est pas cosmétique : le jour
  où un quatrième import arrive, il hérite des bandeaux sans hériter d'un
  comportement qui n'est pas le sien.

  ## Responsive

  Les trois bandeaux enveloppent (`flex-wrap`) : sur téléphone, les tuiles de
  statistiques passent à la ligne, et les boutons de filtre aussi. C'est ce que
  les copies faisaient déjà pour les statistiques et le téléversement — mais
  **pas** pour la rangée de filtres, dont le `display:flex` en ligne n'avait pas
  de `flex-wrap` : au-delà de quatre statuts, les boutons débordaient de la
  largeur de l'écran. Corrigé ici, pour les trois d'un coup.

  ## La RECHERCHE de chaque tableau (#2173, 23/10/2026)

  Demandé : « offrir la possibilité de recherche dans chacun des 3 tableaux ».
  Elle se pose ICI, une fois pour les trois, dans la grille des réglages du site
  (`ReglagesListe`, la page Affaires, standard depuis le 10/10/2026, déjà sur
  Badges & accès) : la **Recherche en tête** — on cherche avant de filtrer —,
  puis le **Statut** en pastilles, le compteur sur la pastille retenue
  (`ux-patterns` §5). Les boutons « Filtrer : » sont devenus ces pastilles :
  même filtre, même ordre, même appel au serveur. Sous 768 px la grille passe
  en une colonne, le champ prend la largeur, et le tableau défile dans sa carte.

  Ce composant ne cherche RIEN : il expose la saisie (`recherche`) et reçoit le
  nombre de lignes affichées (`compte`). La règle — tous les mots, sans accents
  ni casse — est `contientTousLesMots` (`#lib/texte`), appliquée par l'écran à
  ce que SA ligne montre : lui seul sait quelles colonnes il rend.
-->
<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import BilanRecherche from '#lib/components/BilanRecherche.svelte';
	import ChampRecherche from '#lib/components/ChampRecherche.svelte';
	import ChoixPastilles from '#lib/components/ChoixPastilles.svelte';
	import ReglagesListe from '#lib/components/ReglagesListe.svelte';

	/**
	 * Les tuiles du bandeau de statistiques. `couleur` est absente pour le total,
	 * qui reste neutre.
	 *
	 * ⚠️ Type écrit EN LIGNE et non `export interface` : le `<script>` d'un
	 * composant Svelte n'accepte pas de déclaration de type exportée — elle devrait
	 * vivre dans un `<script context="module">`. La forme est simple et locale,
	 * elle reste ici.
	 */
	export let tuiles: { valeur: number | string; libelle: string; couleur?: string }[] = [];
	/** Les colonnes attendues du fichier, affichées en aide. */
	export let colonnesAttendues: string;
	/** Le libellé de la case de remplacement — il diffère d'un import à l'autre.
	 *  Vide : pas de case — l'import remplace toujours ce qui attend (l'état
	 *  descriptif, #2213). */
	export let libelleRemplacer = 'Remplacer les imports en attente existants';
	/** Un import est en cours : le bouton se verrouille. */
	export let enCours = false;
	/** Les statuts proposés au filtre, dans l'ordre. `''` = tous. */
	export let statuts: string[] = [];
	/** Libellé de chaque statut. */
	export let libellesStatuts: Record<string, string> = {};
	/** Le statut retenu (lié bidirectionnellement). */
	export let filtre = '';
	/** La recherche saisie (liée) — l'écran filtre ses lignes avec. */
	export let recherche = '';
	/** Ce que la recherche lit, dit en exemple dans le champ. */
	export let exempleRecherche = 'Un nom, un lot, un code…';
	/** Le nombre de lignes que le tableau AFFICHE, recherche et statut appliqués. */
	export let compte = 0;
	/** Unique sur l'écran : relie le libellé « Recherche » à son champ. */
	export let idRecherche: string;

	const dispatch = createEventDispatcher<{
		importer: { fichier: File; remplacer: boolean };
		filtrer: string;
	}>();

	let fichier: FileList | null = null;
	let remplacer = false;

	//  Le statut est un filtre du SERVEUR : chaque changement relit la liste.
	$: options = statuts
		.filter((s) => s !== '')
		.map((s) => ({ val: s, label: libellesStatuts[s] ?? s }));
	let filtreLu = filtre;
	$: if (filtre !== filtreLu) {
		filtreLu = filtre;
		dispatch('filtrer', filtre);
	}

	function importer() {
		if (!fichier?.length) return;
		dispatch('importer', { fichier: fichier[0], remplacer });
		fichier = null;
	}
</script>

{#if tuiles.length > 0}
	<div class="imp-stats-bar card">
		{#each tuiles as t (t.libelle)}
			<div class="imp-stat">
				<span class="imp-stat-val" style={t.couleur ? `color:${t.couleur}` : ''}>{t.valeur}</span>
				<span class="imp-stat-lbl">{t.libelle}</span>
			</div>
		{/each}
	</div>
{/if}

<div class="card imp-upload-section">
	<h2 class="section-title">Importer un fichier Excel</h2>
	<p class="muted colonnes">
		Colonnes attendues : <code>{colonnesAttendues}</code>
	</p>
	<!--  Ce qui aide à PRÉPARER le fichier (un gabarit à télécharger) se pose ici,
	      à côté de ce qu'il prépare — pas parmi les actions sur les lignes. -->
	<slot name="preparer" />
	<div class="imp-upload-row">
		<input type="file" accept=".xlsx,.xls" bind:files={fichier} class="imp-file-input" />
		{#if libelleRemplacer}
			<label class="imp-checkbox-label">
				<input type="checkbox" bind:checked={remplacer} />
				{libelleRemplacer}
			</label>
		{/if}
		<button class="btn btn-primary" on:click={importer} disabled={enCours || !fichier?.length}>
			{enCours ? 'Import…' : 'Importer'}
		</button>
	</div>
	<!--  Une AUTRE façon de remplir l'import — l'assistant qui lit le règlement
	      (état descriptif, #2218) : sous le fichier, comme l'alternative qu'elle est. -->
	<slot name="autrement" />
</div>

<ReglagesListe>
	<ChampRecherche id={idRecherche} bind:valeur={recherche} placeholder={exempleRecherche} />
	{#if options.length > 0}
		<ChoixPastilles
			{options}
			bind:valeur={filtre}
			tous="Tous"
			{compte}
			libelle="Statut"
			libelleDevant
		/>
	{/if}
</ReglagesListe>

{#if recherche.trim()}
	<BilanRecherche bind:recherche>
		<span><strong>{compte} ligne{compte > 1 ? 's' : ''}</strong> pour « {recherche.trim()} »</span>
	</BilanRecherche>
{/if}

<!--  Les actions de masse (auto-match, auto-résoudre) diffèrent d'un import à
      l'autre : elles restent chez l'appelant, qui les place ici. -->
<div class="imp-actions">
	<slot name="actions" />
</div>

<style>
	/*  Le style voyage avec le balisage : ces règles vivaient en ligne dans les
	    trois copies, donc rien n'empêchait l'une de changer sans les autres. */
	/*  🔴 `flex-wrap` MANQUAIT sur la rangée de filtres des trois écrans : les
	    lots en proposent six, et au-delà de quatre les boutons débordaient de la
	    largeur d'un téléphone (`standards/11` §10). Les filtres sont des
	    pastilles depuis #2173 ; les actions gardent la règle. */
	.imp-actions {
		display: flex;
		gap: 0.35rem;
		align-items: center;
		flex-wrap: wrap;
		margin-bottom: 1rem;
	}
	.imp-actions:empty {
		display: none;
	}
	.colonnes {
		font-size: var(--fs-md);
		margin-bottom: 0.75rem;
	}
</style>
