<!--
  Le COÛT d'un usage de l'assistant : ses limites d'appels et ses trois prix
  (#1383, prix en dollars et cache le 30/09/2026). Sorti de `BlocUsageIA` le
  30/09/2026 : le bloc franchissait 500 lignes (modularité, rang 1).

  🔴 Les limites COMPTENT DES APPELS (04/10/2026), plus des jetons : un
  plafond de « 100000 » jetons ne disait pas combien de synthèses il permet.
  Le PREMIER ESSAI — le premier appel réussi avec le modèle et l'effort
  enregistrés — chiffre ce qu'un appel coûte, donc ce que la limite laisse
  dépenser. C'est le serveur qui le reconnaît et le chiffre (`llm_limites`) :
  l'écran ne recalcule aucun coût.

  Il ÉCRIT dans `valeurs` (lié), comme le bloc : c'est l'onglet qui enregistre,
  d'un seul geste. Le ✨ qui cherche le tarif reste dans le bloc, à côté du
  modèle ; ce composant n'en montre que le compte rendu (`tarifEnregistre`).
-->
<script context="module" lang="ts">
	import type { PrixIA } from '#lib/api/index.ts';

	//  🔴 Les prix, en DOLLARS par million de jetons (30/09/2026, arbitré :
	//  « comme les grilles »), et TROIS — l'entrée lue en cache a le sien chez
	//  OpenAI. Stockés tels que saisis, en texte décimal (« 0.075 ») : jamais
	//  un flottant, et plus des centimes, où 0,075 $ ne tenait pas. Un champ
	//  par prix, écrit UNE fois : les trois ne diffèrent que par leurs mots.
	export const PRIX: { champ: PrixIA; libelle: string; aide: string }[] = [
		{
			champ: 'prix_entree',
			libelle: 'Prix des jetons envoyés',
			aide: 'Comme la grille de votre fournisseur.',
		},
		{
			champ: 'prix_sortie',
			libelle: 'Prix des jetons produits',
			aide: 'La réponse, raisonnement compris. Sans prix, la consommation (Maintenance) s’affiche en jetons seuls.',
		},
		{
			champ: 'prix_cache',
			libelle: 'Prix des jetons en cache',
			aide: 'L’entrée déjà vue, que le fournisseur relit en cache et facture moins cher (« cached input »). Vide : elle compte au prix des jetons envoyés.',
		},
	];
</script>

<script lang="ts">
	import SectionFormulaire from '#lib/components/SectionFormulaire.svelte';
	import type { LimitesUsageIA, UsageIA } from '#lib/api/index.ts';
	import { fmtDate } from '#lib/date.ts';
	import { fmtMontant, fmtNombre } from '#lib/utils.ts';

	/** Toutes les valeurs de configuration, liées : le composant écrit les siennes. */
	export let valeurs: Record<string, string>;
	export let cles: UsageIA['cles'];
	/** Le compte rendu du ✨ quand il vient d'enregistrer un tarif, sinon vide. */
	export let tarifEnregistre = '';
	/** Où en est l'usage — appels du mois, premier essai —, lu par l'onglet. */
	export let limites: LimitesUsageIA | undefined = undefined;
	/** Un geste de personne l'appelle-t-il ? Sinon, pas de limite par personne. */
	export let gesteManuel = true;

	//  0 = aucune limite.
	$: appelsMois = Number(valeurs[cles.appels_mois]) || 0;
	$: appelsHeure = Number(valeurs[cles.appels_heure]) || 0;
	$: essai = limites?.premier_essai ?? null;
	$: coutEssai = essai?.cout_usd == null ? null : Number(essai.cout_usd);
	$: jetonsEssai = (essai?.jetons_entree ?? 0) + (essai?.jetons_sortie ?? 0);
	//  Deux décimales liraient « 0 $ » le coût d'un appel : quatre en dessous du dollar.
	const dollars = (v: number) => fmtMontant(v, 'USD', v < 1 ? 4 : 2);
	//  Une ESTIMATION : un appel peut être plus long que l'essai.
	$: estimation =
		coutEssai !== null && appelsMois
			? ` → ${fmtNombre(appelsMois)} appels ≈ ${dollars(coutEssai * appelsMois)} par mois (estimation)`
			: '';

	function poser(cle: string, valeur: string) {
		valeurs = { ...valeurs, [cle]: valeur };
	}
</script>

<SectionFormulaire titre="Coût et limites">
	<div class="form-grid">
		<label class="field">
			Appels maximum par mois
			<input
				type="number"
				value={appelsMois || ''}
				min="0"
				step="1"
				inputmode="numeric"
				placeholder="Aucune limite"
				on:input={(e) => poser(cles.appels_mois, e.currentTarget.value)}
			/>
			<span class="aide">
				Les appels réussis, du premier au dernier jour du mois. Atteint, l’usage est refusé avant
				tout envoi — l’automatique s’arrête — et le contrôle de 6&nbsp;h le signale. Vide&nbsp;:
				aucune limite.
			</span>
		</label>
		{#if gesteManuel}
			<label class="field">
				Appels maximum par heure et par personne
				<input
					type="number"
					value={appelsHeure || ''}
					min="0"
					step="1"
					inputmode="numeric"
					placeholder="Aucune limite"
					on:input={(e) => poser(cles.appels_heure, e.currentTarget.value)}
				/>
				<span class="aide">
					Sur l’heure glissante, pour qui fait le geste&nbsp;; l’appel automatique n’y est pas
					soumis. Vide&nbsp;: aucune limite.
				</span>
			</label>
		{/if}
		{#each PRIX as p (p.champ)}
			<label class="field">
				{p.libelle} ($ / million)
				<input
					type="number"
					value={valeurs[cles[p.champ]] ?? ''}
					min="0"
					step="any"
					inputmode="decimal"
					placeholder="Non renseigné"
					on:input={(e) => poser(cles[p.champ], e.currentTarget.value)}
				/>
				<span class="aide">{p.aide}</span>
			</label>
		{/each}
	</div>
	{#if essai}
		<p class="aide">
			<strong>1er essai</strong> — {essai.modele} · effort {essai.effort}, le {fmtDate(
				essai.le,
			)}&nbsp;:
			{fmtNombre(jetonsEssai)} jetons · {coutEssai === null
				? 'renseignez les prix pour en avoir le coût'
				: dollars(coutEssai) + estimation}.
		</p>
	{:else if limites}
		<p class="aide">
			Pas encore d’essai avec ce modèle et cet effort&nbsp;: le premier appel réussi en donnera le
			coût. Le test de connexion ne compte pas.
		</p>
	{/if}
	{#if limites}
		<p class="aide">
			Ce mois-ci&nbsp;: {fmtNombre(limites.appels)} appel{limites.appels > 1 ? 's' : ''}{appelsMois
				? ` sur ${fmtNombre(appelsMois)}`
				: ''}.
		</p>
	{/if}
	{#if tarifEnregistre}
		<p class="aide">✅ Tarif enregistré — {tarifEnregistre}</p>
	{/if}
</SectionFormulaire>
