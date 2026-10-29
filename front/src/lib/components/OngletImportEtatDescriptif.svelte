<!--
  L'atelier de l'ÉTAT DESCRIPTIF du règlement — Admin › Imports, source « État descriptif » (#2213).

  La liste du syndic dit qui possède quoi ; l'état descriptif dit ce qu'est chaque
  lot : sa nature, sa porte ou sa place, son niveau, la circulation qui le dessert
  et ses tantièmes (spec `specs/architecture/lots-et-perimetres.md`). Le fichier
  entre dans une table de passage et ne touche au patrimoine qu'au geste
  « Appliquer », une fois TOUS les contrôles passés — la règle vit côté serveur
  (`utils/etat_descriptif`), l'écran ne fait que la montrer.

  ## L'ordre de l'écran suit l'ordre du travail

  1. téléverser (le gabarit vide se télécharge à côté) ;
  2. dire la lettre de l'acte de chaque bâtiment — une correspondance SAISIE,
     jamais déduite de l'ordre ;
  3. lire les contrôles : un bloquant ferme l'application, un « à savoir » (somme qui
     ne tombe pas juste, lot absent d'un côté) ne la ferme pas et se rappelle à la
     confirmation ;
  4. relire les lignes, puis appliquer.

  ## Sans tableau : l'assistant lit le règlement (#2218)

  Une copropriété qui n'a que son règlement (versé dans Ma résidence › Règlement)
  demande à l'assistant de le lire : il rend le MÊME tableau qu'un fichier, rangé
  dans la même table de passage, et passe par les mêmes contrôles. La lecture dure
  plusieurs minutes — au-delà de ce qu'une requête peut attendre derrière le
  mandataire : elle tourne en tâche de fond, et l'écran relit l'atelier toutes les
  dix secondes tant qu'elle est en cours (minuterie arrêtée à la sortie de l'écran).

  🔴 Le fichier d'une copropriété réelle ne s'enregistre nulle part ailleurs que
  dans sa table de passage : le dépôt est public.
