<!--
  LE pied de page de l'application : celui du squelette `(app)`, et son aperçu
  dans Admin › Présentation › Connexion et pied de page. Un seul rendu pour les deux, si bien que l'aperçu montre ce
  que le site affichera (08/10/2026).

  Une carte, sur le modèle de coprofirst.fr (maquette A, arbitrée le 15/10/2026) :
  la marque — logo et nom de la résidence, en gras — à gauche, les mentions en
  petit sous le nom, les liens à droite. Au téléphone, trois lignes centrées
  (arbitré le 17/10/2026, #2040) : logo et nom, les mentions, les liens — qui
  peuvent tenir sur deux rangées, chacune centrée. Les éléments, leur place,
  leur cible et ceux qui se masquent sont dans `$lib/piedDePage`.

  La version s'affiche courte (« v2.118.1 · RPi1 »). L'empreinte du build et sa
  date passent dans l'infobulle : elles servent toujours au diagnostic, par
  exemple pour voir un onglet PWA resté sur une version en cache. P3 lit la
  version dans le bundle, pas ici (`check-version-servie.mjs`).
-->
<script lang="ts">
	import pkg from '../../../package.json';
	import { PUBLIC_INSTANCE_ID } from '$app/env/public';
	import Icon from '$lib/components/Icon.svelte';
	import LogoResidence from '$lib/components/LogoResidence.svelte';
	import { configStore, siteNomStore } from '$lib/stores/pageConfig';
	import {
		dansLaPlace,
		ELEMENT_PIED,
		elementsAffiches,
		mentionAnnee,
		type ReglagePied,
	} from '$lib/piedDePage';

	/** Le réglage, déjà lu (`lireReglagePied`). */
	export let reglage: ReglagePied;
	/** Rendu dans l'aperçu de l'administration : sans la largeur de la page. */
	export let apercu = false;

	const empreinte = import.meta.env.VITE_GIT_HASH ?? 'dev';
	//  Le nœud se lit à l'EXÉCUTION (`PUBLIC_INSTANCE_ID`, docker-compose) : une
	//  image construite par la CI sert les deux nœuds (#1758).
	const serveur = PUBLIC_INSTANCE_ID || '';
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
		<div class="marque-pied">
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
			<!--  Un lien qui sort du site s'ouvre ailleurs et le montre : l'icône
			      est décorative, l'infobulle dit où il mène (#2040). -->
			{#each liens as code (code)}
				{@const e = ELEMENT_PIED.get(code)}
				{#if e?.lien?.externe}<a
						class="element"
						href={e.lien.cible(empreinte)}
						target="_blank"
						rel="noopener noreferrer"
						title={e.lien.infobulle}
						>{e.libelle}<span class="sortie"><Icon name="external-link" size={14} /></span></a
					>{:else if e?.lien}<a class="element" href={e.lien.cible(empreinte)}>{e.libelle}</a>{/if}
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
	.marque-pied {
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
	.sortie {
		display: inline-flex;
		margin-left: 0.25em;
		vertical-align: -0.1em;
	}
	@media (hover: hover) and (pointer: fine) {
		.liens a:hover,
		a.nom:hover {
			color: var(--color-primary-dark);
		}
	}
	/*  Téléphone : trois lignes centrées. `.identite` s'efface de la mise en
	    page (`display: contents`) — le nom rejoint le logo sur la première
	    ligne, les mentions prennent la deuxième à elles seules. */
	@media (max-width: 767px) {
		.carte-pied {
			flex-direction: column;
			text-align: center;
		}
		.marque-pied {
			flex-wrap: wrap;
			justify-content: center;
			row-gap: 0.25rem;
		}
		.identite {
			display: contents;
		}
		.mentions {
			flex-basis: 100%;
			justify-content: center;
			margin: 0;
		}
		.liens {
			justify-content: center;
		}
	}
</style>
