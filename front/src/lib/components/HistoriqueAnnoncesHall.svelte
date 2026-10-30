<!--
  **L'historique des affiches de hall** — la liste, ses archives, et les gestes
  qui s'y appliquent : archiver, renvoyer au CS, télécharger, supprimer.

  Extrait d'`OngletAnnoncesHall` le 01/09/2026, sur refus du contrôle de
  modularité quand l'onglet a reçu les trois canaux de la Diffusion (#480).
  Le refus désignait un **placement** : cet onglet portait deux vues sans rapport
  — un formulaire de création et une liste d'archives —, et seule la première
  avait déjà son composant (`FormulaireAnnonceHall`).

  ⚠️ Il **charge lui-même** sa liste : l'onglet n'a plus à savoir qu'une vue doit
  être amorcée quand on l'ouvre. Après une création, l'hôte appelle `recharger()`
  — c'est le seul lien qui subsiste, et il va dans un seul sens.

  🔴 Les styles voyagent avec le balisage qui les emploie : Svelte scope au
  composant qui rend l'élément, et les laisser chez l'hôte livrerait cette liste
  entièrement NUE (la panne des pastilles de la v2.67.11, refaite deux fois).
-->
<script lang="ts">
	import { onMount } from 'svelte';

	import { annoncesHall as annoncesHallApi } from '#lib/api/index.ts';
	import { messageErreur, tenter } from '#lib/erreurs.ts';
	import type { AnnonceHall } from '#lib/api/index.ts';
	import CarteListe from '#lib/components/CarteListe.svelte';
	import EnteteCarte from '#lib/components/EnteteCarte.svelte';
	import MarqueIA from '#lib/components/MarqueIA.svelte';
	import BadgePerimetre from '#lib/components/BadgePerimetre.svelte';
	import FichiersUpload from '#lib/components/FichiersUpload.svelte';
	import ApercuCarte from '#lib/components/ApercuCarte.svelte';
	import AuteurCarte from '#lib/components/AuteurCarte.svelte';
	import IconeAction from '#lib/components/IconeAction.svelte';
	import { toast } from '#lib/components/Toast.svelte';
	import { fmtDatetimeShort as fmtDatetime } from '#lib/date.ts';
	import { basculer } from '#lib/accordeon.ts';
	import { safeHtml } from '#lib/sanitize.ts';
	import { isAdmin } from '#lib/stores/auth.ts';
	import { confirmer } from '#lib/confirmation.ts';
	import { fmtOctets } from '#lib/utils.ts';
	import EtatListe from '#lib/components/EtatListe.svelte';

	let ahList: AnnonceHall[] = [];
	let ahLoading = false;
	/*  🔴 Sans cette variable, un chargement en échec laissait `ahList` à `[]` et
	    l'écran répondait « Aucune annonce ». Le toast d'erreur, lui, s'efface au
	    bout de quelques secondes ; l'affirmation, non. C'est l'incident #519
	    reproduit ici (#816). */
	let erreur = '';
	let ahLoaded = false;
	let ahExpandedId: number | null = null;

	onMount(() => loadAnnoncesHall());

	/** Rechargement demandé par l'hôte — après une création, par exemple. */
	export async function recharger() {
		await loadAnnoncesHall(true);
	}

	async function loadAnnoncesHall(force = false) {
		if (ahLoaded && !force) return;
		ahLoading = true;
		erreur = '';
		try {
			//  🔴 UNE SEULE liste — actives ET archivées (10/09/2026).
			//
			//  Signalé à l'écran : « il y a l'archive, et dans les archives il y a
			//  encore des archives ; supprime cet archive de bas niveau ». L'onglet
			//  s'appelle déjà « 📁 Archives » ; y remettre un filtre
			//  Annonces / Archives faisait DEUX niveaux du même mot, et obligeait à
			//  chercher dans lequel des deux se trouvait l'affiche qu'on venait de
			//  tirer.
			//
			//  Les archivées restent distinguées par leur badge « Archivée », qui
			//  existait déjà : la distinction n'est pas perdue, elle cesse d'être
			//  une NAVIGATION pour redevenir une information.
			//
			//  ⚠️ Deux appels et non un paramètre « toutes » : le serveur range par
			//  archivage, et la vue les recolle dans l'ordre qu'elle veut — actives
			//  d'abord. Ajouter un troisième régime à l'API pour un besoin d'écran
			//  aurait fait porter au serveur une question de présentation.
			const [actives, archivees] = await Promise.all([
				annoncesHallApi.list(false),
				annoncesHallApi.list(true),
			]);
			ahList = [...actives, ...archivees];
			ahLoaded = true;
		} catch (e) {
			erreur = messageErreur(e, 'Erreur de chargement des annonces');
			//  Le toast PRÉVIENT, l'état d'erreur RESTE. L'un ne remplace pas
			//  l'autre : le toast disparaît, l'écran doit continuer de le dire.
			toast('error', erreur);
		} finally {
			ahLoading = false;
		}
	}

	async function ahArchiver(annonce: AnnonceHall) {
		await tenter(
			async () => {
				await annoncesHallApi.archiver(annonce.id, !annonce.archivee);
				await loadAnnoncesHall(true);
			},
			annonce.archivee ? 'Annonce restaurée' : 'Annonce archivée',
			"Erreur lors de l'archivage",
		);
	}

	async function ahRenvoyer(annonce: AnnonceHall) {
		await tenter(
			async () => {
				await annoncesHallApi.renvoyerEmail(annonce.id);
				await loadAnnoncesHall(true);
			},
			'Annonce renvoyée au CS du périmètre',
			'Erreur lors du renvoi',
		);
	}

	async function ahSupprimer(annonce: AnnonceHall) {
		//  ⚠️ Le message dit ce qui part VRAIMENT — le PDF est effacé du disque par
		//  le serveur, pas seulement la ligne ; les photos restent, car elles sont
		//  souvent celles de l'affaire reprise (#1828). Et il
		//  rappelle l'envoi : une annonce déjà partie par courriel reste dans les
		//  boîtes des destinataires, que la supprimer ici ne rattrape pas.
		const envoyee = annonce.destinataires.length > 0;
		const avertissement = envoyee
			? ' Elle a déjà été envoyée par courriel : les destinataires la gardent.'
			: '';
		if (
			!(await confirmer({
				titre: `Supprimer « ${annonce.titre} » ?`,
				message: `Son PDF sera effacé ; les photos qu'elle reprend restent.${avertissement}`,
				libelleConfirmer: 'Supprimer',
				danger: true,
			}))
		)
			return;
		await tenter(
			async () => {
				await annoncesHallApi.delete(annonce.id);
				await loadAnnoncesHall(true);
			},
			'Annonce supprimée',
			'Erreur lors de la suppression',
		);
	}

	/**  Ce qui CLASSE une affiche dans la gouttière : son format. Le serveur
	 *   l'écrit déjà (`format_label`, « A4 », « A5 ») : il est repris, pas
	 *   réécrit. */
	const classeFormat = (annonce: AnnonceHall) => ({
		icone: 'file-text',
		libelle: `Format ${annonce.format_label}`,
		abrege: annonce.format_label,
	});

	//  Un poids absent ou nul ne s'écrit pas : l'échelle, elle, est `fmtOctets`.
	const ahPoids = (octets: number | null): string => (octets ? fmtOctets(octets) : '');
