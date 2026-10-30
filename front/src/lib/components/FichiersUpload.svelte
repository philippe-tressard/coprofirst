<!--
  Saisie de pièces jointes : liste retirable + bouton d'ajout. Les images
  s'affichent en vignettes, les documents en pastilles nommées — c'est `accept`
  qui décide de ce qu'on peut ajouter, pas le rendu.

  ⚠️ Composant UNIQUE de saisie de pièces jointes. `PhotosUpload.svelte` en était
  une seconde copie à ~80 % identique (même mise en page, même compteur, CSS de la
  croix de suppression rigoureusement identique) — et les deux avaient divergé sur
  le point qui compte : `multiple`. On ne pouvait joindre qu'UNE photo aux
  sondages et à l'espace CS (10/08/2026). Fusionné ici : ne pas recréer de
  variante, c'est la divergence qui produit le défaut, pas le code.

  Le téléversement passe par défaut par l'endpoint générique
  (`POST /uploads/fichier`, qui valide le type MIME). Les rubriques qui ont leur
  PROPRE endpoint (photo de résidence, annonces…) passent un callback `upload` —
  et `remove` si la suppression doit être répercutée côté serveur.

  Le fichier est téléversé immédiatement — avant même que l'élément parent
  existe — et l'URL obtenue part dans le `fichiers_urls` de la création. C'est ce
  qui permet à un ticket envoyé au syndic de partir avec ses documents joints,
  ce que le flux « créer puis téléverser » des photos ne permet pas.

  ## Le mode DIFFÉRÉ (`differe`), et pourquoi il existe

  Deux rubriques ne peuvent PAS téléverser à la sélection : les documents d'une
  actualité deviennent des entités `Document` rattachées à `publication_id`, qui
  n'existe pas tant que l'actualité n'est pas créée. Elles utilisaient donc un
  `<input type="file">` nu — d'où deux apparences pour une même notion sur le
  site, signalé le 16/08/2026 (« le libellé fichier n'est pas conforme »).

  En mode différé, le composant RETIENT les `File` sélectionnés au lieu de les
  envoyer : même rendu, même compteur, même bouton, mêmes vignettes (par
  `URL.createObjectURL`). Le parent lit `bind:fichiers` après la création et les
  téléverse alors. L'apparence est identique — c'est tout l'objet.

  ⚠️ Les URLs d'aperçu sont un **état global du navigateur** : elles sont
  révoquées au retrait ET dans `onDestroy` (socle 11 §12 — la fonction de
  libération est appelée depuis chaque sortie, pas seulement la sortie nominale).

  Props :
    - urls     : liste des URLs (bindable) — mode normal
    - fichiers : liste des `File` retenus (bindable) — mode `differe`
    - differe  : ne pas téléverser, retenir les fichiers pour le parent
    - max      : nombre maximum de documents
    - label    : libellé du bouton d'ajout
    - accept   : filtre du sélecteur de fichiers
    - id       : posé sur l'input, pour qu'un `<label for="…">` le désigne
    - disabled : désactive l'ajout
    - readonly : affichage seul (ni ajout ni retrait)
    - upload   : (file) => Promise<url> — remplace l'endpoint générique
    - remove   : (url) => Promise<url[] | void> — suppression serveur ; si elle
                 retourne une liste, elle fait foi
  Events :
    - change(detail: string[]) — après ajout ou retrait (mode normal)
-->
<script lang="ts">
	import { SEPARATEUR } from '#lib/separateurs.ts';
	import { messageErreur } from '#lib/erreurs.ts';
	import { createEventDispatcher, onDestroy } from 'svelte';
	import Vignette from './Vignette.svelte';
	import PastilleFichier from './PastilleFichier.svelte';
	import { fichiersApi } from '#lib/api/index.ts';
	import { toast } from './Toast.svelte';
	import {
		ACCEPT_DOCUMENTS,
		ACCEPT_FICHIERS,
		ACCEPT_PHOTOS,
		LIBELLE_TYPES,
		MAX_FICHIERS,
		nomFichier,
		separerFichiers,
	} from '#lib/fichiers.ts';

	export let urls: string[] = [];
	export let max = MAX_FICHIERS;
	/** Porte à la fois le filtre du sélecteur et le libellé par défaut : une page
	 *  n'a ni import ni ligne de plus à écrire pour dire « ici, ce sont des photos ». */
	export let mode: 'photos' | 'documents' | 'mixte' = 'documents';
	export let label: string | null = null;
	export let accept: string | null = null;
	/** Ce que le compteur annonce pour un `accept` hors des trois familles (sinon « mixte »). */
	export let types: string | null = null;
	$: accepte =
		accept ?? { photos: ACCEPT_PHOTOS, documents: ACCEPT_DOCUMENTS, mixte: ACCEPT_FICHIERS }[mode];
	$: libelle =
		label ??
		{ photos: 'Ajouter des photos', documents: 'Ajouter un document', mixte: 'Ajouter un fichier' }[
			mode
		];
	export let id: string | undefined = undefined;
	export let disabled = false;
	export let readonly = false;
	export let upload: ((file: File) => Promise<string>) | null = null;
	export let remove: ((url: string) => Promise<string[] | void>) | null = null;
	/** Côté des vignettes d'image, en px. */
	export let size = 64;

	/** Retenir les fichiers au lieu de les téléverser (voir l'en-tête). */
	export let differe = false;
	/** Les `File` retenus en mode différé — à lier avec `bind:`. */
	export let fichiers: File[] = [];

	/** Intitulé affiché au-dessus du champ. Laisser vide : il est DÉDUIT du mode
	    et de `max`. C'est tout l'objet de cette prop — le libellé vivait dans
	    CHAQUE page appelante, et elles avaient divergé : « Photos » sur les
	    actualités et le calendrier, « Photos (max 5) » sur les tickets ;
	    « Documents (PDF, Word, Excel) » ici, « Documents (PDF, Word, Excel —
	    max 5) » là (signalé le 16/08/2026).

	    Le porter ici rend toute évolution HÉRITÉE : changer la formulation, ou
	    les types acceptés, se répercute partout sans toucher une seule page.
	    Ne le surcharger que pour une vraie spécificité d'écran. */
	export let titre: string | null = null;

	/**  Proposer un LIBELLÉ pour le fichier déposé, au-dessus du bouton.
	 *
	 *  🔴 11/09/2026, signalé à l'écran : le dépôt d'un document différait entre
	 *  les contrats et les tickets. Les contrats portaient un champ « Titre »
	 *  écrit à la main par les CONTRATS, les tickets n'en avaient
	 *  aucun — deux gestes pour une même chose, et un fichier de ticket ne
	 *  pouvait porter que le nom que son auteur avait donné sur son disque.
	 *
	 *  Le champ vit donc ICI, dans le composant unique de dépôt : l'ajouter aux
	 *  tickets seulement aurait fait une troisième forme. Toute page qui
	 *  l'active l'obtient au même endroit, avec le même intitulé.
	 *
	 *  ⚠️ Optionnel au sens propre : vide, c'est le nom du fichier qui sert. La
	 *  règle est celle que les contrats appliquaient déjà
	 *  (`titre.trim() || fichier.name`) — elle n'est pas inventée ici, elle est
	 *  remontée d'un cran. */
	export let avecLibelle = false;
	/**  Le libellé saisi — à lier avec `bind:` par qui envoie le fichier. */
	export let libelleFichier = '';

	/**  Le nom à AFFICHER pour une URL donnée — `{ url: 'contrat-2024.pdf' }`.
	 *
	 *  🔴 Ajouté le 12/09/2026 pour que les CONTRATS emploient ce composant au
	 *  lieu de leur liste maison. Leurs documents sont des entités `Document`
	 *  servies par `/documents/<id>/télécharger` : l'URL ne porte ni le nom du
	 *  fichier ni son extension, donc `nomFichier(u)` rendait « télécharger » et
	 *  `typeFichier` ne pouvait deviner aucun type.
	 *
	 *  ⚠️ Une table de noms, pas un modèle : ce composant continue d'ignorer ce
	 *  qu'est un `Document`. L'appelant traduit, et lui seul. */
	export let noms: Record<string, string> = {};

	//  `mode` sert au rendu (vignettes ou liste). Quand il n'est pas donné, le
	//  libellé se déduit d'`accept` plutôt que du défaut : plusieurs champs de
	//  PHOTOS ne précisaient pas `mode`, et auraient annoncé « Documents » au-dessus
	//  de leurs photos (constaté en relevant les 13 usages, 16/08/2026).
	$: _nature =
		accept === ACCEPT_PHOTOS
			? 'photos'
			: accept === ACCEPT_DOCUMENTS
				? 'documents'
				: accept
					? 'mixte'
					: mode;
	//  ⚠️ Le « (max N) » a QUITTÉ l'intitulé le 16/08/2026 : le compteur `0/N`
	//  affiché sous le bouton le dit déjà, et le dit mieux — il se met à jour.
	//  Deux façons d'énoncer la même limite, dont une figée, c'est la duplication
	//  ordinaire (`standards/02` §2), en trois mots.
	$: _titre =
		titre ??
		(_nature === 'photos' ? 'Photos' : _nature === 'documents' ? 'Documents' : 'Pièces jointes');
	//  🔴 Les types annoncés se LISENT dans `#lib/fichiers`, à côté des `ACCEPT_*`
	//  qu'ils décrivent. Ils étaient récités ICI, sous un commentaire qui
	//  affirmait le contraire — et le mode MIXTE annonçait donc « PDF, Word,
	//  Excel, texte » au-dessus d'un contrôle qui accepte aussi les photos
	//  (signalé à l'écran le 21/09/2026).
	//
	//  En aide grise sous le bouton, et non dans l'intitulé, qui est devenu le
	//  titre de section (`SectionFormulaire`).
	$: _types = types ?? LIBELLE_TYPES[_nature as keyof typeof LIBELLE_TYPES] ?? '';

	const dispatch = createEventDispatcher<{ change: string[] }>();

	let envoi = false;

	//  Aperçus des fichiers RETENUS (mode différé). Mémorisés dans une `Map` et
	//  non recalculés : `apercuDe` est appelée depuis un bloc réactif, et créer
	//  une URL d'objet à chaque recalcul fuirait une entrée par frappe clavier.
	const apercus = new Map<File, string>();
	function apercuDe(f: File): string | null {
		if (!f.type.startsWith('image/')) return null;
		let u = apercus.get(f);
		if (!u) {
			u = URL.createObjectURL(f);
			apercus.set(f, u);
		}
		return u;
	}
	function oublier(f: File) {
		const u = apercus.get(f);
		if (u) {
			URL.revokeObjectURL(u);
			apercus.delete(f);
		}
	}
	//  Sortie non nominale : l'utilisateur peut quitter l'écran sans jamais
	//  soumettre ni retirer un fichier (socle 11 §12).
	onDestroy(() => {
		for (const u of apercus.values()) URL.revokeObjectURL(u);
		apercus.clear();
	});

	//  UNE seule liste rendue, quelle que soit l'origine : c'est ce qui garantit
	//  que le mode différé ne peut pas prendre une autre apparence.
	//  `apercu` non nul ⇒ vignette d'image ; nul ⇒ pastille de document.
	type Piece = { cle: string; nom: string; apercu: string | null; fichier: File | null };
	$: pieces = differe
		? fichiers.map((f, i): Piece => ({
				cle: `${i} ${f.name} ${f.size}`,
				nom: f.name,
				apercu: apercuDe(f),
				fichier: f,
			}))
		: (({ photos, documents }) => [
				...photos.map((u): Piece => ({
					cle: u,
					nom: noms[u] ?? nomFichier(u),
					apercu: u,
					fichier: null,
				})),
				...documents.map((u): Piece => ({
					cle: u,
					//  `noms` prime : une URL de téléchargement ne nomme pas son fichier.
					nom: noms[u] ?? nomFichier(u),
					apercu: null,
					fichier: null,
				})),
			])(separerFichiers(urls));
	$: vignettes = pieces.filter((p) => p.apercu !== null);
	$: pastilles = pieces.filter((p) => p.apercu === null);
	$: nombre = differe ? fichiers.length : urls.length;
	$: complet = nombre >= max;

	/**  Le fichier sous le nom que l'auteur lui a donné, extension préservée.
	 *
	 *  🔴 Pourquoi renommer plutôt que stocker un libellé à part (11/09/2026) :
	 *  un document de TICKET n'est pas une entité `Document`, c'est une URL dans
	 *  une liste. Il n'existe aucun champ où ranger un libellé — en ajouter un
	 *  demanderait une migration et une structure `{url, libelle}` partout où ces
	 *  listes sont lues.
	 *
	 *  Le nom du fichier, lui, est déjà ce que TOUS les rendus affichent. Le
	 *  libellé le devient donc, et il est persisté sans que rien d'autre bouge.
	 *
	 *  ⚠️ Sans effet en mode différé : là (contrats, actualités), le libellé
	 *  devient le `titre` d'un vrai `Document`, et c'est l'appelant qui l'envoie.
	 *  Renommer en plus donnerait deux noms pour un fichier.
	 *
	 *  ⚠️ L'assainissement reste côté serveur (`utils/fichiers`, préfixe UUID et
	 *  caractères filtrés) : le refaire ici serait une seconde règle de nommage,
	 *  et c'est la sienne qui fait foi. */
	function renommer(file: File): File {
		const voulu = libelleFichier.trim();
		if (!avecLibelle || !voulu) return file;
		const point = file.name.lastIndexOf('.');
		const extension = point > 0 ? file.name.slice(point) : '';
		//  Si l'auteur a écrit l'extension lui-même, ne pas la doubler.
		const nom = voulu.toLowerCase().endsWith(extension.toLowerCase()) ? voulu : voulu + extension;
		return new File([file], nom, { type: file.type, lastModified: file.lastModified });
	}

	async function ajouter(e: Event) {
		const input = e.target as HTMLInputElement;
		const choisis = Array.from(input.files ?? []);
		input.value = '';
		if (!choisis.length || complet) return;
		//  `slice` borne à ce qui reste sous `max`, dans les deux modes.
		const retenus = choisis.slice(0, max - nombre);
		if (differe) {
			fichiers = [...fichiers, ...retenus];
			return;
		}
		envoi = true;
		try {
			// Séquentiel et non parallèle : l'API valide et redimensionne chaque
			// fichier, et un RPi qui reçoit cinq images de 4 Mo en même temps sature
			// sa mémoire.
			for (const file of retenus) {
				const envoye = renommer(file);
				urls = [...urls, upload ? await upload(envoye) : (await fichiersApi.upload(envoye)).url];
			}
			//  Le libellé a servi : le vider évite qu'il s'applique en silence au
			//  fichier suivant, qui n'a aucune raison de porter le même nom.
			libelleFichier = '';
			dispatch('change', urls);
		} catch (err) {
			toast('error', messageErreur(err, "Erreur lors de l'envoi du document"));
		} finally {
			envoi = false;
		}
	}

	async function retirer(p: Piece) {
		if (p.fichier) {
			oublier(p.fichier);
			fichiers = fichiers.filter((f) => f !== p.fichier);
			return;
		}
		try {
			const maj = remove ? await remove(p.cle) : null;
			urls = Array.isArray(maj) ? maj : urls.filter((u) => u !== p.cle);
			dispatch('change', urls);
		} catch (err) {
			toast('error', messageErreur(err, 'Erreur lors de la suppression'));
		}
	}
</script>

<div class="fichiers-upload">
	{#if _titre}
		<label class="fichiers-titre" for={id}>{_titre}</label>
	{/if}
	{#if vignettes.length}
		<div class="fichiers-liste">
			{#each vignettes as p (p.cle)}
				<Vignette src={p.apercu ?? ''} alt="" {size} title={p.nom}>
					{#if !readonly}
						<button
							type="button"
							class="photo-retirer"
							title="Retirer cette photo"
							aria-label="Retirer {p.nom}"
							on:click={() => retirer(p)}>×</button
						>
					{/if}
				</Vignette>
			{/each}
		</div>
	{/if}
	{#if pastilles.length}
		<div class="fichiers-liste">
			{#each pastilles as p (p.cle)}
				<PastilleFichier nom={p.nom} {readonly} on:click={() => retirer(p)} />
			{/each}
		</div>
	{/if}

	{#if !readonly}
		<!--  🔴 Le bouton et le champ de libellé sur UNE MÊME LIGNE, alignés
		      (12/09/2026, troisième passage à l'écran). Empilés, ils faisaient trois
		      lignes pour un seul geste — et le champ, posé sous le compteur,
		      semblait appartenir à autre chose.

		      L'ordre reste celui du standard (`ux-patterns` §0 bis) : le bouton
		      d'abord, on choisit le fichier avant de le nommer. Le compteur passe
		      SOUS la rangée : il commente ce qui vient d'être déposé, il ne fait
		      pas partie du geste. -->
		<div class="fichiers-geste">
			<label
				class="btn btn-sm btn-outline fichiers-ajout"
				class:disabled={complet || envoi || disabled}
			>
				{envoi ? '⏳ Envoi…' : `\u{1F4CE} ${libelle}`}
				<input
					{id}
					type="file"
					multiple
					accept={accepte}
					disabled={complet || envoi || disabled}
					on:change={ajouter}
				/>
			</label>
			{#if avecLibelle}
				<!--  ⚠️ Pas d'intitulé au-dessus : le placeholder dit à lui seul ce que
				      le champ attend et ce qui se passe s'il reste vide. Un intitulé
				      « Libellé du document » par-dessus son propre placeholder disait deux
				      fois la même chose ; `aria-label` porte le nom accessible sans
				      occuper de ligne.

				      ⚠️ Le placeholder DIT ce qu'il fait — « se substituera au nom du
				      fichier » — parce que c'est la seule chose qu'on ne devine pas :
				      « Le nom de fichier » laissait croire qu'il fallait le recopier
				      (12/09/2026). Le « (optionnel) » y est admis : la règle qui
				      l'interdit vise les INTITULÉS, où l'absence d'astérisque suffit
				      (`ux-patterns` §9) — ici il n'y a pas d'intitulé du tout. -->
				<input
					type="text"
					class="fichiers-libelle"
					aria-label="Libellé du document"
					bind:value={libelleFichier}
					disabled={envoi || disabled}
					placeholder="Nom du document qui se substituera au nom du fichier (optionnel)"
				/>
			{/if}
		</div>
		<span class="fichiers-compte">
			{nombre}/{max}{#if _types}{SEPARATEUR.point}{_types}{/if}
		</span>
	{/if}
</div>

<style>
	/*  Mêmes valeurs que `.field label` : l'œil doit lire la même chose qu'un
	    intitulé de champ ordinaire. */
	/*  Le champ de libellé prend la largeur disponible et passe à la ligne avant
	    le bouton sur téléphone : `.champ-moyen` porte la largeur normée, le
	    `margin-bottom` la respiration qui le sépare du bouton. */
	/*  🔴 « Plus large — 50 % de Description » (11/09/2026). La description occupe
	    toute la largeur de saisie : la moitié se dit donc en pourcentage du même
	    conteneur, et suit l'échelle du produit sans chiffre inventé ici.

	    ⚠️ `min-width` + `max-width` : sur téléphone, 50 % devient trop étroit pour
	    lire ce qu'on tape, et le champ reprend la pleine largeur
	    (`standards/11` §10). */
	/*  La rangée du geste : le bouton, puis le champ qui prend la place restante.
	    `align-items: center` les pose sur la même ligne ; `flex-wrap` fait passer
	    le champ dessous quand la place manque, au lieu de l'écraser
	    (`standards/11` §10 — l'enroulement avant la compression). */
	/*  🔴 `width: 100%` n'est PAS une redite (12/09/2026, mesuré dans le CSS après
	    un second signalement « le champ doit faire 50 % de la largeur de la boîte
	    de Description »).

	    Le conteneur `.fichiers-upload` est une COLONNE avec `align-items:
	    flex-start` : sans largeur explicite, cette rangée se rétrécit à son
	    contenu, et les « 50 % » du champ portaient alors sur le bouton plus
	    lui-même — quelques centaines de pixels au lieu de la moitié du bloc.
	    Le pourcentage était juste ; c'est ce à quoi il se rapportait qui ne
	    l'était pas. */
	.fichiers-geste {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		flex-wrap: wrap;
		width: 100%;
	}
	/*  `0 0 50%` et non `1 1 50%` : exactement la moitié de la boîte, comme la
	    Description au-dessus. Avec `1 1`, le champ absorbait en plus tout l'espace
	    que le bouton laissait — il n'aurait jamais fait 50 % de quoi que ce soit.
	    `flex-wrap` l'envoie sous le bouton quand la moitié ne tient plus. */
	.fichiers-libelle {
		flex: 0 0 50%;
		min-width: 200px;
		max-width: 100%;
	}
	.fichiers-titre {
		display: block;
		font-size: var(--fs-base);
		font-weight: 500;
		color: var(--color-text);
		margin-bottom: 0.3rem;
	}
	.fichiers-upload {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
		align-items: flex-start;
	}
	.fichiers-liste {
		display: flex;
		gap: 0.35rem;
		flex-wrap: wrap;
	}
	/*  Le type en tête, gris et compact : il se lit d'un coup d'œil sans voler la
	    place au nom, qui reste ce qu'on cherche ensuite. */
	.photo-retirer {
		position: absolute;
		top: 2px;
		right: 2px;
		background: rgba(0, 0, 0, 0.6);
		color: var(--color-sur-voile);
		border: none;
		border-radius: 50%;
		width: 18px;
		height: 18px;
		font-size: var(--fs-xs);
		cursor: pointer;
		line-height: 1;
		display: flex;
		align-items: center;
		justify-content: center;
	}
	.fichiers-ajout {
		cursor: pointer;
		display: inline-flex;
		align-items: center;
		gap: 0.3rem;
	}
	.fichiers-ajout.disabled {
		opacity: 0.5;
		cursor: default;
	}
	.fichiers-ajout input {
		display: none;
	}
	.fichiers-compte {
		font-size: var(--fs-2xs);
		color: var(--color-text-muted);
	}
	/*  Au doigt, 44 px comme `.btn-icon` : il en mesurait 22 (#1329). La souris
	    garde sa densité. 🔒 `e2e/depot-fichier.spec.ts`. */
	@media (pointer: coarse) {
		.fichiers-ajout {
			min-height: 44px;
		}
	}
</style>
