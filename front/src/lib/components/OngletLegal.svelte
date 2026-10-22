<!--
  L'onglet **Pages légales** de l'administration (#2065).

  Une installation sert plusieurs syndicats de copropriétaires : chacun est
  responsable du traitement de ses données, l'opérateur de l'installation son
  sous-traitant. Les deux textes portent donc des **champs** — `[[syndic]]`,
  `[[operateur]]`… — que le site remplit de l'identité de CETTE copropriété.

  Ce que l'onglet ajoute aux deux éditeurs :
  - le **constat** : un texte jamais relu, modifié depuis, ou qui dit encore
    « À RENSEIGNER » est à relire — calculé par le serveur, jamais ici ;
  - le geste **« J'ai relu ces textes »**, refusé par le serveur tant qu'il manque
    quelque chose ;
  - l'**adresse où exercer ses droits**, et la valeur de chaque champ.

  ## Ce qui reste chez le parent

  Comme `OngletFonctionnement` : `siteConfig` est LIÉ et `saveSiteConfig` arrive en
  callback — la page parle à l'API et tient le `configStore`. L'onglet ne relit
  que le constat, après un enregistrement ou une relecture.
-->
<script lang="ts">
	import {
		config as configApi,
		type ChampTexteLegal,
		type ConstatTextesLegaux,
		type EtatTexteLegal,
	} from '$lib/api';
	import type { ConfigSite } from '$lib/configSite';
	import { fmtDatetime } from '$lib/date';
	import { messageErreur } from '$lib/erreurs';
	import type { PointConformite } from '$lib/registre-installations';
	import CocheConformite from '$lib/components/CocheConformite.svelte';
	import EncartAvertissement from '$lib/components/EncartAvertissement.svelte';
	import Icon from '$lib/components/Icon.svelte';
	import RichEditor from '$lib/components/RichEditor.svelte';
	import { toast } from '$lib/components/Toast.svelte';

	/** Lié : la page porte l'état et l'enregistre. */
	export let siteConfig: ConfigSite;
	export let siteSaving = false;
	export let saveSiteConfig: () => Promise<void> | void;
	/** Le constat et les champs, lus par la page avec les textes. */
	export let constat: ConstatTextesLegaux;
	export let champs: ChampTexteLegal[];

	let relecture = false;

	function point(e: EtatTexteLegal): PointConformite {
		return {
			conforme: `${e.titre} ${e.participe_relu}`,
			aCorriger: `${e.titre} à relire`,
			inconnu: e.titre,
			explication: e.complet
				? e.relu
					? `Relecture déclarée le ${fmtDatetime(e.relu_le)}, sur le texte enregistré.`
					: 'Aucune relecture déclarée, ou texte modifié depuis la dernière.'
				: 'Il manque encore ce que la liste dessous énumère, avec où le renseigner.',
		};
	}

	async function relireConstat() {
		const source = await configApi.textesLegaux();
		constat = source.etat;
		champs = source.champs;
	}

	async function enregistrer() {
		await saveSiteConfig();
		try {
			await relireConstat();
		} catch (e) {
			toast('error', messageErreur(e, 'Le constat n’a pas pu être relu.'));
		}
	}

	async function declarerRelus() {
		relecture = true;
		try {
			constat = await configApi.declarerRelus();
			toast('success', 'Relecture enregistrée.');
		} catch (e) {
			toast('error', messageErreur(e, 'La relecture n’a pas pu être enregistrée.'));
		} finally {
			relecture = false;
		}
	}
</script>

<section class="card config-section">
	<h2 class="config-section-title"><Icon name="shield-check" size={17} />Relecture</h2>
	{#if constat.a_relire}
		<EncartAvertissement role="status">
			Ces textes engagent le syndicat des copropriétaires : il en est le responsable, et l'opérateur
			de l'installation son sous-traitant. Relisez-les, complétez ce qui manque, enregistrez, puis
			déclarez-les relus.
		</EncartAvertissement>
	{/if}
	<ul class="constat">
		{#each constat.textes as e (e.cle)}
			<li>
				<CocheConformite point={point(e)} conforme={!e.a_relire} />
				{#if e.manques.length}
					<ul class="manques">
						{#each e.manques as m (m)}<li>{m}</li>{/each}
					</ul>
				{/if}
			</li>
		{/each}
	</ul>
	{#if constat.a_relire}
		<div class="form-actions">
			<button
				class="btn btn-outline"
				on:click={declarerRelus}
				disabled={relecture}
				aria-busy={relecture}
			>
				{relecture ? 'Enregistrement…' : 'J’ai relu ces textes'}
			</button>
		</div>
	{/if}
</section>
<hr class="separateur-section" />
<section class="card config-section">
	<h2 class="config-section-title"><Icon name="user" size={17} />Identité nommée par les textes</h2>
	<p class="muted intro-texte">
		Écrivez un champ entre doubles crochets — <code>[[syndic]]</code> — : chaque page le remplace par
		sa valeur ci-dessous, ou par « À RENSEIGNER » s'il n'en a pas.
	</p>
	<div class="largeur-saisie">
		<label class="field">
			<span>Adresse pour exercer ses droits</span>
			<input
				type="email"
				bind:value={siteConfig.contact_donnees}
				placeholder="donnees@exemple.fr"
			/>
			<span class="aide"
				>Le champ <code>[[contact]]</code> : joignable sans compte, au nom du responsable du traitement
				— un droit d'effacement s'exerce souvent après la suppression du compte.</span
			>
		</label>
	</div>
	<dl class="champs">
		{#each champs as c (c.nom)}
			<dt><code>[[{c.nom}]]</code></dt>
			<dd>
				{#if c.valeur}{c.valeur}{:else}<span class="a-renseigner">À renseigner</span> — {c.ou}{/if}
			</dd>
		{/each}
	</dl>
</section>
<hr class="separateur-section" />
<section class="card config-section">
	<h2 class="config-section-title"><Icon name="file-text" size={17} />Mentions légales</h2>
	<p class="muted intro-texte">
		Contenu affiché sur <code>/mentions-legales</code>.
	</p>
	<RichEditor bind:value={siteConfig.mentions_legales} minHeight="380px" titres sourceHtml />
</section>
<hr class="separateur-section" />
<section class="card config-section">
	<h2 class="config-section-title">
		<Icon name="shield" size={17} />Politique de confidentialité
	</h2>
	<p class="muted intro-texte">
		Contenu affiché sur <code>/politique-de-confidentialite</code>.
	</p>
	<RichEditor
		bind:value={siteConfig.politique_confidentialite}
		minHeight="380px"
		titres
		sourceHtml
	/>
</section>
<div class="form-actions">
	<button class="btn btn-primary" on:click={enregistrer} disabled={siteSaving}>
		{siteSaving ? 'Enregistrement…' : 'Enregistrer'}
	</button>
</div>

<style>
	code {
		background: var(--color-bg);
		padding: 0.1rem 0.35rem;
		border-radius: 0.25rem;
		font-size: 0.85em;
	}
	.intro-texte {
		margin-bottom: 1rem;
	}
	.constat {
		list-style: none;
		margin: 0.75rem 0 0;
		padding: 0;
		display: grid;
		gap: 0.5rem;
	}
	.manques {
		margin: 0.25rem 0 0 1.6rem;
		padding-left: 1rem;
		font-size: var(--fs-sm);
		color: var(--color-text-muted);
	}
	.champs {
		display: grid;
		grid-template-columns: max-content 1fr;
		gap: 0.3rem 1rem;
		margin: 0.75rem 0 0;
		font-size: var(--fs-sm);
	}
	.champs dd {
		margin: 0;
		min-width: 0;
		overflow-wrap: anywhere;
	}
	.a-renseigner {
		font-weight: 600;
		color: var(--color-warning-texte);
	}
</style>
