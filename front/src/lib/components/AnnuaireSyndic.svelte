<!--
  **Le syndic dans l'annuaire de l'espace CS** — son en-tête (le contrat fait
  foi, #535) et la fiche de chacun de ses interlocuteurs, dans l'ordre où un
  arrivant les lit.

  Sorti d'`espace-cs/+page.svelte` le 29/09/2026 (#779, modularité), avec son
  pendant `AnnuaireConseil` : même amorçage, mêmes données de référence.

  La LISTE vit dans `AnnuaireMembres` depuis le 02/10/2026 (#1539), avec
  l'ordre (`ordonnable`) et le refus d'un membre sans téléphone (`refus`)
  DÉCLARÉS par ce côté-ci. Ne restent ici que l'en-tête, les champs propres
  (fonction, e-mail, téléphones) et l'interlocuteur principal.
-->
<script lang="ts">
	import { annuaireAdmin, type MembreSyndicAdmin } from '#lib/api/index.ts';
	import { inscritParNom, type SourcesRapprochement } from '#lib/annuaire-rapprochement.ts';
	import EnteteSyndic from '#lib/components/EnteteSyndic.svelte';
	import { type Geste } from '#lib/components/ActionsMembre.svelte';
	import AnnuaireMembres from '#lib/components/AnnuaireMembres.svelte';
	import { type MembreBase } from '#lib/components/CarteMembre.svelte';

	/** Les données de référence du rapprochement par le nom. */
	export let sources: SourcesRapprochement;

	//  L'identifiant, comme `AnnuaireConseil` : absent pour un membre ajouté à
	//  l'écran ; présent, il fait mettre à jour le membre EN PLACE. Sans lui, le
	//  serveur recréait tout le syndic et le fil annonçait en « nouveau membre »
	//  des interlocuteurs inchangés (09/10/2026, `reconcilier_membres`).
	interface MembreSyndicForm extends MembreBase, Partial<Pick<MembreSyndicAdmin, 'id'>> {
		fonction: string;
		email: string;
		telephones: string[];
		est_principal: boolean;
	}

	let nomSyndic = '';
	/** D'où vient le nom affiché — le contrat fait foi (#535, `utils/syndic.py`). */
	let nomSyndicSource: 'contrat' | 'saisie' | 'aucune' = 'aucune';
	let adresseSyndic = '';
	let siteWebSyndic = '';
	let membresSyndic: MembreSyndicForm[] = [];
	let enTeteEdite = false;

	async function charger(): Promise<MembreSyndicForm[]> {
		const donnees = await annuaireAdmin.getSyndic();
		nomSyndic = donnees.nom_syndic ?? '';
		nomSyndicSource = donnees.nom_syndic_source ?? 'aucune';
		adresseSyndic = donnees.adresse ?? '';
		siteWebSyndic = donnees.site_web ?? '';
		return (donnees.membres ?? []).map((m): MembreSyndicForm => ({
			id: m.id,
			genre: m.genre ?? 'Mme',
			prenom: m.prenom ?? '',
			nom: m.nom ?? '',
			fonction: m.fonction ?? '',
			email: m.email ?? '',
			telephones: m.telephone
				? m.telephone
						.split(',')
						.map((t: string) => t.trim())
						.filter(Boolean)
				: [''],
			est_principal: m.est_principal ?? false,
			user_id: m.user_id ?? null,
		}));
	}

	const nouveau = (): MembreSyndicForm => ({
		genre: 'Mme',
		prenom: '',
		nom: '',
		fonction: '',
		email: '',
		telephones: [''],
		est_principal: false,
		user_id: null,
	});

	/** Le nom saisi lie le membre à un inscrit — sans logement : il n'habite pas ici. */
	function surNom(i: number) {
		if (membresSyndic[i].user_id) return;
		const inscrit = inscritParNom(sources.inscrits, membresSyndic[i].nom);
		if (inscrit) {
			membresSyndic[i] = { ...membresSyndic[i], user_id: inscrit.id };
			membresSyndic = [...membresSyndic];
		}
	}

	/**
	 * La charge utile de `putSyndic`, écrite UNE fois : réordonnancement, en-tête
	 * et fiche l'envoient entière. Elle l'a été trois fois, à l'identique.
	 */
	const envoyer = (membres: MembreSyndicForm[]) =>
		annuaireAdmin.putSyndic({
			nom_syndic: nomSyndic,
			adresse: adresseSyndic,
			site_web: siteWebSyndic || null,
			membres: membres.map((m) => ({
				id: m.id ?? null,
				genre: m.genre,
				prenom: m.prenom,
				nom: m.nom,
				fonction: m.fonction || null,
				email: m.email || null,
				telephone:
					m.telephones
						.map((t) => t.trim())
						.filter(Boolean)
						.join(',') || null,
				est_principal: m.est_principal,
				user_id: m.user_id,
			})),
		});

	/** Un membre du syndic s'enregistre avec au moins un téléphone. */
	const refus = (m: MembreSyndicForm) =>
		m.telephones.some((t) => t.trim()) ? null : 'Au moins un téléphone requis';

	/*
	 *  Le geste que la liste du syndic a de plus que celle du CS, avec l'ordre
	 *  (`ordonnable`) : l'un des membres est l'interlocuteur principal. Passé en
	 *  DONNÉES à `ActionsMembre`.
	 */
	function designer(i: number, m: MembreSyndicForm): Geste[] {
		if (m.est_principal) return [];
		return [
			{
				variante: 'designer',
				libelle: 'Définir interlocuteur principal',
				icone: 'star',
				onClic: () =>
					(membresSyndic = membresSyndic.map((x, j) => ({ ...x, est_principal: j === i }))),
			},
		];
	}

	function retirerTelephone(i: number, ti: number) {
		membresSyndic[i].telephones = membresSyndic[i].telephones.filter((_, j) => j !== ti);
		membresSyndic = [...membresSyndic];
	}
	function ajouterTelephone(i: number) {
		membresSyndic[i].telephones = [...membresSyndic[i].telephones, ''];
		membresSyndic = [...membresSyndic];
	}
</script>

<AnnuaireMembres
	bind:membres={membresSyndic}
	{charger}
	{nouveau}
	{envoyer}
	{refus}
	{surNom}
	ordonnable
	gestes={designer}
	accent={(m) => (m.est_principal ? 'principal' : null)}
	libelleAjout="+ Nouveau membre Syndic"
>
	<!--  L'en-tête vit dans son composant (#535) : c'est lui qui porte la règle
	      « le contrat fait foi », et le champ désactivé qui la montre. -->
	<svelte:fragment slot="entete" let:enregistrement let:enregistrer>
		<EnteteSyndic
			bind:nom={nomSyndic}
			bind:adresse={adresseSyndic}
			bind:siteWeb={siteWebSyndic}
			bind:edition={enTeteEdite}
			source={nomSyndicSource}
			{enregistrement}
			onEnregistrer={async () => (enTeteEdite = !(await enregistrer('Syndic enregistré')))}
		/>
	</svelte:fragment>

	<svelte:fragment slot="badge" let:membre={m}>
		{#if m.est_principal}
			<span
				class="summary-role-badge summary-role-badge-principal"
				title="Interlocuteur principal du syndic">&#x2B50; Interlocuteur principal</span
			>
		{/if}
	</svelte:fragment>

	<svelte:fragment slot="champs" let:index={i}>
		<label class="field">
			Fonction
			<input
				type="text"
				bind:value={membresSyndic[i].fonction}
				placeholder="ex. Directeur de gérance"
			/>
		</label>
		<label class="field">
			Email
			<input type="email" bind:value={membresSyndic[i].email} placeholder="Email" />
		</label>
	</svelte:fragment>

	<svelte:fragment slot="edition" let:membre={m} let:index={i}>
		<div class="syndic-telephones">
			<div class="syndic-telephones-titre">
				Téléphone{m.telephones.length > 1 ? 's' : ''}
			</div>
			<!--  Clé = l'INDEX, et c'est la seule honnête : le champ écrit dans le tableau par
			    sa position (`bind:value={…telephones[ti]}`), et une clé tirée de la valeur
			    changerait à chaque caractère tapé — Svelte recréerait le nœud, le champ
			    perdrait le focus (`lint:each-key`, #1571). -->
			{#each m.telephones as _tel, ti (ti)}
				<div class="syndic-telephone">
					<input bind:value={membresSyndic[i].telephones[ti]} placeholder="ex. 01 23 45 67 89" />
					{#if m.telephones.length > 1}
						<button
							type="button"
							class="btn btn-sm btn-outline btn-retirer-tel"
							aria-label="Retirer ce numéro"
							on:click={() => retirerTelephone(i, ti)}
						>
							-
						</button>
					{/if}
				</div>
			{/each}
			<button type="button" class="btn btn-sm btn-outline" on:click={() => ajouterTelephone(i)}>
				+ N° de téléphone
			</button>
		</div>
	</svelte:fragment>

	<svelte:fragment slot="resume" let:membre={m}>
		{#if m.fonction}<span class="summary-fonction">{m.fonction}</span>{/if}
		{#if m.email}<span class="summary-loc">{m.email}</span>{/if}
		{#if m.telephones[0]}
			<span class="summary-loc">{m.telephones.filter((t) => t.trim()).join(' · ')}</span>
		{/if}
		{#if m.user_id}
			<span class="summary-lien">&#x1F517; Inscrit lié</span>
		{/if}
	</svelte:fragment>
</AnnuaireMembres>

<style>
	/*  Les téléphones d'un membre du syndic — le seul champ qui ne tient pas dans
	    la grille d'identité, parce qu'il en faut plusieurs. Le rouge du retrait
	    est celui de la charte (`--color-danger`), jamais écrit en dur. */
	.syndic-telephones {
		margin-top: 0.65rem;
	}
	.syndic-telephones-titre {
		font-size: var(--fs-md);
		font-weight: 600;
		margin-bottom: 0.35rem;
	}
	.syndic-telephone {
		display: flex;
		gap: 0.4rem;
		margin-bottom: 0.35rem;
	}
	.syndic-telephone input {
		flex: 1;
	}
	.btn-retirer-tel {
		color: var(--color-danger);
		border-color: var(--color-danger);
	}
</style>