-->
<script lang="ts">
	import { onDestroy, onMount } from 'svelte';
	import BarreImport from '#lib/components/BarreImport.svelte';
	import ConstatsLots from '#lib/components/ConstatsLots.svelte';
	import EtatListe from '#lib/components/EtatListe.svelte';
	import Icon from '#lib/components/Icon.svelte';
	import IconeIA from '#lib/components/IconeIA.svelte';
	import TableLignesEtatDescriptif from '#lib/components/TableLignesEtatDescriptif.svelte';
	import { toast } from '#lib/components/Toast.svelte';
	import {
		etatDescriptif as api,
		type EtatDescriptif,
		type LigneEtatDescriptif,
	} from '#lib/api/index.ts';
	import { confirmer } from '#lib/confirmation.ts';
	import { fmtDatetime } from '#lib/date.ts';
	import { messageErreur } from '#lib/erreurs.ts';
	import { contientTousLesMots } from '#lib/texte.ts';

	let etat: EtatDescriptif | null = null;
	let chargement = true;
	let televersement = false;
	let enregistrement = false;
	let application = false;
	let lancement = false;
	/** La relecture programmée pendant que l'assistant lit le règlement. */
	let sonde: ReturnType<typeof setTimeout> | undefined;
	const INTERVALLE_SONDE_MS = 10_000;
	let recherche = '';
	/** La lettre saisie pour chaque bâtiment, par identifiant. */
	let lettres: Record<number, string> = {};

	function recevoir(lu: EtatDescriptif) {
		etat = lu;
		lettres = Object.fromEntries(lu.batiments.map((b) => [b.id, b.lettre_rcp ?? '']));
		clearTimeout(sonde);
		if (lu.lecture_ia === 'en_cours') sonde = setTimeout(sonder, INTERVALLE_SONDE_MS);
	}

	/** Relit l'atelier ; à l'issue de la lecture, la dit une fois. */
	async function sonder() {
		try {
			recevoir(await api.lire());
		} catch {
			sonde = setTimeout(sonder, INTERVALLE_SONDE_MS);
			return;
		}
		if (etat?.lecture_ia === 'terminee')
			toast(
				'success',
				`${etat.lignes.length} lot(s) lu(s) dans le règlement — relisez les contrôles, rien n'est encore appliqué`,
			);
		else if (etat?.lecture_ia === 'echec')
			toast('error', etat.erreur_ia ?? 'La lecture du règlement a échoué');
	}
	onDestroy(() => clearTimeout(sonde));

	async function lireReglement() {
		const ok = await confirmer({
			titre: 'Remplir depuis le règlement',
			message:
				"L'assistant lit le règlement versé dans Ma résidence et en tire le tableau des lots, " +
				'comme un fichier importé. La lecture prend plusieurs minutes et remplace ce qui ' +
				'attend ; rien ne touche au patrimoine avant « Appliquer ».',
			libelleConfirmer: 'Lancer la lecture',
		});
		if (!ok) return;
		lancement = true;
		try {
			recevoir(await api.lireReglement());
		} catch (e) {
			toast('error', messageErreur(e, 'Lecture refusée'));
		} finally {
			lancement = false;
		}
	}

	async function charger() {
		try {
			recevoir(await api.lire());
		} catch (e) {
			toast('error', messageErreur(e, "Lecture de l'état descriptif impossible"));
		} finally {
			chargement = false;
		}
	}
	onMount(charger);

	async function televerser(fichier: File) {
		televersement = true;
		try {
			recevoir(await api.televerser(fichier));
			toast('success', `${etat?.lignes.length ?? 0} lot(s) lu(s) — rien n'est encore appliqué`);
		} catch (e) {
			toast('error', messageErreur(e, 'Import refusé'));
		} finally {
			televersement = false;
		}
	}

	async function enregistrerLettres() {
		if (!etat) return;
		enregistrement = true;
		try {
			recevoir(
				await api.saisirLettres(
					etat.batiments.map((b) => ({
						batiment_id: b.id,
						lettre_rcp: lettres[b.id]?.trim() || null,
					})),
				),
			);
			toast('success', 'Correspondance enregistrée');
		} catch (e) {
			toast('error', messageErreur(e));
		} finally {
			enregistrement = false;
		}
	}

	async function appliquer() {
		if (!etat?.applicable) return;
		const ok = await confirmer({
			titre: 'Appliquer au patrimoine',
			message:
				`${etat.lignes.length} lot(s) recevront leur nature, leur circulation et leurs ` +
				'tantièmes ; les caves et les places seront situées dans le bâtiment que dit le ' +
				'règlement. Rejouer le même fichier ensuite ne change rien.' +
				(avertissements.length
					? ` ${avertissements.length} point(s) à savoir ne bloquent pas : ils restent à compléter.`
					: ''),
			libelleConfirmer: 'Appliquer',
		});
		if (!ok) return;
		application = true;
		try {
			const bilan = await api.appliquer();
			toast(
				'success',
				`${bilan.lots} lot(s) désigné(s), ${bilan.quotes_modifiees} tantième(s) posé(s) ou ` +
					`modifié(s), ${bilan.perimetres_modifies} périmètre(s) recalculé(s)`,
			);
			await charger();
		} catch (e) {
			toast('error', messageErreur(e, 'Application refusée'));
		} finally {
			application = false;
		}
	}

	function ligneLue(l: LigneEtatDescriptif): (string | null)[] {
		return [l.lot, l.batiment, l.nature, l.numero_usage, l.niveau, l.circulation, l.lot_origine];
	}

	$: bloquants =
		etat?.constats.filter((c) => c.gravite === 'bloquant' || c.gravite === 'inconnu') ?? [];
	$: avertissements = etat?.constats.filter((c) => c.gravite === 'avertissement') ?? [];
	$: affichees = (etat?.lignes ?? []).filter((l) => contientTousLesMots(ligneLue(l), recherche));
	$: lettresSaisies = new Set(Object.values(lettres).map((l) => l.trim().toUpperCase()));
	$: lectureEnCours = etat?.lecture_ia === 'en_cours';
	/** Une lecture en cours ou échouée n'a encore rien posé : ni tuiles ni contrôles. */
	$: sansLignes = !etat?.importe_le || lectureEnCours || etat?.lecture_ia === 'echec';
	$: lettresManquantes = (etat?.lettres_citees ?? []).filter((l) => !lettresSaisies.has(l));
</script>

<BarreImport
	tuiles={etat && !sansLignes
		? [
				{ valeur: etat.lignes.length, libelle: 'Lots lus' },
				{ valeur: etat.cles.length, libelle: 'Clés de charges' },
				{ valeur: bloquants.length, libelle: 'Bloquants', couleur: 'var(--color-danger)' },
				{
					valeur: avertissements.length,
					libelle: 'À savoir',
					couleur: 'var(--color-warning-texte)',
				},
			]
		: []}
	colonnesAttendues="lot | batiment | nature | numero_usage | niveau | circulation | lot_origine | source | <clé> /<dénominateur>…"
	libelleRemplacer=""
	enCours={televersement}
	bind:recherche
	idRecherche="etat-descriptif-recherche"
	exempleRecherche="N° de lot, bâtiment, nature, porte ou place…"
	rechercheDans="lot, bâtiment, nature, porte ou place, niveau, circulation et lot d'origine"
	compte={affichees.length}
	on:importer={(e) => televerser(e.detail.fichier)}
