<!--
  Le CARNET D'ENTRETIEN — ce qui a été entretenu, réparé et contrôlé, et ce qui
  ne l'a pas été.

  Obligatoire depuis le décret n° 2001-477. Il n'existait nulle part, alors qu'il
  était déjà écrit en morceaux : contrats, interventions du calendrier, tickets
  clos. Le serveur les rassemble (`app/utils/carnet_entretien.py`) ; cet écran ne
  fait que les ranger.

  🔴 RÉSERVÉ aux copropriétaires, au conseil syndical et à l'admin (arbitré le
  10/09/2026). L'onglet est masqué aux locataires ET la route est refusée —
  masquer répond à ce qui s'affiche, refuser à ce qui s'atteint. Le droit est
  tenu par `require_proprietaire` côté serveur : cet écran ne fait que s'y
  conformer, il ne le décide pas.

  ⚠️ Le regroupement par ÉQUIPEMENT est le point de l'écran, pas une commodité de
  tri : c'est lui qui fait apparaître les trous. Une chaudière dont la dernière
  ligne date de trois ans se voit parce que ses voisines en ont de récentes —
  dans une liste chronologique, elle serait simplement plus bas.

  🗂️ Les entrées sont des CARTES au standard de la page Affaires (10/10/2026) :
  la gouttière porte la date et l'ORIGINE (contrat, intervention, affaire), les
  filtres vivent dans la grille des réglages (`ReglagesListe`). Les intertitres
  d'équipement restent — ce sont eux qui font l'écran.
