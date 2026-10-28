<!--
  ChoixPastilles.svelte — choisir UNE entrée d'une liste courte, en pastilles.

  ## Pourquoi ce composant (29 puis 30/08/2026, #491)

  Il s'appelait `BarreFiltres` et ne servait qu'aux filtres. Son propre en-tête
  annonçait ce qui allait arriver :

  > « C'est la duplication la plus discrète : elle vit dans un seul fichier, donc
  >   aucun contrôle inter-fichiers ne la voit, et **elle se recopie une troisième
  >   fois au premier filtre ajouté**. »

  🔴 **La troisième recopie a eu lieu le lendemain**, et pas sur un filtre : en
  convertissant le `<select>` « Type de prestataire » du FORMULAIRE, dans le
  même écran. Le garde-fou de modularité l'a refusée — et il disait vrai, au
  sens de #453 : *le refus signale que le code est au mauvais endroit, pas
  qu'il est trop long.*

  Le motif n'était donc pas « une barre de filtres » mais **« choisir une entrée
  d'une liste courte »**. Le filtre en est un cas : celui qui accepte de ne rien
  choisir.

  | | Filtre | Champ de formulaire |
  |---|---|---|
  | entrée « Tous » | oui | `tous={false}` — un champ requis n'a pas de vide |
  | libellé | invisible (`aria-label`) | visible, avec son `*` |
  | conteneur | rangée défilante | `.field champ-large` |

  ⚠️ Il ne remplace PAS `Pastille` : il l'emploie. Ce qu'il porte, c'est le
  MOTIF — l'entrée qui vide la sélection, l'égalité entre la valeur courante et
  chaque option, le défilement horizontal, et le libellé de groupe.

  🔴 **Le libellé visible est un `libelle-groupe`, pas un `<label>`.** Une rangée
  de `<button>` n'est pas labelable : un `for` posé dessus n'associe rien, **et
  le fait en silence** (`ux-patterns` §9 septies). D'où le couple
  `<span class="libelle-groupe" id>` + `role="group" aria-labelledby`.

  UTILISATION :
    <ChoixPastilles options={TYPES} bind:valeur={filtre} avecDetail />
    <ChoixPastilles options={TYPES} bind:valeur={form.type} tous={false}
                    libelle="Type" requis avecDetail />
-->
<script context="module" lang="ts">
	import EtoileRequis from '#lib/components/EtoileRequis.svelte';
	/** Compte les instances, pour donner un identifiant stable a chaque libelle. */
	let compteur = 0;
</script>

