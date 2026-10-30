<!--
  Le CORPS d'une carte du registre (onglet « Installations », R4 #1880) : ce que la
  référence sait d'une installation, et ce que l'opérateur décide.

  Dans l'ordre du geste :
  0. **Alertes** — ce que la référence lui reproche (R4b #1960), avant tout le reste :
     c'est ce qui appelle la décision ; les graves partent aussi par courriel ;
  1. **Décision** — les gestes que le SERVEUR dit possibles (`gestes_possibles`) ;
     l'écran n'a pas de seconde table des transitions — « Supprimer » compris, offert
     à une installation résiliée seulement ;
  2. **Services accordés** — une case par service que la référence peut accorder ;
  2 bis. **Canal et version** — canal, vague, et la version cible qui en
     découle (`DistributionInstallation`, R5 #1881) ;
  3. **Administrateur d'installation** — le contact qu'il a déclaré ;
  4. **Dernier rapport nocturne** — des nombres et des coches de conformité
     (`CocheConformite` : conforme, à corriger, inconnu), rien d'un résident ;
  5. **Contrat accepté** — le texte EXACT archivé sous l'identifiant (D26) ;
  6. **Journal des décisions** — qui, quand, quoi, pourquoi.

  Un geste et un enregistrement de services demandent un MOTIF (`#lib/saisie`) :
  le journal dit pourquoi. Ils partent dans le bail au prochain renouvellement de
  l'installation — la référence ne pousse jamais (§4.11, règle 5), et l'écran le dit.
-->
<script lang="ts">
	import { SEPARATEUR } from '#lib/separateurs.ts';
	import { createEventDispatcher } from 'svelte';
	import CocheConformite from '#lib/components/CocheConformite.svelte';
	import DistributionInstallation from '#lib/components/DistributionInstallation.svelte';
	import EncartAvertissement from '#lib/components/EncartAvertissement.svelte';
	import Icon from '#lib/components/Icon.svelte';
	import PiedFormulaire from '#lib/components/PiedFormulaire.svelte';
	import type {
		FicheInstallation,
		GesteRegistre,
		ServiceAccordable,
		VagueLue,
		VersionsPubliees,
	} from '#lib/api/index.ts';
	import { fmtDatetime } from '#lib/date.ts';
	import { fmtNombre } from '#lib/utils.ts';
	import { nomAffiche } from '#lib/noms.ts';
	import {
		COPIE_HORS_MACHINE,
		GESTES_REGISTRE,
		libelleDecision,
		pointsPosture,
	} from '#lib/registre-installations.ts';
	import TexteMarkdown from '#lib/components/TexteMarkdown.svelte';

	export let fiche: FicheInstallation;
	export let accordables: ServiceAccordable[] = [];
	export let versions: VersionsPubliees = { proposees: [], lues_le: null };
	export let vagues: VagueLue[] = [];
	export let enCours = false;

	const dispatch = createEventDispatcher<{
		geste: GesteRegistre;
		services: string[];
	}>();

	/** Les cases, partant de ce que la référence accorde aujourd'hui. */
	let choisis: string[] = [];
	$: choisis = [...fiche.services_autorises];
	$: modifie =
		choisis.length !== fiche.services_autorises.length ||
		choisis.some((c) => !fiche.services_autorises.includes(c));

	$: gestes = fiche.gestes_possibles;
	$: r = fiche.dernier_rapport;

	function basculerService(code: string, coche: boolean) {
		choisis = coche ? [...choisis, code] : choisis.filter((c) => c !== code);
	}

	function mo(v: number | null): string {
		return v === null ? 'inconnu' : `${fmtNombre(v)} Mo`;
	}
</script>

{#if fiche.alertes.length}
	<h4 class="intertitre">Alertes</h4>
	<EncartAvertissement role="status">
		<ul class="alertes">
			{#each fiche.alertes as a (a.code)}
				<li>
					<strong>{a.libelle}</strong> — {a.message}
					{#if a.grave}<span class="badge badge-red">courriel à l’opérateur</span>{/if}
				</li>
			{/each}
		</ul>
	</EncartAvertissement>
{/if}

{#if gestes.length}
	<h4 class="intertitre">Décision</h4>
	<div class="gestes">
		{#each gestes as g (g)}
			<button
				type="button"
				class="btn"
				class:btn-primary={GESTES_REGISTRE[g].principal}
				class:btn-danger={GESTES_REGISTRE[g].definitif}
				disabled={enCours}
				title={GESTES_REGISTRE[g].effet}
				on:click={() => dispatch('geste', g)}
			>
				<Icon name={GESTES_REGISTRE[g].icone} size={15} />{GESTES_REGISTRE[g].libelle}
			</button>
		{/each}
	</div>
	<p class="aide">
		Un motif est demandé, et s’inscrit au journal.
		{#if gestes.includes('supprimer')}
			Supprimer retire l’installation de la liste ; seul le contrat accepté reste archivé, cinq ans
			après la résiliation.
		{:else}
			La décision part dans le bail au prochain renouvellement de l’installation — chaque nuit, ou
			quand son administrateur le demande.
		{/if}
	</p>
{/if}

{#if fiche.services_modifiables}
	<h4 class="intertitre">Services accordés</h4>
	<div class="services">
		{#each accordables as s (s.code)}
			<label class="case">
				<input
					type="checkbox"
					checked={choisis.includes(s.code)}
					disabled={enCours}
					on:change={(e) => basculerService(s.code, e.currentTarget.checked)}
				/>
				{s.libelle}
			</label>
		{/each}
	</div>
	<p class="aide">
		Une réplique n’allume que ce qui est coché ici, et seulement tant qu’elle est active. La
		vérification de la version reste toujours permise.
	</p>
	{#if modifie}
		<PiedFormulaire
			soumission={false}
			{enCours}
			on:annule={() => (choisis = [...fiche.services_autorises])}
			on:enregistre={() => dispatch('services', choisis)}
		/>
	{/if}

	<DistributionInstallation {fiche} {versions} {vagues} {enCours} on:distribution />
{/if}

<h4 class="intertitre">Administrateur d’installation</h4>
{#if fiche.contact}
	<dl class="faits">
		<dt>Nom</dt>
		<dd>{nomAffiche(fiche.contact)}</dd>
		<dt>Courriel</dt>
		<dd><a href="mailto:{fiche.contact.courriel}">{fiche.contact.courriel}</a></dd>
		{#if fiche.contact.telephone}
			<dt>Téléphone</dt>
			<dd>{fiche.contact.telephone}</dd>
		{/if}
		<dt>Déclaré le</dt>
		<dd>{fmtDatetime(fiche.contact.mis_a_jour_le)}</dd>
	</dl>
{:else}
	<p class="aide">Aucun contact déclaré.</p>
{/if}

<h4 class="intertitre">Dernier rapport nocturne</h4>
{#if r && fiche.dernier_rapport_le}
	<dl class="faits">
		<dt>Reçu le</dt>
		<dd>{fmtDatetime(fiche.dernier_rapport_le)}</dd>
		<dt>Version</dt>
		<dd>
			v{r.identite
				.version_logicielle}{#if r.identite.derniere_mise_a_jour}{SEPARATEUR.point}dernière mise à
				jour : {r.identite.derniere_mise_a_jour}{/if}
		</dd>
		<dt>Hébergement</dt>
		<dd>
			{[r.hebergement.hebergeur, r.hebergement.pays_donnees, r.hebergement.architecture]
				.filter(Boolean)
				.join(' · ') || 'inconnu'}
		</dd>
		<dt>Disque</dt>
		<dd>{mo(r.hebergement.disque_occupe_mo)} sur {mo(r.hebergement.disque_total_mo)}</dd>
		<dt>Base</dt>
		<dd>{r.hebergement.moteur_base ?? 'inconnu'} · {mo(r.hebergement.taille_bases_mo)}</dd>
		<dt>Sauvegarde</dt>
		<dd>
			<span class="conformites">
				<span>
					{r.sauvegarde.derniere_reussie_le
						? fmtDatetime(r.sauvegarde.derniere_reussie_le)
						: 'aucune connue'}
				</span>
				<CocheConformite point={COPIE_HORS_MACHINE} conforme={r.sauvegarde.copie_hors_machine} />
			</span>
		</dd>
		<dt>Posture</dt>
		<dd>
			<ul class="conformites">
				{#each pointsPosture(r.posture) as p (p.cle)}
					<li><CocheConformite point={p.point} conforme={p.conforme} /></li>
				{/each}
			</ul>
		</dd>
		{#each r.coproprietes as c (c.identifiant)}
			<dt>Copropriété</dt>
			<dd>
				{c.nom} · {fmtNombre(c.lots)} lots · {fmtNombre(c.utilisateurs_actifs)} utilisateurs actifs sur
				{fmtNombre(c.utilisateurs_inscrits)}
			</dd>
		{/each}
	</dl>
{:else}
	<p class="aide">Aucun rapport reçu : il part chaque nuit, avec le renouvellement du bail.</p>
{/if}

<h4 class="intertitre">Contrat accepté</h4>
{#each fiche.contrats as c (c.version)}
	<p class="contrat">
		Version {c.version}, acceptée le {fmtDatetime(c.accepte_le)} par {c.accepte_par}
		<span class="aide">— empreinte <code>{c.empreinte.slice(0, 16)}</code></span>
	</p>
	<details>
		<summary>Lire le texte archivé</summary>
		<TexteMarkdown texte={c.texte} libelle="Texte archivé des conditions, version {c.version}" />
	</details>
{:else}
	<p class="aide">Aucun contrat archivé.</p>
{/each}

<h4 class="intertitre">Journal des décisions</h4>
<ol class="journal">
	{#each fiche.decisions as d, n (n)}
		<li>
			<span class="quand">{fmtDatetime(d.cree_le)}</span>
			<strong>{libelleDecision(d.geste)}</strong>{#if d.motif}{SEPARATEUR.tiret}{d.motif}{/if}
			<span class="auteur">· {d.auteur}</span>
		</li>
	{:else}
		<li class="aide">Aucune décision.</li>
	{/each}
</ol>

<style>
	.intertitre:first-child {
		margin-top: 0.25rem;
	}
	.gestes,
	.services {
		display: flex;
		flex-wrap: wrap;
		gap: 0.5rem 1rem;
		align-items: center;
	}
	.gestes .btn {
		display: inline-flex;
		align-items: center;
		gap: 0.35rem;
	}
	.alertes {
		margin: 0;
		padding-left: 1.1rem;
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
	}
	.faits {
		display: grid;
		grid-template-columns: max-content 1fr;
		gap: 0.25rem 0.75rem;
		margin: 0;
		font-size: var(--fs-sm);
	}
	.faits dt {
		color: var(--color-text-muted);
	}
	.faits dd {
		margin: 0;
		overflow-wrap: anywhere;
	}
	/*  Les points de conformité se suivent et passent à la ligne entiers : une
	    coche ne se sépare jamais de son fait. */
	.conformites {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.3rem 1rem;
		margin: 0;
		padding: 0;
		list-style: none;
	}
	.contrat {
		margin: 0 0 0.3rem;
		font-size: var(--fs-sm);
	}
	.journal {
		list-style: none;
		margin: 0;
		padding: 0;
		display: flex;
		flex-direction: column;
		gap: 0.3rem;
		font-size: var(--fs-sm);
	}
	.auteur {
		color: var(--color-text-muted);
	}
	.quand {
		color: var(--color-text-muted);
		margin-right: 0.4rem;
		font-variant-numeric: tabular-nums;
	}
	@media (max-width: 480px) {
		.faits {
			grid-template-columns: 1fr;
		}
		.faits dd {
			margin-bottom: 0.3rem;
		}
	}
</style>
