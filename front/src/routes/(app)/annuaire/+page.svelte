<script lang="ts">
	import { comparerParNom } from '$lib/noms';
	import Icon from '$lib/components/Icon.svelte';
	import EntetePage from '$lib/components/EntetePage.svelte';
	import CarteContact, { type Medaillon } from '$lib/components/CarteContact.svelte';
	import QRCode from '$lib/components/QRCode.svelte';
	import { onMount } from 'svelte';
	import { annuaire as annuaireApi, type Annuaire, type MembreAnnuaireCS } from '$lib/api';
	import { toast } from '$lib/components/Toast.svelte';
	import { getPageConfig, configStore, siteNomStore, defautsDePage } from '$lib/stores/pageConfig';
	import { fmtDateLong as formatDate } from '$lib/date';
	import { revelerCible } from '$lib/deepLink';
	import { etageLabel, telephonesDe } from '$lib/utils';
	import EtatListe from '$lib/components/EtatListe.svelte';
	import LienConsignes from '$lib/components/LienConsignes.svelte';

	$: _pc = getPageConfig($configStore, 'annuaire', defautsDePage('annuaire'));
	$: _siteNom = $siteNomStore;

	//  Les médaillons d'un membre, décidés ICI et pas dans le balisage : ils
	//  étaient recopiés à l'identique sur les deux rendus d'un membre du CS
	//  (groupé par bâtiment, et sans groupe). Une règle d'affichage qui s'écrit
	//  deux fois finit par ne plus dire la même chose des deux côtés.
	function medaillonsCs(m: MembreAnnuaireCS): Medaillon[] {
		const med: Medaillon[] = [];
		if (m.est_gestionnaire_site)
			med.push({
				role: 'gestionnaire-site',
				titre: `Gestionnaire ${_siteNom}`,
				icone: 'building-2',
			});
		if (m.est_president)
			med.push({ role: 'president-cs', titre: 'Président du Conseil Syndical', icone: 'shield' });
		return med;
	}

	function medaillonsSyndic(m: { est_principal?: boolean }): Medaillon[] {
		return m.est_principal
			? [{ role: 'gestionnaire-principal', titre: 'Gestionnaire principal', icone: 'star' }]
			: [];
	}

	let data: Annuaire = {
		cs: { ag_annee: null, ag_date: null, membres: [] },
		syndic: {
			nom_syndic: '',
			nom_syndic_source: 'aucune',
			adresse: '',
			site_web: null,
			membres: [],
		},
		whatsapp_url: null,
	};
	let loading = true;

	onMount(async () => {
		try {
			data = await annuaireApi.get();
		} catch {
			toast('error', 'Erreur de chargement');
		} finally {
			loading = false;
		}

		//  🔴 L'ancre `#syndic` ne suffit pas. Le navigateur applique le hash à
		//  l'ARRIVÉE, alors que cette page monte vide et se remplit ensuite : la
		//  section visée n'existe pas encore, le saut ne trouve rien, et l'on
		//  reste en haut. Signalé à l'écran le 29/08/2026 depuis le lien « IFF
		//  Gestion » de la fiche de la résidence — l'ancre ÉTAIT là.
		//
		//  ⚠️ Le défaut est propre à toute page qui charge après le montage :
		//  `revelerCible` existe pour ça (#453) et attend le rendu. C'est aussi
		//  ce qui met le titre sous l'en-tête plutôt que derrière.
		if (typeof window !== 'undefined' && window.location.hash === '#syndic') {
			revelerCible('syndic');
		}
	});

	$: batimentsCS = (() => {
		const groups = new Map<string, MembreAnnuaireCS[]>();
		for (const m of data.cs.membres) {
			const key = m.batiment_nom ?? '';
			if (!groups.has(key)) groups.set(key, []);
			groups.get(key)!.push(m);
		}
		const genreOrder = (g: string) => (g === 'Mme' ? 0 : g === 'Mlle' ? 1 : 2);
		return [...groups.entries()]
			.sort(([a], [b]) => {
				if (!a && b) return 1; // sans bâtiment en dernier
				if (a && !b) return -1;
				return a.localeCompare(b, 'fr');
			})
			.map(([key, membres]) => ({
				batiment: key || null,
				membres: [...membres].sort((a, b) => {
					const gd = genreOrder(a.genre) - genreOrder(b.genre);
					if (gd !== 0) return gd;
					//  Puis la règle commune — nom, puis prénom (`$lib/noms`).
					return comparerParNom(a, b);
				}),
			}));
	})();
