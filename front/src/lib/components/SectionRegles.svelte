<!--
  Les RÈGLES & RECOMMANDATIONS de la résidence — couleur des menuiseries, essence
  des haies, ce que la copropriété a décidé et qu'aucun règlement ne dit.

  Extraites de `residence/+page.svelte` le 10/09/2026, au fil de l'eau : cet écran
  était à 1 029 lignes et devait accueillir sa barre d'onglets pour le carnet
  d'entretien. Le plafond de modularité (rang 1) refuse qu'un fichier déjà
  au-dessus de 500 grossisse, et ce bloc est celui qui s'en détache le plus
  proprement — une notion autonome, son endpoint à elle, aucun état partagé avec
  les documents, les plans ou les diagnostics.

  ⚠️ Le balisage part AVEC ses règles CSS. C'est la régression de #356, notée dans
  `ux-patterns` : « le balisage est parti et ses règles sont restées derrière ».
  Svelte scope les styles au composant, donc les laisser dans la page les rendrait
  inertes ici et orphelines là-bas — et `svelte-check` est le seul à le dire.

  Il CHARGE ses propres règles plutôt que de les recevoir en propriété : elles ne
  servent qu'ici, et les faire transiter par l'écran aurait laissé dans celui-ci
  l'état, l'appel et la gestion d'erreur — c'est-à-dire la moitié de ce qu'on
  cherchait à en sortir.

  ## La CARTE au standard de la page Affaires (10/10/2026)

  Une règle se rend en `.carte-liste` avec `EnteteCarte` : le titre et les
  actions au trait sur la première ligne, le détail en aperçu de trois lignes.
  Elle se DÉPLIE quand elle a un détail — le texte entier —, sinon son titre
  reste un simple texte. C'était une ligne `doc-row` dont le détail s'affichait
  en entier, quelle que soit sa longueur.

  La gouttière porte « RÈGL. », et RIEN d'autre (arbitré le 11/10/2026) : une
  règle n'affiche aucune date — la création et la correction n'en rendent pas
  (`RegleResidenceEcrite`), si bien qu'une date posée ici serait fausse, absente
  sur la règle qu'on vient d'écrire, périmée sur celle qu'on vient de corriger.
  Ce que l'objet n'a pas ne s'invente pas (`Gouttiere`).

  ## Les pièces jointes d'une règle (11/10/2026, migration 0278)

  Une règle n'avait aucun fichier ; elle porte désormais jusqu'à dix pièces jointes —
  le nuancier d'une couleur, la photo d'une haie. La section « Pièces jointes »
  est dans le formulaire dès la CRÉATION (arbitré : sinon il faudrait créer la
  règle puis la rouvrir) ; les fichiers choisis attendent alors l'enregistrement
  et s'attachent ensuite (`attacherApres`). Une règle qui porte des annexes se
  déplie, même sans détail.

  ## Sa lecture part avec la Fiche (#1841)
  La section n'est montée qu'une fois la Fiche chargée : ses règles partaient donc
  en troisième vague. La page lance `lireRegles()` avec ses autres appels et la
  lui passe (`lecture`), que la section PREND une fois — rouverte, elle relit.
  L'appel et sa gestion d'erreur restent ici : la page ne fait que le déclencher.
-->
<script context="module" lang="ts">
	import {
		documents as documentsApi,
		reglesResidence as reglesApi,
		type Document,
		type RegleResidenceEcrite,
	} from '#lib/api/index.ts';
	import { essayer } from '#lib/chargement.ts';

	/** Les règles et leurs annexes ; un échec des annexes les laisse vides. */
	export function lireRegles() {
		return Promise.all([
			essayer<RegleResidenceEcrite[]>(reglesApi.list(), []),
			essayer(documentsApi.annexesParFiche('regle'), new Map<number, Document[]>()),
		]);
	}
	export type LectureRegles = ReturnType<typeof lireRegles>;
</script>

