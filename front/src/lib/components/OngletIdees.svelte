<!--
  L'onglet **Boîte à idées** de la Communauté — son formulaire de dépôt, ses
  filtres d'état et sa liste.

  ## Pourquoi il existe (#519)

  La page `sondages/+page.svelte` porte TROIS onglets et n'en avait extrait qu'un
  seul (`OngletAnnonces`). Le garde-fou de modularité a refusé de la laisser
  grossir en recevant les états d'erreur de #519 — et il disait vrai : une page
  de 500 lignes qui rend trois rubriques n'a pas un problème de taille, elle a un
  problème de découpage. Celui-ci rétablit la symétrie.

  ## Ce qui reste chez le parent, et pourquoi

  **Le rendu part, les gestes restent.** Voter, changer un état, supprimer,
  répondre : tout cela touche l'API et l'état partagé de la page (la liste est
  rechargée après chaque action). Les passer en callbacks garde un seul endroit
  qui parle au serveur — dupliquer les appels ici donnerait deux vérités sur
  l'état d'une idée.
-->
<script lang="ts">
	import ChargementDiffere from '$lib/components/ChargementDiffere.svelte';
	import type { Idee } from '$lib/api';
	import EtatListe from '$lib/components/EtatListe.svelte';
	import ListeIdees from '$lib/components/ListeIdees.svelte';
	import ListeEtArchives from '$lib/components/ListeEtArchives.svelte';
	import ChoixPastilles from '$lib/components/ChoixPastilles.svelte';
	import { STATUTS_IDEE } from '$lib/idees';
	import { enCours } from '$lib/archives';

	export let idees: Idee[] = [];
	export let chargement = false;
	/** Non vide = on n'a PAS pu charger. Distinct de « chargé et vide » (#519). */
	export let erreur = '';
	export let filtreStatut = '';
	export let showForm = false;
	export let currentUserId: number | undefined = undefined;
	export let estCS = false;
	export let estAdmin = false;
	export let statutClass: (s: string) => string;

	//  Les gestes vivent chez le parent : c'est lui qui parle à l'API et qui
	//  recharge la liste. Voir l'en-tête.
	export let onVoter: (id: number) => void;
	export let onChangerStatut: (id: number, statut: string) => void;
	export let onSupprimer: (id: number) => void;
	export let onSignaler: (cibleType: string, cibleId: number) => void;
	export let onRepondre: (id: number, contenu: string) => Promise<void> | void;
	export let onSupprimerReponse: (id: number, reponseId: number) => void;

	//  🔴 La partition courants / Archives est portée par `ListeEtArchives`, sur
	//  le `archivee` que le SERVEUR calcule (`app/utils/archivage.py`, règle du
	//  site, un seul délai). Elle était écrite ici, et à l'identique dans les deux
	//  autres onglets de la Communauté.

	//  La correction d'une idée (#783). Une seule à la fois, et l'état vit ICI :
	//  `ListeIdees` est rendu DEUX fois (courantes et Archives), l'y mettre en
	//  aurait monté deux exemplaires sur la même idée. Même construction que
	//  `OngletAnnonces`, qui a rencontré le problème le 02/09.
	let editIdee: Idee | null = null;
	const modifier = (i: Idee) => (editIdee = editIdee?.id === i.id ? null : i);

	function appliquerModification(maj: Idee) {
		idees = idees.map((i) => (i.id === maj.id ? maj : i));
		editIdee = null;
	}
	//  ⚠️ Le message d'état vide ne cite PAS le délai. Il vaut 30 jours par
	//  défaut mais se règle en administration : l'écrire ici en dur ferait mentir
	//  l'écran au premier ajustement, et le transporter avec chaque idée serait
	//  un champ par objet pour une valeur du site. Même formulation que les
	//  annonces, qui ont tranché la question le 18/08.
</script>

<!--  🔴 LE FORMULAIRE DE CORRECTION N'EST PLUS ICI (#787, 06/09/2026).
      Il était monté après les deux listes : « c'est tout en bas, et on ne voit
      pas ». Il remplace maintenant la description DANS la carte, par le slot
      `formulaire` — le pattern de la carte d'actualité, qui existait déjà. -->

<!--  🔴 Cette rangée de boutons était la TROISIÈME écriture du même motif —
      « choisir une entrée d'une liste courte, avec une entrée qui ne choisit
      rien ». `ChoixPastilles` le porte depuis le 30/08/2026 (#491), et son
      en-tête annonçait littéralement ce qui allait arriver : « elle se recopie
      une troisième fois au premier filtre ajouté ».

      ⚠️ `STATUTS_IDEE_FILTRE` portait déjà son entrée « Toutes » en tête de
      liste ; c'est `tous` qui la pose maintenant, et la liste redevient celle
      des seuls statuts (#795). -->
<ChoixPastilles
	options={STATUTS_IDEE.map((s) => ({ val: s.value, label: s.label }))}
	bind:valeur={filtreStatut}
	tous="Toutes"
	compte={enCours(idees).length}
	libelle="Filtrer les idées par état"
/>

<!--  §0 ter : la boîte de création vient APRÈS les filtres — ce qui qualifie la
      liste reste au-dessus du formulaire ouvert (#1186). `lint:filtre-avant-formulaire`. -->
{#if showForm}
	<ChargementDiffere charger={() => import('$lib/components/FormulaireIdee.svelte')}>
		{#snippet contenu(FormulaireIdee)}
			<FormulaireIdee on:cree on:annule />
		{/snippet}
	</ChargementDiffere>
{/if}

<EtatListe
	{chargement}
	{erreur}
	vide={idees.length === 0}
	titreErreur="Impossible d'afficher les idées"
	titreVide="Aucune idée pour l'instant"
	messageVide="Soyez le premier à proposer une idée !"
>
	<ListeEtArchives
		liste={idees}
		titreVideCourant="Aucune idée en cours"
		messageVideCourant="Les idées décidées sont rangées dans les Archives, ci-dessous."
	>
		<svelte:fragment let:items>
			<ListeIdees
				idees={items}
				{currentUserId}
				{estCS}
				{estAdmin}
				{statutClass}
				{onVoter}
				{onChangerStatut}
				{onSupprimer}
				{onSignaler}
				{onRepondre}
				{onSupprimerReponse}
				onModifier={modifier}
				editId={editIdee?.id ?? null}
			>
				<svelte:fragment slot="formulaire" let:idee>
					{#key idee.id}
						<ChargementDiffere charger={() => import('$lib/components/FormulaireIdee.svelte')}>
							{#snippet contenu(FormulaireIdee)}
								<FormulaireIdee
									{idee}
									on:modifie={(e) => appliquerModification(e.detail)}
									on:annule={() => (editIdee = null)}
								/>
							{/snippet}
						</ChargementDiffere>
					{/key}
				</svelte:fragment>
			</ListeIdees>
		</svelte:fragment>
	</ListeEtArchives>
</EtatListe>
