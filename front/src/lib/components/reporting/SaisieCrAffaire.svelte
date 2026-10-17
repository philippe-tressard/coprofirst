<!--
  Le COMPTE RENDU d'une affaire, saisi en direct pendant un point CS / Syndic
  (#2041, arbitré le 17/10/2026).

  - La section Description des affaires, reprise telle quelle
    (`SectionDescription` : gras, italique, assistant IA) — **grande**, une
    douzaine de lignes à l'ouverture, et redimensionnable : *« c'est pénible
    quand la boîte est trop petite »*.
  - Case 🛡️ « Conseil seul » : ce compte rendu ne sera lu que par le conseil.
  - **Annuler** referme sans rien écrire ; **Enregistrer** sauvegarde (le verbe
    du site, `PiedFormulaire`, #396).
  - Fermer AUTREMENT — ouvrir une autre affaire, replier celle-ci — enregistre
    la saisie en **brouillon** : la prise de notes ne s'arrête pas pour une
    question, et rien ne se perd.
-->
<script lang="ts">
	import { onDestroy } from 'svelte';
	import SectionDescription from '$lib/components/SectionDescription.svelte';
	import PiedFormulaire from '$lib/components/PiedFormulaire.svelte';
	import Icon from '$lib/components/Icon.svelte';
	import { toast } from '$lib/components/Toast.svelte';
	import { messageErreur } from '$lib/erreurs';
	import { contexteCommentaire } from '$lib/assistant';
	import { richEmpty } from '$lib/publications';
	import {
		pointsConseil,
		type AffaireOuverte,
		type CompteRenduPoint,
		type CrAffaire,
	} from '$lib/api';

	export let pointId: number;
	export let affaire: AffaireOuverte;
	export let cr: CrAffaire | undefined;
	export let onCompteRendu: (cr: CompteRenduPoint) => void;
	export let onFerme: () => void;

	const depart = { contenu: cr?.contenu ?? '', conseilSeul: cr?.conseil_seul ?? false };
	let contenu = depart.contenu;
	let conseilSeul = depart.conseilSeul;
	let enCours = false;
	/** Fermé par « Annuler » ou après « Sauvegarder » : rien à garder en brouillon. */
	let regle = false;

	$: modifie = contenu !== depart.contenu || conseilSeul !== depart.conseilSeul;

	async function ecrire(brouillon: boolean) {
		const corps = {
			contenu: richEmpty(contenu) ? '' : contenu,
			brouillon,
			conseil_seul: conseilSeul,
		};
		onCompteRendu(await pointsConseil.ecrireCr(pointId, affaire.id, corps));
	}

	async function sauvegarder() {
		enCours = true;
		try {
			await ecrire(false);
			regle = true;
			onFerme();
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
		if (regle || !modifie) return;
		ecrire(true).catch((e) => toast('error', messageErreur(e, 'Brouillon non enregistré')));
	});
</script>

<form class="saisie-cr" on:submit|preventDefault={sauvegarder}>
	<SectionDescription
		premiere
		pliable={false}
		idPrefixe="cr-{affaire.id}"
		idChamp="contenu"
		titre="Compte rendu"
		hauteur="18rem"
		placeholder="Ce qui a été dit, décidé, et qui fait quoi."
		assistant={contexteCommentaire({ titre: affaire.titre, description: affaire.apercu })}
		assistantAvecTitre={false}
		bind:valeur={contenu}
	/>
	<label class="case">
		<input type="checkbox" bind:checked={conseilSeul} />
		<Icon name="shield-check" size={14} /> Conseil seul — lu par le conseil syndical seulement
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
</style>
