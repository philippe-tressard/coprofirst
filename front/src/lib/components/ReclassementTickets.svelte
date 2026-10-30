<!--
  **Les tickets dont la catégorie pourrait être plus juste** — proposition seule.

  ## 🔴 Pourquoi ce relevé, et pourquoi PAS de bouton (#821, 07/09/2026)

  Demandé : *« peux-tu regarder les tickets créés et leur affecter la catégorie la
  plus adéquate ? Me faire une synthèse et me valider avant application. »*

  Quatre catégories sont nées le même jour — Propreté, Espaces verts, Sinistre,
  Étude & travaux — et « Urgence » a disparu. Les tickets déjà ouverts portent
  donc des catégories choisies dans une liste qui n'existe plus telle quelle, et
  beaucoup sont en « Panne » faute de mieux.

  ⚠️ **Rien n'est écrit ici, et c'est ce qui a été demandé.** Une
  reclassification automatique est un pari sur du texte libre : ces règles lisent
  un titre et une description écrits par des humains. Une catégorie fausse posée
  en silence est pire qu'une catégorie approximative assumée.

  C'est le même arbitrage que `BauxSansLocataire` juste à côté, et pour la même
  raison : le relevé répond à la question « le cas se présente-t-il ? », et le
  geste est à un lot de distance si la réponse est oui.

  ## `confiance`, et pourquoi elle change ce qu'on en fait

  | | Ce que c'est |
  |---|---|
  | **haute** | un indice qui ne désigne qu'une chose — « dégât des eaux », « interphone », « élagage ». On valide d'un coup d'œil. |
  | **moyenne** | un indice qui peut appartenir ailleurs — « eau » se lit dans « fuite d'eau chaude », qui est une panne de chauffe-eau ; « badge » peut être une commande d'accès, qui a son propre circuit. |

  🔴 **L'INDICE est affiché**, et ce n'est pas décoratif : sans le mot qui a
  déclenché la règle, on valide à l'aveugle. C'est la différence entre
  « fais-moi confiance » et « voilà pourquoi ».

  ⚠️ La proposition et la confiance viennent du SERVEUR. Les recalculer ici en
  ferait une seconde règle, et deux vues du même relevé proposeraient deux
  catégories — c'est la leçon de `BauxSansLocataire`.
-->
<script lang="ts">
	import { fmtNombre } from '#lib/utils.ts';
	import { onMount } from 'svelte';
	import { admin as adminApi, type ReleveReclassement } from '#lib/api/index.ts';
	import { messageErreur } from '#lib/erreurs.ts';
	import EtatListe from '#lib/components/EtatListe.svelte';

	let releve: ReleveReclassement | null = null;
	let chargement = true;
	/**  Non vide = on n'a PAS pu regarder. Un relevé vide se lirait « tout est
	 *   bien rangé », ce qui serait faux et rassurant (`standards/04`). */
	let erreur = '';

	onMount(async () => {
		try {
			releve = await adminApi.reclassementTickets();
		} catch (e) {
			erreur = messageErreur(e, 'Chargement impossible');
		} finally {
			chargement = false;
		}
	});

	$: propositions = releve?.propositions ?? [];
	$: hautes = propositions.filter((p) => p.confiance === 'haute');
	$: moyennes = propositions.filter((p) => p.confiance !== 'haute');
</script>

<h3 class="section-title">Catégories d’affaires à revoir</h3>

{#if chargement || erreur || propositions.length === 0}
	<EtatListe
		{chargement}
		{erreur}
		vide={propositions.length === 0}
		titreErreur="Impossible d’analyser les tickets"
		titreVide="Aucune catégorie à revoir"
		messageVide={releve
			? `Les ${releve.total_tickets} tickets existants sont dans une catégorie cohérente avec leur contenu.`
			: ''}
	/>
{:else}
	<p class="muted bilan">
		<strong>{propositions.length}</strong> affaire{propositions.length > 1 ? 's' : ''} sur
		{fmtNombre(releve?.total_tickets)} pourrai{propositions.length > 1 ? 'ent' : 't'} changer de catégorie.
		<strong>{hautes.length}</strong> proposition{hautes.length > 1 ? 's' : ''} à confiance haute.
		<br />
		<em
			>Ce relevé ne modifie rien : il propose. La correction se fait affaire par affaire, depuis sa
			fiche.</em
		>
	</p>

	<!--  🔴 `haute` est un BOOLÉEN, pas une classe interpolée. `class="badge
	      {groupe.cls}"` faisait cesser Svelte de déclarer les sélecteurs inutilisés
	      pour TOUT le fichier, et `lint:css-orphelin` y devenait aveugle sans le
	      dire — c'est la panne de #813, et son plafond décroissant l'a refusée
	      ici dans la minute. Deux valeurs connues : la conversion ne coûte rien. -->
	{#each [{ titre: 'Confiance haute', lignes: hautes, haute: true }, { titre: 'À vérifier', lignes: moyennes, haute: false }] as groupe (groupe.titre)}
		{#if groupe.lignes.length > 0}
			<h4 class="sous-titre">
				{groupe.titre}
				<span class="badge" class:badge-green={groupe.haute} class:badge-orange={!groupe.haute}
					>{groupe.lignes.length}</span
				>
			</h4>
			<div class="table-wrap">
				<table class="table">
					<thead>
						<tr>
							<th>Affaire</th><th>Aujourd’hui</th><th>Proposé</th><th>Pourquoi</th>
						</tr>
					</thead>
					<tbody>
						{#each groupe.lignes as p (p.ticket_id)}
							<tr>
								<td>
									<a href="/tickets/{p.ticket_id}">{p.numero}</a>
									<div class="text-muted-sm">{p.titre}</div>
								</td>
								<td><span class="badge badge-gray">{p.actuelle_libelle}</span></td>
								<td><span class="badge badge-blue">{p.proposee_libelle}</span></td>
								<!--  L'indice, en toutes lettres : c'est lui qui permet de juger. -->
								<td class="text-muted-sm">« {p.indice} »</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		{/if}
	{/each}
{/if}

<style>
	/*  🔴 `.text-muted-sm` N'EST PAS redéfinie ici : elle vit dans `styles/ecrans.css`
	    et vaut pour tout le produit. Ma première version la repeignait — deux
	    propriétés, dont une identique à la charte — et `lint:charte` l'a refusée
	    dans la minute. Une règle scopée gagne sur la charte (Svelte ajoute sa
	    classe de portée) : cet écran aurait rendu un gris légèrement autre que
	    ses voisins, sans que personne l'ait décidé.

	    Seul reste ici ce qui n'existe nulle part ailleurs : le titre de groupe,
	    qui porte un compteur à côté de son libellé. */
	.sous-titre {
		font-size: var(--fs-base);
		font-weight: 600;
		margin: 1.25rem 0 0.5rem;
		display: flex;
		align-items: center;
		gap: 0.5rem;
	}
	.bilan {
		margin-bottom: 1rem;
	}
</style>
