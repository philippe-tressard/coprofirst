<!--
  **Une liste de membres de l'annuaire de l'espace CS** — conseil syndical ou
  syndic : son chargement, ses fiches, leurs gestes, et « + Nouveau membre ».

  ## 🔴 Pourquoi ce composant (#1539, 02/10/2026)

  `AnnuaireConseil` et `AnnuaireSyndic`, sortis ensemble d'`espace-cs` le
  29/09 (#779), portaient le MÊME squelette : mêmes imports (`listeDepliable`,
  `accordeon`, `CarteMembre`, `EtatListe`), mêmes états (`chargement`,
  `enregistrementIdx`, l'état dépliable), même amorçage `try / catch / finally`,
  mêmes `ajouter` / `retirer` / `delier`, même enregistrement d'une fiche, la
  même boucle câblant sept événements, et le même bouton d'ajout. Soixante
  lignes sur cent quatre-vingt-deux. C'est la duplication que `CarteMembre`
  avait retirée de la FICHE, revenue d'un cran au-dessus — dans son câblage
  (`standards/02` §4 quinquies).

  ## Ce que la liste porte, et ce que chaque côté déclare

  | Porté ici | Déclaré par l'appelant |
  |---|---|
  | le chargement et son échec | ce qu'on charge (`charger`), et l'en-tête qu'il remplit |
  | l'état dépliable, l'accordéon commun aux deux listes | — |
  | ajouter, retirer, délier, enregistrer une fiche | le membre vierge (`nouveau`), l'envoi (`envoyer`) |
  | refuser un enregistrement, avec son motif | le motif (`refus`) — le syndic exige un téléphone |
  | monter / descendre, sauvegardés en silence | `ordonnable` — l'ordre du syndic est celui que lit un arrivant |
  | — | les gestes en plus (`gestes`), l'accent, le rapprochement par le NOM (`surNom`) |
  | — | le contenu des fiches, par les emplacements de `CarteMembre` |

  L'en-tête (AG du conseil, `EnteteSyndic`) reste chez l'appelant : ce sont
  deux objets différents. Il reçoit l'enregistrement commun par l'emplacement
  `entete` (`let:enregistrer`), parce que l'en-tête et chaque fiche envoient la
  même charge utile, entière.
-->
<script lang="ts" generics="T extends MembreBase">
	import { onDestroy, onMount } from 'svelte';
	import { listeMembre } from '#lib/accordeon.ts';
	import { toast } from '#lib/components/Toast.svelte';
	import { tenter } from '#lib/erreurs.ts';
	import { nomAffiche } from '#lib/noms.ts';
	import {
		REPLIE,
		ajouter,
		basculer,
		editer,
		retirer,
		type EtatDepliable,
	} from '#lib/listeDepliable.ts';
	import { type Geste } from '#lib/components/ActionsMembre.svelte';
	import CarteMembre, { type MembreBase } from '#lib/components/CarteMembre.svelte';
	import EtatListe from '#lib/components/EtatListe.svelte';

	/** Les membres — liés (`bind:membres`) : l'appelant les lit pour ses rapprochements. */
	export let membres: T[] = [];
	/** Charge la liste — et, au passage, ce que l'appelant affiche dans son en-tête. */
	export let charger: () => Promise<T[]>;
	/** Un membre vierge, pour « + Nouveau membre ». */
	export let nouveau: () => T;
	/** Envoie la liste ENTIÈRE : l'en-tête et chaque fiche partent ensemble. */
	export let envoyer: (membres: T[]) => Promise<unknown>;
	/** Ce qui empêche d'enregistrer ce membre, ou `null`. */
	export let refus: (m: T) => string | null = () => null;
	/** Le libellé du bouton d'ajout. */
	export let libelleAjout: string;
	/** La bordure de rôle d'une fiche (`CarteMembre`). */
	export let accent: (m: T) => 'president' | 'principal' | null = () => null;
	/** L'ordre COMPTE : ↑ / ↓ sur chaque fiche, l'ordre sauvegardé en silence. */
	export let ordonnable = false;
	/** Les gestes propres à cette liste, rendus après ↑ / ↓. */
	export let gestes: (i: number, m: T) => Geste[] = () => [];
	/** Le NOM d'une fiche vient d'être saisi : l'appelant y rapproche ce qu'il sait. */
	export let surNom: (i: number) => void = () => {};

	let chargement = true;
	let enregistrement = false;
	let enregistrementIdx: number | null = null;
	//  La mécanique déplier/éditer/ajouter/retirer : `#lib/listeDepliable` (#640).
	let etat: EtatDepliable = REPLIE;
	//  L'accordéon (30/09/2026) : conseil et syndic n'ont qu'une carte ouverte À
	//  EUX DEUX (`listeMembre`).
	const liste = listeMembre(
		'annuaires',
		() => etat,
		(e) => (etat = e),
	);
	onDestroy(liste.liberer);

	onMount(async () => {
		try {
			membres = await charger();
		} catch {
			toast('error', 'Erreur chargement annuaire');
		} finally {
			chargement = false;
		}
	});

	function ajouterMembre() {
		membres = [...membres, nouveau()];
		liste.ouvrir(ajouter(membres.length));
	}
	function retirerMembre(i: number) {
		membres = membres.filter((_, j) => j !== i);
		etat = retirer(etat, i);
	}
	function delier(i: number) {
		membres[i] = { ...membres[i], user_id: null };
		membres = [...membres];
	}

	async function deplacer(i: number, sens: -1 | 1) {
		const j = i + sens;
		if (j < 0 || j >= membres.length) return;
		const copie = [...membres];
		[copie[i], copie[j]] = [copie[j], copie[i]];
		membres = copie;
		etat = REPLIE;
		// Sauvegarde silencieuse de l'ordre
		try {
			await envoyer(copie);
		} catch {
			/* silencieux */
		}
	}

	/** ↑ (sauf en tête) et ↓ (désactivé en dernier), quand l'ordre compte. */
	function gestesOrdre(i: number): Geste[] {
		if (!ordonnable) return [];
		const ordre: Geste[] = [];
		if (i > 0)
			ordre.push({
				variante: 'deplacer',
				libelle: 'Monter',
				icone: 'arrow-up',
				onClic: () => deplacer(i, -1),
			});
		ordre.push({
			variante: 'deplacer',
			libelle: 'Descendre',
			icone: 'arrow-down',
			desactive: i === membres.length - 1,
			onClic: () => deplacer(i, 1),
		});
		return ordre;
	}

	/** L'en-tête enregistre la liste entière : chaque membre doit pouvoir l'être. */
	async function enregistrerEnTete(succes: string): Promise<boolean> {
		const fautif = membres.find((m) => refus(m));
		if (fautif) {
			toast('error', `${refus(fautif)} pour ${nomAffiche(fautif) || '…'}`);
			return false;
		}
		enregistrement = true;
		const ok = await tenter(() => envoyer(membres), succes);
		enregistrement = false;
		return ok;
	}

	async function enregistrerMembre(i: number) {
		const motif = refus(membres[i]);
		if (motif) {
			toast('error', motif);
			return;
		}
		enregistrementIdx = i;
		if (await tenter(() => envoyer(membres), `${nomAffiche(membres[i])} enregistré`)) etat = REPLIE;
		enregistrementIdx = null;
	}
</script>

{#if chargement}
	<EtatListe chargement />
{:else}
	<slot name="entete" {enregistrement} enregistrer={enregistrerEnTete} />

	{#each membres as m, i (m)}
		<CarteMembre
			bind:membre={membres[i]}
			ouvert={etat.ouvert === i}
			edite={etat.edite === i}
			enregistrement={enregistrementIdx === i}
			accent={accent(m)}
			gestes={[...gestesOrdre(i), ...gestes(i, m)]}
			detailPropre={$$slots.detail}
			on:basculer={() => liste.ouvrir(basculer(etat, i))}
			on:editer={() => liste.ouvrir(editer(i))}
			on:supprimer={() => retirerMembre(i)}
			on:enregistrer={() => enregistrerMembre(i)}
			on:annuler={() => (etat = REPLIE)}
			on:nom={() => surNom(i)}
			on:delier={() => delier(i)}
		>
			<svelte:fragment slot="badge"><slot name="badge" membre={m} index={i} /></svelte:fragment>
			<svelte:fragment slot="champs"><slot name="champs" membre={m} index={i} /></svelte:fragment>
			<svelte:fragment slot="edition"><slot name="edition" membre={m} index={i} /></svelte:fragment>
			<svelte:fragment slot="detail"><slot name="detail" membre={m} index={i} /></svelte:fragment>
			<svelte:fragment slot="resume"><slot name="resume" membre={m} index={i} /></svelte:fragment>
		</CarteMembre>
	{/each}

	<button type="button" class="btn btn-sm btn-outline ajout-membre" on:click={ajouterMembre}>
		{libelleAjout}
	</button>
{/if}

<style>
	/*  Le bouton « + Nouveau membre » sous les fiches. Il vivait dans
	    `composants.css` tant que deux composants l'écrivaient (#779) ; il n'en
	    reste qu'un, et le style suit son balisage (#1539). */
	.ajout-membre {
		margin-top: 0.5rem;
	}
</style>
