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
-->
<script lang="ts">
	import { nombreOuNull } from '#lib/utils.ts';
	import { SECTIONS_LIBELLE } from '#lib/entites/types.ts';
	import SectionFormulaire from '#lib/components/SectionFormulaire.svelte';
	import ChargementPartiel from '#lib/components/ChargementPartiel.svelte';
	import { prestataires as prestatairesApi } from '#lib/api/index.ts';
	import { EQUIPEMENTS, contactRenseigne, contratsDuPrestataire } from '#lib/prestataires.ts';
	import { tenter } from '#lib/erreurs.ts';

	/** L'identifiant du prestataire retenu, ou `null`. */
	export let prestataireId: number | null = null;
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
			prestataireId = cree.id;
			creation = false;
			nouveauNom = '';
			contact = { nom: '', telephone: '', email: '' };
		}, 'Prestataire créé');
	}

	//  `<select>` rend des chaînes : la valeur se lit et s'écrit ici, une fois.
	//  ⚠️ Dans les DEUX sens : l'équipement peut proposer un intervenant depuis
	//  l'extérieur (#1097). Une liaison `$: prestataireId = …` à sens unique
	//  l'écrasait aussitôt par le choix affiché.
	let choix = '';
	$: choix = prestataireId === null ? '' : String(prestataireId);
	const choisir = () => {
		prestataireId = nombreOuNull(choix);
		//  Un autre intervenant n'a pas ce contrat : le serveur l'effacerait.
		if (!contratsDuPrestataire(contrats, prestataireId).some((c) => c.id === contratId))
			contratId = null;
	};
	$: retenu = prestataires.find((p) => p.id === prestataireId);

	$: siens = contratsDuPrestataire(contrats, prestataireId);
	let choixContrat = '';
	$: choixContrat = contratId === null ? '' : String(contratId);
	const choisirContrat = () => (contratId = nombreOuNull(choixContrat));
	$: cadre = contratId !== null ? 'sous contrat' : siens.length ? 'hors contrat' : '';
</script>

<SectionFormulaire
	titre={SECTIONS_LIBELLE.intervenant}
	{pliable}
	resume={retenu ? [retenu.nom, cadre].filter(Boolean).join(' · ') : 'aucun'}
	valeurModifiee={prestataireId !== null}
	pour="{idPrefixe}-prestataire"
>
	<ChargementPartiel
		{erreur}
		consequence="Le menu des prestataires est vide : ce n'est pas qu'il n'en existe aucun."
	/>
	<div class="field">
		<select id="{idPrefixe}-prestataire" bind:value={choix} on:change={choisir}>
			<option value="">— Aucun —</option>
			{#each prestataires.filter((p) => p.actif !== false || p.id === prestataireId) as p (p.id)}
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
					{#each EQUIPEMENTS as e (e.val)}<option value={e.val}>{e.label}</option>{/each}
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
