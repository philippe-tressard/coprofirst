<!--
  BarreOnglets.svelte — LA rangée d'onglets d'une page, écrite une fois.

  ## Pourquoi (05/09/2026)

  Un onglet n'avait pas d'adresse. `/sondages` ouvrait toujours les sondages, et
  « Petites annonces » ne s'atteignait que par un clic : impossible d'ENVOYER un
  lien vers une rubrique. Signalé par l'utilisateur, qui voulait partager une
  annonce et n'avait à copier que l'adresse de la page voisine.

  Le remède n'est pas d'écrire l'onglet dans l'URL après coup — c'est que
  **l'onglet SOIT une adresse**. Chaque onglet est donc un `<a href>` vers sa
  route déclarée (`$lib/pages.ts`), et la page lit l'onglet actif dans le chemin.
  On y gagne trois choses qu'un `<button>` ne donnait pas : le lien se copie, le
  bouton Précédent revient à l'onglet précédent, et le clic milieu ouvre la
  rubrique dans un nouvel onglet du navigateur.

  ## Ce que ce composant supprime

  Les cinq pages à onglets écrivaient leur rangée à la main, et elles avaient déjà
  divergé : `<button>` nu ici, `<Onglet>` là, libellés pris dans la configuration
  sur quatre pages et **codés en dur** sur `/prestataires` — dont le troisième
  onglet n'était même pas déclaré dans la table, donc ni renommable ni
  descriptible depuis l'administration.

  ⚠️ Le libellé se replie sur celui de la TABLE, jamais sur une chaîne écrite ici :
  une configuration enregistrée avant l'ajout d'un onglet ne porte pas sa clé
  (`getPageConfig` remplace le dictionnaire entier), et l'onglet neuf s'afficherait
  sans nom.
-->
<script lang="ts">
	import Onglet from '$lib/components/Onglet.svelte';
	import { configStore, getPageConfig, defautsDePage } from '$lib/stores/pageConfig';
	import { PAGES } from '$lib/pages';
	import { safeHtml } from '$lib/sanitize';
	import { stripHtml } from '$lib/utils';
	import { browser } from '$app/environment';
	import { goto } from '$app/navigation';
	import { isProprioOuCS, isLocataire, isOperateur, authResolue } from '$lib/stores/auth';

	/** L'identifiant de configuration de la page — celui de `PAGES`. */
	export let pageId: string;
	/** L'onglet actif, tel que la page l'a résolu depuis le chemin. */
	export let actif: string;
	/**  Les onglets que l'utilisateur courant ne doit pas voir. C'est la PAGE qui
	 *   sait à quels droits ils répondent (le Kanban et les Archives du calendrier
	 *   sont fermés aux locataires) — ce composant ne connaît que l'affichage. */
	export let masques: readonly string[] = [];
	/** Pastilles de compte, par identifiant d'onglet. */
	export let comptes: Record<string, number> = {};
	/**  Les onglets grisés : ceux d'un service coupé (Admin › Services). Ils
	 *   restent visibles et ouvrables — c'est la page qui sait lesquels. */
	export let eteints: readonly string[] = [];

	$: defauts = defautsDePage(pageId);
	$: _pc = getPageConfig($configStore, pageId, defauts);
	//  Deux raisons de ne pas voir un onglet, et elles ne se confondent pas :
	//    • `reserve` — une exigence de RÔLE, déclarée avec l'onglet (`pages.ts`) ;
	//    • `masques` — un masquage qui dépend des DONNÉES, que seule la page sait
	//      (« Gestion locative » n'apparaît que si le lot a des baux).
	$: visible = (o: { reserve?: string }) =>
		!o.reserve ||
		(o.reserve === 'proprioOuCS' && $isProprioOuCS) ||
		(o.reserve === 'nonLocataire' && !$isLocataire) ||
		(o.reserve === 'operateur' && $isOperateur);
	$: onglets = (PAGES.find((p) => p.id === pageId)?.onglets ?? []).filter(
		(o) => !masques.includes(o.id) && visible(o),
	);
	//  Les GROUPES de la rangée (`groupe` dans la table) : une rangée nommée par
	//  groupe, dans l'ordre de la table. Une page sans groupe n'en a qu'un, sans
	//  nom — c'est le cas de toutes, sauf l'administration (01/10/2026), qui
	//  écrivait ses deux rangées à la main.
	$: groupes = onglets.reduce<{ nom: string; onglets: typeof onglets }[]>((acc, o) => {
		const nom = o.groupe ?? '';
		const dernier = acc[acc.length - 1];
		if (dernier && dernier.nom === nom) dernier.onglets.push(o);
		else acc.push({ nom, onglets: [o] });
		return acc;
	}, []);
	$: descriptifOnglet =
		_pc.onglets?.[actif]?.descriptif ?? defauts.onglets?.[actif]?.descriptif ?? '';
	//  Une phrase ne se lit pas deux fois (#1369) : quand l'onglet dit mot pour mot
	//  ce que la page dit déjà au-dessus (`EntetePage`), sa ligne se tait. C'est le
	//  cas de l'onglet ouvert par défaut, qui porte souvent le nom de l'écran —
	//  « Fiche » de Résidence l'affichait sous la même phrase. Comparé SANS le
	//  balisage : les deux textes sont administrables, et l'éditeur riche enveloppe
	//  l'un d'un <p> quand l'autre, resté celui de la table, n'en a pas.
	$: descriptif =
		texteSeul(descriptifOnglet) === texteSeul(_pc.descriptif ?? '') ? '' : descriptifOnglet;
	const texteSeul = (html: string) => stripHtml(html).replace(/\s+/g, ' ');

	//  🔴 Masquer ne suffit pas : un onglet EST une adresse, et un favori ou un
	//  lien reçu y mène quand même. Le masquage répond à ce qui s'AFFICHE, cette
	//  redirection à ce qui s'ATTEINT — les deux vont ensemble, et c'est pour les
	//  avoir séparées que `/residence/carnet` restait atteignable (#1039).
	//
	//  `browser` : en rendu serveur, `goto` n'a pas de sens et l'onglet actif vient
	//  déjà du chemin. `replaceState` : l'adresse refusée ne doit pas rester dans
	//  l'historique, sinon le bouton Précédent y ramène en boucle.
	//  🔴 `$authResolue` d'abord, et ce n'est pas une précaution de style : les
	//  stores de rôle valent **faux** tant que `authApi.me()` n'a pas répondu. Sans
	//  cette garde, un copropriétaire qui ouvre `/residence/carnet` par un favori
	//  est renvoyé sur la fiche — l'onglet lui est refusé sur « on ne sait pas
	//  encore ». C'est le défaut corrigé sur `/admin` le 12/08/2026, que ce
	//  composant venait de réintroduire (#1083).
	$: if (browser && $authResolue && onglets.length > 0 && !onglets.some((o) => o.id === actif)) {
		goto(onglets[0].route, { replaceState: true });
	}
