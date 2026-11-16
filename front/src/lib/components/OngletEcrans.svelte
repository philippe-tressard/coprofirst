<!--
  Espace CS › Écrans du hall (#2770) — appairer, voir, retirer.

  Un écran de hall est un APPAREIL (une Apple TV branchée sur un écran), pas une
  personne : il n'a pas de compte. Il affiche un code court ; un membre du conseil
  le saisit ici avec un nom et un périmètre, et l'écran reçoit son accès — qui ne
  lit que les annonces de hall de ce périmètre (`api/app/utils/ecran_affiches.py`).

  La forme est celle de toute liste du site : l'action primaire sur sa rangée
  (`BoutonNouveau`), la boîte de création dans la page (`FormulaireCreation`,
  `ux-patterns` §14), la liste et ses trois états (`EtatListe`), le retrait
  confirmé en rouge comme la révocation d'une délégation.
-->
<script lang="ts">
	import { onDestroy } from 'svelte';
	import Badge from '#lib/components/Badge.svelte';
	import BadgePerimetre from '#lib/components/BadgePerimetre.svelte';
	import BoutonNouveau from '#lib/components/BoutonNouveau.svelte';
	import EtatListe from '#lib/components/EtatListe.svelte';
	import EtoileRequis from '#lib/components/EtoileRequis.svelte';
	import FormulaireCreation from '#lib/components/FormulaireCreation.svelte';
	import PerimetrePicker from '#lib/components/PerimetrePicker.svelte';
	import PiedFormulaire from '#lib/components/PiedFormulaire.svelte';
	import { toast } from '#lib/components/Toast.svelte';
	import { ecrans as ecransApi, type EcranHall } from '#lib/api/index.ts';
	import { confirmer } from '#lib/confirmation.ts';
	import { fmtDateShort, fmtDatetime } from '#lib/date.ts';
	import { messageErreur } from '#lib/erreurs.ts';
	import { perimetreDefautListe } from '#lib/utils.ts';
	import { SEPARATEUR } from '#lib/separateurs.ts';
	import { marquerDonneesAffichees } from '#lib/telemetry.ts';

	/**  Le temps qu'un écran met à venir chercher son accès : il interroge toutes les
	 *   5 secondes (`appairage_ecran.INTERVALLE`). La liste se relit une fois après. */
	const RELECTURE_APRES_APPAIRAGE_MS = 8000;

	let liste: EcranHall[] = [];
	let chargement = true;
	let erreur = '';

	let ouvert = false;
	let code = '';
	let nom = '';
	let perimetre: string[] = perimetreDefautListe();
	let enCours = false;
	let relecture: ReturnType<typeof setTimeout> | undefined;

	/**  Le code tel que l'écran l'affiche (`BCDF-GHJK`) : huit lettres, tiret et casse libres. */
	$: lettres = code.toUpperCase().replace(/[^A-Z]/g, '');
	$: complet = lettres.length === 8 && nom.trim() !== '' && perimetre.length === 1;

	async function charger() {
		try {
			liste = await ecransApi.lister();
			erreur = '';
		} catch (e) {
			erreur = messageErreur(e);
		} finally {
			chargement = false;
			marquerDonneesAffichees();
		}
	}
	charger();
	onDestroy(() => clearTimeout(relecture));

	function fermer() {
		ouvert = false;
		code = '';
		nom = '';
		perimetre = perimetreDefautListe();
	}

	async function appairer() {
		if (!complet) return;
		enCours = true;
		try {
			const r = await ecransApi.confirmer({
				code_court: lettres,
				nom: nom.trim(),
				perimetre: perimetre[0],
			});
			toast(
				'success',
				`« ${r.nom} » est appairé : l'écran reçoit son accès dans quelques secondes.`,
			);
			fermer();
			clearTimeout(relecture);
			relecture = setTimeout(charger, RELECTURE_APRES_APPAIRAGE_MS);
		} catch (e) {
			toast('error', messageErreur(e));
		} finally {
			enCours = false;
		}
	}

	async function retirer(e: EcranHall) {
		const ok = await confirmer({
			titre: 'Retirer cet écran',
			message: `« ${e.nom} » cessera aussitôt d'afficher les annonces. Pour le remettre en service, il faudra l'appairer de nouveau.`,
			libelleConfirmer: 'Retirer',
			danger: true,
		});
		if (!ok) return;
		try {
			await ecransApi.retirer(e.id);
			liste = liste.filter((x) => x.id !== e.id);
			toast('success', 'Écran retiré');
		} catch (err) {
			toast('error', messageErreur(err));
		}
	}
</script>

<div class="actions-onglet">
	<BoutonNouveau {ouvert} libelle="Appairer un écran" on:basculer={() => (ouvert = true)} />
</div>

{#if ouvert}
	<FormulaireCreation titre="Appairer un écran">
		<form on:submit|preventDefault={appairer}>
			<p class="aide">
				Sur l'écran du hall, ouvrez l'application CoproFirst : elle affiche un code de huit lettres,
				valable dix minutes. Saisissez-le ici.
			</p>
			<div class="field">
				<label for="ecran-code"
					>Code affiché par l'écran<EtoileRequis vide={lettres.length !== 8} /></label
				>
				<input
					id="ecran-code"
					class="champ-code"
					type="text"
					bind:value={code}
					autocomplete="off"
					autocapitalize="characters"
					spellcheck="false"
					maxlength="12"
					placeholder="BCDF-GHJK"
				/>
			</div>
			<div class="field">
				<label for="ecran-nom">Nom de l'écran<EtoileRequis vide={!nom.trim()} /></label>
				<input
					id="ecran-nom"
					type="text"
					bind:value={nom}
					maxlength="80"
					placeholder="Hall du bâtiment 2"
				/>
			</div>
			<PerimetrePicker mode="single" titre="Annonces affichées" bind:value={perimetre} />
			<p class="aide">
				L'écran affiche le titre, le message et les photos des annonces de hall en cours qui
				concernent ce périmètre, sans l'auteur ni les destinataires. Il ne peut rien modifier.
			</p>
			<PiedFormulaire {enCours} desactive={!complet} on:annule={fermer} />
		</form>
	</FormulaireCreation>
{/if}

{#if chargement || erreur || liste.length === 0}
	<EtatListe
		{chargement}
		{erreur}
		vide={!chargement && !erreur && liste.length === 0}
		titreVide="Aucun écran appairé"
		messageVide="Un écran appairé fait défiler les annonces de hall dans le hall de la résidence."
	/>
{:else}
	<ul class="ecrans">
		{#each liste as e (e.id)}
			<li class="card ecran">
				<div class="ecran-corps">
					<div class="ecran-titre">
						<strong>📺 {e.nom}</strong>
						<BadgePerimetre libelle={e.perimetre_libelle} />
						{#if e.echu}
							<Badge teinte="badge-gray" compact>Échu : à appairer de nouveau</Badge>
						{/if}
					</div>
					<span class="text-muted-sm">
						{e.vu_le
							? `Dernière lecture : ${fmtDatetime(e.vu_le)}`
							: 'Aucune lecture pour le moment'}{SEPARATEUR.point}appairé le {fmtDateShort(
							e.cree_le,
						)}
					</span>
				</div>
				<button
					class="btn btn-sm btn-danger"
					aria-label={`Retirer l'écran ${e.nom}`}
					on:click={() => retirer(e)}>Retirer</button
				>
			</li>
		{/each}
	</ul>
{/if}

<style>
	.ecrans {
		list-style: none;
		margin: 0;
		padding: 0;
		display: flex;
		flex-direction: column;
		gap: 0.6rem;
	}
	.ecran {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 1rem;
		flex-wrap: wrap;
		padding: 0.9rem 1.1rem;
	}
	.ecran-corps {
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
		min-width: 0;
		flex: 1;
	}
	.ecran-titre {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		flex-wrap: wrap;
	}
	.ecran-titre strong {
		overflow-wrap: anywhere;
	}
	/*  Le code se lit lettre à lettre, comme l'écran l'affiche. */
	.champ-code {
		font-family: var(--font-mono, monospace);
		letter-spacing: 0.12em;
		text-transform: uppercase;
		max-width: 14rem;
	}
</style>
