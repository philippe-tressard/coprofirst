<!--
  La section **Destinataires** du cadre — *à qui* on l'adresse.

  Extraite de `ChampsCommuns` le 22/09/2026, au fil de l'eau : le fichier
  dépassait 500 lignes et le garde-fou de modularité (rang 1) a refusé qu'il
  grossisse en relayant la fin de validité d'une actualité (#1093).

  Ce n'est pas un découpage arbitraire : **neuf sections sur onze avaient déjà
  leur composant** — `SectionQuand`, `SectionDescription`, `SectionDiffusion`,
  `SectionOptionsPublication`, `SectionWorkflow`… Les deux dernières écrites en
  ligne étaient le Périmètre et celle-ci, restées là parce qu'elles tiennent en
  quinze lignes. Une exception qui n'a d'autre raison que sa brièveté finit par
  être la raison pour laquelle le fichier ne peut plus rien recevoir.

  🔴 Le sélecteur se tait (`titre=""`) : c'est la SECTION qui nomme. Sans quoi
  on lirait « DESTINATAIRES » puis « Destinataires * », le nom deux fois —
  signalé à l'écran le 16/08/2026, dès la mise en production.

  ## La pastille de lecture (lot 1, 25/09/2026)

  Quand l'écran dit la NATURE (`lecture`), la section répond à « qui d'autre
  la lit ? » : la pastille est son badge d'état — et son résumé, pliée —, la
  case « Confidentielle » l'ouvre, et la phrase entière se lit dessous.
  Sans `lecture`, la section reste celle d'avant (sondages, événements).

  ## Une affaire choisit ses destinataires (#1343, 26/09/2026)

  *« il n'est toujours pas possible de choisir son destinataire ! c'est
  urgent »* — dans toute édition. Les pastilles sont TOUJOURS là, présélection
  faite par la nature (`destinatairesParDefaut`) ; le conseil les change à tout
  moment. Ce qu'il laisse tel quel reste VIDE — la règle de la nature, qui
  suivra l'affaire si elle se date —, ce qu'il change est retenu, et le
  serveur l'applique (`ticket_visible`). « Résident concerné » y remplace la
  case Confidentielle : l'auteur, ou la personne pour qui elle a été saisie,
  et le conseil — c'est ce que le drapeau a toujours voulu dire sur une affaire.
-->
<script lang="ts">
	import DestinatairePicker from '$lib/components/DestinatairePicker.svelte';
	import SectionFormulaire from '$lib/components/SectionFormulaire.svelte';
	import CaseConfidentielle from '$lib/components/CaseConfidentielle.svelte';
	import { LIBELLE_TOUS, concerneTousLesResidents } from '$lib/destinataires';
	import { SECTIONS_LIBELLE } from '$lib/entites/types';
	import { destinatairesParDefaut, estConcerne, lectureDe, titreLecture } from '$lib/lecture';
	import { perimetreRestreint, type NatureLue } from '$lib/lecture-ticket';
	import { perimetresStore } from '$lib/stores/perimetres';
	import { relire } from '$lib/utils';

	/** Préfixe des identifiants — l'écran en ouvre parfois plusieurs à la fois. */
	export let idPrefixe: string;

	export let premiere = false;

	/** Repliée par défaut — la valeur vient de la déclaration (#1095). */
	export let pliable = false;

	export let destinataires: string[] = ['résidents'];

	/**  🔴 Il est REÇU, plus écrit en dur (22/09/2026).
	 *
	 *   Ce composant posait `requis` lui-même. La déclaration ne le savait donc
	 *   pas, et `lint:etats` ne pouvait pas voir qu'une section obligatoire
	 *   était déclarée pliée : l'écran affichait « DESTINATAIRES* » sur une
	 *   ligne fermée, ce que la règle interdit — signalé à l'écran, deux fois.
	 *
	 *   ⚠️ Même angle mort que `pliable` le matin même : ce qu'un composant
	 *   PORTEUR écrit lui-même échappe à la déclaration qui gouverne les
	 *   autres. `lint:pliage-transmis` le refuse désormais pour les deux. */
	export let requis = false;

	/**  Le badge du TITRE de section, calculé ici et nulle part ailleurs.
	 *
	 *   Il n'invente rien : `concerneTousLesResidents` est la fonction qu'emploie
	 *   déjà le sélecteur lui-même. */
	$: badge = concerneTousLesResidents(destinataires) ? LIBELLE_TOUS : '';
	/** Le motif d'extinction de la section, ou `''` (`inactivePour`, #1191). */
	export let inactive = '';

	/**  La nature lue — `null` : pas de pastille de lecture (section d'avant).
	 *   Avec elle viennent la case, le périmètre et sa réserve, qui la décident. */
	export let lecture: NatureLue | null = null;
	export let confidentiel = false;
	export let perimetre: string[] = [];
	export let reservePerimetre = false;
	/**  Les destinataires d'une affaire sans choix — donnés par une Suite, qui
	 *   n'a pas de `lecture` ; déduits de la nature sinon. `null` : aucun. */
	export let parDefaut: string[] | null = null;
	/** Le « Résident concerné » — l'auteur, ou pour qui elle a été saisie. */
	export let concerne = '';
	$: defaut = lecture && !lecture.actualite ? destinatairesParDefaut(lecture) : parDefaut;
	/**  Le défaut de la catégorie est « Résident concerné » (#1436) : la pastille
	 *   est cochée tant que le conseil ne choisit rien — sans poser le drapeau. */
	$: defautConcerne = estConcerne(defaut);
	$: concerneActif = confidentiel || (defautConcerne && !destinataires.length);
	/**  Cocher « Résident concerné » quand c'est le défaut, c'est y REVENIR ; le
	 *   décocher n'a pas de sens — on le quitte en choisissant un autre profil. */
	function basculerConcerne(actif: boolean) {
		if (!defautConcerne) confidentiel = actif;
		else if (actif) [destinataires, confidentiel] = [[], false];
	}
	const cle = (c: string[]) => [...c].sort().join();
	/**  Vide = la règle de la nature : ce qui revient au défaut n'est pas un choix. */
	function choisir(e: CustomEvent<string[]>) {
		destinataires = defaut && cle(e.detail) === cle(defaut) ? [] : e.detail;
	}
	/*  La vignette lit la MÊME nature que les pastilles — catégorie et bâtiments
	    compris. Elle ne recevait que `actualite` : sur une Panne, « Tous » était
	    coché et la vignette disait « Copropriétaires » (#1434, signalé à l'écran
	    le 28/09/2026). 🔒 `e2e/destinataires-panne.spec.ts`. */
	$: lue = relire($perimetresStore, () =>
		lectureDe({
			...lecture,
			actualite: !!lecture?.actualite,
			confidentiel,
			publicCible: destinataires,
			perimetreRestreint: perimetreRestreint(perimetre),
			reservePerimetre,
		}),
	);
	/*  « Rempli » (l'étoile noire) — une valeur par défaut ACTIVE en est une :
	    la liste vide vaut « Tous », et la pastille l'affiche sélectionnée.
	    L'étoile était rouge sur ce « Tous » (27/09/2026, signalé à l'écran :
	    « * rouge, c'est uniquement s'il n'y a aucune valeur »).
	    🔒 `e2e/etoile-valeur-defaut.spec.ts`. */
	$: modifiee =
		confidentiel || (defaut ? destinataires.length > 0 : !concerneTousLesResidents(destinataires));
	/*  Une Suite n'a pas de `lecture`, mais un défaut (`parDefaut`) : liste vide, le
	    badge disait « Tous » alors que la pastille cochée était « Résident concerné »
	    (signalé à l'écran le 03/10/2026). Le badge lit ce que la rangée coche. */
	$: luePar = relire($perimetresStore, () =>
		lectureDe({
			actualite: false,
			confidentiel: concerneActif,
			publicCible: destinataires.length ? destinataires : defautConcerne ? [] : (defaut ?? []),
			perimetreRestreint: false,
			reservePerimetre: false,
		}),
	);
	$: sansLecture = !lecture && !!defaut && !concerneTousLesResidents(defaut) ? luePar : null;