<script lang="ts">
	import { onMount } from 'svelte';
	import { attacherApres } from '#lib/fichiers.ts';
	import ListeDocuments from './ListeDocuments.svelte';
	import type { PiecesFiche } from './PiecesJointesFiche.svelte';
	import { messageErreur } from '#lib/erreurs.ts';
	import { confirmer, SUPPRESSION } from '#lib/confirmation.ts';
	import CarteListe from '#lib/components/CarteListe.svelte';
	import type { ClasseGouttiere } from '#lib/gouttiere.ts';
	import { toast } from '#lib/components/Toast.svelte';
	import { isCS } from '#lib/stores/auth.ts';
	import EtatListe from './EtatListe.svelte';
	import ApercuCarte from './ApercuCarte.svelte';
	import EnteteCarte from './EnteteCarte.svelte';
	import IconeAction from './IconeAction.svelte';
	import TexteDeplie from './TexteDeplie.svelte';
	import { basculer } from '#lib/accordeon.ts';
	import FormulaireDocument from './FormulaireDocument.svelte';

	/** La lecture lancée par la page, prise une fois (puis remise à `null`). */
	export let lecture: LectureRegles | null = null;

	/**  Le classement de la gouttière — le même mot que le règlement, l'icône de
	 *   la section (📋) pour les distinguer. */
	const CLASSE: ClasseGouttiere = {
		icone: 'clipboard-list',
		libelle: 'Règle ou recommandation',
		abrege: 'RÈGL.',
	};

	//  Une règle qu'on vient d'ajouter n'a ni auteur ni dates (`RegleResidenceEcrite`).
	let regles: RegleResidenceEcrite[] = [];
	let eRegles = '';
	let chargement = true;

	let showRegleForm = false;
	let editingRegleId: number | null = null;
	let regleTitre = '';
	let regleContenu = '';
	let savingRegle = false;
	//  UNE règle dépliée à la fois (`#lib/accordeon`).
	let deplie: number | null = null;
	/** Les annexes, rangées sous leur règle ; un échec les laisse vides. */
	let annexes = new Map<number, Document[]>();
	/** Les pièces choisies pendant la CRÉATION, attachées après l'enregistrement. */
	let annexesEnAttente: File[] = [];
	let piecesRegle: PiecesFiche | null = null;

	const chargerAnnexes = async () => {
		[annexes] = await essayer(documentsApi.annexesParFiche('regle'), annexes);
	};

	onMount(async () => {
		const lue = lecture ?? lireRegles();
		lecture = null;
		[[regles, eRegles], [annexes]] = await lue;
		chargement = false;
	});

	// ── Règles & Recommandations ───────────────────────────────────────────────
	function openRegleForm(regle?: RegleResidenceEcrite) {
		if (regle) {
			editingRegleId = regle.id;
			regleTitre = regle.titre;
			regleContenu = regle.contenu;
		} else {
			editingRegleId = null;
			regleTitre = '';
			regleContenu = '';
		}
		annexesEnAttente = [];
		piecesRegle = {
			cible: 'regle',
			objetId: regle?.id ?? null,
			onChange: (liste) => {
				if (regle) annexes = new Map(annexes).set(regle.id, liste);
			},
		};
		showRegleForm = true;
	}

	async function saveRegle() {
		if (!regleTitre.trim()) return;
		savingRegle = true;
		try {
			if (editingRegleId) {
				const updated = await reglesApi.update(editingRegleId, {
					titre: regleTitre.trim(),
					contenu: regleContenu.trim(),
				});
				regles = regles.map((r) => (r.id === editingRegleId ? { ...r, ...updated } : r));
				toast('success', 'Règle mise à jour');
			} else {
				const created = await reglesApi.create({
					titre: regleTitre.trim(),
					contenu: regleContenu.trim(),
				});
				regles = [...regles, created];
				toast('success', 'Règle ajoutée');
				await attacherApres('regle', created.id, annexesEnAttente, 'Règle ajoutée');
				if (annexesEnAttente.length) await chargerAnnexes();
			}
			showRegleForm = false;
			regleTitre = '';
			regleContenu = '';
			editingRegleId = null;
		} catch (e) {
			toast('error', messageErreur(e));
		} finally {
			savingRegle = false;
		}
	}

	async function deleteRegle(id: number) {
		if (!(await confirmer(SUPPRESSION('Cette règle')))) return;
		try {
			await reglesApi.remove(id);
			regles = regles.filter((r) => r.id !== id);
			toast('success', 'Règle supprimée');
		} catch (e) {
			toast('error', messageErreur(e));
		}
	}
