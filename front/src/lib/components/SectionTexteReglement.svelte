<!--
  Ma résidence › Règlement — la section « Texte du règlement ».

  Ce qu'elle montre dépend de qui lit (arbitré le 11/10/2026) :

  | Lecteur | Ce qu'il voit |
  |---|---|
  | copropriétaire | le titre du texte, et les ACTES qui font foi (liens) |
  | conseil syndical | en plus, la fiche technique du texte (fichier, taille, qui l'a chargé) |
  | administration | en plus, le choix des actes montrés et le chargement d'une version |

  Le serveur ne rend la fiche technique qu'au conseil et à l'administration, et
  ce que l'administration peut lier qu'à elle : l'écran ne fait que suivre.

  Les actes sont des documents de la bibliothèque rangés sur Ma résidence ; le
  lien de chacun est calculé par le serveur pour CE lecteur (`lien_document`), et
  un acte qu'il ne peut pas lire n'arrive pas jusqu'ici. Aucun numéro de document
  n'est écrit dans le code : l'application sert d'autres copropriétés.
-->
<script lang="ts">
	import FichiersUpload from '$lib/components/FichiersUpload.svelte';
	import LibelleGroupe from '$lib/components/LibelleGroupe.svelte';
	import { toast } from '$lib/components/Toast.svelte';
	import { reglement as reglementApi, type EtatReglement } from '$lib/api';
	import { fmtDatetime } from '$lib/date';
	import { messageErreur } from '$lib/erreurs';
	import { ACCEPT_TEXTE_REGLEMENT } from '$lib/reglement';
	import { isAdmin, isCS } from '$lib/stores/auth';
	import { fmtNombre } from '$lib/utils';

	export let etat: EtatReglement;
	/** Relit l'état et l'historique — après un chargement ou un choix d'actes. */
	export let onRecharger: () => Promise<void>;

	let fichiers: File[] = [];
	let chargementTexte = false;

	//  Les actes cochés, dans l'ordre où on les coche : c'est l'ordre d'affichage.
	let choisis: number[] = [];
	let choixLu: number[] | null = null;
	$: if (etat.documents_ids && etat.documents_ids !== choixLu) {
		choixLu = etat.documents_ids;
		choisis = [...etat.documents_ids];
	}
	$: choixModifie = !!choixLu && choisis.join(',') !== choixLu.join(',');
	let enregistrementActes = false;

	function cocher(id: number, coche: boolean) {
		choisis = coche ? [...choisis.filter((x) => x !== id), id] : choisis.filter((x) => x !== id);
	}

	async function enregistrerActes() {
		enregistrementActes = true;
		try {
			await reglementApi.choisirDocuments(choisis);
			await onRecharger();
			toast('success', 'Actes enregistrés.');
		} catch (e) {
			toast('error', messageErreur(e));
		} finally {
			enregistrementActes = false;
		}
	}

	async function chargerTexte() {
		const fichier = fichiers[0];
		if (!fichier) return;
		chargementTexte = true;
		try {
			const version = await reglementApi.charger(fichier.name, await fichier.text());
			const nouvelle = version.id !== etat.texte?.id;
			await onRecharger();
			fichiers = [];
			toast('success', nouvelle ? 'Texte du règlement chargé.' : 'Ce texte est déjà en vigueur.');
		} catch (e) {
			toast('error', messageErreur(e));
		} finally {
			chargementTexte = false;
		}
	}
</script>

<section class="card config-section">
	<h3 class="config-section-title">Texte du règlement</h3>
	{#if etat.texte}
		<p class="texte-courant">
			<strong>{etat.texte.titre}</strong>
			{#if $isCS && etat.texte.nom_fichier}
				<span class="aide"
					>{etat.texte.nom_fichier} · {fmtNombre(etat.texte.nb_caracteres ?? 0)} caractères · chargé le
					{fmtDatetime(etat.texte.cree_le)}{etat.texte.charge_par
						? ` par ${etat.texte.charge_par}`
						: ''}{etat.nb_versions > 1 ? ` · version ${etat.nb_versions}` : ''}</span
				>
			{/if}
		</p>
	{:else}
		<p class="aide">
			{$isAdmin
				? "Aucun texte n'est chargé : chargez le règlement pour pouvoir l'interroger."
				: "Aucun texte n'est chargé : l'administration doit charger le règlement avant qu'on puisse l'interroger."}
		</p>
	{/if}

	{#if etat.documents.length}
		<p class="aide">
			L'assistant lit un texte de travail ; seuls les actes font foi. Les consulter :
		</p>
		<ul class="actes">
			{#each etat.documents as d (d.id)}
				<li><a href={d.lien}>{d.titre}</a></li>
			{/each}
		</ul>
	{/if}

	{#if $isAdmin && etat.documents_candidats}
		<LibelleGroupe titre="Actes montrés à côté du texte" id="reglement-actes">
			<div class="choix-actes">
				{#each etat.documents_candidats as c (c.id)}
					<label class="case">
						<input
							type="checkbox"
							checked={choisis.includes(c.id)}
							on:change={(e) => cocher(c.id, e.currentTarget.checked)}
						/>
						<span>{c.titre} <span class="aide">· {c.categorie}</span></span>
					</label>
				{:else}
					<p class="aide">
						Aucun document n'est rangé sur Ma résidence (plans, règlement, PV d'AG) : déposez-y les
						actes pour pouvoir les lier.
					</p>
				{/each}
			</div>
		</LibelleGroupe>
		<p class="aide">
			Ils s'affichent dans l'ordre où vous les cochez, à chacun selon ses droits de lecture.
		</p>
		{#if choixModifie}
			<div class="form-actions">
				<button class="btn btn-primary" disabled={enregistrementActes} on:click={enregistrerActes}
					>{enregistrementActes ? 'Enregistrement…' : 'Enregistrer'}</button
				>
			</div>
		{/if}
	{/if}

	{#if $isAdmin}
		<FichiersUpload
			differe
			bind:fichiers
			max={1}
			accept={ACCEPT_TEXTE_REGLEMENT}
			types="Markdown (.md)"
			label="Choisir le fichier"
			titre={etat.texte ? 'Charger une nouvelle version (Markdown)' : 'Charger le texte (Markdown)'}
		/>
		{#if fichiers.length}
			<div class="form-actions">
				<button class="btn btn-primary" disabled={chargementTexte} on:click={chargerTexte}
					>{chargementTexte ? 'Chargement…' : 'Charger ce texte'}</button
				>
			</div>
		{/if}
	{/if}
	{#if $isCS}
		<p class="aide">
			Le texte reste dans l'application : il n'est ni publié, ni versé au dépôt du code. Les
			questions déjà posées gardent la version qu'elles ont lue.
		</p>
	{/if}
</section>

<style>
	.texte-courant {
		display: flex;
		flex-direction: column;
		gap: 0.15rem;
		margin: 0 0 0.75rem;
	}
	.actes {
		margin: 0.25rem 0 0.75rem;
		padding-left: 1.2rem;
		display: flex;
		flex-direction: column;
		gap: 0.3rem;
	}
	.choix-actes {
		display: flex;
		flex-direction: column;
		gap: 0.4rem;
		margin-top: 0.4rem;
	}
</style>