<script lang="ts">
	import Pastille from '#lib/components/Pastille.svelte';

	/**
	 *  Les entrées. `desc` n'est lue que si `avecDetail` est vrai.
	 *
	 *  `marquee` pose un **repère** sur certaines entrées : un liseré doré le
	 *  long du bord gauche de la pastille, qui la distingue des autres sans rien
	 *  ajouter à son libellé.
	 *
	 *  🔴 C'était un EMOJI (📒) jusqu'au 22/09/2026 — illisible, signalé à
	 *  l'écran : un libellé de catégorie commence déjà par son propre emoji, et le
	 *  second disparaît sur le fond bleu de la pastille retenue.
	 *
	 *  ⚠️ `marqueAide` reste OBLIGATOIRE dès que `marquee` est vrai, et elle
	 *  compte plus qu'avant : un emoji s'annonçait à un lecteur d'écran, un liseré
	 *  ne dit rien du tout.
	 */
	export let options: readonly {
		val: string;
		label: string;
		desc?: string;
		marquee?: boolean;
		marqueAide?: string;
		/** En tête, pleine ligne, suivie d'un filet — voir `Pastille.enTete`. */
		enTete?: boolean;
	}[] = [];

	//  Les entrées EN TÊTE d'abord, puis un filet, puis les autres : l'ordre
	//  se lit dans la donnée, il ne s'écrit pas dans l'écran.
	$: ordonnees = [...options.filter((o) => o.enTete), ...options.filter((o) => !o.enTete)];
	$: avecFilet = options.some((o) => o.enTete) && options.some((o) => !o.enTete);

	/** La valeur retenue. Chaîne vide = rien de choisi. */
	export let valeur = '';

	/**
	 * Le libellé de l'entrée qui vide la sélection — ou `false` pour ne pas
	 * l'offrir.
	 *
	 * ⚠️ `false` sur un champ **requis** : proposer « Tous » y donnerait un moyen
	 * de vider une valeur que le formulaire exige, donc un choix qui ne peut pas
	 * être soumis.
	 */
	export let tous: string | false = 'Tous';
	/**  🔢 UN FILTRE DE LISTE DIT COMBIEN IL MONTRE — le standard (10/10/2026,
	 *   maquette J arbitrée à l'écran) : le nombre d'éléments que la liste
	 *   affiche, filtres et recherche appliqués, en vignette `Compte` sur la
	 *   pastille RETENUE seulement (« Tous » compris) — `Pastille` en décide.
	 *
	 *   UN nombre, et non un par entrée : celui des pastilles non retenues
	 *   chargeait la rangée (dix vignettes pour deux filtres), et celui de la
	 *   retenue est la longueur de la liste, que l'écran connaît déjà — la lire
	 *   là, c'est ne pas pouvoir mentir sur ce qu'on voit.
	 *
	 *   `null` : un choix de formulaire, qui ne filtre rien. Une rangée qui
	 *   filtre une liste le passe — 🔒 `npm run lint:compte-filtres`. */
	export let compte: number | null = null;

	/**  Rendre la description sous le libellé ?
	 *
	 *   ⚠️ À réserver aux listes COURTES qui en portent une : au-delà du seuil de
	 *   6 (`ux-patterns`), des pastilles à deux lignes remplissent l'écran. Faux
	 *   par défaut — un enrichissement ne s'impose pas à ses appelants. */
	export let avecDetail = false;

	/** Ce que la rangée choisit. Toujours annoncé ; affiché si `libelleVisible`. */
	export let libelle = 'Filtres';

	/** Afficher le libellé au-dessus de la rangée — le cas du formulaire. */
	export let libelleVisible = false;

	/**  Afficher le libellé DEVANT la rangée, sur la même ligne — le cas d'une
	 *   barre de FILTRES qui en porte plusieurs (23/09/2026, variante A arbitrée
	 *   à l'écran : « Nature » et « Suivi » se confondaient). Le libellé ne
	 *   défile pas avec les pastilles. */
	export let libelleDevant = false;

	/**
	 *  La rangée DÉFILE-t-elle horizontalement, ou se replie-t-elle sur plusieurs
	 *  lignes ?
	 *
	 *  🔴 Le défilement était posé en dur, pour toutes les instances. Signalé à
	 *  l'écran le 07/09/2026 sur les huit catégories de ticket : trois d'entre
	 *  elles — « Étude & travaux », « Question », « Bug » — étaient **hors du
	 *  cadre**, et rien ne le disait sinon une barre de défilement grise.
	 *
	 *  `composants.css` l'écrivait pourtant au-dessus de la règle : *« un
	 *  défilement horizontal masque des filtres sans le dire, là où `flex-wrap:
	 *  wrap` les montre tous »*. La variante était nommée pour ne pas s'hériter —
	 *  et elle s'héritait quand même, par ce composant.
	 *
	 *  ⚠️ Vrai par DÉFAUT : les filtres d'une barre existante continuent de
	 *  défiler, et ce lot ne change que ce qu'on lui demande de changer. Un choix
	 *  de formulaire, lui, doit montrer TOUTES ses valeurs — on ne choisit pas
	 *  dans une liste dont on ignore la fin.
	 */
	export let defilante = true;

	/**
	 *  Rendre la rangée en GRILLE — colonnes égales, remplissage complet.
	 *
	 *  Pour un choix qu'on doit **embrasser d'un coup d'œil** : les huit
	 *  catégories de ticket. En `flex-wrap`, chaque vignette prend la largeur de
	 *  son texte, et le nombre par ligne dépend de la longueur des phrases — deux
	 *  lignes n'étaient pas garanties, seulement probables.
	 *
	 *  ⚠️ Exclusif de `defilante` : une grille qui déborde horizontalement n'a
	 *  aucun sens. La combinaison est refusée plus bas, à la compilation du
	 *  composant plutôt qu'à l'œil.
	 *
	 *  ⚠️ **Deux lignes sur ordinateur et tablette, TROIS sur téléphone** —
	 *  mesuré au navigateur, pas supposé : 900 px → 5 + 3 vignettes ; 700 px →
	 *  6 + 2 ; 380 px → 3 + 3 + 2. À 380 px, tenir huit vignettes en deux lignes
	 *  demanderait quatre colonnes de 85 px, où le sous-texte cesse d'être
	 *  lisible. Trois lignes lisibles valent mieux que deux illisibles, et le
	 *  socle (11 §10) va dans le même sens.
	 */
	export let grille = false;

	//  🔴 Une erreur PARLANTE, et non un rendu silencieusement faux. Les deux
	//  modes se contredisent ; laisser passer donnerait une grille sans
	//  `flex-wrap` dont on ne verrait le défaut qu'à l'écran, sur un écran donné.
	$: if (grille && defilante) {
		throw new Error(
			'ChoixPastilles : `grille` et `defilante` s’excluent — une grille qui ' +
				'déborde horizontalement n’a pas de sens. Passer `defilante={false}`.',
		);
	}

	/** Ajoute le ` *` de la charte au libellé visible. */
	export let requis = false;

	/**
	 * Nom du groupe de **boutons radio** — active le mode `radiogroup`.
	 *
	 * ⚠️ À réserver au choix EXCLUSIF et obligatoire d'un formulaire, là où la
	 * navigation par flèches a un sens. Un filtre reste des `<button>` : il n'y a
	 * rien à « parcourir », et l'entrée « Tous » n'est pas une valeur du modèle.
	 *
	 * Le conteneur porte alors `role="radiogroup"` et non `role="group"` — sans
	 * quoi un lecteur d'écran annonce un groupe quelconque et n'énonce ni la
	 * position (« 2 sur 5 ») ni l'exclusivité du choix.
	 */
	export let radio = '';

	//  Un identifiant par instance : deux rangées sur le même écran ne doivent pas
	//  se renvoyer au même libellé.
	//
	//  ⚠️ Un compteur de MODULE, et non `Math.random()` ni `performance.now()` :
	//  ceux-là donnent une valeur au rendu serveur et une autre à l'hydratation,
	//  d'où un `aria-labelledby` qui ne pointe sur rien pendant un instant — et
	//  rien ne le signale.
	const idTitre = `choix-pastilles-${++compteur}`;
