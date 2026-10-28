<!--
  **Une rubrique de documents de la résidence** — plans, règlement, comptes-rendus
  d'AG : la liste, son dépôt, sa correction et sa suppression, écrits UNE fois.

  ## Pourquoi (#779, 30/09/2026)

  `residence/+page.svelte` portait ces trois rubriques en trois exemplaires :
  trois fonctions d'ajout, six ou sept variables d'état chacune, la même garde
  recopiée, le même bloc de correction monté trois fois. Le rendu était déjà
  commun (`SectionDocuments`, `FormulaireDocument`, #522) ; la LOGIQUE ne
  l'était pas — et elle a déjà divergé : le sélecteur de périmètre du plan était
  lié à la variable du CR d'AG (#470), si bien que choisir un périmètre sur un
  plan pré-remplissait en douce le formulaire d'AG.

  Ce qui distingue les rubriques se déclare par props : `avecPerimetre` (plan,
  AG), le `mode` `ag` qui ajoute année et date d'assemblée, le tri, les badges
  (slot). La correction reste l'objet `CorrectionDocument` de
  `FormulaireEditionDocument`, désormais propre à chaque rubrique : elle met à
  jour SA liste, sans aiguillage par mode.

  ## Les pièces jointes d'un document (11/10/2026, migration 0278)

  La correction porte la section « Pièces jointes » : une seule liste, dix
  fichiers en tout — le fichier du document en tête, ses annexes ensuite
  (`PiecesJointesFiche`). La rubrique charge les annexes de TOUTE la
  bibliothèque en un appel (`annexesParFiche`) et les range sous chaque carte.
-->
<script lang="ts">
	import type { ClasseGouttiere } from '#lib/gouttiere.ts';
	import { nombreOuNull } from '#lib/utils.ts';
	import { jourIso } from '#lib/date.ts';
	import { onMount } from 'svelte';
	import { documents as documentsApi, type Document } from '#lib/api/index.ts';
	import { essayer } from '#lib/chargement.ts';
	import { tenter } from '#lib/erreurs.ts';
	import type { PiecesFiche } from '#lib/components/PiecesJointesFiche.svelte';
	import { supprimerDocument } from '#lib/gestes-document.ts';
	import { titreOuNomDuFichier } from '#lib/fichiers.ts';
	import ChampDateDocument from '#lib/components/ChampDateDocument.svelte';
	import ChampsCrAg from '#lib/components/ChampsCrAg.svelte';
	import FormulaireDocument from '#lib/components/FormulaireDocument.svelte';
	import FormulaireEditionDocument, {
		correctionVide,
		type CorrectionDocument,
		type ModeDocument,
	} from '#lib/components/FormulaireEditionDocument.svelte';
	import SectionDocuments from '#lib/components/SectionDocuments.svelte';
	import { aboutirGeste, ouvrirGeste } from '#lib/aboutissement.ts';

	export let mode: ModeDocument;
	export let titre: string;
	/** La catégorie de dépôt ; `null` tant qu'elle n'est pas lue — rien ne part. */
	export let categorieId: number | null;
	export let documents: Document[] = [];
	export let erreur = '';
	export let messageVide: string;
	export let peutModifier = false;
	/** L'ordre d'affichage ; la liste elle-même garde l'ordre d'arrivée. */
	export let trier: (docs: Document[]) => Document[] = (docs) => docs;
	/** Le formulaire de dépôt. */
	export let intitule: string;
	export let placeholderTitre: string;
	export let placeholderDescription: string;
	/**  Le périmètre DÉCRIT de quoi parle le document ; il ne restreint jamais sa
	 *   lecture (migration 0159, #617) : les droits restent à `résidence`. */
	export let avecPerimetre = false;
	/** « Ce plan », « Ce règlement »… — la confirmation de suppression le nomme. */
	export let quoi: string;
	export let messageAjout: string;

	const avecAg = mode === 'ag';
	/** Le règlement porte SA date (migration 0280) — demandée, proposée, modifiable. */
	const avecDate = mode === 'reglement';

	/**  La GOUTTIÈRE de chaque carte (10/10/2026, la page Affaires devenue le
	 *   standard) : QUAND, puis ce qui CLASSE. Le classement est la rubrique ;
	 *   les abréviations tiennent dans la colonne, comme « CAL. » (#1220).
	 *
	 *   🔴 La date est celle DU document, jamais celle de son dépôt (arbitré le
	 *   11/10/2026) : l'assemblée d'un compte-rendu, la date d'un règlement ; un
	 *   plan n'en montre aucune. Elle était `publie_le` pour le plan et le
	 *   règlement — un règlement de 1998 déposé ce mois-ci s'y datait du mois,
	 *   sous la colonne qui donne ailleurs la date de l'AG. */
	const GOUTTIERE: Record<
		ModeDocument,
		{ quand: (d: Document) => string | null; classe: ClasseGouttiere | null }
	> = {
		plan: {
			quand: () => null,
			classe: { icone: 'layers', libelle: 'Plan', abrege: 'PLAN' },
		},
		reglement: {
			quand: (d) => d.date_document,
			classe: { icone: 'book-open', libelle: 'Règlement', abrege: 'RÈGL.' },
		},
		ag: {
			quand: (d) => d.date_ag,
			classe: { icone: 'users', libelle: 'Assemblée générale', abrege: 'AG' },
		},
	};

	function saisieVide() {
		return {
			titre: '',
			description: '',
			perimetre: [] as string[],
			fichiers: [] as File[],
			annee: '' as string | number,
			dateAg: '',
			//  PROPOSÉE : aujourd'hui, que le conseil corrige s'il le faut.
			dateDocument: jourIso(),
		};
	}

	let ouvert = false;
	$: if (ouvert) ouvrirGeste('document.deposer'); //  Le geste mesuré (#1633).
	let saisie = saisieVide();
	let enregistrement = false;
	let correction: CorrectionDocument = correctionVide();
	let enregistrementCorrection = false;
	/** La section « Pièces jointes » du document en correction. */
	let piecesCorrection: PiecesFiche | null = null;

	/**  Les annexes, rangées sous leur document. Un échec de lecture les laisse
	 *   vides : les cartes restent lisibles, seules leurs annexes manquent. */
	let annexes = new Map<number, Document[]>();
	onMount(async () => {
		[annexes] = await essayer(documentsApi.annexesParFiche('document'), annexes);
	});
	$: annexesDe = (doc: Document) => annexes.get(doc.id) ?? [];

	function piecesDe(doc: Document): PiecesFiche {
		return {
			cible: 'document',
			objetId: doc.id,
			principal: {
				url: documentsApi.downloadUrl(doc.id),
				nom: doc.fichier_nom,
				retirer: async () => {
					const suivant = await documentsApi.retirerFichier(doc.id);
					documents = documents.map((d) => (d.id === suivant.id ? suivant : d));
					return { url: documentsApi.downloadUrl(suivant.id), nom: suivant.fichier_nom };
				},
			},
			onChange: (liste) => (annexes = new Map(annexes).set(doc.id, liste)),
		};
	}

	$: affiches = trier(documents);
	//  Le titre est facultatif : sans lui, chaque fichier prend le sien (#1479).
	$: complet =
		!!saisie.fichiers?.length &&
		(!avecAg || (!!saisie.annee && !!saisie.dateAg)) &&
		(!avecDate || !!saisie.dateDocument);

	/**  Plusieurs fichiers → un document chacun (#1479) : un document porte UN
	 *   fichier. Même motif que Diagnostics, même règle du titre. */
	async function ajouter() {
		if (!categorieId || !complet) return;
		//  Capturés AVANT le rappel : TypeScript ne conserve pas dans une closure
		//  le fait que la garde ci-dessus a écarté `null`.
		const categorie = categorieId;
		const s = saisie;
		const fichiers = Array.from(s.fichiers);
		enregistrement = true;
		await tenter(
			async () => {
				const deposes: Document[] = [];
				for (const fichier of fichiers) deposes.push(await deposer(s, categorie, fichier));
				aboutirGeste('document.deposer');
				documents = [...deposes, ...documents];
				ouvert = false;
				saisie = saisieVide();
			},
			fichiers.length > 1 ? `${fichiers.length} documents ajoutés` : messageAjout,
		);
		enregistrement = false;
	}

	function deposer(s: ReturnType<typeof saisieVide>, categorie: number, fichier: File) {
		return documentsApi.upload({
			titre: titreOuNomDuFichier(s.titre, fichier),
			categorieId: categorie,
			file: fichier,
			description: s.description.trim(),
			//  🔴 UN PV D'AG — ni un plan — N'EST JAMAIS RESTREINT PAR SON
			//  PÉRIMÈTRE : il dit de quoi il parle, pas qui peut le lire. Il part
			//  en `résidence` côté DROITS, les périmètres dans `perimetre_cible`.
			...(avecPerimetre ? { perimetreCible: s.perimetre } : {}),
			...(avecAg
				? { annee: nombreOuNull(s.annee) ?? undefined, dateAg: s.dateAg || undefined }
				: {}),
			...(avecDate ? { dateDocument: s.dateDocument } : {}),
		});
	}

	function corriger(doc: Document) {
		correction = {
			...correctionVide(),
			id: doc.id,
			mode,
			titre: doc.titre ?? '',
			annee: doc.annee ?? '',
			dateAg: doc.date_ag ? String(doc.date_ag).substring(0, 10) : '',
			//  Un document déposé avant la 0280 n'a pas de date : la correction
			//  PROPOSE celle de son dépôt, modifiable.
			dateDocument: doc.date_document ?? jourIso(doc.publie_le),
			description: doc.description ?? '',
			//  ⚠️ `perimetre_cible` sort du serveur en LISTE, jamais en JSON brut
			//  (`schemas.DocumentRead`). Le re-parser ici serait une seconde façon de
			//  lire la même chose, et elles divergeraient au premier format ajouté.
			perimetre: Array.isArray(doc.perimetre_cible) ? [...doc.perimetre_cible] : [],
		};
		piecesCorrection = piecesDe(doc);
	}

	async function enregistrerCorrection() {
		if (!correction.id) return;
		const docId = correction.id;
		enregistrementCorrection = true;
		await tenter(async () => {
			const corrige = await documentsApi.update(docId, {
				titre: correction.titre.trim() || undefined,
				//  🔴 Les deux champs que la correction n'envoyait pas (#852) —
				//  et que le serveur n'acceptait pas non plus.
				description: correction.description,
				perimetre_cible: correction.perimetre,
				annee: nombreOuNull(correction.annee),
				date_ag: correction.dateAg || null,
				...(avecDate ? { date_document: correction.dateDocument || null } : {}),
			});
			documents = documents.map((d) => (d.id === docId ? corrige : d));
			correction = correctionVide();
		}, 'Document mis à jour');
		enregistrementCorrection = false;
	}

	const supprimer = (id: number) =>
		supprimerDocument(id, quoi, (i) => (documents = documents.filter((d) => d.id !== i)));
</script>

<SectionDocuments
	{titre}
	documents={affiches}
	{erreur}
	{messageVide}
	{peutModifier}
	urlTelechargement={(d) => documentsApi.downloadUrl(d.id)}
	{annexesDe}
	quandDe={GOUTTIERE[mode].quand}
	classe={GOUTTIERE[mode].classe}
	onAjouter={() => (ouvert = true)}
	onModifier={corriger}
	onSupprimer={supprimer}
>
	<svelte:fragment slot="formulaire">
		{#if ouvert}
			<FormulaireDocument
				{intitule}
				bind:titre={saisie.titre}
				{placeholderTitre}
				titreRequis={false}
				aideTitre="Sans titre, chaque fichier prend le sien."
				multiple
				libelleFichier="Fichier(s)"
				{avecPerimetre}
				bind:perimetre={saisie.perimetre}
				bind:fichiers={saisie.fichiers}
				{enregistrement}
				{complet}
				on:annuler={() => (ouvert = false)}
				on:enregistrer={ajouter}
			>
				<svelte:fragment slot="specifiques">
					{#if avecAg}
						<ChampsCrAg requis bind:annee={saisie.annee} bind:dateAg={saisie.dateAg} />
					{:else if avecDate}
						<ChampDateDocument idPrefixe={mode} bind:valeur={saisie.dateDocument} />
					{/if}
				</svelte:fragment>
				<label class="field" for="{mode}-description" slot="description">
					Description
					<textarea
						id="{mode}-description"
						bind:value={saisie.description}
						placeholder={placeholderDescription}
						rows="3"></textarea>
				</label>
			</FormulaireDocument>
		{/if}
		{#if correction.id !== null}
			<FormulaireEditionDocument
				bind:correction
				piecesJointes={piecesCorrection}
				enregistrement={enregistrementCorrection}
				on:annuler={() => (correction = correctionVide())}
				on:enregistrer={enregistrerCorrection}
			/>
		{/if}
	</svelte:fragment>
	<svelte:fragment slot="badges" let:doc>
		<slot name="badges" {doc} />
	</svelte:fragment>
</SectionDocuments>
