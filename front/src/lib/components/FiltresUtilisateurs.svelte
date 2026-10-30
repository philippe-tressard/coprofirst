<!--
  Les réglages de la liste des utilisateurs (Admin) — recherche, type, compte,
  et les compteurs.

  🔴 Sortie de `admin/+page.svelte` le 26/09/2026 (#1329) : ses deux filtres
  étaient des `<select>` natifs repeints à la main (`.role-select`), à côté
  d'une barre de filtres partout ailleurs en pastilles. `ux-patterns` : au-delà
  de six entrées, `PastilleDeroulante` ; en dessous, des pastilles.
  `lint:seuil-listes` ne l'a pas vu — il cherchait la classe `filter-select`,
  qui n'existait plus nulle part.

  Le FILTRAGE reste dans la page : ce composant ne dit que ce qu'on a choisi.
-->
<script lang="ts">
	import PastilleDeroulante from '#lib/components/PastilleDeroulante.svelte';
	import ChoixPastilles from '#lib/components/ChoixPastilles.svelte';
	import ChampRecherche from '#lib/components/ChampRecherche.svelte';
	import ReglagesListe from '#lib/components/ReglagesListe.svelte';
	import { LIBELLES_STATUT_ABREGE } from '#lib/roles.ts';

	export let recherche = '';
	export let statut = '';
	export let compte = '';
	/** Les compteurs affichés à droite. */
	export let affiches = 0;
	export let total = 0;
	export let nbCS = 0;

	const OPTIONS_STATUT = Object.entries(LIBELLES_STATUT_ABREGE).map(([val, label]) => ({
		val,
		label,
	}));
	const OPTIONS_COMPTE = [
		{ val: 'actif', label: 'Actifs' },
		{ val: 'inactif', label: 'En attente' },
	];
</script>

<!--  🔴 Les RÉGLAGES de la liste, à la façon de la page Affaires — standard du
      site depuis le 10/10/2026 (`ReglagesListe`) : la recherche en tête, puis
      une rangée par filtre, son libellé devant. Le compteur est celui de la
      pastille retenue (`ux-patterns` §5) ; le total et les membres du CS, qui
      ne sont pas des filtres, restent dessous en aide.

      ⚠️ `PastilleDeroulante` n'a pas de libellé devant (elle porte le sien en
      `aria-label`) : sa rangée pose le libellé à côté, dans la même grille, pour
      que le TYPE s'aligne sur RECHERCHE et COMPTE. -->
<ReglagesListe>
	<ChampRecherche
		id="admin-recherche-utilisateur"
		bind:valeur={recherche}
		placeholder="Dupont, dupont@…"
		dans="prénom, nom et adresse e-mail"
	/>
	<span class="libelle-groupe libelle-devant" aria-hidden="true">Type</span>
	<div>
		<PastilleDeroulante
			options={OPTIONS_STATUT}
			bind:valeur={statut}
			tous="Tous les types"
			libelle="Filtrer par type d’utilisateur"
		/>
	</div>
	<ChoixPastilles
		options={OPTIONS_COMPTE}
		bind:valeur={compte}
		tous="Tous comptes"
		compte={affiches}
		libelle="Compte"
		libelleDevant
	/>
	<p class="aide">
		{affiches} / {total} utilisateur{total > 1 ? 's' : ''}
		&nbsp;·&nbsp;
		{nbCS} membre{nbCS > 1 ? 's' : ''} CS
	</p>
</ReglagesListe>
