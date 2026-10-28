<!--
  Les `Document` rattachés à UN objet — les pièces d'un contrat d'entretien, les
  annexes d'une fiche de Ma résidence — **le rendu des tickets, sans écart**.

  ## Il s'appelait `DocumentsContrat` (11/10/2026)

  Les fiches de Ma résidence ont reçu des annexes (migration 0278) : des
  `Document` rattachés à un objet existant, ajoutés dès qu'on les choisit,
  retirés d'une croix. C'est EXACTEMENT ce que ce composant faisait pour les
  contrats, à un nom de champ près — que `uploadPour(cible, …)` porte déjà. Il
  a donc été renommé et paramétré par `cible`, plutôt que recopié.

  ## Pourquoi (30/08/2026, #453 · #640) puis refait le 12/09/2026

  `prestataires/+page.svelte` rendait ce bloc **deux fois**, dans le formulaire du
  haut et dans l'édition en ligne. Ce composant l'a écrit une fois — mais il l'a
  écrit **à sa manière** : une liste verticale en styles inline, un titre
  « 📄 Documents (N) » qui doublait celui de la section, et un dépôt en deux temps
  (« Choisir un document » puis un bouton « + Document »).

  🔴 Signalé à l'écran le 12/09/2026, capture à l'appui :

  > La section document n'est pas standard en édition — regarde le différentiel
  > avec Documents de Tickets ⇒ adopte le même rendu : **je n'accepte pas de
  > différence** (sauf dans le libellé).

  Le différentiel mesuré, et aucun écart n'était voulu :

  | | Tickets | Contrats (avant) |
  |---|---|---|
  | les pièces | pastilles « PDF: nom × » | liste verticale + 🗑️, styles inline |
  | le titre | celui de la section, une fois | **deux fois** |
  | le dépôt | « Ajouter un document » | « Choisir un document » **+ « + Document »** |
  | le plafond | 10 | 1 |
  | le champ de nom | pleine largeur | étroit, sur sa propre ligne |

  ## Ce qui rendait le dépôt en DEUX temps, et pourquoi il n'a plus lieu d'être

  Un document de ticket est une URL dans une liste ; un document de contrat est
  une entité `Document` rattachée à un `contrat_id`. D'où un envoi séparé — et un
  bouton pour le déclencher.

  Mais **en édition le contrat existe déjà** : son identifiant est connu au
  moment où l'on choisit le fichier. L'envoi peut donc partir tout de suite, par
  le `upload` que `FichiersUpload` accepte depuis toujours, et le second bouton
  disparaît. Le composant du dépôt n'avait pas besoin d'être adapté : **il savait
  déjà faire**, et c'est le troisième « le composant existait déjà » de la semaine.

  ⚠️ La seule différence qui subsiste est celle que l'utilisateur a admise : le
  **libellé** du champ de nommage. Elle est portée par `FichiersUpload`, pas ici.

  ## La première pastille d'une fiche (11/10/2026)

  Une fiche de Ma résidence EST un fichier, et porte des annexes. L'édition les
  montrait en deux blocs — le fichier (1/1), puis « Annexes — jusqu'à dix ».
  Demandé : *« ne réinvente pas cet objet, il doit être standard »* — une seule
  liste, ce composant, dix fichiers en tout. Le fichier de la fiche y entre par
  `principal` : première pastille, même rendu, et sa croix le RETIRE — la pièce
  suivante prend sa place côté serveur (`utils/annexes`).
-->
<script lang="ts" context="module">
	/**  Le fichier qui EST l'objet, en tête de liste. `retirer` confirme, agit et
	 *   recharge : il ne rend la main qu'une fois la liste à jour. */
	export interface PiecePrincipale {
		url: string;
		nom: string;
		retirer: () => Promise<unknown>;
	}
</script>

