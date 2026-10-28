<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import Pastille from '#lib/components/Pastille.svelte';
	import {
		DESTINATAIRES,
		LIBELLE_TOUS,
		TOUS_LES_RESIDENTS,
		concerneTousLesResidents,
	} from '#lib/destinataires.ts';

	/** Valeurs sélectionnées — tableau de strings. Ex: ['résidents'] ou ['copropriétaires_occupants','locataires'] */
	export let value: string[] = ['résidents'];

	/** Intitulé du champ — porté par l'objet, comme pour le périmètre. Les pages
	    l'écrivaient chacune de leur côté. */
	export let titre = 'Destinataires';

	/** Astérisque des champs requis. */
	export let requis = true;

	/**  La pastille « Résident concerné » d'une AFFAIRE (#1343) — son libellé, ou
	 *   `null` : absente. Rendue entre Locataires et Conseil syndical ; elle ne
	 *   s'ajoute pas à `value` (elle écrit `confidentiel`), d'où son événement. */
	export let concerne: string | null = null;
	export let concerneActif = false;

	const dispatch = createEventDispatcher<{ change: string[]; concerne: boolean }>();

	/** Un profil choisi éteint « Résident concerné » : les deux ne se cumulent pas. */
	function quitterConcerne() {
		if (concerneActif) dispatch('concerne', false);
	}

	//  ⚠️ La table des profils n'est PLUS ici : elle vit dans `#lib/destinataires.ts`.
	//  Écrite dans le sélecteur, elle n'était disponible que pour SÉLECTIONNER —
	//  et la liste des sondages affichait donc les valeurs brutes de la base dans
	//  ses badges, faute de pouvoir les traduire. Même partage que
	//  `#lib/perimetres.ts` pour l'axe géographique.
	//
	//  « Bailleurs » (13/08/2026) et « Copropriétaires occupants » (16/08/2026)
	//  sont symétriques : « Copropriétaires » couvre les DEUX statuts
	//  `copropriétaire_*`, si bien qu'on ne savait s'adresser ni aux uns ni aux
	//  autres seuls — alors que des pans entiers du produit leur sont propres.
	//  Les deux ajouts sont purement additifs côté serveur : une valeur inconnue
	//  tombait déjà sur un refus, donc aucune publication existante ne change de
	//  public.

	$: isTous = concerneTousLesResidents(value);
	$: selected = new Set(value);

	function selectTous() {
		quitterConcerne();
		value = [TOUS_LES_RESIDENTS];
		dispatch('change', value);
	}

	function toggleItem(val: string) {
		quitterConcerne();
		const s = new Set(value.filter((v) => v !== TOUS_LES_RESIDENTS));
		if (s.has(val)) s.delete(val);
		else s.add(val);
		value = s.size > 0 ? [...s] : [TOUS_LES_RESIDENTS];
		dispatch('change', value);
	}
</script>

{#if titre}
	<!--  Badge d'état : « Tous » se lit sans dépiler les pastilles.
	      Même règle que le périmètre (skill `ux-patterns` §9 quater). -->
	<div class="destinataire-titre">
		{titre}{#if requis}
			*{/if}
		{#if isTous}<span class="badge badge-green destinataire-badge">{LIBELLE_TOUS}</span>{/if}
	</div>
{/if}
<div class="destinataire-pills">
	<Pastille active={!concerneActif && isTous} icone="users-round" on:click={selectTous}
		>{LIBELLE_TOUS}</Pastille
	>
	{#each DESTINATAIRES as o (o.code)}
		{#if concerne !== null && o.code === 'conseil_syndical'}
			<Pastille
				active={concerneActif}
				icone="lock"
				on:click={() => dispatch('concerne', !concerneActif)}>{concerne}</Pastille
			>
		{/if}
		<Pastille
			active={!concerneActif && !isTous && selected.has(o.code)}
			icone={o.icone}
			on:click={() => toggleItem(o.code)}>{o.libelle}</Pastille
		>
	{/each}
</div>

<style>
	.destinataire-pills {
		display: flex;
		flex-wrap: wrap;
		gap: 0.4rem;
	}
	.destinataire-titre {
		font-size: var(--fs-base);
		font-weight: 500;
		color: var(--color-text);
		margin-bottom: 0.3rem;
	}
	.destinataire-badge {
		font-size: var(--fs-2xs);
		margin-left: 0.4rem;
	}
</style>
