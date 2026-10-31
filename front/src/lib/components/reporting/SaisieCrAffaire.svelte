<!--
  Le COMPTE RENDU d'une affaire, saisi en direct pendant un point CS / Syndic
  (#2041, arbitré le 17/10/2026).

  - La section Description des affaires, reprise telle quelle
    (`SectionDescription` : gras, italique, assistant IA) — **grande**, une
    douzaine de lignes à l'ouverture, et redimensionnable : *« c'est pénible
    quand la boîte est trop petite »*.
  - Case « CS et présents » (#2082, ex-« Conseil seul ») : lu du conseil et des
    présents — PDF et validation compris —, masqué au fil et dans l'affaire.
  - **L'état à la validation** (#2082) : l'état actuel, et celui que l'affaire
    prendra quand le CR sera validé — pas avant. Coché d'office par le serveur
    (`etat_par_defaut` : « Chez le syndic », mais « À l'AG » reste à l'AG).
  - **Annuler** referme sans rien écrire ; **Enregistrer** sauvegarde (le verbe
    du site, `PiedFormulaire`, #396) et rend la main à la vue (`onEnregistre`),
    qui ouvre l'affaire suivante.
  - Fermer AUTREMENT — ouvrir une autre affaire, replier celle-ci — enregistre
    la saisie en **brouillon** : la prise de notes ne s'arrête pas pour une
    question, et rien ne se perd.
-->
<script lang="ts">
	import { onDestroy } from 'svelte';
	import SectionDescription from '#lib/components/SectionDescription.svelte';
	import PiedFormulaire from '#lib/components/PiedFormulaire.svelte';
	import Icon from '#lib/components/Icon.svelte';
	import { toast } from '#lib/components/Toast.svelte';
	import { messageErreur } from '#lib/erreurs.ts';
	import { contexteCommentaire } from '#lib/assistant.ts';
	import { richEmpty } from '#lib/publications.ts';
	import { LIBELLE_CS_ET_PRESENTS } from '#lib/points-conseil.ts';
	import { statutTicketLabel } from '#lib/tickets.ts';
	import {
		pointsConseil,
		type AffaireOuverte,
		type CompteRenduPoint,
		type CrAffaire,
		type EtatValidation,
	} from '#lib/api/index.ts';
	import { SEPARATEUR } from '#lib/separateurs.ts';

	export let pointId: number;
	export let affaire: AffaireOuverte;
	export let cr: CrAffaire | undefined;
	export let onCompteRendu: (cr: CompteRenduPoint) => void;
	/** « Annuler » : la saisie se referme. */
	export let onFerme: () => void;
	/** « Enregistrer » a réussi : la vue ouvre l'affaire suivante (#2082). */
	export let onEnregistre: () => void = onFerme;
	/** Les états proposés pour la validation — la liste du serveur. */
	export let etats: EtatValidation[] = [];
	/**  Fermer sans geste enregistre-t-il en brouillon ? Pendant le point
	 *   seulement : terminé, un CR se corrige et s'enregistre, ou rien (#2042). */
	export let brouillonAuto = true;

	const depart = {
		contenu: cr?.contenu ?? '',
		conseilSeul: cr?.conseil_seul ?? false,
		etat: cr?.etat_cible ?? affaire.etat_par_defaut,
	};
	let contenu = depart.contenu;
	let conseilSeul = depart.conseilSeul;
	let etat = depart.etat;
	let enCours = false;
	/** Fermé par « Annuler » ou après « Sauvegarder » : rien à garder en brouillon. */
	let regle = false;

	$: modifie =
		contenu !== depart.contenu || conseilSeul !== depart.conseilSeul || etat !== depart.etat;

	async function ecrire(brouillon: boolean) {
		const corps = {
			contenu: richEmpty(contenu) ? '' : contenu,
			brouillon,
			conseil_seul: conseilSeul,
			etat_cible: etat || null,
		};
		onCompteRendu(await pointsConseil.ecrireCr(pointId, affaire.id, corps));
	}

	async function sauvegarder() {
		enCours = true;
		try {
			await ecrire(false);
			regle = true;
			onEnregistre();
		} catch (e) {
			toast('error', messageErreur(e, 'Enregistrement impossible'));
		} finally {
			enCours = false;
		}
	}

	function annuler() {
		regle = true;
		onFerme();
	}

	//  Fermée sans geste — une autre affaire s'ouvre, celle-ci se replie : la
	//  saisie part en brouillon. Le composant est déjà démonté ; l'écran reçoit
	//  le compte rendu à jour par `onCompteRendu`.
	onDestroy(() => {
		if (regle || !modifie || !brouillonAuto) return;
		ecrire(true).catch((e) => toast('error', messageErreur(e, 'Brouillon non enregistré')));
	});
</script>

<form class="saisie-cr" on:submit|preventDefault={sauvegarder}>
	<SectionDescription
		premiere
		idPrefixe="cr-{affaire.id}"
		idChamp="contenu"
		titre="Compte rendu"
		hauteur="18rem"
		placeholder="Ce qui a été dit, décidé, et qui fait quoi."
		assistant={contexteCommentaire({ titre: affaire.titre, description: affaire.apercu })}
		assistantAvecTitre={false}
		bind:valeur={contenu}
	/>
	{#if etats.length}
		<div class="etat">
			<p class="actuel">État actuel : <strong>{statutTicketLabel(affaire.statut)}</strong></p>
			<div class="field">
				<label for="etat-cr-{affaire.id}">État à la validation du compte rendu</label>
				<select id="etat-cr-{affaire.id}" bind:value={etat}>
					{#each etats as e (e.cle)}
						<option value={e.cle}>{e.libelle}</option>
					{/each}
				</select>
			</div>
		</div>
	{/if}
	<label class="case">
		<input type="checkbox" bind:checked={conseilSeul} />
		<Icon name="shield-check" size={14} />
		{LIBELLE_CS_ET_PRESENTS}{SEPARATEUR.tiret}lu par le conseil syndical et les présents seulement
	</label>
	<PiedFormulaire petit {enCours} on:annule={annuler} />
</form>

<style>
	.saisie-cr {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
		padding: 0.5rem 0 0.25rem;
	}
	.etat {
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
	}
	.actuel {
		margin: 0;
		font-size: var(--fs-sm);
		color: var(--color-text-muted);
	}
</style>
