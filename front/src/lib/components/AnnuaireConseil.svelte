<!--
  **Le conseil syndical dans l'annuaire de l'espace CS** — l'AG qui l'a élu,
  le lien de la communauté WhatsApp, et la fiche de chacun de ses membres.

  Sorti d'`espace-cs/+page.svelte` le 29/09/2026 (#779, modularité) : la page
  faisait 1 356 lignes, et l'onglet Annuaire en portait la moitié. Il s'amorce
  seul, comme `OngletAnnoncesHall` ; la page ne lui passe que les données de
  RÉFÉRENCE qu'elle charge de toute façon (inscrits, lots, registre importé),
  qui servent à rapprocher un nom saisi d'un inscrit et d'un logement
  (`#lib/annuaire-rapprochement`). Son pendant : `AnnuaireSyndic`.

  La LISTE — chargement, fiches, gestes, ajout — vit dans `AnnuaireMembres`
  depuis le 02/10/2026 (#1539) : les deux annuaires la recopiaient. Ne reste
  ici que ce qui est propre au conseil — l'en-tête de l'AG, la localisation et
  le président.
-->
<script lang="ts">
	import { confirmer } from '#lib/confirmation.ts';
	import { annuaireAdmin, type MembreConseilAdmin } from '#lib/api/index.ts';
	import { toast } from '#lib/components/Toast.svelte';
	import { fmtDateShort } from '#lib/date.ts';
	import { comparerParNom, nomAffiche } from '#lib/noms.ts';
	import { localisationMembre } from '#lib/utils.ts';
	import {
		inscritParNom,
		localisationParNom,
		type SourcesRapprochement,
	} from '#lib/annuaire-rapprochement.ts';
	import PiedFormulaire from '#lib/components/PiedFormulaire.svelte';
	import ActionsMembre from '#lib/components/ActionsMembre.svelte';
	import AnnuaireMembres from '#lib/components/AnnuaireMembres.svelte';
	import { type MembreBase } from '#lib/components/CarteMembre.svelte';

	/** Les données de référence du rapprochement par le nom. */
	export let sources: SourcesRapprochement;

	//  🔴 La forme DÉRIVE de `MembreBase` (civilité, prénom, NOM, inscrit lié),
	//  qui vit dans `CarteMembre` — le composant qui la rend. L'identifiant vient
	//  du type du CLIENT (#1680) : absent pour un membre ajouté à l'écran, que le
	//  serveur créera ; présent, il fait mettre à jour le membre EN PLACE.
	interface MembreCSForm extends MembreBase, Partial<Pick<MembreConseilAdmin, 'id'>> {
		batiment_id: number | null;
		batiment_nom: string | null;
		etage: number | null;
		est_gestionnaire_site: boolean;
		est_president: boolean;
	}

	let agAnnee: number | null = null;
	let agDate = '';
	let whatsappUrl = '';
	let membresCS: MembreCSForm[] = [];
	let enTeteEdite = false;

	async function charger(): Promise<MembreCSForm[]> {
		const donnees = await annuaireAdmin.getCS();
		agAnnee = donnees.ag_annee ?? null;
		agDate = donnees.ag_date ?? '';
		whatsappUrl = donnees.whatsapp_url ?? '';
		//  🔴 L'IDENTIFIANT est rendu tel quel (#1680) : sans lui, `PUT
		//  /admin/annuaire/cs` ne reconnaît personne, supprime et recrée tout le
		//  conseil — `cree_le` remis à l'instant, et autant de « nouveau membre »
		//  au fil. Le serveur réconcilie depuis le 31/08/2026 ; encore faut-il
		//  lui renvoyer ce qu'il a donné.
		const membres = (donnees.membres ?? []).map((m: MembreConseilAdmin): MembreCSForm => ({
			id: m.id,
			genre: m.genre ?? 'Mme',
			prenom: m.prenom ?? '',
			nom: m.nom ?? '',
			batiment_id: m.batiment_id ?? null,
			batiment_nom: m.batiment_nom ?? null,
			etage: m.etage ?? null,
			user_id: m.user_id ?? null,
			est_gestionnaire_site: m.est_gestionnaire_site ?? false,
			est_president: m.est_president ?? false,
		}));
		return membres.sort((a: MembreCSForm, b: MembreCSForm) => {
			const bat = (a.batiment_nom ?? 'zzz').localeCompare(b.batiment_nom ?? 'zzz', 'fr');
			//  Puis la règle commune — nom, puis prénom (`#lib/noms`).
			return bat !== 0 ? bat : comparerParNom(a, b);
		});
	}

	const nouveau = (): MembreCSForm => ({
		genre: 'Mme',
		prenom: '',
		nom: '',
		batiment_id: null,
		batiment_nom: null,
		etage: null,
		user_id: null,
		est_gestionnaire_site: false,
		est_president: false,
	});

	/** Le nom saisi localise le membre (registre importé) et le lie à un inscrit. */
	function surNom(i: number) {
		const nom = membresCS[i].nom;
		const logement = localisationParNom(sources, nom);
		if (logement) membresCS[i] = { ...membresCS[i], ...logement };
		if (!membresCS[i].user_id) {
			const inscrit = inscritParNom(sources.inscrits, nom);
			if (inscrit) membresCS[i] = { ...membresCS[i], user_id: inscrit.id };
		}
		membresCS = [...membresCS];
	}

	/** Un seul président : en désigner un second demande de remplacer le premier. */
	async function surPresident(i: number) {
		if (!membresCS[i].est_president) {
			membresCS[i] = { ...membresCS[i], est_president: false };
			membresCS = [...membresCS];
			return;
		}
		const actuel = membresCS.findIndex((m, j) => m.est_president && j !== i);
		const nouveau = nomAffiche(membresCS[i]);
		const remplacer =
			actuel === -1 ||
			(await confirmer({
				titre: 'Remplacer le président',
				message: `Un président existe déjà (${nomAffiche(membresCS[actuel])}).\n\nVoulez-vous remplacer par ${nouveau} ?`,
				libelleConfirmer: 'Remplacer',
			}));
		if (remplacer && actuel !== -1)
			membresCS[actuel] = { ...membresCS[actuel], est_president: false };
		membresCS[i] = { ...membresCS[i], est_president: remplacer };
		membresCS = [...membresCS];
		if (remplacer) toast('info', `${nouveau} est maintenant président du CS`);
	}

	/**
	 *  La charge utile de `putCS`, écrite UNE fois : l'en-tête et chaque fiche
	 *  l'envoient entière. Elle l'a été deux fois, et un champ ajouté à l'une des
	 *  copies serait parti selon le bouton employé.
	 */
	const envoyer = (membres: MembreCSForm[]) =>
		annuaireAdmin.putCS({
			ag_annee: agAnnee,
			ag_date: agDate || null,
			whatsapp_url: whatsappUrl || null,
			membres,
		});
</script>

<AnnuaireMembres
	bind:membres={membresCS}
	{charger}
	{nouveau}
	{envoyer}
	{surNom}
	accent={(m) => (m.est_president ? 'president' : null)}
	libelleAjout="+ Nouveau membre CS"
>
	<svelte:fragment slot="entete" let:enregistrement let:enregistrer>
		{#if enTeteEdite}
			<div class="form-grid largeur-saisie entete-conseil">
				<label class="field">
					Voté en AG
					<input type="number" min="2000" max="2099" placeholder="ex. 2024" bind:value={agAnnee} />
				</label>
				<label class="field">
					Date de l'AG
					<input type="date" bind:value={agDate} />
				</label>
				<label class="field">
					URL communauté WhatsApp
					<input type="url" placeholder="https://chat.whatsapp.com/..." bind:value={whatsappUrl} />
				</label>
				<!--  🔴 `PiedFormulaire` (12/09/2026) — cf. `EnteteSyndic` : cette rangée
				      était une copie du pied commun sous une autre classe, divergente
				      sur l'ordre des boutons et sur les libellés. -->
				<PiedFormulaire
					enCours={enregistrement}
					soumission={false}
					petit
					on:enregistre={async () =>
						(enTeteEdite = !(await enregistrer('Conseil Syndical enregistré')))}
					on:annule={() => (enTeteEdite = false)}
				/>
			</div>
		{:else}
			<div class="header-summary">
				<span
					>{agAnnee ? `AG ${agAnnee}` : 'Année AG non renseignée'}{agDate
						? ` · ${fmtDateShort(agDate)}`
						: ''}</span
				>
				{#if whatsappUrl}<span class="lien-whatsapp"
						>· <a href={whatsappUrl} target="_blank" rel="noopener">WhatsApp</a></span
					>{/if}
				<ActionsMembre barre={false} onModifier={() => (enTeteEdite = true)} />
			</div>
		{/if}
	</svelte:fragment>

	<svelte:fragment slot="badge" let:membre={m}>
		<!--  Les rôles se disent par UNE pastille, celle de « Gestionnaire du
		      Site » (23/09/2026, signalé à l'écran) — et une seule fois : le
		      Président paraissait deux fois, ici et dans le résumé. -->
		{#if m.est_gestionnaire_site}
			<span class="summary-role-badge" title="Gestionnaire du Site">
				&#x1F3E2; Gestionnaire du Site
			</span>
		{/if}
		{#if m.est_president}
			<span
				class="summary-role-badge summary-role-badge-president"
				title="Président du Conseil Syndical">&#x1F451; Président</span
			>
		{/if}
	</svelte:fragment>

	<svelte:fragment slot="edition" let:membre={m} let:index={i}>
		{#if m.batiment_nom || m.etage != null}
			<div class="localisation-info">&#x1F4CD; {localisationMembre(m)}</div>
		{/if}
		<div class="cs-role-flags">
			<label class="cs-role-flag">
				<input
					type="checkbox"
					checked={membresCS[i].est_president}
					on:change={() => surPresident(i)}
				/>
				<span>Président du Conseil Syndical</span>
			</label>
		</div>
	</svelte:fragment>

	<svelte:fragment slot="detail" let:membre={m}>
		{#if m.batiment_nom || m.etage != null}
			<div class="localisation-info">&#x1F4CD; {localisationMembre(m)}</div>
		{/if}
	</svelte:fragment>

	<svelte:fragment slot="resume" let:membre={m}>
		{#if m.batiment_nom || m.etage != null}
			<span class="summary-loc">&#x1F4CD; {localisationMembre(m)}</span>
		{/if}
		{#if m.user_id}
			<span class="summary-lien">&#x1F517; Inscrit lié</span>
		{/if}
	</svelte:fragment>
</AnnuaireMembres>

<style>
	/*  Seuls la répartition et l'espacement : la peau des contrôles vit dans la
	    charte (`check-styles-nus.mjs`, volet C). */
	.form-grid {
		grid-template-columns: repeat(auto-fit, minmax(min(150px, 100%), 1fr));
		gap: 0.65rem;
	}
	.entete-conseil {
		margin-bottom: 1rem;
	}
	.lien-whatsapp {
		margin-left: 0.5rem;
	}
	.cs-role-flags {
		display: flex;
		flex-direction: column;
		gap: 0.35rem;
		margin-top: 0.65rem;
	}
	.cs-role-flag {
		display: inline-flex;
		align-items: center;
		gap: 0.45rem;
		font-size: var(--fs-sm);
		color: var(--color-text);
	}
	.cs-role-flag input {
		accent-color: var(--color-primary);
	}
</style>
