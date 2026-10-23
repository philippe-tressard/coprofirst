<!--
  BoutonLien.svelte — copier l'adresse d'UNE publication, pour l'envoyer.

  ## Pourquoi (05/09/2026)

  Demandé par l'utilisateur, en même temps que les URL dédiées des onglets :
  *« toutes les publications du site : une nouvelle icône pour récupérer le lien
  de la publication, à côté de l'icône Modifier »*.

  Une publication a toujours eu une adresse — `/annonces#annonce-42` — mais elle
  n'était écrite nulle part : seuls l'API la fabriquait, pour ses e-mails et son
  fil. Un résident qui voulait montrer une annonce à un voisin ne pouvait envoyer
  que l'adresse de la page, à charge pour l'autre de chercher.

  ## Ce que ce composant N'EST PAS — et la nuance de #1357

  Il ne s'ouvre sur rien, ne propose pas WhatsApp et ne demande aucune
  permission : le clic COPIE une chaîne, comme avant. La diffusion vers
  l'extérieur reste une **décision** de l'auteur (section 9 du cadre #430).

  🔴 Une nuance depuis le 26/09/2026 (#1357, option E des maquettes) : le
  message « Lien copié » propose ensuite « L'envoyer par courriel »
  (`PartageCourriel`) — d'abord pour une affaire, puis pour TOUT objet qui porte
  un 🔗 (*« dans tous les cas, si celui-ci n'a pas les droits, il ne verra
  rien »*). Ce que le lien désigne se DÉDUIT du lien (`cibleDuLien`). Le copier
  reste à un clic ; l'envoi est un second geste, choisi. Cette phrase disait
  « ni WhatsApp ni e-mail » : elle est réécrite dans le lot qui change la décision.

  ## Le droit

  Aucun. Tout ce qui est affiché à quelqu'un peut lui être copié : l'adresse ne
  donne pas plus d'accès que l'écran d'où elle vient, puisque la page vérifie les
  droits du visiteur, pas ceux de l'expéditeur. C'est ce que demandait
  l'utilisateur — *« accessible à tous ceux qui ont accès »*.

  ⚠️ L'icône est un ÉMOJI, comme ✏️ et 🗑️ dans la même rangée. Le catalogue
  `$lib/icones-svg.json` aurait donné un tracé plus net, mais mélanger un SVG et
  deux émojis sur une même ligne se voit tout de suite : ils n'ont ni la même
  hauteur d'œil ni la même graisse. Le jour où la rangée passera au catalogue,
  elle y passera en entier.
-->
<script lang="ts">
	import { tick } from 'svelte';
	import { page } from '$app/stores';
	import { toast } from '$lib/components/Toast.svelte';
	import PartageCourriel from '$lib/components/PartageCourriel.svelte';
	import IconeAction from '$lib/components/IconeAction.svelte';
	import { cibleDuLien } from '$lib/partage';
	import { portail } from '$lib/portail';

	/**  L'ancre de l'élément, sans le `#` — `annonce-42`. C'est l'`id` que la carte
	 *   pose déjà sur son conteneur pour les liens profonds : les deux ne peuvent
	 *   pas diverger, ils désignent le même élément. */
	export let ancre: string | null = null;
	/**  Le chemin de la publication quand elle a une page à elle (`/tickets/12`).
	 *   Par défaut, celui de la page courante — une carte de liste vit sur la route
	 *   de sa rubrique, qui est justement l'adresse qu'on veut envoyer. */
	export let chemin: string | null = null;
	/** Ce dont on copie le lien, pour l'annonce vocale : « Copier le lien de … ». */
	export let quoi = 'la publication';
	/**  Ce que le lien désigne, s'il peut aussi partir par courriel (#1357) :
	 *   déduit du lien lui-même — aucun appelant n'a à le dire. */
	$: cible = cibleDuLien(chemin, ancre);
	let bouton: HTMLButtonElement;
	let zone: HTMLDivElement;

	//  🔴 DEUX RÉGIMES (arbitré le 26/09/2026, `emil-design-eng`) : un message
	//  simple va au coin fixe (`Toast`) — il a une place prévisible ; la SUITE
	//  d'un geste sur cet élément naît de lui. « Lien copié · L'envoyer par
	//  courriel » s'affichait en bas à droite, loin de l'icône : la main
	//  traversait l'écran pour atteindre un champ lié au 🔗.
	/** La position de la bulle, sous le 🔗 (au-dessus s'il le faut) — `null` : fermée. */
	let bulle: { haut: number; droite: number; dessus?: boolean } | null = null;
	let minuterie: ReturnType<typeof setTimeout> | undefined;

	async function ouvrirBulle() {
		const r = bouton.getBoundingClientRect();
		bulle = { haut: r.bottom + 6, droite: Math.max(8, window.innerWidth - r.right) };
		relancer();
		//  🔴 Elle se RETOURNE au-dessus du 🔗 quand elle sortirait par le bas : fixée
		//  à l'écran et fermée au défilement, elle était alors hors d'atteinte. Une
		//  carte au bas d'un téléphone suffisait (trouvé avec #2165, le texte
		//  grandissant). 🔒 `e2e/partage-courriel-champ.spec.ts`, profil mobile.
		await tick();
		const h = zone?.getBoundingClientRect().height ?? 0;
		if (bulle && bulle.haut + h > window.innerHeight - 8)
			bulle = { ...bulle, haut: Math.max(8, r.top - 6 - h), dessus: true };
	}
	function fermer() {
		clearTimeout(minuterie);
		bulle = null;
	}
	/** Elle part seule si l'on ne s'en sert pas — et reste tant qu'on s'en sert. */
	function relancer() {
		clearTimeout(minuterie);
		minuterie = setTimeout(fermer, 6000);
	}
	function suspendre() {
		clearTimeout(minuterie);
	}
	/*  🔴 `composedPath()`, pas `e.target.contains` (03/10/2026) : « L'envoyer par
	    courriel » est REMPLACÉ par le champ au clic, donc le bouton a quitté le DOM
	    quand l'événement atteint la fenêtre — `zone.contains(cible)` rendait faux, et
	    la bulle se fermait avant que le champ ne se voie. Le chemin est fixé au
	    départ de l'événement. 🔒 `e2e/partage-courriel-champ.spec.ts`. */
	function clicDehors(e: MouseEvent) {
		const chemin = e.composedPath();
		if (bulle && !chemin.includes(zone) && !chemin.includes(bouton)) fermer();
	}

	/** « Lien copié » — et, pour ce qui se transmet, la proposition de l'envoyer. */
	function annoncerCopie(copie: boolean) {
		if (!copie) return toast('error', 'Copie impossible');
		if (!cible) return toast('success', 'Lien copié');
		ouvrirBulle();
	}

	$: base = chemin ?? $page.url.pathname;
	$: lien = ancre ? `${base}#${ancre}` : base;

	async function copier() {
		//  Absolue : un lien relatif collé dans un SMS ou un e-mail ne mène nulle part.
		const url = new URL(lien, window.location.origin).href;
		try {
			await navigator.clipboard.writeText(url);
			annoncerCopie(true);
		} catch {
			//  Le presse-papiers est refusé hors contexte sécurisé et par certains
			//  navigateurs embarqués (celui d'une application de messagerie, par
			//  exemple — exactement là où l'on veut coller un lien). Le repli n'est pas
			//  décoratif : sans lui, le geste échoue en silence là où il sert le plus.
			const zone = document.createElement('textarea');
			zone.value = url;
			zone.setAttribute('readonly', '');
			zone.style.position = 'fixed';
			zone.style.opacity = '0';
			document.body.appendChild(zone);
			zone.select();
			const copie = document.execCommand('copy');
			document.body.removeChild(zone);
			annoncerCopie(copie);
		}
	}
</script>

<svelte:window on:click={clicDehors} on:scroll={fermer} on:resize={fermer} />

<button
	bind:this={bouton}
	class="btn-icon"
	type="button"
	title="Copier le lien"
	aria-label="Copier le lien de {quoi}"
	aria-expanded={bulle !== null}
	on:click|stopPropagation={copier}><IconeAction icone="link" /></button
>
{#if bulle && cible}
	<div
		bind:this={zone}
		use:portail
		class="bulle-lien"
		role="dialog"
		tabindex="-1"
		aria-label="Lien copié"
		class:bulle-dessus={bulle.dessus}
		style:top="{bulle.haut}px"
		style:right="{bulle.droite}px"
		on:pointerenter={suspendre}
		on:pointerleave={relancer}
		on:focusin={suspendre}
	>
		<p class="copie">✓ Lien copié</p>
		<PartageCourriel {cible} retour={bouton} on:fermer={fermer} />
	</div>
{/if}

<style>
	/*  Elle naît du 🔗 : origine en haut à droite, sous l'icône. 180 ms, courbe
	    « ease-out » du site ; de 96 % à 100 %, jamais de zéro (`emil-design-eng`). */
	.bulle-lien {
		position: fixed;
		z-index: 60;
		width: min(320px, calc(100vw - 16px));
		padding: 0.6rem 0.75rem;
		background: var(--color-surface);
		border: 1px solid var(--color-border);
		border-left: 4px solid var(--color-success);
		border-radius: var(--radius);
		box-shadow: var(--shadow);
		font-size: var(--fs-base);
		transform-origin: 100% 0;
		animation: bulle-entree var(--duree-apparition) var(--ease-out);
	}
	/*  Retournée au-dessus du 🔗, elle naît de son bord bas. */
	.bulle-lien.bulle-dessus {
		transform-origin: 100% 100%;
	}
	.copie {
		margin: 0;
		font-weight: 600;
		color: var(--color-success);
	}
	@keyframes bulle-entree {
		from {
			opacity: 0;
			transform: scale(0.96) translateY(-4px);
		}
	}
	@media (prefers-reduced-motion: reduce) {
		.bulle-lien {
			animation: none;
		}
	}
</style>