>
	<p slot="preparer" class="aide gabarit">
		<a href={api.gabaritUrl()} download>Télécharger le gabarit vide</a> — les en-têtes seuls, une colonne
		par clé de charges à ajouter sur le modèle de la dernière.
	</p>
	<div slot="autrement">
		{#if etat?.ia_disponible}
			<div class="autrement">
				<p class="aide">
					Pas de tableau ? L'assistant peut lire l'état descriptif dans le règlement versé (Ma
					résidence › Règlement) et remplir l'atelier à votre place.
				</p>
				<button
					class="btn btn-outline btn-sm"
					type="button"
					on:click={lireReglement}
					disabled={lancement || lectureEnCours}
					aria-busy={lancement || lectureEnCours}
				>
					<IconeIA enCours={lancement || lectureEnCours} />
					{lectureEnCours ? 'L’assistant lit le règlement…' : 'Remplir depuis le règlement'}
				</button>
			</div>
		{/if}
	</div>
</BarreImport>

{#if chargement}
	<EtatListe chargement />
{:else if etat}
	<section class="card config-section">
		<h2 class="config-section-title"><Icon name="building-2" size={17} />Lettres de l'acte</h2>
		<p class="config-section-intro muted">
			Le règlement nomme les bâtiments par une lettre ou un numéro qui n'est pas forcément celui de
			l'application. La correspondance se saisit ici — elle ne se déduit jamais de l'ordre.
		</p>
		<div class="lettres">
			{#each etat.batiments as b (b.id)}
				<label class="field">
					{b.libelle}
					<input
						type="text"
						maxlength="8"
						autocomplete="off"
						bind:value={lettres[b.id]}
						placeholder="Lettre de l'acte"
					/>
				</label>
			{/each}
		</div>
		{#if etat.lettres_citees.length}
			<p class="aide">
				Le fichier cite : {etat.lettres_citees.join(', ')}.
				{#if lettresManquantes.length}
					<strong class="manquantes">Sans correspondance : {lettresManquantes.join(', ')}.</strong>
				{/if}
			</p>
		{/if}
		<div class="form-actions largeur-saisie">
			<button
				class="btn btn-primary"
				on:click={enregistrerLettres}
				disabled={enregistrement}
				aria-busy={enregistrement}
			>
				{enregistrement ? 'Enregistrement…' : 'Enregistrer'}
			</button>
		</div>
	</section>

	{#if lectureEnCours}
		<div class="empty-state card" role="status">
			<h3>L'assistant lit le règlement</h3>
			<p>
				Quelques minutes : l'écran se met à jour seul, et vous pouvez le quitter. Le tableau
				arrivera ici, avec ses contrôles — rien ne sera appliqué sans vous.
			</p>
		</div>
	{:else if etat.lecture_ia === 'echec'}
		<div class="empty-state card" role="alert">
			<h3>La lecture du règlement a échoué</h3>
			<p>{etat.erreur_ia ?? 'Réessayez, ou importez un fichier.'}</p>
		</div>
	{:else if !etat.importe_le}
		<div class="empty-state card">
			<h3>Aucun état descriptif</h3>
			<p>
				Téléchargez le gabarit, recopiez-y l'état descriptif du règlement, puis importez-le : rien
				ne touche au patrimoine avant le geste « Appliquer ».
			</p>
		</div>
	{:else}
		<section class="card config-section">
			<h2 class="config-section-title"><Icon name="shield-check" size={17} />Contrôles</h2>
			<ConstatsLots constats={etat.constats} videTexte="Aucun constat : le fichier tombe juste." />
		</section>

		<section class="card config-section">
			<h2 class="config-section-title"><Icon name="clipboard-list" size={17} />Lignes lues</h2>
			{#if affichees.length === 0}
				<p class="muted">Aucune ligne pour cette recherche.</p>
			{:else}
				<TableLignesEtatDescriptif lignes={affichees} toutes={etat.lignes} cles={etat.cles} />
			{/if}
		</section>

		<div class="card config-section application">
			<p class="muted">
				{#if etat.applique_le}
					Appliqué le {fmtDatetime(etat.applique_le)}. Importez un nouveau fichier pour le
					remplacer.
				{:else if etat.applicable}
					{#if avertissements.length}
						Aucun contrôle ne bloque. {avertissements.length} point(s) à savoir resteront à compléter
						après l'application.
					{:else}
						Tous les contrôles sont passés.
					{/if}
				{:else}
					Un contrôle bloque : corrigez le fichier ou la correspondance, puis réimportez.
				{/if}
			</p>
			<button
				class="btn btn-primary"
				on:click={appliquer}
				disabled={!etat.applicable || application}
				aria-busy={application}
			>
				{application ? 'Application…' : 'Appliquer au patrimoine'}
			</button>
		</div>
	{/if}
{/if}

<style>
	/*  Une lettre tient en un caractère : le champ prend la largeur de son contenu
	    (`ux-patterns` §9 bis), plusieurs bâtiments par ligne, et passe à la ligne. */
	.lettres {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(8rem, 11rem));
		gap: 0.75rem 1rem;
	}
	.gabarit {
		margin: 0 0 0.75rem;
	}
	.autrement {
		display: flex;
		flex-direction: column;
		align-items: flex-start;
		gap: 0.4rem;
		margin-top: 1rem;
		padding-top: 0.75rem;
		border-top: 1px solid var(--color-border);
	}
	.autrement p {
		margin: 0;
	}
	.manquantes {
		color: var(--color-danger);
	}
	.application {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		justify-content: space-between;
		gap: 0.75rem;
	}
	.application p {
		margin: 0;
	}
</style>
