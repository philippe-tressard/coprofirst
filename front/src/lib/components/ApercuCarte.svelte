<!--
  Aperçu d'une carte repliée : les cinq premières lignes du texte, et la vignette
  de sa photo à droite. Sert les actualités ET les tickets — d'où le nom neutre :
  un composant partagé qui porte le nom d'une seule rubrique finit par être
  recopié plutôt que réutilisé.

  Pourquoi un composant pour si peu : quatre listes affichent le même aperçu —
  actualités (fil + historique) et tickets (fil + archives) — et le rendaient
  chacune de leur côté. Le 15/08/2026, il a fallu leur ajouter la vignette : deux
  fois d'abord (#351), puis deux autres quand l'utilisateur a constaté que les
  tickets n'en avaient pas. Exactement le geste qui finit par diverger le jour où
  l'on ne pense qu'à l'un des quatre.

  Le placement suit `ux-patterns` §11 : vignette là où l'on survole, grand format
  là où l'on a demandé à voir. La vignette est à DROITE, comme dans le fil
  d'activité — la gauche porte déjà le bord coloré de la carte.

  ⚠️ Seules les PHOTOS sont connues à ce stade. Les documents joints ne sont
  chargés qu'au dépliage : les compter ici coûterait une requête par carte pour
  afficher un trombone.
-->
<script lang="ts">
	import FluxVignette from '#lib/components/FluxVignette.svelte';
	import { safeDescription } from '#lib/sanitize.ts';

	/**  Contenu de l'élément, brut. `safeDescription` l'assainit ET enveloppe le
	 *   texte non-HTML dans un paragraphe : les descriptions de tickets sont parfois
	 *   du texte simple, dont `safeHtml` seul perdrait les retours à la ligne. */
	export let contenu: string;
	/** URLs des photos ; la première sert de vignette. */
	export let photos: string[] = [];
	/**  Documents joints, quand l'écran les connaît déjà. `FluxVignette` rend
	 *   alors une tuile 📎 plutôt que rien.
	 *
	 *   ⚠️ NE PAS les verser dans `photos` : la vignette prend `photos[0]` et le
	 *   pose dans un `<img>`. Un événement dont la seule pièce est un devis PDF
	 *   sortait donc en image cassée — c'est ce que faisait `CarteEvenement` (supprimé avec #1092).
	 *
	 *   Les ACTUALITÉS n'en passent pas : leurs documents sont des entités
	 *   `Document` chargées au dépliage, et les compter ici coûterait une requête
	 *   par carte pour afficher un trombone. */
	export let fichiers: string[] = [];
	/**  L'aperçu vit dans une LIGNE de liste, pas au pied d'une carte : il n'a
	 *   alors pas à porter le rembourrage de la carte, que la ligne pose déjà.
	 *
	 *   ⚠️ Une PROP, et non une copie de ce composant dans l'écran concerné. Les
	 *   cinq lignes, le dégradé mesuré et l'assainissement sont la NOTION
	 *   « aperçu d'une description » ; seule sa marge dépend de l'hôte. Le premier
	 *   écran qui a eu besoin de la variante est la liste des documents de
	 *   /residence, dont la description était coupée à DEUX lignes par une règle
	 *   écrite sur place (09/09/2026). */
	export let dansLigne = false;

	//  🔴 LE DÉGRADÉ DE FIN A ÉTÉ RETIRÉ (18/09/2026, signalé à l'écran : « il y a
	//  un flou sur la 3ᵉ ligne »). Sa hauteur était FIXE — 2,2 em — et l'aperçu est
	//  passé de 5 lignes d'interligne 1,6 à 3 lignes d'interligne 1,25 : il
	//  couvrait 28 % du texte, il en couvrait 59 %. Deux lignes sur trois.
	//
	//  ⚠️ Une valeur absolue dans un bloc dont la hauteur change est une bombe à
	//  retardement : elle reste juste jusqu'au jour où la densité bouge, et
	//  personne ne relit une règle qui n'a pas été touchée.
	//
	//  Le fil d'activité, qui sert de référence à cette carte, n'en a jamais eu :
	//  le texte s'y arrête net. La mesure après rendu (`scrollHeight`) part avec
	//  le dégradé — elle n'existait que pour lui.
</script>

<div class="carte-apercu" class:dans-ligne={dansLigne}>
	<div class="carte-preview rich-content clamp-3">
		{@html safeDescription(contenu)}
	</div>
	<FluxVignette {photos} {fichiers} />
</div>

<style>
	/*  `min-width:0` : sans lui un enfant flex ne rétrécit pas sous la largeur de
	    son contenu, et le `-webkit-line-clamp` de .clamp-3 n'est jamais appliqué. */
	.carte-apercu {
		display: flex;
		align-items: flex-start;
		gap: 0.85rem;
		padding: 0 0.95rem 0.85rem;
	}
	/*  Rendu DANS l'en-tête de la carte, qui porte déjà son retrait. Depuis le
	    18/09/2026 c'est le cas de tous les aperçus de carte : l'extrait doit
	    venir AVANT les pastilles, et seul l'en-tête peut les ordonner. */
	.carte-apercu.dans-ligne {
		padding: 0;
		margin-top: 0.1rem;
	}
	.carte-apercu .carte-preview {
		flex: 1;
		min-width: 0;
	}
	/*  🔴 LA TYPOGRAPHIE VIENT DU FIL D'ACTIVITÉ (18/09/2026, demandé à l'écran :
	    « inspire-toi du fil d'actualité pour les polices »). `.flux-detail` rend
	    0,8 rem en gris ; l'aperçu d'une carte rendait 0,875 rem avec un interligne
	    de 1,6, soit deux textes différents pour une même notion — le début d'un
	    contenu qu'on n'a pas encore ouvert.

	    L'interligne descend à 1,25 et la marge entre paragraphes à 0,12 em : dans
	    un extrait de trois lignes, c'est la marge de paragraphe qui aère le plus,
	    et elle valait 0,4 em. Validé à l'écran après mesure. */
	/*  0,75 rem et non 0,8 (18/09/2026, validé à l'écran) : c'est l'ÉCART avec le
	    titre qui fait ressortir le titre, et 0,8 rem n'en laissait que 2,1 px.
	    Le fil d'activité rend 0,8 — l'aperçu d'une carte descend d'un cran parce
	    qu'il vit sous un titre en gras, ce que le fil n'a pas. */
	.carte-preview {
		font-size: var(--fs-xs);
		line-height: 1.25;
		color: var(--color-text-muted);
		position: relative;
	}
	.carte-preview :global(p) {
		margin: 0 0 0.12em;
	}

	@media (max-width: 767px) {
		.carte-apercu {
			padding: 0 0.75rem 0.7rem;
			gap: 0.6rem;
		}
	}
</style>
