<!--
  SectionIntervenant.svelte — la section 6 du cadre : qui intervient.

  Construite le 23/09/2026 (#1092, lot 5). Elle était déclarée « pas encore
  construite » (#1097) et rendue grisée à son rang : les événements du
  calendrier, qui portaient leur prestataire, deviennent des affaires, et ce
  lien ne devait pas se perdre en chemin (seize événements le portent).

  Le conseil seul y désigne le prestataire, et seulement pour une catégorie du
  bâti : ailleurs, la section est rendue INACTIVE par la déclaration `TICKET`
  (`inactivePour`), pas par cette page. Les règles serveur vivent dans
  `api/app/utils/intervenant.py`.

  🆕 Le CADRE de l'intervention (#1445, 28/09/2026) : un prestataire intervient
  sous contrat ou hors contrat. Le choix ne s'offre que s'il a des contrats en
  cours — « hors contrat » n'apprendrait rien d'un prestataire qui n'en a aucun
  (arbitré). Liste construite à la volée : un `<select>`, comme le prestataire
  (`ux-patterns` §0, seuil des listes courtes).

  🆕 PLUSIEURS prestataires, dans l'ordre (#2704, 12/11/2026) : une liste qu'on
  complète (menu « Ajouter »), réordonne (↑ ↓) et allège (✕), sur le modèle des
  Affaires liées. Le premier mène : c'est lui que lisent les clients antérieurs.
  Un seul contrat cadre l'intervention, celui de l'UN d'eux (Q4).
-->
<script lang="ts">
	import { nombreOuNull } from '#lib/utils.ts';
	import { SECTIONS_LIBELLE } from '#lib/entites/types.ts';
	import SectionFormulaire from '#lib/components/SectionFormulaire.svelte';
	import ChargementPartiel from '#lib/components/ChargementPartiel.svelte';
	import IconeAction from '#lib/components/IconeAction.svelte';
	import { prestataires as prestatairesApi } from '#lib/api/index.ts';
	import {
		contactRenseigne,
		contratsDesPrestataires,
		deplacerDansLaListe,
	} from '#lib/prestataires.ts';
	import { optionsEquipements } from '#lib/equipements.ts';
	import { equipementsStore } from '#lib/stores/equipements.ts';
	import { tenter } from '#lib/erreurs.ts';

	/** Les prestataires retenus, dans l'ordre — le premier mène (#2704). */
	export let prestataireIds: number[] = [];
	/** Les prestataires proposables — chargés par l'appelant, qui connaît ses droits. */
	export let prestataires: { id: number; nom: string; actif?: boolean }[] = [];
	/** L'échec de chargement de la liste — un menu vide n'est pas « aucun prestataire ». */
	export let erreur = '';
	export let idPrefixe = 'intervenant';
	/** Relayé par l'appelant depuis la déclaration (`lint:pliage-transmis`). */
	export let pliable = false;
	/** L'équipement de l'affaire : il pré-remplit celui d'un prestataire créé ici. */
	export let equipement = '';
	/** Le contrat sous lequel il intervient, `null` hors contrat (#1445). */
	export let contratId: number | null = null;
	/** Les contrats en cours — chargés par l'appelant, comme les prestataires. */
	export let contrats: { id: number; prestataire_id: number; libelle: string }[] = [];

	//  ＋ CRÉER celui qui manque, sans quitter le formulaire (#1145, demandé à
	//  l'écran le 22/09/2026). Ce que le serveur exige, et rien de plus : nom,
	//  équipement — et, depuis le 24/09/2026 (#1229), UN CONTACT JOIGNABLE (un
	//  nom, un téléphone ou un e-mail). En demander autant que la fiche complète
	//  ferait renoncer ; la fiche se complète ensuite dans Prestataires. Le droit est
	//  tenu par la route (`require_cs_or_admin`) ; la section, elle, n'est
	//  ouverte qu'au conseil (`inactivePour.resident`).
	let creation = false;
	let nouveauNom = '';
	let nouvelEquipement = '';
	let contact = { nom: '', telephone: '', email: '' };
	function ouvrirCreation() {
		creation = true;
		nouvelEquipement = equipement;
	}
	async function creer() {
		const nom = nouveauNom.trim();
		if (!nom || !nouvelEquipement) return;
		await tenter(async () => {
			const cree = await prestatairesApi.create({
				nom,
				specialite: nouvelEquipement,
				//  Facultatif depuis #1327 : un contact vide ne part pas.
				contacts: contactRenseigne(contact) ? [contact] : [],
			});
			prestataires = [...prestataires, cree].sort((a, b) => a.nom.localeCompare(b.nom, 'fr'));
			prestataireIds = [...prestataireIds, cree.id];
			creation = false;
			nouveauNom = '';
			contact = { nom: '', telephone: '', email: '' };
		}, 'Prestataire créé');
	}

	//  Un contrat qui n'appartient plus à aucun d'eux : le serveur l'effacerait (Q4).
	function poser(ids: number[]) {
		prestataireIds = ids;
		if (!contratsDesPrestataires(contrats, ids).some((c) => c.id === contratId)) contratId = null;
	}
	//  « Ajouter » : un `<select>` qui revient à son invite après chaque choix.
	let ajout = '';
	function ajouter() {
		const id = nombreOuNull(ajout);
		ajout = '';
		if (id !== null && !prestataireIds.includes(id)) poser([...prestataireIds, id]);
	}
	const retirer = (id: number) => poser(prestataireIds.filter((x) => x !== id));
	const deplacer = (i: number, sens: -1 | 1) => poser(deplacerDansLaListe(prestataireIds, i, sens));

	//  Un archivé déjà retenu reste lisible ; on n'en ajoute pas un neuf (Q3).
	$: retenus = prestataireIds.map(
		(id) => prestataires.find((p) => p.id === id) ?? { id, nom: `Prestataire n° ${id}` },
	);
	$: proposables = prestataires.filter((p) => p.actif !== false && !prestataireIds.includes(p.id));

	$: siens = contratsDesPrestataires(contrats, prestataireIds);
	let choixContrat = '';
	$: choixContrat = contratId === null ? '' : String(contratId);
	const choisirContrat = () => (contratId = nombreOuNull(choixContrat));
	$: cadre = contratId !== null ? 'sous contrat' : siens.length ? 'hors contrat' : '';
</script>

<SectionFormulaire
	titre={SECTIONS_LIBELLE.intervenant}
	{pliable}
	resume={retenus.length
		? [retenus.map((p) => p.nom).join(', '), cadre].filter(Boolean).join(' · ')
		: 'aucun'}
	valeurModifiee={prestataireIds.length > 0}
	pour="{idPrefixe}-prestataire"
>
	<ChargementPartiel
		{erreur}
		consequence="Le menu des prestataires est vide : ce n'est pas qu'il n'en existe aucun."
	/>
	{#if retenus.length}
		<ol class="retenus" aria-label="Prestataires retenus">
			{#each retenus as p, i (p.id)}
				<li class="retenu">
					<span class="retenu-rang">{i + 1}</span>
					<span class="retenu-nom">{p.nom}</span>
					<button
						type="button"
						class="btn-icon retenu-geste"
						disabled={i === 0}
						aria-label="Monter {p.nom}"
						on:click={() => deplacer(i, -1)}><IconeAction icone="arrow-up" /></button
					>
					<button
						type="button"
						class="btn-icon retenu-geste"
						disabled={i === retenus.length - 1}
						aria-label="Descendre {p.nom}"
						on:click={() => deplacer(i, 1)}><IconeAction icone="arrow-down" /></button
					>
					<button
						type="button"
						class="btn-icon retenu-geste"
						aria-label="Retirer {p.nom}"
						on:click={() => retirer(p.id)}><IconeAction icone="x" /></button
					>
				</li>
			{/each}
		</ol>
	{/if}
	<div class="field">
		<label for="{idPrefixe}-prestataire"
			>{retenus.length ? 'Ajouter un prestataire' : 'Prestataire'}</label
		>
		<select id="{idPrefixe}-prestataire" bind:value={ajout} on:change={ajouter}>
			<option value="">{retenus.length ? '— Ajouter —' : '— Aucun —'}</option>
			{#each proposables as p (p.id)}
				<option value={String(p.id)}>{p.nom}</option>
			{/each}
		</select>
	</div>
	{#if siens.length}
		<div class="field">
			<label for="{idPrefixe}-contrat">Cadre de l'intervention</label>
			<select id="{idPrefixe}-contrat" bind:value={choixContrat} on:change={choisirContrat}>
				<option value="">Hors contrat</option>
				{#each siens as c (c.id)}
					<option value={String(c.id)}>Sous contrat : {c.libelle}</option>
				{/each}
			</select>
		</div>
	{/if}
	{#if creation}
		<!--  Pas de `<form>` : on est DANS celui de l'affaire, et un formulaire
		      imbriqué soumettrait l'affaire. Les boutons sont `type="button"`. -->
		<div class="creation-prestataire">
			<label class="field">Nom du prestataire<input bind:value={nouveauNom} /></label>
			<label class="field"
				>Équipement
				<select bind:value={nouvelEquipement}>
					<option value="">— Sélectionner —</option>
					{#each optionsEquipements('contrat', null, $equipementsStore) as e (e.val)}<option
							value={e.val}>{e.label}</option
						>{/each}
				</select>
			</label>
			<label class="field">Nom du contact<input bind:value={contact.nom} /></label>
			<div class="form-grid form-grid-2">
				<label class="field">Téléphone<input bind:value={contact.telephone} /></label>
				<label class="field">E-mail<input type="email" bind:value={contact.email} /></label>
			</div>
			<div class="actions-creation">
				<button type="button" class="btn btn-sm btn-outline" on:click={() => (creation = false)}
					>Annuler</button
				>
				<button
					type="button"
					class="btn btn-sm btn-primary"
					disabled={!nouveauNom.trim() || !nouvelEquipement}
					on:click={creer}>Créer</button
				>
			</div>
		</div>
	{:else}
		<button type="button" class="btn btn-sm btn-outline ajout-prestataire" on:click={ouvrirCreation}
			>＋ Nouveau prestataire</button
		>
	{/if}
</SectionFormulaire>

<style>
	/*  La liste a l'allure des Affaires liées (`SectionAffairesLiees`) : filet,
	    rayon, séparateurs ; gestes de 44 px au doigt (`standards/11` §10). */
	.retenus {
		list-style: none;
		margin: 0 0 0.5rem;
		padding: 0;
		border: 1px solid var(--color-border);
		border-radius: var(--radius);
		overflow: hidden;
		background: var(--color-surface);
	}
	.retenu + .retenu {
		border-top: 1px solid var(--color-border);
	}
	.retenu {
		display: flex;
		align-items: center;
		gap: 0.25rem;
		min-height: 44px;
		padding: 0 0.25rem 0 0.75rem;
	}
	.retenu-rang {
		min-width: 1.25rem;
		font-size: var(--fs-sm);
		font-weight: 700;
		color: var(--color-text-muted);
		font-variant-numeric: tabular-nums;
	}
	.retenu-nom {
		flex: 1;
		min-width: 0;
		overflow-wrap: anywhere;
	}
	.retenu-geste {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		width: 44px;
		height: 44px;
	}
	.ajout-prestataire,
	.creation-prestataire {
		margin-top: 0.5rem;
	}
	.creation-prestataire {
		display: grid;
		gap: 0.5rem;
		padding: 0.6rem;
		border: 1px dashed var(--color-border);
		border-radius: 6px;
	}
	.actions-creation {
		display: flex;
		justify-content: flex-end;
		gap: 0.5rem;
	}
</style>