</script>

<svelte:head><title>{_pc.titre} — {_siteNom}</title></svelte:head>

<EntetePage titre={_pc.titre} descriptif={_pc.descriptif} icone={_pc.icone || 'users'} />

{#if loading}
	<EtatListe chargement />
{:else}
	<section class="section-annuaire">
		<div class="entete-annuaire">
			<h2 class="section-title titre-annuaire">Conseil Syndical</h2>
			{#if data.cs.ag_annee}
				<span class="ag-info">
					Voté en AG {data.cs.ag_annee}{#if data.cs.ag_date}
						- {formatDate(data.cs.ag_date)}{/if}
				</span>
			{/if}
		</div>
		{#if data.whatsapp_url}
			<div class="url-block bloc-groupe">
				<QRCode data={data.whatsapp_url} size={45} />
				<div>
					<strong>Groupe WhatsApp copropriété</strong>
					<span class="contact-societe"
						><a href={data.whatsapp_url} target="_blank" rel="noopener">{data.whatsapp_url}</a
						></span
					>
				</div>
			</div>
		{/if}
		{#if data.cs.membres.length === 0}
			<p class="text-muted-base">Aucun membre CS enregistré.</p>
		{:else if batimentsCS.length > 1}
			{#each batimentsCS as groupe (groupe.batiment ?? '')}
				<div class="batiment-section">
					<div class="batiment-label">
						<Icon name="building-2" size={12} />
						{groupe.batiment ? `Bâtiment ${groupe.batiment}` : 'Sans bâtiment'}
					</div>
					<div class="contact-grid">
						{#each groupe.membres as m (m.id)}
							<!--  Le bâtiment n'est PAS répété ici : il titre déjà le groupe. C'est la
							      seule différence avec la carte sans groupe plus bas, et elle est
							      voulue — avant l'extraction elle se perdait dans trente lignes
							      recopiées. -->
							<CarteContact personne={m} medaillons={medaillonsCs(m)}>
								{#if m.etage != null}
									<div class="contact-loc">{etageLabel(m.etage, { suffixe: true })}</div>
								{/if}
							</CarteContact>
						{/each}
					</div>
				</div>
			{/each}
		{:else}
			<div class="contact-grid">
				{#each data.cs.membres as m (m.id)}
					<CarteContact personne={m} medaillons={medaillonsCs(m)}>
						{#if m.batiment_nom || m.etage != null}
							<div class="contact-loc">
								{#if m.batiment_nom}Bât. {m.batiment_nom}{/if}{#if m.batiment_nom && m.etage != null}
									-
								{/if}{#if m.etage != null}{etageLabel(m.etage, { suffixe: true })}{/if}
							</div>
						{/if}
					</CarteContact>
				{/each}
			</div>
		{/if}
	</section>

	<section>
		<!--  Ancre visée par la fiche de la résidence (« Syndic » → ici). Le
	      `scroll-margin-top` évite que le titre se range sous l'en-tête collant. -->
		<h2 class="section-title" id="syndic">Syndic</h2>
		{#if data.syndic.nom_syndic}
			<p class="syndic-header">
				<strong>{data.syndic.nom_syndic}</strong>
				{#if data.syndic.adresse}<span class="contact-societe">{data.syndic.adresse}</span>{/if}
			</p>
			{#if data.syndic.site_web}
				<div class="url-block">
					<QRCode data={data.syndic.site_web} size={45} />
					<div>
						<strong>Espace client</strong>
						<span class="contact-societe"
							><a href={data.syndic.site_web} target="_blank" rel="noopener"
								>{data.syndic.site_web}</a
							></span
						>
					</div>
				</div>
			{/if}
		{/if}
		{#if data.syndic.membres.length === 0}
			<p class="text-muted-base">Aucun contact syndic enregistré.</p>
		{:else}
			<div class="contact-grid">
				{#each data.syndic.membres as m (m.id)}
					<CarteContact personne={m} medaillons={medaillonsSyndic(m)} principal={m.est_principal}>
						{#if m.fonction}<div class="contact-role">{m.fonction}</div>{/if}
						{#if m.email}
							<a href="mailto:{m.email}" class="contact-email">{m.email}</a>
						{/if}
						{#if m.telephone}
							{#each telephonesDe(m.telephone) as tel, ti (`${ti}|${tel}`)}
								<a href="tel:{tel}" class="contact-email">&#x1F4DE; {tel}</a>
							{/each}
						{/if}
					</CarteContact>
				{/each}
			</div>
		{/if}
	</section>

	<LienConsignes />
{/if}

<style>
	/*  `.section-title` : la charte porte tout (composants.css). Retiree le 28/08/2026 (#607). */
	.contact-loc {
		font-size: var(--fs-sm);
		color: var(--color-text-muted);
		margin-top: 0.1rem;
	}
	.ag-info {
		font-size: var(--fs-sm);
		color: var(--color-text-muted);
	}
	#syndic {
		scroll-margin-top: 5rem;
	}
	.syndic-header {
		margin-bottom: 0.75rem;
		display: flex;
		flex-direction: column;
		gap: 0.15rem;
	}

	.batiment-section {
		margin-bottom: 1.5rem;
	}
	.batiment-label {
		font-size: var(--fs-2xs);
		font-weight: 700;
		text-transform: uppercase;
		letter-spacing: 0.07em;
		color: var(--color-primary);
		border-left: 3px solid var(--color-primary);
		padding-left: 0.5rem;
		margin-bottom: 0.6rem;
		display: flex;
		align-items: center;
		gap: 0.3rem;
	}
	/*  Une rangée `flex` et non une grille (10/10/2026) : une colonne de grille
	    `auto-fill` a une largeur FIXE, et le nom « Mr Prénom NOM » s'y coupait.
	    En `flex`, chaque carte (base 15 rem, `CarteContact`) garde au moins la
	    largeur de son nom sur une ligne. */
	.contact-grid {
		display: flex;
		flex-wrap: wrap;
		gap: 1rem;
	}
	/*  `.contact-card` et `.card-principal` vivent dans `CarteContact.svelte`
	    depuis le 16/09/2026 : la carte y est rendue, son style l'accompagne. */
	/* La variable cascade jusqu'au fond de repli d'`Avatar` (initiales) : le
	   gestionnaire principal garde sa pastille dorée sans classe dédiée. */
	/*  Les trois médaillons de rôle sont partis dans `MedaillonRole`
	    (14/09/2026, #779) : leur géométrie était écrite DEUX fois ici, à onze
	    propriétés près identiques, et seule la couleur de fond changeait. Elles
	    suivent leur balisage — Svelte scope le style au composant qui rend. */

	.contact-societe {
		font-size: var(--fs-sm);
		font-style: italic;
		color: var(--color-text-muted);
		margin: 0.1rem 0;
		display: block;
	}
	.contact-role {
		font-size: var(--fs-sm);
		color: var(--color-text-muted);
		margin: 0.1rem 0;
	}
	.contact-email {
		display: block;
		font-size: var(--fs-md);
		color: var(--color-primary);
		text-decoration: none;
		margin-top: 0.1rem;
	}
	@media (hover: hover) and (pointer: fine) {
		.contact-email:hover {
			text-decoration: underline;
		}
	}

	.url-block {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		margin-top: 0.75rem;
		padding: 0.6rem 0.75rem;
		background: var(--color-bg);
		border: 1px solid var(--color-border);
		border-radius: var(--radius);
		max-width: 520px;
	}
	.url-block strong {
		font-size: var(--fs-md);
		display: block;
	}
	.url-block .contact-societe {
		margin: 0;
	}
	.url-block a {
		word-break: break-all;
	}
	.section-annuaire {
		margin-bottom: 2rem;
	}
	.entete-annuaire {
		display: flex;
		align-items: baseline;
		gap: 1rem;
		flex-wrap: wrap;
		margin-bottom: 0.75rem;
	}
	.titre-annuaire {
		margin-bottom: 0;
	}
	.bloc-groupe {
		margin-bottom: 0.75rem;
	}
</style>
