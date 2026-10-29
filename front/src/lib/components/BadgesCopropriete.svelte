<!--
  **Quels badges circulent, et chez qui** — la vue du conseil syndical.

  ## 🔴 Pourquoi cet écran (#805, 06/09/2026)

  `GET /acces/admin/vigiks` et `/admin/telecommandes` existaient depuis
  longtemps, réservées au CS, et **aucun écran ne les appelait**. Le ticket posait
  la question franchement : les livrer, ou les retirer ?

  Arbitrage du 06/09 : **lecture seule** — RENVERSÉ le 14/09 (cf. plus bas).
  Trois autres routes, qui créaient et modifiaient
  des badges, ont été supprimées le même jour — enregistrer un badge est déjà
  couvert deux fois (l'import Excel en masse, `declarer-badge` par le résident à
  l'unité), et une troisième voie jamais exercée est du code qui dérive.

  Ces deux lectures-ci restent parce qu'elles répondent à une question
  qu'**aucun autre écran ne sait poser** : *« qui a le badge 4521 ? »*. Sur une
  copropriété, elle se pose — au départ d'un locataire, ou quand un badge est
  retrouvé dans le hall.

  ## ⚠️ La route a dû être ENRICHIE pour être utile

  Elle rendait l'objet brut, donc `user_id` : un écran bâti dessus aurait affiché
  « badge 4521 → utilisateur 37 », c'est-à-dire rien. Le nom du porteur et le
  libellé du lot sont résolus côté serveur, une fois — pas par un rapprochement
  que cet écran referait à sa façon.

  C'est la leçon générale de #801 : une route sans appelant n'est jamais mise à
  l'épreuve de la question à laquelle elle est censée répondre.

  ## 🔴 Ce paragraphe disait l'INVERSE de ce que l'écran fait (corrigé le 15/09/2026)

  Il annonçait : « Aucun geste. Pas de création, pas de changement de statut, pas
  de suppression. […] Ouvrir l'écriture ici rouvrirait la troisième voie qu'on
  vient de fermer. » C'était vrai le 06/09, et **faux depuis le 14** — le
  renversement a ajouté les routes, les boutons, les droits et le manuel, et
  laissé les deux textes qui décrivaient la décision d'avant. Le paragraphe
  d'aide de l'écran disait de même « Cette vue est en lecture seule », à trois
  centimètres du bouton « Enregistrer un accès ».

  ⚠️ C'est le motif que le dépôt connaît par cœur : **le seul endroit qui parlait
  du sujet affirmait que le problème n'existait pas.** Un commentaire périmé ne
  se contente pas d'être inutile — il est cru.

  ## Ce que cet écran fait aujourd'hui

  Le conseil syndical **enregistre** un accès pour un copropriétaire, le
  **corrige** et l'**exporte** (un fichier par type). Un résident déclare les
  siens depuis son espace, et l'import Excel les enregistre en masse : les trois
  voies coexistent parce qu'elles répondent à trois situations, et elles passent
  toutes par le même descripteur (`utils/types_acces`) — c'est ce qui les empêche
  de diverger, pas leur nombre.

  🔒 La suppression définitive reste à l'**administrateur** : un badge perdu ou
  rendu passe en statut, parce qu'il a existé et qu'il circule.
-->
<script lang="ts">
	import { TYPES_ACCES } from '#lib/types-acces.ts';
	import { onMount } from 'svelte';
	import ConstatsBadges from '#lib/components/ConstatsBadges.svelte';
	import {
		acces as accesApi,
		admin as adminApi,
		type AccesAdmin,
		type ChoixAcces,
		type LotPourBadge,
	} from '#lib/api/index.ts';
	import { isAdmin } from '#lib/stores/auth.ts';
	import BoutonNouveau from '#lib/components/BoutonNouveau.svelte';
	import FormulaireAcces from '#lib/components/FormulaireAcces.svelte';
	import TableParcAcces from '#lib/components/TableParcAcces.svelte';
	import { confirmerPuis } from '#lib/confirmation.ts';
	import { messageErreur, tenter } from '#lib/erreurs.ts';
	import { comparerParNom, nomAffiche } from '#lib/noms.ts';
	import EtatListe from '#lib/components/EtatListe.svelte';
	import ChoixPastilles from '#lib/components/ChoixPastilles.svelte';
	import ChampRecherche from '#lib/components/ChampRecherche.svelte';
	import { contientTousLesMots } from '#lib/texte.ts';
	import ReglagesListe from '#lib/components/ReglagesListe.svelte';
	import { ACCES } from '#lib/entites/acces.ts';

	let vigiks: AccesAdmin[] = [];
	let telecommandes: AccesAdmin[] = [];
	let chargement = true;
	/**  Non vide = on n'a PAS pu regarder. Distinct de « regardé, il n'y a rien »
	 *   — un relevé de badges vide se lirait « aucun badge en circulation », ce
	 *   qui serait faux et rassurant (`standards/04`, #519). */
	let erreur = '';

	//  Deux types, donc deux pastilles plus « Tous » : sous le seuil des listes
	//  courtes, `ChoixPastilles` s'impose (`ux-patterns`).
	//  La liste vit dans `#lib/types-acces` : elle était écrite trois fois (#1329).
	const TYPES = TYPES_ACCES;
	let filtreType = '';
	let recherche = '';

	//  ── Les gestes, ouverts le 14/09/2026 (#953) ────────────────────────────
	//
	//  🔴 Cet écran était en LECTURE SEULE depuis le 06/09 (#805), et c'était une
	//  décision : trois routes d'écriture avaient été supprimées ce jour-là parce
	//  qu'enregistrer un badge était déjà couvert deux fois. Le choix est renversé
	//  sur demande explicite — le conseil syndical remet des badges en main
	//  propre, et rien ne le lui permettait.
	//  La PERSONNE, pas seulement son rendu : `affiche` sert au sélecteur,
	//  `prenom` et `nom` au classement — qui se fait sur le nom de famille
	//  (`comparerParNom`, `#lib/noms`). Les confondre revenait à classer
	//  « Alain FAURE » à la lettre A.
	let porteurs: { id: number; affiche: string; prenom: string; nom: string }[] = [];
	/**  🔒 Ce que chaque type d'accès a le droit d'ouvrir, par clé de type.
	 *
	 *   Demandé le 15/09/2026 : un vigik ouvre la copropriété, un bâtiment ou un
	 *   portillon ; une télécommande, les portails. La liste vient du SERVEUR,
	 *   qui la calcule sur l'arborescence administrée — l'écrire ici en ferait
	 *   une seconde liste, et c'est celle de l'écran qu'on aurait oublié de
	 *   mettre à jour.
	 *
	 *   ⚠️ Elle ne protège rien : la même liste est opposée à la requête sur les
	 *   deux gestes d'écriture. Ici elle PROPOSE, et c'est tout ce qu'un écran
	 *   sait faire. */
	let choixAcces: Record<string, ChoixAcces> = {};
	let lots: LotPourBadge[] = [];
	let formOuvert = false;
	let editId: string | null = null;
	let enregistrement = false;

	const SAISIE_VIERGE = () => ({
		type: 'vigik',
		code: '',
		porteur_id: null as number | null,
		lot_id: null as number | null,
		perimetre_cible: [] as string[],
		statut: 'actif',
		ticket_numero: '',
	});
	let saisie = SAISIE_VIERGE();

	function ouvrirCreation() {
		saisie = SAISIE_VIERGE();
		editId = null;
		formOuvert = true;
	}

	function ouvrirEdition(a: AccesAdmin & { type: string }) {
		saisie = {
			type: a.type,
			code: a.code,
			porteur_id: a.porteur_id ?? null,
			lot_id: a.lot_id ?? null,
			perimetre_cible: [...(a.perimetre_cible ?? [])],
			statut: String(a.statut),
			ticket_numero: '',
		};
		editId = `${a.type}-${a.id}`;
		formOuvert = false;
	}

	function fermer() {
		formOuvert = false;
		editId = null;
	}

	async function recharger() {
		[vigiks, telecommandes] = await Promise.all([
			accesApi.listVigiks(),
			accesApi.listTelecommandes(),
		]);
	}

	async function enregistrer() {
		enregistrement = true;
		//  ⚠️ `tenter` porte le message d'erreur : un `try/catch` local serait la
		//  soixante-huitième écriture de ce ternaire (`lint:message-erreur`).
		await tenter(async () => {
			const corps = {
				code: saisie.code.trim(),
				porteur_id: saisie.porteur_id,
				//  `0` DÉLIE en correction ; à la création, « aucun » s'envoie vide.
				lot_id: saisie.lot_id ?? (editId ? 0 : null),
				perimetre_cible: saisie.perimetre_cible,
				statut: saisie.statut,
				ticket_numero: saisie.ticket_numero.trim() || null,
			};
			if (editId) {
				const [type, id] = editId.split('-');
				await accesApi.modifierAcces(type, Number(id), corps);
			} else {
				await accesApi.creerAcces(saisie.type, corps);
			}
			await recharger();
			fermer();
		});
		enregistrement = false;
	}

	//  🔒 Réservé à l'admin côté SERVEUR : le bouton ne s'affiche que pour lui,
	//  et l'écran dit alors la même chose que le serveur — ni plus, ni moins.
	async function supprimer(a: AccesAdmin & { type: string }) {
		//  ⚠️ `confirmerPuis` et non `confirmer` + `tenter` : le couple
		//  « demander, faire, annoncer » est écrit UNE fois dans le dépôt, et le
		//  recomposer ici en serait la copie suivante.
		await confirmerPuis(
			{
				message:
					`Supprimer définitivement ${labelType[a.type]} ${a.code} ? ` +
					'Pour un badge perdu ou rendu, préférer le statut : il garde la ' +
					'trace que ce badge a existé, et donc qu’il circule.',
				libelleConfirmer: 'Supprimer',
				danger: true,
			},
			'Accès supprimé',
			async () => {
				await accesApi.supprimerAcces(a.type, a.id);
				await recharger();
			},
		);
	}

	onMount(async () => {
		try {
			[vigiks, telecommandes] = await Promise.all([
				accesApi.listVigiks(),
				accesApi.listTelecommandes(),
			]);
			//  Les porteurs proposés à la saisie. Chargés ici plutôt qu'à
			//  l'ouverture du formulaire : une liste qui se remplit après le
			//  premier rendu ferait clignoter le sélecteur.
			porteurs = (await adminApi.utilisateurs()).map((u) => ({
				id: u.id,
				affiche: nomAffiche(u),
				prenom: u.prenom ?? '',
				nom: u.nom ?? '',
			}));
			choixAcces = await accesApi.choixAcces();
			lots = await accesApi.lotsImports();
		} catch (e) {
			erreur = messageErreur(e, 'Chargement impossible');
		} finally {
			chargement = false;
		}
	});

	//  Le type est porté par la LIGNE, pas par deux tableaux séparés : c'est ce
	//  qui permet de chercher un code sans savoir de quel objet il s'agit — et
	//  c'est justement la situation où l'on pose la question.
	$: toutes = [
		...vigiks.map((v) => ({ ...v, type: 'vigik' as const })),
		...telecommandes.map((t) => ({ ...t, type: 'telecommande' as const })),
	];

	/**  La colonne de tri, et son sens.
	 *
	 *  🔴 « Porteur » par défaut, demandé à l'écran le 12/09/2026 : la question
	 *  qu'on pose à cette table est « qui détient quoi », et surtout « que détient
	 *  CETTE personne » — au départ d'un locataire, ou quand un badge est
	 *  retrouvé. Triée par code, elle dispersait les trois badges d'un même
	 *  porteur sur trois écrans.
	 *
	 *  ⚠️ Un tri, pas un regroupement : les lignes restent des lignes. Grouper
	 *  demanderait de décider ce qu'on affiche pour un porteur sans badge, et la
	 *  table ne répond pas à cette question-là. */
	let triCol: 'porteur' | 'type' | 'code' | 'lot' | 'acces' | 'statut' = 'porteur';
	let triAsc = true;

	function trierPar(col: typeof triCol) {
		//  Recliquer la même colonne inverse le sens — le geste que tout tableau
		//  du web a, et qu'il serait surprenant de ne pas trouver.
		if (triCol === col) triAsc = !triAsc;
		else {
			triCol = col;
			triAsc = true;
		}
	}

	//  Le porteur d'une ligne, retrouvé par son identifiant : la ligne ne porte
	//  que « Prénom NOM » composé, et le classement a besoin des deux morceaux.
	$: parId = new Map(porteurs.map((p) => [p.id, p]));

	/**  La valeur comparée pour une ligne. `localeCompare` avec `sensitivity`
	 *   pour que « Ébert » se range après « Dupont » et non en fin de liste. */
	function cle(a: (typeof toutes)[number]): string {
		if (triCol === 'type') return a.type ?? '';
		if (triCol === 'lot') return a.lot_libelle ?? '';
		//  ⚠️ Trié sur les CODES, pas sur le libellé : le libellé dépend de
		//  l'arbre, qui peut n'être pas encore chargé — l'ordre changerait alors
		//  sous les yeux. Les codes, eux, arrivent avec la ligne.
		if (triCol === 'acces') return (a.perimetre_cible ?? []).join(' ');
		if (triCol === 'statut') return a.statut ?? '';
		return a.code ?? '';
	}

	$: filtrees = toutes
		.filter((a) => !filtreType || a.type === filtreType)
		.filter((a) => contientTousLesMots([a.code, a.porteur_nom, a.lot_libelle], recherche))
		//  ⚠️ Trié APRÈS les filtres : trier d'abord ferait le même travail sur des
		//  lignes qu'on s'apprête à écarter.
		//  🔴 La colonne « Porteur » classe sur le NOM DE FAMILLE, pas sur la
		//  chaîne affichée : `porteur_nom` vaut « Alain FAURE », et trier dessus
		//  rangeait Alain à la lettre A (signalé à l'écran le 15/09/2026).
		//
		//  La règle est celle de `#lib/noms.comparerParNom` — la plus déployée du
		//  produit (annuaire, administration, espace CS) —, pas une comparaison
		//  écrite ici.
		.sort((x, y) => {
			const ordre = triAsc ? 1 : -1;
			if (triCol === 'porteur') {
				return ordre * comparerParNom(parId.get(x.porteur_id ?? -1), parId.get(y.porteur_id ?? -1));
			}
			return ordre * cle(x).localeCompare(cle(y), 'fr', { sensitivity: 'base' });
		});

	const labelType: Record<string, string> = Object.fromEntries(TYPES.map((t) => [t.val, t.label]));
</script>

<section class="card bc-carte">
	<div class="section-header">
		<h2 class="section-title">Tous les badges de la copropriété</h2>
	</div>
	<ConstatsBadges />
	<!--  🔴 Ce paragraphe annonçait « Cette vue est en LECTURE SEULE » alors que
	      l'écran porte, depuis la v1.37.0, un bouton « Enregistrer un accès », un
	      crayon et une corbeille sur chaque ligne. Signalé le 15/09/2026, sur une
	      capture d'écran où les deux se voyaient à trois centimètres l'un de
	      l'autre.

	      ⚠️ C'est le motif que le dépôt connaît : le seul endroit qui parlait du
	      sujet disait que le problème n'existait pas. Le renversement de #805 a
	      ouvert l'écriture, ajouté les routes, les boutons, les droits et le
	      manuel — et laissé la phrase qui décrivait la décision d'avant. -->
	<p class="bc-aide">
		Qui détient quoi, badges Vigik et télécommandes confondus. Le conseil syndical peut
		<strong>enregistrer</strong> un accès pour un copropriétaire, le <strong>corriger</strong> et l'<strong
			>exporter</strong
		> ; un résident déclare les siens depuis son espace, et l'import Excel les enregistre en masse. Seul
		un administrateur retire définitivement une ligne.
	</p>

	<!--  Les RÉGLAGES de la liste, à la façon de la page Affaires — standard du
	      site depuis le 10/10/2026 : la recherche en tête (on cherche avant de
	      trier), le filtre de type dessous, son libellé devant ; le compteur sur
	      la pastille retenue seule (`ux-patterns` §5). -->
	<ReglagesListe>
		<ChampRecherche
			id="bc-recherche"
			bind:valeur={recherche}
			placeholder="4521, Dupont, appartement 12…"
			dans="code, porteur et lot"
		/>
		<ChoixPastilles
			options={TYPES}
			bind:valeur={filtreType}
			tous="Tous"
			compte={filtrees.length}
			libelle="Type"
			libelleDevant
		/>
	</ReglagesListe>

	<!--  ⚠️ L'ordre suit `ux-patterns` §0 ter : ce qui QUALIFIE la liste et ses
	      commandes restent au-dessus du formulaire, qui reste au-dessus de la
	      table. Ouvrir « Enregistrer » ne doit pas repousser la recherche hors
	      de l'écran.

	      🔗 L'export est un LIEN, pas un bouton : la réponse est un fichier, et
	      le navigateur sait le recevoir. Le faire passer par le client d'API
	      obligerait à fabriquer un `blob:` puis un lien de téléchargement — trois
	      gestes pour ce qu'une ancre fait seule, cookies de session compris. -->
	<div class="bc-actions">
		<BoutonNouveau
			ouvert={formOuvert}
			libelle={ACCES.libelleNouveau}
			on:basculer={ouvrirCreation}
		/>
		<!--  🔴 UN export PAR TYPE depuis le 15/09/2026, sur demande. La liste
		      est engendrée par `TYPES` — la même qui nourrit les pastilles de
		      filtre et le formulaire : un troisième type d'accès apporterait son
		      bouton sans qu'on touche à ce balisage. Deux ancres écrites à la
		      main auraient divergé, et c'est exactement ce que `TYPES` évite
		      déjà trois lignes plus haut. -->
		{#each TYPES as t (t.val)}
			<a class="btn btn-outline" href={accesApi.urlExportParc(t.val)} download>
				⬇️ Exporter {t.label}
			</a>
		{/each}
	</div>

	{#if formOuvert}
		<FormulaireAcces
			types={TYPES}
			{porteurs}
			{lots}
			{choixAcces}
			bind:saisie
			{enregistrement}
			cle="creation"
			on:annule={fermer}
			on:enregistre={enregistrer}
		/>
	{/if}

	<EtatListe
		{chargement}
		{erreur}
		vide={toutes.length === 0}
		titreErreur="Impossible d’afficher les badges"
		titreVide="Aucun badge enregistré"
		messageVide="Les badges apparaissent ici une fois l’import Excel résolu, ou déclarés par leurs porteurs."
	>
		{#if filtrees.length === 0}
			<p class="bc-aide">Aucun badge ne correspond à cette recherche.</p>
		{:else}
			<TableParcAcces
				lignes={filtrees}
				{labelType}
				{triCol}
				{triAsc}
				{editId}
				estAdmin={$isAdmin}
				on:trier={(e) => trierPar(e.detail as typeof triCol)}
				on:editer={(e) => ouvrirEdition(e.detail)}
				on:supprimer={(e) => supprimer(e.detail)}
			>
				<svelte:fragment slot="edition">
					<!--  `encadre={false}` : le formulaire s'ouvre DANS une ligne de
					      tableau, et une bordure de plus y serait « la carte dans la
					      carte » (#425). Pas de `cle` non plus : rien n'a bougé. -->
					<FormulaireAcces
						types={TYPES}
						{porteurs}
						{lots}
						{choixAcces}
						bind:saisie
						modeEdition
						{enregistrement}
						encadre={false}
						on:annule={fermer}
						on:enregistre={enregistrer}
					/>
				</svelte:fragment>
			</TableParcAcces>
			<p class="bc-compte">
				{filtrees.length} badge{filtrees.length !== 1 ? 's' : ''}
				{#if filtrees.length !== toutes.length}sur {toutes.length}{/if}
			</p>
		{/if}
	</EtatListe>
</section>

<style>
	/*  Les deux commandes de tête, sur une ligne — et qui s'enroule sous 767 px
	    plutôt que de déborder : c'est la largeur à laquelle tout le site bascule
	    en mobile (#839). */
	.bc-actions {
		display: flex;
		gap: 0.5rem;
		flex-wrap: wrap;
		align-items: center;
		margin-bottom: 0.75rem;
	}
	/*  La ligne d'édition n'est pas une ligne de données : elle reprend le fond
	    de la page pour se distinguer de ce qu'elle interrompt. */

	/*  L'en-tête cliquable ressemble à un en-tête, pas à un bouton : c'est la
	    flèche qui dit qu'il trie, et le survol qui dit qu'il se clique. */
	/*  `.section` n'est PAS globale - elle vit dans `acces-securite`, scopee a ce
	    fichier-la. L'employer ici aurait rendu la carte sans son cadre : c'est la
	    regression des pastilles nues (`standards/02` §4 ter), et `lint:classes-nues`
	    l'a refusee. Le padding est donc pose ici, avec la carte qui le porte. */
	.bc-carte {
		padding: 1.25rem;
		margin-top: 1rem;
	}
	.bc-aide {
		font-size: var(--fs-md);
		color: var(--color-text-muted);
		margin: 0 0 0.75rem;
	}
	.bc-compte {
		font-size: var(--fs-sm);
		color: var(--color-text-muted);
		margin: 0.5rem 0 0;
		text-align: right;
	}
</style>