</script>

<!-- ── Section : Règles & Recommandations ──────────────────────────── -->
<section class="section-regles">
	<div class="section-header">
		<h2 class="section-title">&#x1F4CB; Règles & Recommandations</h2>
		{#if $isCS}
			<button class="btn btn-sm" on:click={() => openRegleForm()}>+ Ajouter</button>
		{/if}
	</div>

	{#if showRegleForm}
		<FormulaireDocument
			edition={editingRegleId !== null}
			intitule={editingRegleId ? 'Modifier la règle' : 'Ajouter une règle'}
			bind:titre={regleTitre}
			placeholderTitre="Ex : RAL menuiseries façade bâtiment A"
			avecFichier={false}
			piecesJointes={piecesRegle}
			bind:annexesEnAttente
			enregistrement={savingRegle}
			complet={!!regleTitre.trim()}
			on:annuler={() => (showRegleForm = false)}
			on:enregistrer={saveRegle}
		>
			<label class="field" for="regle-contenu" slot="description">
				Détail / valeur
				<textarea
					id="regle-contenu"
					bind:value={regleContenu}
					placeholder="Ex : Façade extérieure RAL 6021 vert clair"
					rows="3"></textarea>
			</label>
		</FormulaireDocument>
	{/if}

	<EtatListe
		{chargement}
		compact
		erreur={eRegles}
		vide={regles.length === 0}
		messageVide="Aucune règle ajoutée."
	>
		{#each regles as regle (regle.id)}
			{@const pieces = annexes.get(regle.id) ?? []}
			{@const depliable = !!regle.contenu || pieces.length > 0}
			<!--  Repliée, toute la carte déplie ; dépliée, seul le titre replie
			      (`ux-patterns` §3). -->
			<CarteListe
				classe={CLASSE}
				expanded={deplie === regle.id}
				onDeplier={depliable ? () => (deplie = regle.id) : null}
			>
				<EnteteCarte
					titre={regle.titre}
					basculable={depliable}
					on:toggle={() => (deplie = basculer(deplie, regle.id))}
				>
					<svelte:fragment slot="actions">
						{#if $isCS}
							<button
								class="btn-icon-edit"
								aria-label="Modifier"
								title="Modifier"
								on:click|stopPropagation={() => openRegleForm(regle)}
								><IconeAction icone="pencil" /></button
							>
							<button
								class="btn-icon-danger"
								aria-label="Supprimer"
								title="Supprimer"
								on:click|stopPropagation={() => deleteRegle(regle.id)}
								><IconeAction icone="trash-2" /></button
							>
						{/if}
					</svelte:fragment>
					<svelte:fragment slot="apercu">
						{#if regle.contenu && deplie !== regle.id}
							<ApercuCarte contenu={regle.contenu} dansLigne />
						{/if}
					</svelte:fragment>
				</EnteteCarte>
				{#if deplie === regle.id}
					<!--  Le corps ne replie pas la carte : on lit, on sélectionne. Le
					      même assainisseur que l'aperçu : un texte simple garde ses
					      retours à la ligne, un texte riche ses balises sûres. -->
					<div class="carte-corps" role="presentation" on:click|stopPropagation>
						{#if regle.contenu}<TexteDeplie contenu={regle.contenu} />{/if}
						{#if pieces.length}<ListeDocuments documents={pieces} />{/if}
					</div>
				{/if}
			</CarteListe>
		{/each}
	</EtatListe>
</section>

<style>
	.section-regles {
		margin-bottom: 2.5rem;
	}
</style>
