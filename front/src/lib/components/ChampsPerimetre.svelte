<!--
  Les champs d'un nœud de périmètre — libellé, description, icône, et les
  drapeaux qui disent ce que ce nœud EST.

  Extrait d'`OngletPerimetres` le 31/08/2026, quand le contrôle de modularité a
  refusé que l'onglet franchisse les 500 lignes pour recevoir « Espace privatif ».
  Ce n'est pas un découpage de confort : les sept autres entités du site ont
  chacune leur `Formulaire<Entité>` ou `Champs<Entité>`, et l'administration des
  périmètres écrivait les siens à même l'onglet.

  ⚠️ Il porte les CHAMPS, pas le cadre ni les boutons : l'onglet ouvre une boîte
  à la création et une modale à l'édition (`ux-patterns` §14 bis), et c'est lui
  qui sait ce qu'enregistrer veut dire.
-->
<script lang="ts">
	import Icon from '#lib/components/Icon.svelte';
	import EtoileRequis from '#lib/components/EtoileRequis.svelte';
	import { ICONES_PERIMETRE } from '#lib/perimetres/index.ts';
	import { TYPES_ACCES } from '#lib/types-acces.ts';
	import { SEPARATEUR } from '#lib/separateurs.ts';

	/** L'objet de saisie, lié dans les deux sens : l'onglet porte son cycle de vie. */
	export let form: {
		libelle: string;
		libelle_court: string;
		description: string;
		icone: string;
		portee_globale: boolean;
		selectionnable: boolean;
		privatif: boolean;
		hors_copropriete: boolean;
		ordre: number;
		actif: boolean;
		acces_fixes: string[];
	};
	/**  Le code du nœud — **immuable** : il est enregistré dans les contenus déjà
	 *   publiés. C'est pourquoi ce composant ne sert QUE l'édition ; la création
	 *   demande le code, et pose donc d'autres champs. */
	export let code: string;
	/** Le libellé long, proposé en filigrane du libellé court. */
	export let libelleParDefaut = '';
	/**  Ce nœud concerne-t-il déjà tous les résidents **par héritage** ? La case
	 *   ci-dessous ne dit que ce qui est décidé ICI ; sans cette distinction, un
	 *   nœud hérité affichait une case décochée qui semblait le contredire. */
	export let concerneTousHerite = false;

	function basculerAcces(type: string, coche: boolean) {
		form.acces_fixes = coche
			? [...form.acces_fixes, type]
			: form.acces_fixes.filter((t) => t !== type);
	}
</script>

<p class="modal-code">
	Code <code>{code}</code>{SEPARATEUR.tiret}non modifiable : il est enregistré dans les contenus
	déjà publiés.
</p>

<label class="field"
	><span>Libellé<EtoileRequis vide={!form.libelle.trim()} /></span>
	<input bind:value={form.libelle} required />
</label>
<label class="field"
	>Libellé court
	<input bind:value={form.libelle_court} placeholder={libelleParDefaut} />
	<span class="aide">Employé sur les pastilles étroites du calendrier.</span>
