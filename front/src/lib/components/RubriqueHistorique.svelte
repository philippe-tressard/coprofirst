<!--
  RubriqueHistorique.svelte — LE FIL, écrit une fois.

  ## Vocabulaire (cadre #430, tranché le 17/08/2026)

  **Historique** = le fil. **Évolution** = une entrée du fil. « Commentaire » est
  abandonné : le mot est trop étroit, l'entrée pouvant porter un changement
  d'état, des pièces jointes et une diffusion. C'est déjà le vocabulaire du code
  (`TicketEvolution`, `EvolForm`), et l'adopter *supprime* un troisième registre.

  ⚠️ Le cadre parle d'évolutions ; **l'écran parle de gestes** — « Commenter »,
  « Changer l'état », « Modifier ». « Ajouter une évolution » ne veut rien dire
  pour un résident, et ce composant n'écrit donc ce mot nulle part.

  ## Pourquoi il naît (#431)

  Le fil était rendu **à la main six fois** dans le produit, dont **trois fois
  dans les deux seuls fichiers des tickets** : la liste (carte active), la liste
  (carte d'archive) et la fiche. Le CSS `.evol-list` était redéfini quatre fois.

  Et ces copies avaient **déjà divergé** :

  | Écart | Où |
  |---|---|
  | pièces jointes des évolutions **absentes** | un des deux fils de l'Espace CS |
  | marge haute du fil perdue | fiche du ticket |
  | « Voir les N **entrées** » / « Voir les N **évolutions** » | liste / fiche |
  | une réponse rendue en texte riche / réduite à « Nouvelle réponse (…) » | liste / fiche |

  La dernière n'est pas cosmétique : sur la liste, le fil est le SEUL endroit où
  le contenu d'une réponse apparaît. Retenu : le texte riche, partout — c'est la
  forme qui ne perd jamais d'information.

  ## R5 — cette rubrique ne s'est PAS généralisée dans ce lot

  Trois recopies sur six sont remplacées ici. Les trois autres (Espace CS ×2,
  Actualités) attendent que celle-ci se fasse constater à l'écran : *une rubrique
  se propose sur un écran, se fait constater, puis se généralise*. Jamais
  l'inverse — c'est la pastille partie nue en production qui a fait écrire cette
  règle.
-->
<script lang="ts">
	import FiltreFil from './FiltreFil.svelte';
	import MarqueIA from '#lib/components/MarqueIA.svelte';
	import MessageOrigine from '#lib/components/MessageOrigine.svelte';
	import { createEventDispatcher } from 'svelte';
	import type { TicketEvolution } from '#lib/api/types.ts';
	import PiecesJointes from './PiecesJointes.svelte';
	import IconeAction from './IconeAction.svelte';
	import { safeDescription } from '#lib/sanitize.ts';
	import { fmtDate, fmtDatetime } from '#lib/date.ts';
	import { perimetreLabel } from '#lib/perimetres/index.ts';
	import { entreesDuFil, evolutionIcone } from '#lib/evolutions.ts';
	import { peutEditer } from '#lib/droits.ts';
	import { confirmer } from '#lib/confirmation.ts';

	export let evolutions: TicketEvolution[] = [];
	/** Libellés du workflow — `STATUT_TICKET_LABELS` et rien d'autre (#415). */
	export let statutLabels: Record<string, string> = {};
	/** En-tête de la rubrique. Vide : le fil s'insère dans un bloc déjà nommé. */
	export let titre = '';
	/** Texte affiché quand le fil est vide. Vide : la rubrique ne rend rien. */
	export let vide = '';
	/** Au-delà de ce nombre d'entrées, le fil se replie sur `apercu`. */
	export let seuil = 7;
	export let apercu = 5;
	/**  L'écran autorise-t-il la correction ? Interrupteur GÉNÉRAL : un écran de
	 *   pure lecture le laisse à `false`. Il ne dit pas QUI peut corriger — cela
	 *   se décide par entrée, ci-dessous. */
	export let peutModifier = false;
	/**  Qui regarde, et est-il administrateur ? La règle du serveur est « l'auteur
	 *   de l'entrée, ou un admin » ; sans ces deux valeurs, l'écran ne peut que
	 *   l'approximer — et il l'approximait par « membre du CS », donc trop large :
	 *   le crayon s'affichait sur l'entrée d'un autre, le clic partait, le serveur
	 *   répondait 403, et l'écran annonçait « Accès refusé » pour un geste qu'il
	 *   avait lui-même proposé.
	 *
	 *   ⚠️ Le serveur refait le contrôle : ceci n'est qu'un confort d'écran
	 *   (`standards/03` §1). Cacher un bouton n'a jamais protégé quoi que ce soit.
	 */
	export let currentUserId: number | undefined = undefined;
	export let estAdmin = false;
	/** Entrée actuellement ouverte en correction — le parent porte l'état. */
	export let enEdition: number | null = null;

	/**
	 * **Tout / Seulement les avancées** — le filtre du fil (#1094).
	 *
	 * 🔴 Il n'apparaît QUE là où il sert : un fil où tout est du même type n'a
	 * rien à filtrer, et deux pastilles inertes coûteraient une ligne d'écran à
	 * tous pour n'aider personne. `avecFiltre` demande le filtre ; le composant
	 * décide ensuite s'il y a matière.
	 *
	 * ⚠️ Sur une actualité, le fil ne porte que des paroles — le filtre n'y a
	 * donc pas de sens, et l'écran ne le demande pas.
	 */
	export let avecFiltre = false;

	/**  🔴 L'écran DÉCLARE qu'il sait effacer. Défaut `false` (#505, 19/08/2026).
	 *
	 *   Le bouton 🗑️ ne dépendait que de `estAdmin`. Or ce composant sert CINQ
	 *   écrans, et seuls les deux du ticket écoutent `on:supprimer` — parce que
	 *   seuls les tickets ont une route `DELETE /tickets/{id}/evolutions/{evolId}`.
	 *   Sur le Calendrier, les Actualités et l'Espace CS, tout administrateur
	 *   voyait donc le bouton, cliquait, et **rien ne se passait** : pas d'action,
	 *   pas d'erreur, pas de trace.
	 *
	 *   Le remède n'est pas d'ajouter trois `on:supprimer` : le geste n'existe pas
	 *   côté serveur pour ces entités, un écouteur n'aurait rien à appeler. C'est
	 *   la symétrie exacte de l'interdiction du cadre — **on n'ouvre pas un geste
	 *   que le serveur ne consomme pas** — appliquée cette fois à un bouton.
	 *
	 *   Un écran qui gagnera la capacité passera `avecSuppression` ET écoutera
	 *   `on:supprimer` : les deux, ou aucun des deux. L'ouverture des routes
	 *   manquantes (publications, événements) est suivie en #512. */
	export let avecSuppression = false;

	const dispatch = createEventDispatcher<{ modifier: number; supprimer: number }>();

	//  🔴 Les MÊMES MOTS que le serveur, et dans le même ordre — types puis
	//  identité. Une règle d'écran qui paraphrase une règle de serveur finit
	//  toujours par en dire autre chose ; ici on peut au moins les comparer.
	//
	//  `reponse` est exclu : une réponse du CS n'est pas une entrée de suivi, et
	//  le serveur la refuse déjà (« ce type d'évolution ne peut pas être modifié »).
	const TYPES_CORRIGEABLES = ['commentaire', 'etat'];

	/**  Ce qui s'EFFACE — les MÊMES types que le serveur, et dans le même ordre.
	 *
	 *   ⚠️ Les transitions d'état en font partie depuis le 18/08/2026, et c'est un
	 *   arbitrage CORRIGÉ : je les avais exclues de moi-même (« un mouvement de
	 *   workflow est un fait, pas un texte qu'on rature »), alors que la demande
	 *   était « une suppression pour les historiques », sans distinction. L'absence
	 *   a été constatée dès la première entrée d'état rencontrée.
	 *
	 *   Ce qui la rend acceptable : supprimer l'entrée NE CHANGE PAS l'état du
	 *   ticket — `statut` vit dans sa propre colonne, le fil n'en est que le récit.
	 *   Le coût est une perte de traçabilité, pas une incohérence.
	 *
	 *   ⚠️ Les RÉPONSES restent hors de portée : elles appartiennent à leur auteur,
	 *   souvent un résident. Les effacer supprimerait la parole de quelqu'un
	 *   d'autre — ce n'est pas la même chose que retirer une ligne écrite par le
	 *   système ou par soi-même. Le serveur les refuse (`422`), et l'écran dit la
	 *   même chose que lui, ni plus ni moins (ux-patterns §15). */
	const TYPES_EFFACABLES = ['commentaire', 'etat'];

	/**  🔴 Effacer est réservé à l'ADMINISTRATEUR (18/08/2026, demandé à l'écran :
	 *   « bon pour l'admin seul »).
	 *
	 *   Corriger son propre commentaire est un geste ordinaire, ouvert à son auteur.
	 *   Effacer ne l'est pas : cela fait disparaître une trace que d'autres ont pu
	 *   lire, et sur laquelle ils ont pu agir. Même frontière que la suppression d'un
	 *   ticket, et même règle que « archiver n'est pas supprimer ».
	 *
	 *   La capacité est née d'un besoin réel : deux entrées « Correction : … »
	 *   s'étaient inscrites sur un ticket alors qu'une seule catégorie avait changé,
	 *   et RIEN ne permettait de les retirer — pas même à l'admin. Un fil est une
	 *   mémoire ; une mémoire qui garde des faits inventés vaut moins qu'une mémoire
	 *   trouée. */
	function peutEffacer(evol: TicketEvolution): boolean {
		return avecSuppression && estAdmin && TYPES_EFFACABLES.includes(evol.type);
	}

	function peutCorriger(evol: TicketEvolution): boolean {
		if (!peutModifier || !TYPES_CORRIGEABLES.includes(evol.type)) return false;
		//  `peutEditer` porte les trois cas — l'admin, l'auteur, et le « saisi pour ».
		//  Cette fonction les réécrivait à la ligne près, moins le dernier : deux
		//  écritures d'une même règle, dont une qui en savait moins (#1041).
		//  Sans `auteur_id` elle rend `false` : on n'affiche pas un bouton dont on
		//  ignore s'il aboutira (`standards/04` §2).
		return peutEditer(evol, currentUserId, estAdmin);
	}

	/**  Effacer se CONFIRME (15/10/2026, maquette A de la carte dépliée) : le geste
	 *   partait au premier clic, sur une corbeille voisine du crayon. La question
	 *   vit ici, une fois, et non chez les deux hôtes qui écoutent `supprimer`. */
	async function effacer(evol: TicketEvolution) {
		const ok = await confirmer({
			titre: 'Supprimer cette entrée',
			message: `L’entrée du ${fmtDate(evol.cree_le)} disparaît du fil. L’état de l’affaire ne change pas.`,
			libelleConfirmer: 'Supprimer',
			danger: true,
		});
		if (ok) dispatch('supprimer', evol.id);
	}

	let deplie = false;

	//  Le plus récent en premier : on vient lire ce qui vient d'arriver.
	//  Sans la Suite de synthèse : elle a son bloc au-dessus du fil (`SyntheseFil`).
	$: triees = entreesDuFil(evolutions).sort(
		(a, b) => new Date(b.cree_le).getTime() - new Date(a.cree_le).getTime(),
	);
	//  Ce qui compte comme une avancée, et pourquoi le filtre ne s'affiche pas
	//  toujours : `FiltreFil` le porte, avec son libellé et ses pastilles.
	const AVANCEES = ['etat'];
	let filtre = 'tout';
	$: filtrees = filtre === 'avancees' ? triees.filter((e) => AVANCEES.includes(e.type)) : triees;
	$: replie = filtrees.length > seuil && !deplie;
	$: visibles = replie ? filtrees.slice(0, apercu) : filtrees;
</script>

{#if titre || $$slots.action}
	<div class="hist-entete">
		{#if titre}<h2 class="hist-titre">{titre}</h2>{/if}
		<slot name="action" />
	</div>
{/if}

{#if avecFiltre}
	<FiltreFil
		bind:valeur={filtre}
		compte={filtrees.length}
		avancees={AVANCEES}
		types={triees.map((e) => e.type)}
	/>
{/if}

{#if filtrees.length === 0}
	{#if filtre === 'avancees'}
		<p class="hist-vide">Aucune avancée pour l’instant — le fil n’a que des échanges.</p>
	{:else if vide}<p class="hist-vide">{vide}</p>{/if}
{:else}
	<div class="evol-list">
		{#each visibles as evol, i (evol.id)}
			{#if i > 0}<hr class="evol-sep" />{/if}
			<!--  🔴 Un `class:` par type plutôt que `evol-{evol.type}` (#810) : devant une
			      classe interpolée, Svelte cesse de déclarer les sélecteurs inutilisés
			      pour TOUT le fichier, et `lint:css-orphelin` devient aveugle ici.
			      Les valeurs sont les clés de `EVOLUTION_ICONE` (#lib/evolutions) : un
			      type ajouté là-bas reçoit son fond ici, à la main (synthèse, #1643). -->
			<div
				class="evol-item"
				class:evol-commentaire={evol.type === 'commentaire'}
				class:evol-etat={evol.type === 'etat'}
				class:evol-reponse={evol.type === 'reponse'}
			>
				<!--  🔴 L'icône vient de `#lib/evolutions`, plus d'une chaîne écrite ici.
				      Elle valait 📝 pour un commentaire alors que le bouton qui le crée
				      dit « 💬 Commenter » — signalé à l'écran le 19/08/2026 : *« pourquoi
				      mon commentaire a une icône de type relance ? »*. La bulle était
				      prise par `reponse`. Le geste et son résultat portent désormais le
				      même signe. -->
				<span class="evol-icon">{evolutionIcone(evol.type)}</span>
				<div class="evol-body">
					<div class="evol-ligne-meta">
						<!--  🔴 La marque ✨ est COLLÉE au nom (06/10/2026) : enfant direct de la
						      ligne en `space-between`, elle se répartissait au milieu. -->
						<span class="evol-qui">
							<span class="evol-meta"
								>{fmtDatetime(evol.cree_le)}{evol.auteur_nom ? ` · ${evol.auteur_nom}` : ''}</span
							>
							<MarqueIA assiste={evol.assiste_ia} />
						</span>
						<!--  🔴 LES DEUX ICÔNES DANS UN MÊME GROUPE, cadré à droite
						      (18/08/2026, signalé à l'écran). Elles étaient enfants directs
						      d'une ligne en `space-between` : à DEUX enfants — la méta et le
						      crayon — cela donnait bien « méta à gauche, crayon à droite » ;
						      la corbeille en a fait un TROISIÈME, et `space-between` l'a
						      réparti au milieu. Le style n'avait pas changé, c'est son
						      contenu qui avait cessé de lui correspondre.

						      Groupées, elles suivent la norme de l'en-tête de carte : ✏️ puis
						      🗑️, collées, à l'extrémité droite (ux-patterns §3). -->
						{#if enEdition !== evol.id && (peutCorriger(evol) || peutEffacer(evol))}
							<span class="evol-actions">
								{#if peutCorriger(evol)}
									<!--  Le CRAYON SEUL, comme partout ailleurs sur le site : ce
									      bouton portait « ✏️ Modifier » et était le dernier à écrire
									      le mot. Le sens vit dans `title` et `aria-label`. -->
									<button
										type="button"
										class="btn-icon btn-icon-edit"
										aria-label="Modifier cette entrée"
										title="Modifier"
										on:click={() => dispatch('modifier', evol.id)}
										><IconeAction icone="pencil" /></button
									>
								{/if}
								{#if peutEffacer(evol)}
									<!--  La corbeille EN DERNIER parce qu'elle est irréversible. -->
									<button
										type="button"
										class="btn-icon-danger"
										aria-label="Supprimer cette entrée"
										title="Supprimer cette entrée"
										on:click={() => effacer(evol)}><IconeAction icone="trash-2" /></button
									>
								{/if}
							</span>
						{/if}
					</div>

					{#if evol.type === 'etat'}
						<span class="evol-text">
							Statut : <strong>{statutLabels[evol.ancien_statut ?? ''] || 'Aucun'}</strong>
							→ <strong>{statutLabels[evol.nouveau_statut ?? ''] || evol.nouveau_statut}</strong>
						</span>
					{/if}

					<!--  Le périmètre PRÉCISÉ par cette entrée (#497). Il se lit sur la même
					      ligne que le changement d'état, parce que c'est le même genre de
					      fait : ce que cette entrée a changé au dossier.
					      🔹 = périmètre logique, jamais 📍 qui désigne un lieu physique. Et
					      il est TOUJOURS affiché quand l'entrée en déclare un, même s'il
					      vaut « résidence » — la règle « pas de badge sur le périmètre par
					      défaut » vaut pour l'ÉTAT d'un objet, pas pour un CHANGEMENT :
					      élargir un ticket à toute la résidence est un fait qui se dit. -->
					{#if evol.perimetre_cible?.length}
						<span class="evol-text evol-perimetre">
							Périmètre précisé : <strong>&#x1F539; {perimetreLabel(evol.perimetre_cible)}</strong>
						</span>
					{/if}

					{#if enEdition === evol.id}
						<!--  Le formulaire de correction vient de l'écran hôte. -->
						<div class="evol-edition"><slot name="edition" {evol} /></div>
					{:else}
						{#if evol.contenu}
							<div class="evol-content rich-content">{@html safeDescription(evol.contenu)}</div>
						{/if}
						<MessageOrigine texte={evol.contenu_origine} />
						<!--  🔴 GRAND FORMAT, et c'est un REVIREMENT (18/08/2026) : `ux-patterns`
						      §11 rangeait les fils du côté « vignette » (on survole une liste).
						      Capture à l'appui : un fil d'Historique ne s'atteint qu'en DÉPLIANT
						      une carte — on a donc déjà demandé à voir, et sur un événement de
						      calendrier les photos du suivi sont TOUT le contenu. Le critère de
						      §11 ne change pas (« survole-t-on, ou a-t-on demandé à voir ? »),
						      sa lecture si. `compact` reste : typographie des liens seulement. -->
						{#if evol.fichiers_urls?.length}
							<div class="evol-pj">
								<PiecesJointes urls={evol.fichiers_urls} format="grand" compact />
							</div>
						{/if}
					{/if}
				</div>
			</div>
		{/each}

		{#if replie}
			<hr class="evol-sep" />
			<button type="button" class="evol-more" on:click={() => (deplie = true)}>
				Voir les {filtrees.length - apercu} entrées plus anciennes
			</button>
		{/if}
	</div>
{/if}

<style>
	.hist-entete {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 0.5rem;
		margin-bottom: 0.5rem;
	}
	.hist-titre {
		font-size: var(--fs-xl);
		font-weight: 600;
		margin: 0;
	}
	.hist-vide {
		font-size: var(--fs-md);
		color: var(--color-text-muted);
	}

	/*  ⚠️ Ces classes sont définies ICI, avec le balisage qui les porte. Les
	    laisser dans le `<style>` des pages hôtes ne les atteindrait pas : Svelte
	    scope le style au composant qui l'écrit, et c'est très exactement la panne
	    qui a envoyé des pastilles nues en production (v2.67.11). La marge haute
	    (`margin-top`) revient au parent, qui seul sait ce que le fil suit. */
	.evol-list {
		border: 1px solid var(--color-border);
		border-radius: 6px;
		overflow: hidden;
	}
	.evol-sep {
		margin: 0;
		border: none;
		border-top: 1px solid var(--color-border);
	}
	.evol-item {
		display: flex;
		gap: 0.5rem;
		padding: 0.5rem 0.75rem;
		font-size: var(--fs-md);
	}
	.evol-icon {
		flex-shrink: 0;
		font-size: var(--fs-base);
		margin-top: 0.1rem;
	}
	.evol-body {
		display: flex;
		flex-direction: column;
		gap: 0.15rem;
		flex: 1;
		min-width: 0;
	}
	.evol-ligne-meta {
		display: flex;
		align-items: flex-start;
		justify-content: space-between;
		gap: 0.5rem;
	}
	/*  Le groupe d'actions : collées entre elles, et poussé à droite par le
	    `space-between` de la ligne — quel que soit le NOMBRE de boutons. */
	.evol-actions {
		display: flex;
		gap: 0.3rem;
		flex-shrink: 0;
	}
	/*  La méta et la marque IA : un seul enfant de la ligne, donc la marque suit le nom. */
	.evol-qui {
		display: flex;
		align-items: baseline;
		gap: 0.3rem;
		min-width: 0;
	}
	.evol-meta {
		font-size: var(--fs-xs);
		color: var(--color-text-muted);
	}
	.evol-text {
		color: var(--color-text);
		line-height: 1.5;
	}
	/*  Le périmètre précisé se lit SOUS le changement d'état quand les deux sont
	    là : deux faits, deux lignes, plutôt qu'une phrase qui les enchaîne. */
	.evol-perimetre {
		display: block;
		margin-top: 0.15rem;
	}
	.evol-content {
		margin-top: 0.2rem;
		color: var(--color-text);
		line-height: 1.6;
		font-size: var(--fs-md);
	}
	.evol-content :global(p) {
		margin: 0 0 0.3em;
	}
	.evol-pj {
		margin-top: 0.4rem;
	}
	.evol-edition {
		margin: 0.4rem 0;
		border: 1px solid var(--color-border);
		border-radius: 8px;
		padding: 0.75rem;
		background: var(--color-bg);
	}
	/*  Les teintes de fond disent le TYPE d'entrée sans lire un badge. */
	.evol-etat {
		background: var(--color-info-fond);
	}
	.evol-reponse {
		background: var(--color-success-fond);
	}
	.evol-commentaire {
		background: var(--color-neutre-fond);
	}

	.evol-more {
		width: 100%;
		background: none;
		border: none;
		padding: 0.45rem;
		font-size: var(--fs-sm);
		color: var(--color-primary);
		cursor: pointer;
		text-align: center;
	}
	@media (hover: hover) and (pointer: fine) {
		.evol-more:hover {
			background: var(--color-bg);
		}
	}
</style>
