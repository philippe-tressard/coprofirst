<!--
  🔴 Ce formulaire était écrit une SECONDE fois dans `mon-lot` (01/09/2026,
  #672) : mêmes champs, même recherche de locataire, six variables d'état en
  double et trois fonctions recopiées. Deux écritures du même formulaire, et rien
  pour dire qu'elles avaient divergé — c'est le défaut qui a fait qu'un sélecteur
  de périmètre de plan écrivait dans la variable du CR d'AG (#453).

  `avecLots` et `avecDateEntree` portent les DEUX seules différences : un bail
  existant ne change ni de lot ni de date d'entrée. C'est ce qui justifie que la
  création et la correction restent DEUX rendus — mais le second doit alors se
  ramener à l'écran par la `cle` de `FormulaireCreation`, sans quoi il s'ouvre en
  bas de page (signalé à l'écran le 10/09/2026 sur les contrats, trouvé ici par
  l'audit qui a suivi).
-->
<!--
  L'OBJET « formulaire de bail » — les lots, le locataire, les dates, les notes.

  ## Pourquoi il existe (01/09/2026, #672)

  « Nouveau bail » était la **dernière** modale de création du site : le paradigme
  que #367 a supprimé après trois signalements de l'utilisateur, et la seule des
  sept que #672 recensait à ne pas avoir été convertie. Elle y avait échappé parce
  que `lint:formulaires` ne cherchait qu'un `<form>` — ce formulaire n'en porte
  aucun, seulement des `.field`.

  ⚠️ La conversion demandait une extraction, pas un simple changement de cadre :
  `mon-lot/+page.svelte` pesait **2 229 lignes**, très au-dessus du plafond de
  modularité, et le contrôle refuse d'y ajouter une ligne. C'est le même constat
  que les huit refus précédents (#453) — **le contrôle désigne un placement, pas
  une longueur** : la saisie d'un bail n'a jamais eu sa place dans l'écran qui
  liste les lots, les baux, les accès et les diagnostics.

  ## Le cadre suit le GESTE, et c'est le composant qui le pose

  Création → `FormulaireCreation` (la boîte dans la page, #367) ·
  Édition → `Modale` (#640). Le choix du cadre vit dans `CadreFormulaire`, écrit
  une fois pour les six formulaires concernés (02/09/2026) ; ici on ne déclare que
  le GESTE, par `edition`.

  ⚠️ Ce fichier passait `fermetureAuFond={false}` avec un commentaire d'incident.
  C'était **redondant** : `Modale` l'impose dès que `edition` est posé
  (`fondFermant = fermetureAuFond && !edition && …`). La prop laissait croire que
  les trois formulaires qui ne la passaient pas avaient un défaut — ils n'en
  avaient aucun.

  ## Ce que ce composant ne sait PAS, et c'est voulu

  Il ne connaît ni `LotDetail`, ni la façon d'étiqueter un lot, ni quels baux sont
  actifs : il reçoit des **lots à cocher** (`{ id, libelle, occupe }`), préparés par
  la page. Lui passer la structure de données de l'écran l'aurait rendu inutilisable
  ailleurs, et aurait recopié `lotTypeLabel` — qui sert encore deux fois là-bas.

  La recherche de locataire, en revanche, lui appartient : elle n'existe que dans ce
  formulaire, et la laisser dans la page l'obligeait à porter six variables d'état
  qui ne parlent que de lui.
-->
<script lang="ts" context="module">
	/** Compteur d'instances — voir `uid` : il remplace `Math.random()`. */
	let compteur = 0;
</script>

<script lang="ts">
	import { createEventDispatcher } from 'svelte';

	import SectionFormulaire from '#lib/components/SectionFormulaire.svelte';
	import { BAIL } from '#lib/entites/bail.ts';
	import { SECTIONS_LIBELLE, sectionPresente, type Etat } from '#lib/entites/types.ts';
	import { pliageDe, requisDe } from '#lib/pliage.ts';
	import CadreFormulaire from '#lib/components/CadreFormulaire.svelte';
	import RechercheLocataire from '#lib/components/RechercheLocataire.svelte';
	import SectionDescription from '#lib/components/SectionDescription.svelte';
	import PiedFormulaire from '#lib/components/PiedFormulaire.svelte';
	import EtoileRequis from '#lib/components/EtoileRequis.svelte';

	/** Un lot proposé à la sélection. `occupe` grise la ligne et la verrouille. */
	export let lots: { id: number; libelle: string; occupe: boolean }[] = [];

	/**  Le geste : `false` on crée (boîte dans la page), `true` on corrige un bail
	 *   existant (modale). C'est la seule chose qui change de cadre. */
	export let edition = false;
	export let intitule = 'Nouveau bail';

	/**  🔴 Les DEUX seules différences entre créer et corriger un bail — et c'est
	 *   pour elles que ce composant existe. La page portait le formulaire DEUX
	 *   fois : « Nouveau bail » et « Modifier les informations », écrits l'un après
	 *   l'autre, avec six variables d'état en double (`editRechercheLocataire`,
	 *   `editLocataireTrouve`…) et trois fonctions de recherche recopiées.
	 *
	 *   ⚠️ Un bail existant ne change ni de lot ni de date d'entrée : le premier est
	 *   sa raison d'être, la seconde un fait passé. Les masquer n'est pas un détail
	 *   d'affichage — c'est ce qui distingue les deux gestes. */
	export let avecDateEntree = !edition;
	/**  Les états du cadre : un bail se CRÉE (boîte dans la page) ou se CORRIGE. */
	$: etat = (edition ? 'edition' : 'creation') as Etat;
	/**  Les lots ne se choisissent qu'à la création — la déclaration `BAIL` le dit
	 *   (`perimetre` absent en édition, motif `geste`). */
	$: avecLots = sectionPresente(BAIL, etat, 'perimetre');

	/** Les lots retenus — lié, pour que la page sache ce qui partira. */
	export let lotIds: Set<number> = new Set();
	/**  Les champs du bail, d'un seul tenant : c'est la charge utile de l'envoi.
	 *
	 *   ⚠️ `date_entree` est OPTIONNELLE dans le type, et ce n'est pas une facilité :
	 *   en correction elle n'est pas affichée (`avecDateEntree`), donc l'appelant
	 *   n'a aucune raison de la porter. L'exiger l'obligerait à inventer une valeur
	 *   pour un champ que personne ne lit — et cette valeur finirait par partir. */
	export let bail: {
		locataire_nom: string;
		locataire_prenom: string;
		locataire_email: string;
		locataire_telephone: string;
		date_entree?: string;
		date_sortie_prevue: string;
		notes: string;
	} = {
		locataire_nom: '',
		locataire_prenom: '',
		locataire_email: '',
		locataire_telephone: '',
		date_entree: '',
		date_sortie_prevue: '',
		notes: '',
	};
	/** Le compte associé, ou `null` si le locataire est saisi à la main. */
	export let locataireId: number | null = null;

	export let enregistrement = false;

	const dispatch = createEventDispatcher<{ annuler: void; enregistrer: void }>();

	//  Un identifiant propre à CHAQUE instance : deux formulaires ouverts sur la
	//  même page partageraient sinon le `for` de leurs libellés.
	//  ⚠️ Un compteur, pas `Math.random()` : le rendu serveur et le rendu client
	//  doivent produire le MÊME identifiant, sinon l'hydratation remplace le nœud
	//  et un champ en cours de saisie y perd son contenu.
	const uid = `fb-${++compteur}`;

	//  Le composant de recherche dit s'il a associé un compte : les trois champs
	//  d'identité sont alors VERROUILLÉS. Ils décrivent une personne enregistrée,
	//  que ce formulaire n'a pas à renommer au passage.
	let compteAssocie = false;

	function basculerLot(id: number) {
		if (lotIds.has(id)) lotIds.delete(id);
		else lotIds.add(id);
		lotIds = new Set(lotIds);
	}

	//  Le formulaire dit lui-même s'il est complet : la page n'a pas à redire la
	//  règle. À la création, un lot au moins et une date d'entrée — les deux
	//  astérisques. En correction, ces deux champs n'existent pas : exiger ce qui
	//  n'est pas affiché rendrait le bouton inerte sans dire pourquoi.
	$: complet = (!avecLots || lotIds.size > 0) && (!avecDateEntree || !!bail.date_entree);
</script>

<CadreFormulaire {edition} titre={intitule} on:fermer={() => dispatch('annuler')}>
	<!--  🔴 L'ORDRE DU CADRE (arbitré le 28/09/2026 sur maquette, option A, #1329) —
	      Quand · Périmètre (les lots) · Description (les notes) · Au nom de (le
	      locataire). Les champs étaient posés à plat, sans section : rien n'était
	      déclaré, donc rien n'était contrôlé. `BAIL` dit les correspondances ;
	      `lint:etats` et `lint:ordre-sections` tiennent l'ordre. -->
	{#if sectionPresente(BAIL, etat, 'quand')}
		<SectionFormulaire
			titre={SECTIONS_LIBELLE.quand}
			requis={requisDe(BAIL, 'quand')}
			pliable={pliageDe(BAIL, 'quand')}
			rempli={!avecDateEntree || !!bail.date_entree}
			premiere
		>
			<div class="form-grid form-grid-2">
				{#if avecDateEntree}
					<div class="field">
						<label for="{uid}-entree">Date d'entrée<EtoileRequis vide={!bail.date_entree} /></label>
						<input id="{uid}-entree" type="date" bind:value={bail.date_entree} />
					</div>
				{/if}
				<div class="field">
					<label for="{uid}-sortie">Sortie prévue</label>
					<input id="{uid}-sortie" type="date" bind:value={bail.date_sortie_prevue} />
				</div>
			</div>
		</SectionFormulaire>
	{/if}

	{#if sectionPresente(BAIL, etat, 'perimetre')}
		<!--  🔴 `.bail-lots` enveloppe, et le style de la liste est `:global()` IMBRIQUÉ.
		      La classe passée en prop `classe=` est appliquée par `LibelleGroupe` sur SON
		      balisage : elle y reçoit le scope de `LibelleGroupe`, jamais celui d'ici.
		      `.lot-checklist { … }` écrit à plat produit donc `.lot-checklist.svelte-xxxx`,
		      qui ne correspond à rien — la liste partait NUE, sans bordure ni colonne, et
		      ce depuis toujours. Même famille que la panne des pastilles (v2.67.11).
		      Le `:global()` est borné par `.bail-lots` : il ne peut pas fuir vers une
		      autre page (mémoire `project_css_route_fuite_globale`). -->
		<SectionFormulaire
			titre="Lot(s) concerné(s)"
			idTitre="{uid}-lots-titre"
			requis={requisDe(BAIL, 'perimetre')}
			pliable={pliageDe(BAIL, 'perimetre')}
			rempli={lotIds.size > 0}
		>
			<div class="field bail-lots">
				<div class="lot-checklist" role="group" aria-labelledby="{uid}-lots-titre">
					{#each lots as lot (lot.id)}
						<label
							class="lot-check-item"
							class:disabled={lot.occupe}
							title={lot.occupe ? 'Ce lot a déjà un bail actif' : undefined}
						>
							<input
								type="checkbox"
								checked={lotIds.has(lot.id)}
								disabled={lot.occupe}
								on:change={() => basculerLot(lot.id)}
							/>
							<span class="lot-check-label">
								<span class="lot-check-name">{lot.libelle}</span>
								{#if lot.occupe}<span class="badge badge-yellow bail-actif">Bail actif</span>{/if}
							</span>
						</label>
					{/each}
				</div>
				{#if lotIds.size > 0}
					<p class="lot-selection-hint">
						{lotIds.size} lot{lotIds.size > 1 ? 's' : ''} sélectionné{lotIds.size > 1 ? 's' : ''} — un
						bail sera créé pour chacun
					</p>
				{/if}
			</div>
		</SectionFormulaire>
	{/if}

	{#if sectionPresente(BAIL, etat, 'description')}
		<!--  Par `SectionDescription`, comme toute Description (`lint:description-unique`) :
		      sans assistant — des notes de bail n'appellent pas de rédaction assistée. -->
		<SectionDescription
			idPrefixe={uid}
			idChamp="notes"
			bind:valeur={bail.notes}
			placeholder="Notes sur le bail…"
			hauteur="80px"
			pliable={pliageDe(BAIL, 'description')}
		/>
	{/if}

	{#if sectionPresente(BAIL, etat, 'au_nom_de')}
		<SectionFormulaire titre={SECTIONS_LIBELLE.au_nom_de} pliable={pliageDe(BAIL, 'au_nom_de')}>
			<!--  Qui est le locataire — recherche, suggestions, dissociation. C'est une
			      question autonome, et elle vit dans son composant : elle ne parle ni de
			      lots, ni de dates, ni de notes. Elle était écrite DEUX fois avant ce lot,
			      une par formulaire, et les deux copies avaient déjà divergé (#672). -->
			<RechercheLocataire
				{uid}
				bind:locataireId
				bind:nom={bail.locataire_nom}
				bind:prenom={bail.locataire_prenom}
				bind:email={bail.locataire_email}
				bind:associe={compteAssocie}
			/>
			<!-- Nom et prénom pré-remplis et verrouillés si un compte est associé ;
			     l'adresse, non : le compte ne la donne plus en entier (#2153). -->
			<div class="form-grid form-grid-2">
				<div class="field">
					<label for="{uid}-prenom">Prénom</label>
					<input
						id="{uid}-prenom"
						type="text"
						bind:value={bail.locataire_prenom}
						placeholder="Prénom"
						readonly={compteAssocie}
					/>
				</div>
				<div class="field">
					<label for="{uid}-nom">Nom</label>
					<input
						id="{uid}-nom"
						type="text"
						bind:value={bail.locataire_nom}
						placeholder="Nom"
						readonly={compteAssocie}
					/>
				</div>
				<div class="field">
					<label for="{uid}-email">E-mail</label>
					<input
						id="{uid}-email"
						type="email"
						bind:value={bail.locataire_email}
						placeholder="email@exemple.fr"
					/>
				</div>
				<div class="field">
					<label for="{uid}-tel">Téléphone</label>
					<input
						id="{uid}-tel"
						type="text"
						bind:value={bail.locataire_telephone}
						placeholder="06 …"
					/>
				</div>
			</div>
		</SectionFormulaire>
	{/if}
	<!--  ⚠️ `soumission={false}` : ce formulaire n'a pas de `<form>` — c'est écrit
	      en toutes lettres dans son en-tête, et `lint:formulaires` le sait. -->
	<PiedFormulaire
		enCours={enregistrement}
		desactive={!complet}
		soumission={false}
		on:annule={() => dispatch('annuler')}
		on:enregistre={() => dispatch('enregistrer')}
	/>
</CadreFormulaire>

<style>
	/*  Le balisage part avec ses styles : une classe posée ici et définie dans la
	    page ne serait pas atteinte (panne des pastilles nues, v2.67.11). Ces
	    vingt-quatre règles vivaient dans `mon-lot/+page.svelte` et n'habillaient
	    que ce formulaire. */
	.bail-actif {
		font-size: var(--fs-2xs);
	}
	.bail-lots :global(.lot-checklist) {
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
		border: 1px solid var(--color-border);
		border-radius: var(--radius);
		overflow: hidden;
	}
	.lot-check-item {
		display: flex;
		align-items: center;
		gap: 0.65rem;
		padding: 0.5rem 0.75rem;
		cursor: pointer;
		background: var(--color-bg);
		border-bottom: 1px solid var(--color-border);
		transition: background var(--duree-geste);
	}
	.lot-check-item:last-child {
		border-bottom: none;
	}
	@media (hover: hover) and (pointer: fine) {
		.lot-check-item:hover:not(.disabled) {
			background: color-mix(in srgb, var(--color-primary) 5%, var(--color-bg));
		}
	}
	.lot-check-item.disabled {
		opacity: 0.55;
		cursor: default;
	}
	.lot-check-label {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		flex-wrap: wrap;
		font-size: var(--fs-base);
		line-height: 1.3;
	}
	.lot-check-name {
		flex: 1;
	}
	.lot-selection-hint {
		font-size: var(--fs-sm);
		color: var(--color-primary);
		margin-top: 0.35rem;
	}
	/*  Les deux intitulés des suggestions. Ils étaient en `style=` en ligne dans la
	    page : nommés ici, ils cessent d'être à réécrire à chaque reprise. */
</style>