</script>

{#each groupes as g (g.nom)}
	<div class="tabs-group">
		{#if g.nom}<div class="tabs-group-label">{g.nom}</div>{/if}
		<div class="tabs" role="tablist" aria-label={g.nom || undefined}>
			{#each g.onglets as o (o.id)}
				<Onglet
					href={o.route}
					actif={actif === o.id}
					compte={comptes[o.id] ?? null}
					eteint={eteints.includes(o.id)}
				>
					{_pc.onglets?.[o.id]?.label ?? defauts.onglets?.[o.id]?.label ?? o.label}
				</Onglet>
			{/each}
		</div>
	</div>
{/each}
{#if descriptif}
	<p class="tab-descriptif">{@html safeHtml(descriptif)}</p>
{/if}

<style>
	/*  `.tabs` et `.tab-btn` vivent dans la feuille commune : la rangée est un
	    conteneur d'écran, partagé avec l'administration qui garde ses boutons.
	    Ne sont ici que les écarts.

	    ⚠️ La marge basse N'Y EST PAS : la charte la porte déjà, à la même valeur.
	    Les cinq pages l'écrivaient pourtant en style EN LIGNE — cinq fois la
	    valeur dont elles héritaient. C'est `lint:charte` qui l'a dit, en refusant
	    la règle que j'avais reprise d'elles. */
	.tabs {
		padding-bottom: 0.1rem;
		/*  Les onglets DÉFILENT plutôt que de se replier — même parti que les tags
		    d'`EnteteCarte`. C'était l'écart de `/prestataires`, seule page à trois
		    onglets longs ; il n'a plus de raison d'être propre à un écran. */
		overflow-x: auto;
		/*  🔴 `overflow-y: hidden` N'EST PAS DÉCORATIF (14/09/2026, signalé à
		    l'écran : « une espèce de double flèche en fin de ligne de menus »).
		
		    En CSS, dès qu'un axe cesse d'être `visible`, l'autre bascule de
		    `visible` à `auto` — c'est la spécification, pas un défaut de
		    navigateur. Poser `overflow-x: auto` rendait donc l'axe VERTICAL
		    défilable lui aussi, et il suffisait que la rangée dépasse d'un pixel
		    — un liseré d'onglet actif, une icône un peu haute — pour qu'une
		    barre de défilement verticale apparaisse au bout. Ses deux petites
		    flèches ressemblaient à une commande ; elles ne commandaient rien.
		
		    ⚠️ Les onglets ne défilent QUE latéralement : une rangée d'onglets
		    n'a pas de hauteur à parcourir. Masquer l'axe vertical ne cache donc
		    rien — il n'y a rien dessous. */
		overflow-y: hidden;
		scrollbar-width: thin;
	}

	/*  `:global()` IMBRIQUÉ, donc borné à cette rangée : `.tab-btn` est rendu par
	    `Onglet.svelte`, et le style d'un composant n'atteint pas le balisage d'un
	    enfant (leçon de `Pastille.svelte`, v2.67.11). Ce qui fuirait, c'est un
	    `:global()` de PAGE — cf. #672. */
	/*  L'intitulé d'un groupe d'onglets — repris tel quel de l'administration,
	    qui le portait seule (01/10/2026). */
	.tabs-group + .tabs-group {
		margin-top: 0.5rem;
	}
	.tabs-group-label {
		font-size: var(--fs-2xs);
		font-weight: 700;
		text-transform: uppercase;
		letter-spacing: 0.06em;
		color: var(--color-text-muted);
		padding: 0 0.25rem 0.3rem;
	}
	.tabs :global(.tab-btn) {
		white-space: nowrap;
	}
</style>