</script>

{#if ahLoading || erreur || ahList.length === 0}
	<EtatListe
		chargement={ahLoading}
		{erreur}
		vide={ahList.length === 0}
		titreErreur="Impossible d’afficher les annonces de hall"
		titreVide="Aucune annonce"
		messageVide="Créez la première annonce depuis l'onglet « Nouvelle annonce »."
	/>
{:else}
	{#each ahList as annonce (annonce.id)}
		<!--  🔴 La carte de liste du site (`.carte-liste`, `EnteteCarte`) avec sa
		      GOUTTIÈRE — la page Affaires est le standard (10/10/2026) : QUAND,
		      puis CE QUI CLASSE l'affiche.

		      Ce qui la classe, c'est son FORMAT (A4, A5) : c'est lui qui décide de
		      sa taille, de sa mise en page et du panneau où elle s'affiche. Sa
		      provenance (« Actualité ») est un trait de l'objet, pas un classement :
		      elle reste en capsule sur la dernière ligne, comme les marqueurs d'une
		      affaire. Le badge de format quitte donc cette ligne — un seul fait,
		      une place.

		      ⚠️ Le bouton ▲/▼ qui doublait le titre a disparu : `EnteteCarte
		      basculable` rend déjà le chevron, et toute la carte repliée ouvre.
		      Deux affordances pour un geste n'en apprenaient pas plus qu'une. -->
		<CarteListe
			quand={annonce.cree_le}
			classe={classeFormat(annonce)}
			expanded={ahExpandedId === annonce.id}
			onDeplier={() => (ahExpandedId = basculer(ahExpandedId, annonce.id))}
		>
			<EnteteCarte
				titre={annonce.titre}
				basculable
				on:toggle={() => (ahExpandedId = basculer(ahExpandedId, annonce.id))}
			>
				<svelte:fragment slot="actions">
					<!--  🔴 LES ACTIONS SONT DANS L'EN-TÊTE, à droite du titre — jamais
					      en pied de carte (`ux-patterns` §3, signalé à l'écran le
					      10/09/2026). Ordre : PDF · renvoyer · ranger · effacer — le
					      lien d'abord, le destructif en dernier. Au trait
					      (`IconeAction`) : le standard des actions du site. -->
					<a
						class="btn btn-sm btn-outline ah-pdf"
						href={annoncesHallApi.pdfUrl(annonce.id)}
						target="_blank"
						rel="noopener"
						on:click|stopPropagation
					>
						<IconeAction icone="file-text" /> PDF {#if annonce.taille_octets}<span class="ah-poids"
								>{ahPoids(annonce.taille_octets)}</span
							>{/if}
					</a>
					<button
						class="btn-icon"
						title="Renvoyer au CS du périmètre"
						aria-label="Renvoyer cette annonce au CS"
						on:click|stopPropagation={() => ahRenvoyer(annonce)}
						><IconeAction icone="mail" /></button
					>
					<!--  Le geste n'est offert que s'il a un effet (#515, 02/09/2026) :
					      une affiche archivée par le TEMPS ne se restaure pas, et un
					      bouton qui ne ferait rien ne s'affiche pas. -->
					{#if !annonce.archivee || annonce.archivee_manuellement}
						<button
							class="btn-icon"
							title={annonce.archivee ? 'Restaurer' : 'Archiver'}
							aria-label={annonce.archivee ? 'Restaurer cette annonce' : 'Archiver cette annonce'}
							on:click|stopPropagation={() => ahArchiver(annonce)}
							><IconeAction icone={annonce.archivee ? 'undo-2' : 'archive'} /></button
						>
					{/if}
					{#if $isAdmin}
						<button
							class="btn-icon-danger"
							title="Supprimer définitivement"
							aria-label="Supprimer définitivement cette annonce"
							on:click|stopPropagation={() => ahSupprimer(annonce)}
							><IconeAction icone="trash-2" /></button
						>
					{/if}
				</svelte:fragment>
				<!--  L'aperçu passe par l'en-tête, avant la dernière ligne — avec la
				      vignette de la première illustration à droite, comme toute carte. -->
				<svelte:fragment slot="apercu">
					{#if ahExpandedId !== annonce.id}
						<ApercuCarte contenu={annonce.apercu} photos={annonce.images ?? []} dansLigne />
					{/if}
				</svelte:fragment>
				<!--  La dernière ligne, dans l'ordre du site (`ux-patterns` §3) :
				      état · 🔹 · marqueurs · ce qui est propre à l'objet (l'envoi) ·
				      ✍️ auteur · ✨ en fin de ligne. -->
				<svelte:fragment slot="tags">
					{#if annonce.archivee}<span class="badge badge-gray">Archivée</span>{/if}
					<BadgePerimetre perimetre={annonce.perimetre_cible} />
					{#if annonce.ticket_id}<span class="badge badge-gray" title="Générée depuis une actualité"
							>&#x1F4F0; Actualité</span
						>{/if}
					{#if annonce.destinataires.length}
						<span class="badge badge-gray"
							>&#x2709; {annonce.destinataires.length} destinataire{annonce.destinataires.length > 1
								? 's'
								: ''}</span
						>
					{:else}
						<span class="badge badge-orange">Non envoyée</span>
					{/if}
					<AuteurCarte nom={annonce.auteur_nom} />
					<MarqueIA assiste={annonce.assiste_ia} />
				</svelte:fragment>
			</EnteteCarte>

			{#if ahExpandedId === annonce.id}
				<!--  Le corps ne replie pas la carte : on y lit, on y sélectionne. -->
				<div class="carte-corps ah-corps" role="presentation" on:click|stopPropagation>
					<div class="rich-content message-annonce">
						{@html safeHtml(annonce.message)}
					</div>
					{#if annonce.images?.length}
						<div class="bloc-suite">
							<FichiersUpload urls={annonce.images} readonly size={64} />
						</div>
					{/if}
					{#if annonce.destinataires.length}
						<p class="ah-card-meta bloc-suite">
							Envoyée le {fmtDatetime(annonce.envoye_le ?? annonce.cree_le)} à
							{annonce.destinataires.join(', ')}
						</p>
					{/if}
				</div>
			{/if}
		</CarteListe>
	{/each}
{/if}

<style>
	/*  Les règles suivent le balisage qui les emploie : un style laissé chez
	    l'hôte n'atteint pas un enfant (Svelte scope au composant, v2.67.11).
	    Conteneur, survol, dépliage et gouttière viennent de `CarteListe`
	    (`normes.css`). */

	/*  Le retrait de l'en-tête (`EnteteCarte`) : le corps s'aligne sur le titre. */
	.ah-corps {
		padding: 0 0.7rem 0.75rem;
	}
	.ah-card-meta {
		color: var(--color-text-muted);
		font-size: var(--fs-sm);
	}
	.ah-pdf {
		display: inline-flex;
		align-items: center;
		gap: 0.3rem;
	}
	.ah-poids {
		font-size: var(--fs-2xs);
		color: var(--color-text-muted);
	}
	.message-annonce {
		font-size: var(--fs-base);
	}
	.bloc-suite {
		margin-top: 0.6rem;
	}
</style>
