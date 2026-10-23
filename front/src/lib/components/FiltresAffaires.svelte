<!--
  FiltresAffaires.svelte — la barre de filtres de la page Affaires : la
  RECHERCHE libre, puis Nature et Suivi (dans cet ordre depuis la maquette B du
  10/10/2026, alignés sur la gouttière des cartes).

  Sortie de la page le 23/09/2026 (variante A arbitrée à l'écran) : la page
  était à son plafond de 500 lignes, et la barre y portait déjà son propre
  style. Elle ne décide rien — elle expose des valeurs liées.

  🔴 La ligne « Catégorie » a cédé la place à la recherche le 27/09/2026
  (maquette A, avec l'extrait et les Archives de la C) : on cherche un mot, pas
  une case — et la catégorie reste trouvable, le serveur cherche aussi son
  libellé (`app/utils/recherche_affaires.py`).

  🔴 La case « Inclure les Archives » a disparu le 28/09/2026 (demande de
  l'utilisateur) : elle doublait « Les inclure » du bilan, qui ne s'offre que
  quand des archivées correspondent — la seule fois où la question se pose.
  Sans case, l'état ne se voit plus que dans le bilan (« dont N aux
  Archives ») ; il retombe donc à faux quand la recherche s'efface, sinon la
  recherche suivante inclurait les Archives sans que rien ne le dise.

  🔢 La pastille RETENUE de chaque rangée dit combien la liste montre
  (10/10/2026, maquette J — le standard de `ChoixPastilles.compte`). Le nombre
  vient de la PAGE, qui tient la liste : c'est sa longueur, pas un recalcul
  qui pourrait diverger. Le bilan de recherche le lit au même endroit.
-->
<script lang="ts">
	import ChoixPastilles from '$lib/components/ChoixPastilles.svelte';
	import ChampRecherche from '$lib/components/ChampRecherche.svelte';
	import ReglagesListe from '$lib/components/ReglagesListe.svelte';
	import BilanRecherche from '$lib/components/BilanRecherche.svelte';
	import { OPTIONS_FILTRE_NATURE } from '$lib/tickets';
	import type { Ticket } from '$lib/api';
	import { archiveesTrouvees, type EtatRecherche } from '$lib/recherche-affaires';

	/** Les états présents dans la liste — calculés par la page, qui la connaît. */
	export let optionsStatut: { value: string; label: string; statuts: readonly string[] }[] = [];
	/** Toutes les affaires chargées : les archivées trouvées se comptent dessus. */
	export let tickets: Ticket[] = [];
	/** Combien la liste en montre — porté par la pastille retenue de chaque
	 *  rangée, et lu par le bilan de recherche. */
	export let affichees = 0;
	export let nature = '';
	export let statut = '';
	export let recherche = '';
	export let inclureArchives = false;
	/** Où en est la recherche — tenu par `rechercheAffaires()`. */
	export let etat: EtatRecherche;

	const pluriel = (n: number, mot: string) => `${n} ${mot}${n > 1 ? 's' : ''}`;

	$: if (!recherche.trim()) inclureArchives = false;

	/** Combien d'archivées la recherche a trouvées, et que la liste tait. */
	$: archivees = archiveesTrouvees(tickets, etat.resultats);
</script>

<!--  🔴 DEUX rangées écrites à la main, soit la deuxième et la troisième
      écriture du motif « choisir une entrée d'une liste courte » —
      `ChoixPastilles` (#491) le porte, avec l'entrée qui ne choisit rien, le
      défilement horizontal et le libellé de groupe accessible.

      ⚠️ Le libellé N'EST PAS un `<label>` : une rangée de `<button>` n'est pas
      labelable, et un `for` posé dessus n'associe rien **en silence**
      (`ux-patterns` §9 septies). Le composant pose `role="group"` +
      `aria-labelledby` — c'est une des raisons d'être de ce composant, et elle
      se perdait à chaque recopie.
      Chaque rangée porte son libellé DEVANT (23/09/2026, variante A arbitrée à
      l'écran) : « Nature » et « Suivi » se confondaient ; la recherche a sa ligne. -->
<!--  🗂️ ALIGNÉES SUR LA GOUTTIÈRE (maquette B, 10/10/2026) : la grille est
      `ReglagesListe`, le standard de toute liste à gouttière. La recherche
      passe EN TÊTE : on cherche avant de trier. -->
<ReglagesListe>
	<ChampRecherche
		id="recherche-affaires"
		bind:valeur={recherche}
		placeholder="Un mot, un nom, un n° d'affaire…"
		aide="Cherche partout : n°, titre, description, catégorie, lieu, auteur, prestataire, équipement, suites, messages et pièces jointes — sans tenir compte des accents ni des majuscules."
	/>
	<ChoixPastilles
		options={OPTIONS_FILTRE_NATURE}
		bind:valeur={nature}
		tous="Tous"
		compte={affichees}
		libelle="Nature"
		libelleDevant
	/>
	<ChoixPastilles
		options={optionsStatut.map((s) => ({ val: s.value, label: s.label }))}
		bind:valeur={statut}
		tous="Tous"
		compte={affichees}
		libelle="Suivi"
		libelleDevant
	/>
</ReglagesListe>

{#if etat.terme || etat.enCours || etat.erreur}
	<BilanRecherche bind:recherche>
		{#if etat.erreur}
			La recherche n'a pas abouti : {etat.erreur}
		{:else if etat.enCours && !etat.resultats}
			Recherche…
		{:else}
			<strong>{pluriel(affichees, 'affaire')}</strong> pour « {etat.terme} »
			{#if archivees && inclureArchives}
				· dont {archivees} aux Archives
			{:else if archivees}
				· {pluriel(archivees, 'autre')} aux Archives
				<button
					type="button"
					class="btn btn-outline btn-sm"
					on:click={() => (inclureArchives = true)}>Les inclure</button
				>
			{/if}
		{/if}
	</BilanRecherche>
{/if}
