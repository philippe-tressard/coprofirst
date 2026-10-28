<script lang="ts">
	/**
	 * Une section de la fiche de copropriété **adossée à un contrat**.
	 *
	 * ## Pourquoi un composant, et pas deux sections écrites à la suite
	 *
	 * L'assurance et le syndic posent la **même** question : *lequel des contrats
	 * existants cette fiche désigne-t-elle ?* Puis ils affichent la même chose —
	 * l'organisation, le contrat, ses dates, son document — et renvoient au même
	 * endroit pour modifier.
	 *
	 * Les écrire deux fois aurait donné deux sections libres de diverger au
	 * premier enrichissement demandé d'un seul côté (`standards/02` §2). C'est
	 * exactement ce qui est arrivé aux six formulaires de création avant
	 * `ChampsCommuns`, et aux cartes avant `EnteteCarte`.
	 *
	 * ## Le régime : on DÉSIGNE ici, on MODIFIE ailleurs
	 *
	 * 🔴 Le sélecteur ne crée ni ne modifie un contrat — il dit lequel fait foi.
	 * Un objet se modifie à UN endroit, et cet endroit existe : Prestataires →
	 * Contrats. Deux écrans d'édition pour le même contrat, c'est la promesse de
	 * deux vérités — celle que #490 a précisément supprimée en retirant les trois
	 * champs de texte libre.
	 *
	 * C'est aussi pourquoi le détail est une **liste de définitions** et non des
	 * champs de saisie : la forme dit le régime sans qu'on ait à le lire.
	 */
	import { onMount } from 'svelte';
	import {
		copropriete as coproprieteApi,
		documents as documentsApi,
		type ContratCandidat,
	} from '#lib/api/index.ts';
	import SectionFormulaire from '#lib/components/SectionFormulaire.svelte';
	import { fmtDateShort } from '#lib/date.ts';

	export let titre: string;
	export let icone: string;
	/**  `'assurance'` ou `'syndic'` — le serveur valide contre une liste blanche. */
	export let section: 'assurance' | 'syndic';
	/**  Le contrat désigné. `null` = aucun, et l'écran le dit. */
	export let contratId: number | null = null;
	/**  Ce qui s'affiche une fois le contrat désigné : `[libellé, valeur]`.
	 *   Les valeurs vides sont écartées par le composant — une ligne vide se lit
	 *   comme une donnée manquante alors qu'elle est simplement absente.
	 *
	 *   ⚠️ **Le libellé sert de clé de liste** (`{#each … (label)}`), il doit donc
	 *   être unique DANS UN MÊME APPEL. Les deux appelants actuels le sont, et
	 *   deux d'entre eux partagent bien « Téléphone » et « Courriel » — sans
	 *   conséquence, puisque chaque appel a son propre tableau. Un libellé répété
	 *   dans le même tableau ferait lever Svelte à l'affichage : c'est un défaut
	 *   de saisie visible tout de suite, et non un état qui glisse en silence —
	 *   ce que l'absence de clé produisait. */
	export let lignes: [string, string | null | undefined][] = [];
	/**  L'identifiant du document attaché au contrat, s'il y en a un. */
	export let documentId: number | null = null;

	let candidats: ContratCandidat[] = [];
	let erreur = false;

	onMount(async () => {
		try {
			candidats = await coproprieteApi.contratsCandidats(section);
		} catch {
			//  ⚠️ On DIT que la liste n'a pas pu être chargée. Une liste vide
			//  silencieuse se lit « aucun contrat n'existe » — donc une invitation
			//  à en créer un qui existe déjà (`standards/04` §1).
			erreur = true;
		}
	});

	$: visibles = lignes.filter(([, v]) => v !== null && v !== undefined && v !== '');

	function libelleCandidat(c: ContratCandidat): string {
		const parts = [c.prestataire ?? c.libelle];
		if (c.numero_contrat) parts.push(`n° ${c.numero_contrat}`);
		parts.push(`depuis le ${fmtDateShort(c.date_debut)}`);
		//  Un contrat échu reste proposable — une copropriété désigne parfois un
		//  mandat expiré le temps d'en signer un nouveau. Mais elle doit le SAVOIR.
		if (!c.actif) parts.push('— résilié');
		return parts.join(' · ');
	}