</script>

<div
	class={libelleVisible ? 'field champ-large' : ''}
	class:choix-libelle-devant={libelleDevant && !libelleVisible}
>
	{#if libelleVisible || libelleDevant}
		<span class="libelle-groupe" class:libelle-devant={libelleDevant} id={idTitre}
			>{libelle}{#if requis}<EtoileRequis vide={!valeur} />{/if}</span
		>
	{/if}
	<div
		class="filters"
		class:filters--defilante={defilante}
		class:filters--grille={grille}
		class:filters--egalisee={avecDetail && !grille}
		role={radio ? 'radiogroup' : 'group'}
		aria-label={libelleVisible || libelleDevant ? undefined : libelle}
		aria-labelledby={libelleVisible || libelleDevant ? idTitre : undefined}
	>
		{#if tous !== false}
			<!--  Jamais en radio : « Tous » n'est pas une valeur du modèle, c'est
			      l'absence de filtre. Le mode radio est réservé au choix exclusif
			      et obligatoire d'un formulaire, où ce vide n'existe pas. -->
			<Pastille active={valeur === ''} {compte} on:click={() => (valeur = '')}>{tous}</Pastille>
		{/if}
		<!--  ⚠️ DEUX branches, et non un `{#if}` autour du `slot=` : Svelte exige
		      qu'un attribut `slot` soit enfant DIRECT du composant. Enveloppé dans une
		      condition, il devient une erreur de compilation — pas un rendu dégradé.
		      C'est aussi ce qui garde `$$slots.detail` faux quand il n'y a rien à
		      montrer, donc la pastille sur une seule ligne. -->
		{#each ordonnees as o, i (o.val)}
			{#if avecFilet && i > 0 && ordonnees[i - 1].enTete && !o.enTete}
				<span class="filet-en-tete" aria-hidden="true"></span>
			{/if}
			{#if avecDetail && o.desc}
				<Pastille
					active={valeur === o.val}
					marquee={!!o.marquee}
					marqueAide={o.marqueAide}
					enTete={!!o.enTete}
					{compte}
					radio={radio ? { nom: radio, valeur: o.val } : null}
					on:click={() => (valeur = o.val)}
					on:change={() => (valeur = o.val)}
				>
					{o.label}<span slot="detail">{o.desc}</span>
				</Pastille>
			{:else}
				<Pastille
					active={valeur === o.val}
					marquee={!!o.marquee}
					marqueAide={o.marqueAide}
					enTete={!!o.enTete}
					{compte}
					radio={radio ? { nom: radio, valeur: o.val } : null}
					on:click={() => (valeur = o.val)}
					on:change={() => (valeur = o.val)}
				>
					{o.label}
				</Pastille>
			{/if}
		{/each}
	</div>
</div>

<style>
	/*  Le filet qui sépare « informer » de « faire traiter » (variante A,
	    23/09/2026) : pleine ligne dans la grille, pointillé discret. */
	/*  Le libellé DEVANT la rangée : la règle de la ligne est globale
	    (`composants.css`, partagée avec `FiltrePerimetre`) ; restent ici ses
	    enfants, propres à ce balisage. */
	:global(.choix-libelle-devant) > .libelle-groupe {
		flex-shrink: 0;
		/*  Compense la marge basse de la rangée qui défile (réservée à sa barre
		    de défilement) : sans elle, le libellé tombe sous le centre des
		    pastilles. */
		margin-bottom: 0.25rem;
	}
	:global(.choix-libelle-devant) > .filters {
		min-width: 0;
		margin-bottom: 0;
	}
	.filet-en-tete {
		grid-column: 1 / -1;
		flex-basis: 100%;
		border-top: 1px dashed var(--color-border);
		margin: 0.15rem 0;
	}
</style>