-->
<script lang="ts">
	import type { ClasseGouttiere } from '$lib/gouttiere';
	import { onMount } from 'svelte';
	import CarteListe from '$lib/components/CarteListe.svelte';
	import EncartAvertissement from '$lib/components/EncartAvertissement.svelte';
	import { carnet as carnetApi, type Carnet, type EntreeCarnet } from '$lib/api';
	import { EQUIPEMENTS } from '$lib/prestataires';
	import { perimetreLabel } from '$lib/perimetres';
	import { perimetresStore } from '$lib/stores/perimetres';
	import { relire } from '$lib/utils';
	import FiltrePerimetre from './FiltrePerimetre.svelte';
	import ChoixPastilles from './ChoixPastilles.svelte';
	import ReglagesListe from './ReglagesListe.svelte';
	import EnteteCarte from './EnteteCarte.svelte';
	import ApercuCarte from './ApercuCarte.svelte';
	import IconeAction from './IconeAction.svelte';
	import LienAction from './LienAction.svelte';
	import { anneesDuCarnet, entreesDeLAnnee } from '$lib/carnet';
	import { categorieTicketLabel, NATURES } from '$lib/tickets';
	import { essayer } from '$lib/chargement';
	import EtatListe from './EtatListe.svelte';
	import SyntheseAffaire from './SyntheseAffaire.svelte';
	import { basculer } from '$lib/accordeon';
	import { isCS } from '$lib/stores/auth';

	let donnees: Carnet | null = null;
	let erreur = '';
	let chargement = true;
	/**  Un CODE de périmètre (`'bat:3'`, `'parking'`), jamais un identifiant de
	 *   bâtiment : c'est ce qui permet de filtrer sur un espace qui n'en a pas. */
	let perimetreChoisi: string | null = null;

	async function charger() {
		chargement = true;
		[donnees, erreur] = await essayer<Carnet | null>(carnetApi.lire(perimetreChoisi), null);
		chargement = false;
	}

	onMount(charger);

	/**  Le libellé d'un équipement vient d'`EQUIPEMENTS`, la table unique déjà
	 *   comparée à l'énumération du serveur par `test_types_equipement.py`. Le
	 *   serveur envoie la valeur ; en écrire une seconde table ici en ferait la
	 *   troisième écriture. */
	function libelleEquipement(valeur: string | null): string {
		if (!valeur) return 'Sans équipement rattaché';
		return EQUIPEMENTS.find((e) => e.val === valeur)?.label ?? valeur;
	}

	/**  La PORTÉE d'une entrée, toujours dite.
	 *
	 *   🔴 Elle est écrite même sous un filtre — surtout sous un filtre : un
	 *   contrat qui couvre toute la résidence apparaît sous « Bât. 3 », parce
	 *   qu'il l'entretient aussi. Sans sa portée, il s'y lirait comme propre à ce
	 *   bâtiment, et le filtre mentirait plus discrètement que celui qu'il
	 *   remplace.
	 *
	 *   `perimetreLabel` est la source unique du libellé — celle qui qualifie un
	 *   espace par son parent et trie par l'arbre, jamais par l'ordre des clics. */
	//  ⚠️ Une FONCTION appelée dans le gabarit ne crée aucune dépendance : Svelte
	//  ne la rappelle que si l'expression qui l'entoure change. `relire` la relie à
	//  l'arbre, qui arrive après le premier rendu (#947).
	$: portee = relire($perimetresStore, () => (codes: string[]) => perimetreLabel(codes ?? []));

	/**  Les entrées rangées par équipement, chaque groupe gardant l'ordre du
	 *   serveur — du fait le plus récent au plus ancien.
	 *
	 *   ⚠️ Les groupes sont triés par leur entrée la plus RÉCENTE, pas par ordre
	 *   alphabétique : ce qui a bougé récemment se lit en premier, et l'équipement
	 *   dont plus rien ne bouge tombe en bas — où il se remarque. */
	//  📅 Le filtre par ANNÉE (24/09/2026) — la règle, et ce que le décret
	//  n° 2001-477 en dit, vivent dans `$lib/carnet`.
	let anneeChoisie = '';
	$: annees = anneesDuCarnet(donnees?.entrees ?? []).map((a) => ({ val: a, label: a }));
	$: entreesVues = entreesDeLAnnee(donnees?.entrees ?? [], anneeChoisie);

	$: groupes = (() => {
		const par = new Map<string, EntreeCarnet[]>();
		for (const entree of entreesVues) {
			const cle = entree.equipement ?? '';
			if (!par.has(cle)) par.set(cle, []);
			par.get(cle)!.push(entree);
		}
		return [...par.entries()].sort((a, b) => (a[1][0].date < b[1][0].date ? 1 : -1));
	})();

	/**  Les entrées en alerte — l'encart les NOMME : un compte sans les noms oblige à
	 *   chercher dans la liste ce que l'encart vient d'annoncer. */
	$: enAlerte = (donnees?.entrees ?? []).filter((e) => e.alerte);
	$: enRetard = enAlerte.length;

	/**  🧾 La ligne d'une affaire qui a une synthèse VALIDÉE se déplie (#1643) :
	 *   la synthèse, puis le lien vers l'affaire. Une seule ouverte à la fois. */
	let ouverte: string | null = null;

	/**  Un contrat se lit chez les prestataires, que seul le CS voit : pour un
	 *   copropriétaire le lien mènerait à une page refusée. Il lit le nom, sans lien. */
	const lienOuvert = (e: EntreeCarnet, cs: boolean) =>
		e.origine === 'contrat' && !cs ? '' : e.lien;

	/**  Ce que chaque ORIGINE d'une entrée donne à sa carte — UNE table, une
	 *   entrée par origine (`lint:tables-statuts`) :
	 *   - `classe` : ce que la gouttière écrit, ce qui classe l'entrée. L'affaire
	 *     reprend la nature « Affaire » de la page Affaires (`NATURES`) : même
	 *     pictogramme, même abréviation, une seule écriture ;
	 *   - `vers` : « le contrat », « l'intervention », « l'affaire » — le nom du
	 *     lien de la carte. */
	const affaire = NATURES.find((n) => n.val === 'activite');
	const ORIGINES: Record<
		EntreeCarnet['origine'],
		{ classe: ClasseGouttiere | null; vers: string }
	> = {
		contrat: {
			classe: { icone: 'file-text', libelle: 'Contrat', abrege: 'CONTRAT' },
			vers: 'le contrat',
		},
		intervention: {
			classe: { icone: 'hard-hat', libelle: 'Intervention', abrege: 'INTERV.' },
			vers: "l'intervention",
		},
		affaire: {
			classe: affaire
				? { icone: affaire.icone, libelle: affaire.libelle, abrege: affaire.abrege }
				: null,
			vers: "l'affaire",
		},
	};