</script>

<SectionFormulaire {icone} {titre}>
	<div class="field largeur-saisie">
		<label for="ref-{section}">Contrat de référence</label>
		<select id="ref-{section}" bind:value={contratId}>
			<option value={null}>— aucun —</option>
			{#each candidats as c (c.id)}
				<option value={c.id}>{libelleCandidat(c)}</option>
			{/each}
		</select>
	</div>

	{#if erreur}
		<p class="ref-alerte">
			La liste des contrats n'a pas pu être chargée. Ce qui s'affiche ci-dessous reste juste ; seule
			la <strong>modification</strong> du choix est indisponible.
		</p>
	{:else if candidats.length === 0}
		<p class="ref-vide">Aucun contrat de ce type n'est enregistré.</p>
	{/if}

	{#if visibles.length}
		<dl class="ref-lecture">
			{#each visibles as [label, valeur] (label)}
				<dt>{label}</dt>
				<dd>{valeur}</dd>
			{/each}
		</dl>
		{#if documentId}
			<p class="ref-renvoi">
				<a href={documentsApi.downloadUrl(documentId)}>Télécharger le document du contrat</a>
			</p>
		{/if}
	{:else}
		<p class="ref-vide">Aucun contrat désigné.</p>
	{/if}

	<!--  Un complément propre à la section — un champ que l'appelant veut voir
	      AVEC ces lignes, et pas ailleurs. Le renvoi reste en dernier : il dit où
	      aller modifier, c'est une sortie, pas un contenu. -->
	<div class="ref-complement">
		<slot name="complement" />
	</div>

	<p class="ref-renvoi">
		<slot name="renvoi" />
	</p>
</SectionFormulaire>

<style>
	/*  ⚠️ Ces règles voyagent AVEC le balisage. Svelte scope les styles au
	    fichier : les laisser dans la page aurait rendu cette section nue, comme
	    les pastilles de la v2.67.11 et les six écrans d'admin du 19/08. */
	.ref-lecture {
		display: grid;
		grid-template-columns: auto 1fr;
		gap: 0.3rem 0.75rem;
		margin: 0.75rem 0 0;
		font-size: var(--fs-base);
	}
	.ref-lecture dt {
		color: var(--color-text-muted);
	}
	.ref-lecture dd {
		margin: 0;
	}

	/*  Sous 520 px, deux colonnes écrasent la valeur contre le libellé : on
	    empile. C'est la même bascule que les autres listes de définitions du
	    site — la responsivité appartient au composant qui porte le balisage. */
	@media (max-width: 767px) {
		.ref-lecture {
			grid-template-columns: 1fr;
			gap: 0 0;
		}
		.ref-lecture dt {
			margin-top: 0.5rem;
		}
	}

	/*  🔴 La respiration du complément vit ICI, pas chez l'appelant (11/09/2026,
	    signalé à l'écran : « attention à bien respecter les espacements de
	    ligne »). Le champ s'affichait collé à la dernière ligne de définition,
	    sans rien pour l'en séparer.

	    ⚠️ Et c'est une marge VIDE quand le slot l'est : `:empty` évite d'ajouter
	    un blanc dans les sections qui n'ont pas de complément — sinon corriger
	    l'espacement d'une section en créerait un ailleurs. */
	.ref-complement:not(:empty) {
		margin-top: 0.9rem;
	}
	/*  « Aucun contrat… » se lit comme le renvoi : une phrase d'état, grise, au
	    corps des aides. Elle n'avait que sa marge, et s'affichait donc en texte
	    courant noir (16 px) entre des libellés et des aides de 13 px — relevé
	    à l'écran le 02/10/2026 en reprenant l'identité de la fiche. */
	.ref-renvoi,
	.ref-vide {
		font-size: var(--fs-md);
		color: var(--color-text-muted);
		margin: 0.6rem 0 0;
		line-height: 1.5;
	}
	.ref-alerte {
		font-size: var(--fs-md);
		line-height: 1.5;
		margin: 0.6rem 0 0;
		padding: 0.5rem 0.7rem;
		border-left: 3px solid var(--color-warning);
		background: var(--color-bg);
	}
</style>
