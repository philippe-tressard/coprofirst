<!--
  LE pied de page de l'application : celui du squelette `(app)`, et son aperçu
  dans Admin › Site. Un seul rendu pour les deux, si bien que l'aperçu montre ce
  que le site affichera (08/10/2026).

  Une carte, sur le modèle de coprofirst.fr (maquette A, arbitrée le 15/10/2026) :
  la marque — logo et nom de la résidence, en gras — à gauche, les mentions en
  petit sous le nom, les liens à droite. Au téléphone, les liens passent sous la
  marque. Les éléments, leur place et ceux qui se masquent sont dans `$lib/piedDePage`.

  La version s'affiche courte (« v2.118.1 · RPi1 »). L'empreinte du build et sa
  date passent dans l'infobulle : elles servent toujours au diagnostic, par
  exemple pour voir un onglet PWA resté sur une version en cache. P3 lit la
  version dans le bundle, pas ici (`check-version-servie.mjs`).
-->
<script lang="ts">
	import pkg from '../../../package.json';
	import { env } from '$env/dynamic/public';
	import LogoResidence from '$lib/components/LogoResidence.svelte';
	import { configStore, siteNomStore } from '$lib/stores/pageConfig';
	import { lienSource, NOM_PLATEFORME } from '$lib/plateforme';
	import { dansLaPlace, elementsAffiches, mentionAnnee, type ReglagePied } from '$lib/piedDePage';

	/** Le réglage, déjà lu (`lireReglagePied`). */
	export let reglage: ReglagePied;
	/** Rendu dans l'aperçu de l'administration : sans la largeur de la page. */
	export let apercu = false;

	const empreinte = import.meta.env.VITE_GIT_HASH ?? 'dev';
	//  Le nœud se lit à l'EXÉCUTION (`PUBLIC_INSTANCE_ID`, docker-compose) : une
	//  image construite par la CI sert les deux nœuds (#1758).
	const serveur = env.PUBLIC_INSTANCE_ID || '';
	const version = `v${pkg.version}`;
	const build = [version, empreinte, import.meta.env.VITE_BUILD_DATE].filter(Boolean).join(' · ');
	const anneeCourante = new Date().getFullYear();

	$: siteUrl = $configStore['site_url'] ?? '';
	$: nom = [reglage.prefixeNom, $siteNomStore].filter(Boolean).join(' ');
	//  Sans identifiant de nœud (poste de développement), il n'y a rien à dire.
	$: affiches = elementsAffiches(reglage).filter((c) => c !== 'serveur' || serveur);
	$: mentions = dansLaPlace(affiches, 'mention');
	$: liens = dansLaPlace(affiches, 'lien');
</script>

<footer class="app-footer" class:container={!apercu} class:apercu>
	<div class="carte-pied">
		<div class="marque">
			<LogoResidence taille={32} />
			<div class="identite">
				{#if siteUrl}
					<a class="nom" href={siteUrl} target="_blank" rel="noopener noreferrer">{nom}</a>
				{:else}
					<span class="nom">{nom}</span>
				{/if}
				{#if mentions.length}
					<!--  Le séparateur est tracé par la feuille de style, entre deux
					      éléments : écrit dans le balisage, il héritait des blancs du
					      gabarit d'un seul côté. -->
					<p class="mentions">
						{#each mentions as code (code)}
							<span class="element"
								>{#if code === 'annee'}{mentionAnnee(
										reglage.anneeDebut,
										anneeCourante,
									)}{:else if code === 'texte'}{reglage.texte}{:else if code === 'version'}<span
										title={build}>{version}</span
									>{:else if code === 'serveur'}RPi{serveur}{/if}</span
							>
						{/each}
					</p>
				{/if}
			</div>
		</div>
		<nav class="liens" aria-label="Pied de page">
			{#each liens as code (code)}
				{#if code === 'source'}<a
						class="element"
						href={lienSource(empreinte)}
						target="_blank"
						rel="noopener noreferrer"
						title="Le code source de la version en service">{NOM_PLATEFORME} (code source)</a
					>{:else if code === 'mentions'}<a class="element" href="/mentions-legales"
						>Mentions légales</a
					>{:else if code === 'confidentialite'}<a
						class="element"
						href="/politique-de-confidentialite">Confidentialité</a
					>{/if}
			{/each}
		</nav>
	</div>
</footer>

<style>
	.app-footer {
		padding-top: 0.5rem;
		padding-bottom: 1.5rem;
	}
	.app-footer.apercu {
		padding: 0.5rem;
	}
	.carte-pied {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		justify-content: space-between;
		gap: 0.75rem 1.5rem;
		padding: 1rem 1.4rem;
		background: var(--color-surface);
		border: 1px solid var(--color-border);
		border-radius: calc(var(--radius) * 2);
	}
	.marque {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		min-width: 0;
		color: var(--color-primary);
	}
	.identite {
		min-width: 0;
	}
	.nom {
		display: block;
		font-family: var(--police-titres);
		font-weight: 700;
		font-size: var(--fs-lg);
		color: var(--color-primary);
		text-decoration: none;
	}
	.mentions {
		margin: 0.1rem 0 0;
		display: flex;
		flex-wrap: wrap;
		font-size: var(--fs-xs);
		color: var(--color-text-muted);
	}
	.mentions .element:not(:last-child)::after {
		/*  Un point de lecture, pas un mot : le texte de remplacement est vide.
		    Accroché à l'élément qui PRÉCÈDE, il reste en fin de ligne quand les
		    mentions passent à la ligne, au lieu d'en ouvrir une. */
		content: '·' / '';
		margin: 0 0.4em;
	}
	.liens {
		display: flex;
		flex-wrap: wrap;
		gap: 0.4rem 1.25rem;
		font-size: var(--fs-md);
	}
	.liens a {
		color: var(--color-text-muted);
		text-decoration: none;
		border-bottom: 1px solid var(--color-accent);
		padding-bottom: 1px;
		transition: color var(--duree-geste);
	}
	@media (hover: hover) and (pointer: fine) {
		.liens a:hover,
		a.nom:hover {
			color: var(--color-primary-dark);
		}
	}
</style>