</script>

<div class="carnet">
	<p class="aide">
		Ce que la copropriété a fait entretenir, réparer et contrôler. Il est constitué automatiquement
		à partir des contrats, des entretiens terminés et des affaires résolues du bâti, rangées sous
		l'équipement que le conseil syndical désigne — rien n'y est saisi à la main. Une question ou une
		nuisance n'y figure pas.
	</p>

	<!--  Le filtre est le composant STANDARD : il prend ses pastilles dans
	      l'arborescence administrée, donc un périmètre créé demain y apparaît
	      sans qu'on touche à cet écran. Les deux rangées tiennent dans la
	      grille des réglages, libellés alignés sur la gouttière des cartes. -->
	<ReglagesListe>
		<FiltrePerimetre
			libelleDevant
			bind:choisi={perimetreChoisi}
			compte={entreesVues.length}
			on:changer={charger}
		/>
		{#if annees.length > 1}
			<ChoixPastilles
				options={annees}
				bind:valeur={anneeChoisie}
				tous="Toutes"
				compte={entreesVues.length}
				libelle="Année"
				libelleDevant
			/>
			<p class="aide">Les contrats en cours restent affichés : ils valent pour chaque année.</p>
		{/if}
	</ReglagesListe>

	{#if enRetard > 0}
		<!--  L'alerte est en TÊTE parce que c'est ce que le carnet apprend et que
		      rien d'autre ne dit. La date de prochaine visite existe en base depuis
		      toujours ; aucun écran ne la comparait à aujourd'hui. -->
		<EncartAvertissement role="status">
			⚠️ <strong
				>{enRetard} visite{enRetard > 1 ? 's' : ''} attendue{enRetard > 1 ? 's' : ''}</strong
			>
			dont l'échéance est dépassée :
			<ul class="concernees">
				{#each enAlerte as entree (entree.origine + entree.lien + entree.date)}
					<li>
						{#if lienOuvert(entree, $isCS)}
							<a href={entree.lien}>{entree.libelle}</a>
						{:else}
							<strong>{entree.libelle}</strong>
						{/if}
						<span class="concernee-detail"
							>({libelleEquipement(entree.equipement)} · {portee(entree.perimetre)}) — {entree.alerte}</span
						>
					</li>
				{/each}
			</ul>
		</EncartAvertissement>
	{/if}

	<EtatListe
		{chargement}
		{erreur}
		vide={groupes.length === 0}
		messageVide="Aucun contrat, aucune intervention terminée ni aucun ticket résolu pour ce périmètre."
	>
		<div class="groupes">
			{#each groupes as [equipement, entrees] (equipement)}
				<section>
					<h3 class="groupe-titre">{libelleEquipement(equipement)}</h3>
					<ol class="entrees">
						{#each entrees as entree (entree.origine + entree.lien + entree.date)}
							<li>
								<!--  Une carte ne se DÉPLIE que si elle a une synthèse validée
								      (#1643) ; sinon le titre reste un texte, et c'est la flèche
								      qui mène à la fiche d'origine. -->
								<CarteListe
									quand={entree.date}
									classe={ORIGINES[entree.origine].classe}
									expanded={ouverte === entree.lien}
									onDeplier={entree.synthese ? () => (ouverte = entree.lien) : null}
								>
									<EnteteCarte
										titre={entree.libelle}
										basculable={!!entree.synthese}
										on:toggle={() => (ouverte = basculer(ouverte, entree.lien))}
									>
										<svelte:fragment slot="actions">
											<LienAction
												href={entree.lien}
												icone="arrow-right"
												titre="Ouvrir"
												libelle="Ouvrir {ORIGINES[entree.origine].vers} : {entree.libelle}"
											/>
											{#if entree.synthese}
												<button
													type="button"
													class="btn-icon"
													aria-expanded={ouverte === entree.lien}
													aria-label="Synthèse de l'affaire"
													title="Synthèse de l'affaire"
													on:click|stopPropagation={() =>
														(ouverte = basculer(ouverte, entree.lien))}
													><IconeAction icone="receipt" /></button
												>
											{/if}
										</svelte:fragment>
										<!--  Juste sous le titre, les trois lignes de l'aperçu :
										      « Ce qui s'est passé » si une synthèse validée le
										      raconte, sinon la demande (24/10/2026) — le serveur
										      choisit. -->
										<svelte:fragment slot="apercu">
											{#if entree.extrait}
												<ApercuCarte contenu={entree.extrait} dansLigne />
											{/if}
											{#if entree.detail}
												<p class="detail">{entree.detail}</p>
											{/if}
										</svelte:fragment>
										<!--  La dernière ligne : ce qui DÉCRIT en capsules neutres, ce
										      qui ALERTE en capsule teintée. Une affaire se dit par sa
										      CATÉGORIE (26/09/2026) — son origine est déjà dans la
										      gouttière. -->
										<svelte:fragment slot="tags">
											{#if entree.categorie}
												<span class="badge badge-gray"
													>{categorieTicketLabel(entree.categorie)}</span
												>
											{/if}
											{#if entree.alerte}
												<span class="badge badge-orange">⚠️ {entree.alerte}</span>
											{/if}
											{#if portee(entree.perimetre)}
												<span class="badge badge-gray">{portee(entree.perimetre)}</span>
											{/if}
										</svelte:fragment>
									</EnteteCarte>
									{#if entree.synthese && ouverte === entree.lien}
										<div
											class="carte-corps pli"
											role="presentation"
											on:click|stopPropagation
											on:keydown|stopPropagation
										>
											<SyntheseAffaire synthese={entree.synthese} />
											<a class="vers-affaire" href={entree.lien}>Voir l'affaire →</a>
										</div>
									{/if}
								</CarteListe>
							</li>
						{/each}
					</ol>
				</section>
			{/each}
		</div>
	</EtatListe>
</div>

<style>
	.carnet {
		display: flex;
		flex-direction: column;
		gap: 1rem;
	}
	.groupes {
		display: flex;
		flex-direction: column;
		gap: 1.4rem;
	}
	.groupe-titre {
		margin: 0 0 0.5rem;
		font-size: var(--fs-lg);
		color: var(--color-primary);
		border-bottom: 1px solid var(--color-border);
		padding-bottom: 0.35rem;
	}
	.entrees {
		list-style: none;
		margin: 0;
		padding: 0;
	}
	/*  Le détail (prestataire, échéance…) dans la typographie de l'aperçu d'une
	    carte aérée : `--fs-md`, interligne 1,5, gris (`EnteteCarte`). */
	.detail {
		margin: 0.3rem 0 0;
		font-size: var(--fs-md);
		line-height: 1.5;
		color: var(--color-text-muted);
	}
	.concernees {
		margin: 0.35rem 0 0;
		padding-left: 1.25rem;
	}
	.concernees a {
		color: inherit;
		font-weight: 600;
	}
	.concernee-detail {
		font-size: var(--fs-sm);
	}
	/*  Le pli de la synthèse, dans le retrait de l'en-tête de la carte. */
	.pli {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
		padding: 0 1.1rem 0.9rem;
	}
	.vers-affaire {
		align-self: flex-end;
		font-size: var(--fs-sm);
		color: var(--color-primary);
	}
	@media (max-width: 480px) {
		.pli {
			padding: 0 0.7rem 0.75rem;
		}
	}
</style>