</script>

<SectionFormulaire
	{premiere}
	{pliable}
	badge={lecture ? titreLecture(lue) : sansLecture ? titreLecture(sansLecture) : badge}
	badgeIcones={lecture ? lue.icones : (sansLecture?.icones ?? [])}
	badgeIconeFin={lecture && lue.perimetreReserve ? 'lock' : ''}
	titre={SECTIONS_LIBELLE.destinataires}
	{inactive}
	{requis}
	rempli={destinataires.length > 0 || !!defaut || concerneTousLesResidents(destinataires)}
	valeurModifiee={modifiee}
	idTitre="{idPrefixe}-destinataires-titre"
>
	{#if lecture?.actualite}
		<CaseConfidentielle bind:coche={confidentiel} />
	{/if}
	{#if defaut}
		<!--  « Résident concerné » est UNE PASTILLE DE LA RANGÉE, entre Locataires
		      et Conseil syndical (arbitré à l'écran le 26/09/2026) — pas une ligne
		      à part : c'est un destinataire comme les autres, le plus restreint
		      avant le conseil seul. Choisie, elle éteint les autres. -->
		<fieldset
			class="field champ-large destinataires-groupe"
			aria-labelledby="{idPrefixe}-destinataires-titre"
		>
			<DestinatairePicker
				value={destinataires.length ? destinataires : defautConcerne ? [] : defaut}
				titre=""
				concerne={lecture || parDefaut
					? `Résident concerné${concerne ? ` : ${concerne}` : ''}`
					: null}
				{concerneActif}
				on:change={choisir}
				on:concerne={(e) => basculerConcerne(e.detail)}
			/>
		</fieldset>
	{:else}
		<!--  Les pastilles ne sont pas un contrôle labelable — `for` n'y associerait
		      rien —, d'où le couple `id` sur le titre / `aria-labelledby` sur le
		      groupe. Éteintes, pas effacées, quand « Confidentielle » passe outre :
		      `disabled` d'un `fieldset` désactive chaque bouton sans les recopier. -->
		<fieldset
			class="field champ-large destinataires-groupe"
			disabled={lecture !== null && confidentiel}
			aria-labelledby="{idPrefixe}-destinataires-titre"
		>
			<DestinatairePicker bind:value={destinataires} titre="" />
		</fieldset>
	{/if}
	{#if lecture}
		<p class="aide">
			{lue.phrase}
			{lue.exclus}
		</p>
		{#if lue.avertissement}<p class="aide avertissement">{lue.avertissement}</p>{/if}
	{/if}
</SectionFormulaire>

<style>
	/*  Un `fieldset` sans son cadre natif : il ne sert qu'à éteindre le groupe. */
	.destinataires-groupe {
		border: none;
		margin: 0;
		padding: 0;
		min-width: 0;
	}
	.destinataires-groupe:disabled {
		opacity: 0.45;
	}
	.avertissement {
		color: var(--color-warning-texte);
	}
</style>
