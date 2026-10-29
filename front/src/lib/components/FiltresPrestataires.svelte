<!--
  La barre de FILTRES de l'annuaire des prestataires — métier, cadre, recherche.

  Extraite de `prestataires/+page.svelte` le 28/09/2026 (#1444) : le filtre
  « sous contrat » l'aurait fait grossir, et la page dépasse déjà 500 lignes
  (`standards/02` §6, « on découpe QUAND on y touche »). La règle de tri, elle,
  vit dans `#lib/prestataires` (`filtrerPrestataires`) — le composant ne fait
  que la saisir.

  Les rangées et le champ « Catégorie » du formulaire : UN motif, porté par
  `ChoixPastilles` (#491). `avecDetail` sur les catégories : leur description
  vivait dans un `title`, donc invisible au tactile.

  🔴 **Deux lignes sur ordinateur** (28/09/2026, demandé à l'écran) : le métier
  sur la première, le cadre et la RECHERCHE sur la seconde. La rangée des douze
  équipements, qui défilait sous les deux autres, a cédé la place à la
  recherche — `ChampRecherche`, le même champ que la page Affaires ; un
  équipement se retrouve en le tapant.

  🗂️ **La grille de la page Affaires** (10/10/2026, devenue le standard du site) :
  `ReglagesListe` — la RECHERCHE en tête, puis la catégorie et le contrat, leur
  libellé DEVANT, dans la colonne de la gouttière des cartes. Les « deux lignes »
  du 28/09 cèdent la place à cette grille : on cherche avant de trier, et les
  champs partent du même bord que le contenu des cartes. Les libellés se
  raccourcissent pour tenir dans la colonne (« Catégorie », « Contrat ») : ce
  sont aussi les noms accessibles des rangées.
-->
<script lang="ts">
	import ChoixPastilles from './ChoixPastilles.svelte';
	import ChampRecherche from './ChampRecherche.svelte';
	import ReglagesListe from './ReglagesListe.svelte';
	import {
		FILTRES_CONTRAT,
		TYPES_PRESTATAIRE,
		type FiltresPrestataires,
	} from '#lib/prestataires.ts';

	export let filtres: FiltresPrestataires;
	/** Combien l'annuaire en montre — porté par la pastille retenue de chaque rangée. */
	export let affiches: number | null = null;
</script>

<ReglagesListe>
	<ChampRecherche
		id="recherche-prestataires"
		bind:valeur={filtres.recherche}
		placeholder="Nom, métier, équipement, contact, téléphone…"
		dans="nom, métier, catégorie, téléphone, e-mail, adresse, description et contacts"
	/>
	<ChoixPastilles
		options={TYPES_PRESTATAIRE}
		bind:valeur={filtres.type}
		avecDetail
		compte={affiches}
		libelle="Catégorie"
		libelleDevant
	/>
	<!--  Le CADRE, séparé du métier (#1444) : il se lit sur les contrats actifs. -->
	<ChoixPastilles
		options={FILTRES_CONTRAT}
		bind:valeur={filtres.contrat}
		compte={affiches}
		libelle="Contrat"
		libelleDevant
	/>
</ReglagesListe>