</label>
<div class="field">
	Icône
	<div class="icones">
		<button
			type="button"
			class="icone"
			class:icone-active={!form.icone}
			title="Aucune icône"
			aria-label="Aucune icône"
			on:click={() => (form.icone = '')}>—</button
		>
		{#each ICONES_PERIMETRE as ic (ic.nom)}
			<button
				type="button"
				class="icone"
				class:icone-active={form.icone === ic.nom}
				title={ic.libelle}
				aria-label={ic.libelle}
				on:click={() => (form.icone = ic.nom)}
			>
				<Icon name={ic.nom} size={18} />
			</button>
		{/each}
	</div>
	<span class="aide"> Affichée sur la pastille du sélecteur, devant le libellé. </span>
</div>

<label class="field"
	>Description
	<textarea bind:value={form.description} rows="4"></textarea>
	<span class="aide"> Affichée sous le sélecteur, au moment où l’on choisit ce périmètre. </span>
</label>
<label class="field"
	>Ordre
	<input type="number" bind:value={form.ordre} />
</label>

<label class="field-check">
	<input type="checkbox" bind:checked={form.selectionnable} />
	Proposé à la saisie
	<span class="aide">
		Décochez pour un regroupement, ou pour retirer un périmètre des formulaires sans toucher aux
		contenus qui le citent déjà.
	</span>
</label>

<label class="field-check">
	<input type="checkbox" bind:checked={form.privatif} />
	Espace privatif
	<span class="aide">
		Un logement, une cave, une place attribuée. La pastille s'en distingue à la saisie.
	</span>
</label>

<!--  🔴 Deux questions distinctes, et l'AFUL répond différemment à chacune :
      « concerne tous les résidents » (qui VOIT) et « appartient à la
      copropriété » (ce qui la COUVRE). L'aide le dit, parce que cocher la
      mauvaise case ici fait disparaître des lignes d'un filtre. -->
<label class="field-check">
	<input type="checkbox" bind:checked={form.hors_copropriete} />
	N'appartient pas à la copropriété
	<span class="aide">
		Un espace géré par un tiers{SEPARATEUR.tiret}l'AFUL, une voie communale. Ce qui couvre « toute
		la copropriété » ne le couvre alors pas&nbsp;: un contrat d'entretien de la résidence
		n'apparaîtra pas dans son filtre. Sans effet sur qui le voit.
	</span>
</label>

<!--  🔴 Réglés ICI depuis le 17/10/2026 (#2060) : ces accès étaient lus par le
      serveur (`utils/acces_choix`) sans qu'aucun écran ne les écrive. Un portillon
      se coche là où il est décrit ; la liste se compose sur le serveur. -->
<div class="field" role="group" aria-label="Accès fixes">
	Accès fixes
	{#each TYPES_ACCES as t (t.val)}
		<label class="field-check">
			<input
				type="checkbox"
				checked={form.acces_fixes.includes(t.val)}
				on:change={(e) => basculerAcces(t.val, e.currentTarget.checked)}
			/>
			{t.label}
		</label>
	{/each}
	<span class="aide">
		Ce périmètre s’ouvre avec tout accès du type coché, sans dépendre d’aucun lot{SEPARATEUR.tiret}un
		portillon, un portail. Il est alors proposé, et accepté, pour chacun.
	</span>
</div>

<label class="field-check">
	<input type="checkbox" bind:checked={form.actif} />
	Actif
</label>

<label class="field-check danger">
	<input type="checkbox" bind:checked={form.portee_globale} />
	Visible de tous
	{#if concerneTousHerite && !form.portee_globale}
		<span class="aide herite">
			ℹ️ Ce périmètre est <strong>déjà</strong> visible de tous, par héritage de son parent{SEPARATEUR.tiret}la
			case ci-dessus est décochée, et c’est normal. La cocher n’ajouterait rien ; la laisser
			décochée ne retire rien. Pour changer cela, il faut décocher la case du périmètre parent.
		</span>
	{/if}
	<span class="aide">
		⚠️ Un contenu ciblé sur ce périmètre{SEPARATEUR.tiret}ou sur l’un de ses sous-périmètres{SEPARATEUR.tiret}sera
		visible de <strong>tous</strong>
		et notifiera
		<strong>l’ensemble du conseil syndical</strong>, quel que soit leur bâtiment.
	</span>
</label>

<style>
	.modal-code {
		font-size: var(--fs-sm);
		color: var(--color-text-muted);
		margin: -0.4rem 0 1rem;
	}
	.icones {
		display: flex;
		flex-wrap: wrap;
		gap: 0.3rem;
		margin-top: 0.3rem;
	}
	.icone {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		width: 2rem;
		height: 2rem;
		border: 1px solid var(--color-border);
		border-radius: var(--radius);
		background: var(--color-surface);
		cursor: pointer;
		color: var(--color-text-muted);
		font-size: var(--fs-sm);
	}
	@media (hover: hover) and (pointer: fine) {
		.icone:hover {
			border-color: var(--color-primary);
			color: var(--color-text);
		}
	}
	.icone-active {
		background: var(--color-primary-plein);
		color: var(--color-sur-plein);
		border-color: var(--color-primary-plein);
	}
	.field-check {
		display: block;
		font-size: var(--fs-md);
		margin-bottom: 0.8rem;
	}
	.field-check.danger {
		border-left: 3px solid var(--color-warning);
		padding-left: 0.6rem;
	}
	.herite {
		border-left: 2px solid var(--color-border);
		padding-left: 0.5rem;
		margin-top: 0.4rem;
	}
</style>