<script lang="ts">
	import { tick } from 'svelte';
	import FichiersUpload from '#lib/components/FichiersUpload.svelte';
	import { documents as docsApi, type CibleDocument, type Document } from '#lib/api/index.ts';

	/** L'objet qui porte les documents — le rattachement que l'API attend. */
	export let cible: CibleDocument;

	/**  L'objet dont on montre les pièces — `null` PENDANT SA CRÉATION.
	 *
	 *  🔴 La section était absente à la création (dette `motif: api`, #921), au
	 *  motif qu'un document se rattache à un `contrat_id` qui n'existe pas encore.
	 *  C'était vrai, et la conclusion était fausse : les ACTUALITÉS déposent leurs
	 *  documents à la création depuis #531, en gardant les fichiers de côté et en
	 *  les attachant une fois l'objet enregistré. Aucun endpoint ne manquait — le
	 *  geste existait, sur un autre écran.
	 *
	 *  ⚠️ C'est aussi ce qui protège l'invariant du serveur : *une ligne `document`
	 *  porte toujours un rattachement*. Créer le contrat à blanc pour obtenir un
	 *  identifiant l'aurait violé le temps d'un formulaire abandonné — donc pour
	 *  toujours. */
	export let objetId: number | null;
	/** Les documents déjà attachés. */
	export let documents: Document[] = [];
	/** Qui sait supprimer — l'écran, qui tient la table. */
	export let onSupprimer: (objetId: number, docId: number) => void;
	/** Qui sait recharger après un ajout. */
	export let onAjoute: (objetId: number) => void;
	/**  Ce que le dépôt accepte : un contrat ne porte que des DOCUMENTS (un
	 *   contrat est un document, pas une constatation) ; une fiche de Ma
	 *   résidence aussi des photos — le nuancier d'une règle, une façade. */
	export let mode: 'documents' | 'mixte' = 'documents';
	/** Identifiant du champ de téléversement — unique par emplacement. */
	export let idChamp: string;
	/**  Les types acceptés, quand ils sortent de `mode` — les fichiers du
	 *   règlement acceptent aussi le Markdown (11/10/2026). Relayés tels quels. */
	export let accept: string | null = null;
	export let types: string | null = null;

	/**  Les fichiers EN ATTENTE, quand l'objet n'existe pas encore. L'écran les
	 *   attache après création, par `attacherApres(cible, …)` — la même fonction
	 *   que les actualités, et non une seconde boucle d'envoi. */
	export let fichiersEnAttente: File[] = [];
	/**  Le fichier de l'objet lui-même — absent partout, sauf sur une fiche de Ma
	 *   résidence qui en porte un. Il compte dans le plafond de la liste. */
	export let principal: PiecePrincipale | null = null;

	//  Deux régimes, un seul rendu. `FichiersUpload` porte déjà la bascule
	//  (`differe`) : la choisir ici plutôt que dupliquer le composant, c'est ce
	//  qui garantit que la création et la correction se ressemblent.
	$: differe = objetId === null;

	/**  Le nom de fichier saisi au dépôt. `FichiersUpload` s'en sert pour RENOMMER
	 *   le fichier avant l'envoi — c'est ainsi que les tickets le font, et le
	 *   `titre` du `Document` reçoit ensuite ce même nom. Une seule règle de
	 *   nommage, donc, et non deux qui finiraient par diverger. */
	let libelleFichier = '';

	//  Les pièces sont rendues par leur URL de téléchargement, et `noms` dit
	//  comment les afficher : l'URL `/documents/12/télécharger` ne porte ni le
	//  nom ni l'extension, donc ni le type de la pastille.
	$: urls = [
		...(principal ? [principal.url] : []),
		...(documents ?? []).map((d) => docsApi.downloadUrl(d.id)),
	];
	$: noms = Object.fromEntries([
		...(principal ? [[principal.url, principal.nom]] : []),
		...(documents ?? []).map((d) => [docsApi.downloadUrl(d.id), d.titre || d.fichier_nom]),
	]);

	/**  L'envoi part dès que le fichier est choisi — l'objet existe déjà.
	 *
	 *  ⚠️ L'URL rendue n'est PAS conservée : `onAjoute` recharge la table depuis
	 *  l'API, qui seule connaît l'identifiant du document, sa date et son titre
	 *  définitif. Rendre l'URL sert à `FichiersUpload`, qui attend une chaîne. */
	async function envoyer(file: File): Promise<string> {
		const doc = await docsApi.uploadPour(cible, objetId!, file.name, file);
		onAjoute(objetId!);
		return docsApi.downloadUrl(doc.id);
	}

	/**  Retirer une pastille supprime le document. L'écran tient la table : il
	 *   rend la nouvelle liste, et `FichiersUpload` s'y aligne. */
	async function retirer(url: string): Promise<string[]> {
		if (principal && url === principal.url) {
			//  Rend la liste RECHARGÉE — refusée ou annulée, la pastille reste.
			await principal.retirer();
			await tick();
			return urls;
		}
		const doc = (documents ?? []).find((d) => docsApi.downloadUrl(d.id) === url);
		if (doc) onSupprimer(objetId!, doc.id);
		return urls.filter((u) => u !== url);
	}
</script>

<!--  Un seul appel, deux régimes : à la création les fichiers attendent dans
      `fichiersEnAttente` ; à la correction ils partent dès qu'ils sont choisis.
      Le rendu — pastilles, bouton, champ de nom — est le même des deux côtés,
      parce que c'est le même composant. -->
<FichiersUpload
	id={idChamp}
	{mode}
	{accept}
	{types}
	titre=""
	avecLibelle
	bind:libelleFichier
	{differe}
	bind:fichiers={fichiersEnAttente}
	{urls}
	{noms}
	upload={differe ? null : envoyer}
	remove={differe ? null : retirer}
/>
