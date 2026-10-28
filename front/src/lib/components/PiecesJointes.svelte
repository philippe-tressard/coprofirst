<!--
  Affichage en lecture seule d'une liste de pièces jointes : vignettes pour les
  images, liens nommés pour les documents.

  Ce bloc était réécrit à l'identique dans quatre pages (fiche ticket, actualité,
  espace CS, affaires) — avec à chaque fois sa propre expression régulière pour
  décider ce qui est une image, et son propre `split('/').pop()` pour le nom
  affiché. La règle vit désormais dans `#lib/fichiers.ts`, le rendu ici.

  Props :
    - urls   : liste d'URLs internes (/uploads/…)
    - size   : côté des vignettes en px (format « vignette » uniquement)
    - compact: réduit la typographie des liens (fils d'évolutions)
    - format : « vignette » (aperçu) ou « grand » (contenu déplié)

  Deux formats, parce que la vignette ne répond pas à la même question. Dans une
  liste ou un fil d'évolutions, elle signale « il y a une photo » sans casser le
  rythme de lecture. Une fois le contenu déplié, l'utilisateur a demandé à voir :
  lui laisser un timbre-poste de 72 px l'oblige à un clic de plus pour ce qu'il
  vient justement de demander.

  Le format « grand » ne coûte aucun octet supplémentaire : il n'existe pas de
  miniature côté serveur, les photos sont réduites à 1600 px au téléversement, et
  la vignette téléchargeait déjà ce fichier-là pour l'afficher en 72 px.

  `object-fit: contain` en grand format, et non `cover` : une photo portrait
  affichée dans un cadre carré perd ses bords haut et bas. Sur un dégât des eaux,
  c'est précisément ce qu'on cherchait à montrer.
-->
<script lang="ts">
	import { onDestroy } from 'svelte';
	import Lightbox from './Lightbox.svelte';
	import Vignette from './Vignette.svelte';
	import { nomFichier, separerFichiers } from '#lib/fichiers.ts';

	export let urls: string[] | null | undefined = [];
	export let size = 72;
	export let compact = false;
	export let format: 'vignette' | 'grand' = 'vignette';

	$: ({ photos, documents } = separerFichiers(urls));

	//  null = visionneuse fermée. Le clic n'ouvre plus un onglet : il ouvrait le
	//  fichier brut hors de la PWA, et le retour ramenait sur un article refermé.
	let photoOuverte: number | null = null;

	//  ── Galerie horizontale (#334) ────────────────────────────────────────────
	//  Le défilement est NATIF : `scroll-snap` apporte l'inertie, le rebond et le
	//  geste tactile du système, mieux que ne le ferait une bibliothèque de
	//  carrousel — et sans dépendance à surveiller. Il ne reste ici qu'à savoir
	//  QUELLE photo est en vue, pour que le compteur ne mente pas.
	let piste: HTMLDivElement | null = null;
	let courante = 0;

	function glisser(sens: number) {
		if (!piste) return;
		//  On se déplace de la largeur visible, pas d'une largeur de photo : les
		//  photos n'ont pas toutes la même (une portrait est plus étroite qu'une
		//  paysage), et `scroll-snap` recale de toute façon sur la plus proche.
		piste.scrollBy({ left: sens * piste.clientWidth * 0.8, behavior: 'smooth' });
	}

	//  `IntersectionObserver` plutôt qu'un écouteur de défilement : il ne se
	//  déclenche qu'au changement de photo visible, là où `on:scroll` recalculerait
	//  à chaque pixel parcouru.
	function observerPiste(noeud: HTMLDivElement) {
		if (typeof IntersectionObserver === 'undefined') return; // rendu serveur
		//  ⚠️ « la dernière entrée visible gagne » est FAUX : plusieurs photos sont
		//  visibles à la fois — c'est même le but, la lisière suivante est ce qui
		//  signale qu'on peut défiler. Le compteur affichait « 2 / 5 » à l'ouverture,
		//  sur la première photo.
		//
		//  Ma première correction retenait la photo la plus proche du CENTRE. Elle
		//  affichait encore « 2 / 5 » au repos, et à juste titre : la première photo
		//  est étroite et calée à gauche, donc la deuxième EST la plus centrée. La
		//  règle était mauvaise, pas la mesure — deux passages à l'écran pour le voir.
		//
		//  La bonne règle suit `scroll-snap-align: start` : la photo courante est
		//  celle dont le bord gauche est au bord gauche de la bande, ce qui est
		//  aussi la façon dont on lit un ruban d'images.
		const visibles = new Set<Element>();
		const recalculer = () => {
			const bord = noeud.getBoundingClientRect().left;
			let meilleure = -1;
			let ecartMin = Infinity;
			for (const cible of visibles) {
				const ecart = Math.abs(cible.getBoundingClientRect().left - bord);
				if (ecart < ecartMin) {
					ecartMin = ecart;
					meilleure = [...noeud.children].indexOf(cible);
				}
			}
			if (meilleure >= 0) courante = meilleure;
		};
		const vues = new IntersectionObserver(
			(entrees) => {
				for (const e of entrees) {
					e.isIntersecting ? visibles.add(e.target) : visibles.delete(e.target);
				}
				recalculer();
			},
			{ root: noeud, threshold: 0.6 },
		);
		for (const enfant of noeud.children) vues.observe(enfant);
		return vues;
	}

	let observateur: IntersectionObserver | undefined;
	$: if (piste && photos.length > 1) {
		observateur?.disconnect();
		observateur = observerPiste(piste);
	}
	onDestroy(() => observateur?.disconnect());
</script>

{#if photos.length || documents.length}
	<div class="pj">
		{#if photos.length}
			{#if format === 'grand' && photos.length > 1}
				<!--  Galerie horizontale (#334). Une seule photo garde le rendu simple
				      ci-dessous : lui ajouter des commandes de galerie serait du bruit. -->
				<div class="pj-galerie-bloc">
					<div
						class="pj-galerie"
						bind:this={piste}
						role="group"
						aria-label="Galerie de {photos.length} photos"
					>
						{#each photos as url, i (`${i}|${url}`)}
							<button
								type="button"
								class="pj-slide"
								aria-label="Agrandir {nomFichier(url)} ({i + 1} sur {photos.length})"
								on:click|stopPropagation={() => (photoOuverte = i)}
							>
								<img src={url} alt={nomFichier(url)} loading="lazy" decoding="async" />
							</button>
						{/each}
					</div>

					<!--  Flèches réservées au pointeur fin : au doigt, le défilement natif
					      fait le travail, et deux cibles de plus mangeraient la photo. -->
					<button
						type="button"
						class="pj-fleche pj-fleche-prec"
						aria-hidden="true"
						tabindex="-1"
						on:click|stopPropagation={() => glisser(-1)}>&#x2039;</button
					>
					<button
						type="button"
						class="pj-fleche pj-fleche-suiv"
						aria-hidden="true"
						tabindex="-1"
						on:click|stopPropagation={() => glisser(1)}>&#x203A;</button
					>

					<div class="pj-jauge">
						<!--  Le compteur suit le DÉFILEMENT, pas les seuls boutons : piloté par
						      les clics, il mentirait dès le premier glissement du doigt. -->
						<span class="pj-compteur" aria-live="polite">{courante + 1} / {photos.length}</span>
						{#if photos.length <= 8}
							<span class="pj-points" aria-hidden="true">
								{#each photos as _, i (`${i}|${_}`)}
									<span class="pj-point" class:pj-point-actif={i === courante}></span>
								{/each}
							</span>
						{/if}
					</div>
				</div>
			{:else if format === 'grand'}
				<div class="pj-grandes">
					{#each photos as url, i (`${i}|${url}`)}
						<button
							type="button"
							class="pj-grande"
							aria-label="Agrandir {nomFichier(url)}"
							on:click|stopPropagation={() => (photoOuverte = i)}
						>
							<img src={url} alt={nomFichier(url)} loading="lazy" />
						</button>
					{/each}
				</div>
			{:else}
				<div class="pj-photos">
					{#each photos as url, i (`${i}|${url}`)}
						<button
							type="button"
							class="pj-vignette"
							aria-label="Agrandir {nomFichier(url)}"
							on:click|stopPropagation={() => (photoOuverte = i)}
						>
							<Vignette src={url} alt="" {size} title={nomFichier(url)} />
						</button>
					{/each}
				</div>
			{/if}
		{/if}
		{#if documents.length}
			<div class="pj-docs">
				{#each documents as url, di (`${di}|${url}`)}
					<a
						class="pj-doc"
						class:pj-doc-compact={compact}
						href={url}
						target="_blank"
						rel="noopener"
					>
						<span aria-hidden="true">&#x1F4C4;</span>
						<span class="pj-doc-nom">{nomFichier(url)}</span>
					</a>
				{/each}
			</div>
		{/if}
	</div>
{/if}

{#if photoOuverte !== null}
	<Lightbox {photos} index={photoOuverte} on:fermer={() => (photoOuverte = null)} />
{/if}

<style>
	.pj {
		display: flex;
		flex-direction: column;
		gap: 0.4rem;
	}
	.pj-photos {
		display: flex;
		gap: 0.5rem;
		flex-wrap: wrap;
	}

	/*  Boutons et non liens : l'action reste dans la page. Le style par défaut du
	    bouton est neutralisé pour que seule la photo se voie. */
	.pj-vignette,
	.pj-grande {
		padding: 0;
		border: none;
		background: none;
		cursor: zoom-in;
		display: block;
		line-height: 0;
	}
	/*  ── Galerie horizontale (#334) ──────────────────────────────────────────
	    LA décision de tout le lot : la bande impose sa HAUTEUR, chaque photo prend
	    la LARGEUR que son rapport lui donne. Avant, le cadre prenait toute la
	    largeur du contenu et une photo portrait — le cas courant sur un chantier —
	    flottait au milieu d'un vide gris occupant la moitié de la surface. En
	    fixant la hauteur, les bandes vides disparaissent d'elles-mêmes et le
	    mélange portrait/paysage cesse d'être un accident. */
	.pj-galerie-bloc {
		position: relative;
	}
	.pj-galerie {
		--pj-h: clamp(220px, 42vh, 300px);
		display: flex;
		gap: 0.5rem;
		overflow-x: auto;
		scroll-snap-type: x mandatory;
		scroll-behavior: smooth;
		scrollbar-width: none;
		-webkit-overflow-scrolling: touch;
	}
	.pj-galerie::-webkit-scrollbar {
		display: none;
	}
	@media (min-width: 768px) {
		.pj-galerie {
			--pj-h: 360px;
		}
	}

	.pj-slide {
		flex: 0 0 auto;
		scroll-snap-align: start;
		height: var(--pj-h);
		/*  Plancher de largeur, en PIXELS et volontairement bas : il ne sert qu'à
		    réserver une empreinte avant que l'image ne soit chargée — sa largeur
		    réelle n'est connue qu'à ce moment-là.
		    ⚠️ Une première version mettait `45%` : une photo portrait, plus étroite
		    que ce plancher, se retrouvait alors calée à gauche d'une case trop
		    large, avec une bande vide à sa droite — le défaut même que ce lot
		    supprime, réintroduit à l'intérieur de la case. Vu à l'écran, pas dans
		    le code. Une portrait 9:16 mesure ici 124 à 202 px selon la hauteur :
		    120 px passe sous toutes. */
		min-width: 120px;
		max-width: 100%;
		padding: 0;
		border: 1px solid var(--color-border);
		border-radius: 10px;
		overflow: hidden;
		background: var(--color-bg);
		cursor: zoom-in;
	}
	.pj-slide img {
		height: 100%;
		width: auto;
		max-width: 100%;
		object-fit: contain;
		display: block;
	}
	.pj-slide:focus-visible {
		outline: 2px solid var(--color-primary);
		outline-offset: 2px;
	}

	/*  Flèches réservées au pointeur FIN. Au doigt, le défilement natif fait le
	    travail et deux cibles de plus mangeraient la photo. */
	.pj-fleche {
		display: none;
	}
	@media (hover: hover) and (pointer: fine) {
		.pj-fleche {
			display: grid;
			place-items: center;
			position: absolute;
			top: calc(50% - 22px);
			width: 44px; /* cible tactile minimale, socle 11 §10 */
			height: 44px;
			border: none;
			border-radius: 50%;
			background: rgba(0, 0, 0, 0.5);
			color: var(--color-sur-voile);
			font-size: var(--fs-chiffre);
			line-height: 1;
			cursor: pointer;
			opacity: 0;
			transition: opacity var(--duree-geste);
		}
		.pj-galerie-bloc:hover .pj-fleche,
		.pj-fleche:focus-visible {
			opacity: 1;
		}
		.pj-fleche-prec {
			left: 0.35rem;
		}
		.pj-fleche-suiv {
			right: 0.35rem;
		}
	}

	.pj-jauge {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		margin-top: 0.35rem;
	}
	.pj-compteur {
		font-size: var(--fs-xs);
		color: var(--color-text-muted);
	}
	.pj-points {
		display: flex;
		gap: 0.25rem;
	}
	.pj-point {
		width: 6px;
		height: 6px;
		border-radius: 50%;
		background: var(--color-border);
		transition: background var(--duree-geste);
	}
	.pj-point-actif {
		background: var(--color-primary);
	}

	/*  Non négociable : `smooth` et les fondus sont des déclencheurs de malaise
	    pour les personnes concernées, pas un confort. */
	@media (prefers-reduced-motion: reduce) {
		.pj-galerie {
			scroll-behavior: auto;
		}
		.pj-fleche,
		.pj-point {
			transition: none;
		}
	}

	.pj-grandes {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
	}
	.pj-grande {
		width: 100%;
	}
	.pj-grande img {
		width: 100%;
		/*  Plafond de hauteur : une photo portrait 1200×1600 affichée pleine
		    largeur occuperait deux écrans sur mobile et repousserait commentaires
		    et actions hors de vue. `contain` préserve les proportions. */
		max-height: 60vh;
		object-fit: contain;
		border-radius: var(--radius);
		border: 1px solid var(--color-border);
		background: var(--color-neutre-fond);
	}
	.pj-docs {
		display: flex;
		gap: 0.35rem;
		flex-wrap: wrap;
	}
	.pj-doc {
		display: inline-flex;
		align-items: center;
		gap: 0.3rem;
		max-width: 100%;
		padding: 0.2rem 0.5rem;
		border: 1px solid var(--color-border);
		border-radius: var(--radius);
		background: var(--color-neutre-fond);
		color: var(--color-primary);
		font-size: var(--fs-md);
		text-decoration: none;
	}
	.pj-doc-compact {
		font-size: var(--fs-xs);
	}
	@media (hover: hover) and (pointer: fine) {
		.pj-doc:hover {
			border-color: var(--color-primary);
		}
	}
	/* Un nom long ne doit pas pousser la carte hors de l'écran sur mobile. */
	.pj-doc-nom {
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		max-width: 220px;
	}
	@media (max-width: 480px) {
		.pj-doc-nom {
			max-width: 62vw;
		}
	}
</style>
