<script lang="ts">
	import { fmtNombre } from '#lib/utils.ts';
	import Badge from '#lib/components/Badge.svelte';
	import { messageErreur } from '#lib/erreurs.ts';
	import Icon from '#lib/components/Icon.svelte';
	//  Extrait de `admin/+page.svelte` (2577 lignes, cinq fois le plafond de
	//  modularité) le 11/08/2026, plutôt que d'y ajouter la colonne « Tâche ».
	//
	//  Les deux tableaux vivent ensemble parce qu'ils décrivent le MÊME fait sous
	//  deux angles — ce qui aurait dû arriver, et ce qui est arrivé. Les séparer
	//  est précisément ce qui a rendu l'écran illisible : « Maintenance
	//  hebdomadaire : jamais exécutée » au-dessus d'un tableau qui semblait
	//  montrer des maintenances quotidiennes réussies.
	import { onMount } from 'svelte';
	import { admin as adminApi, type ExecutionTache, type SanteMaintenance } from '#lib/api/index.ts';
	import { fmtDatetime } from '#lib/date.ts';
	import { toast } from '#lib/components/Toast.svelte';
	import { LIBELLE_TACHE, LIBELLE_ACTION } from '#lib/taches.ts';
	//  🔴 Les trois tables de STATUT vivent dans `#lib/taches.ts`, à côté des
	//  libellés de tâches — c'est la même notion, et les libellés y étaient déjà
	//  pour la raison qui vaut ici : les redéfinir dans un écran est ce qui les
	//  fait diverger. Le garde-fou de modularité a refusé leur croissance dans ce
	//  fichier (#488) ; la bonne réponse n'était pas de raboter mais de remonter.
	import { LIBELLE_STATUT, AIDE_STATUT, CLASSE_STATUT } from '#lib/taches.ts';
	import ConfigSauvegarde from '#lib/components/ConfigSauvegarde.svelte';
	import EtatListe from '#lib/components/EtatListe.svelte';
	import TableExecutionsTache from '#lib/components/TableExecutionsTache.svelte';
	import { SEPARATEUR } from '#lib/separateurs.ts';

	//  Le bouton dit ce qu'il FAIT, pas le nom de la tâche — voir LIBELLE_ACTION.
	//  Défaut : « Lancer <nom de la tâche> », qui reste juste là où le bouton
	//  déclenche bien la tâche entière (sauvegarde, agrégation).
	const libelleBouton = (t: string) =>
		LIBELLE_ACTION[t] ?? `Lancer ${LIBELLE_TACHE[t].toLowerCase()}`;

	let sante: SanteMaintenance | null = null;
	let santeLoading = true;
	/*  🔴 `catch { sante = null }` faisait dire « Aucune donnée — aucune exécution
	    n'a encore été enregistrée » sur un chargement en ÉCHEC (#816). Sur l'écran
	    qui surveille les tâches planifiées, c'est le pire message possible : il
	    annonce que rien ne tourne, alors qu'on n'a pas pu regarder. */
	let erreur = '';
	let enCours: string | null = null;

	//  Le tableau des exécutions filtrait sur RIEN : il affichait toutes les
	//  tâches de `historique_maintenance` — bascules et copies hors site
	//  comprises — sous un titre qui annonce des maintenances, et sans colonne
	//  pour les distinguer. D'où des lignes « 02:00 » quotidiennes en face d'une
	//  tâche hebdomadaire déclarée jamais exécutée, et des colonnes Taille DB et
	//  Détail vides : une bascule n'a ni l'une ni l'autre à déclarer.
	//  Signalé par l'utilisateur le 11/08/2026, par aucun contrôle.
	//
	//  Les libellés eux-mêmes vivent dans `#lib/taches.ts` : ils servent AUSSI aux
	//  titres des cartes de détail, qui sont dans un autre fichier. Les redéfinir
	//  ici est précisément ce qui les avait fait diverger.

	//  « Jamais exécutée » affirmait plus que ce que le contrôle mesure : il
	//  observe l'absence de RAPPORT en base, pas l'absence d'exécution. Les deux
	//  ont été confondus le 09/08/2026, la maintenance ayant tourné le matin même
	//  sans que sa ligne survive à la rétention. Le libellé dit désormais ce qui
	//  est mesuré (`standards/04-fiabilite-des-controles.md` §14).
	//  🔴 CINQ états, pas trois (#488). « Exécutée, rapport non reçu » était
	//  indiscernable d'« À jour », puis d'« Exécution manquante » : deux jours de
	//  faux vert, puis un faux rouge, du 16 au 18/08/2026.

	//  ⚠️ La couleur suit la GRAVITÉ, pas le nom. « En cours » est vert : la tâche
	//  fait ce qu'on attend d'elle. « Rapport non reçu » est orange et non rouge —
	//  rien n'est cassé côté tâche, c'est la surveillance qui est aveugle, et un
	//  rouge y enverrait chercher au mauvais endroit.

	async function charger() {
		santeLoading = true;
		erreur = '';
		try {
			sante = await adminApi.santeMaintenance();
		} catch (e) {
			sante = null;
			erreur = messageErreur(e, 'Chargement impossible');
		} finally {
			santeLoading = false;
		}
		//  Les historiques déjà dépliés sont rechargés : après un déclenchement
		//  manuel, la ligne ouverte doit montrer le passage qu'on vient de causer.
		for (const t of Object.keys(historiques)) await chargerHistorique(t, true);
	}

	//  Chaque tâche a SA source. Le tableau unique « Journal des exécutions »
	//  mélangeait les trois tâches de `historique_maintenance` sous un titre qui
	//  n'en annonçait qu'une, et laissait les deux autres — sauvegarde et
	//  agrégation — dans des cartes séparées : trois tableaux pour un même fait,
	//  aucun ne le disant. Signalé illisible par l'utilisateur le 11/08/2026.
	//  Le détail vit désormais SOUS la ligne qui l'annonce.
	//  🔴 La table `SOURCE` des routes d'historique a REJOINT le client le
	//  06/09/2026 (#801) : deux de ses routes y étaient déjà déclarées
	//  (`telemetryHistorique`, `telemetryAgreger`) et figuraient au relevé des
	//  méthodes « sans appelant » — elles en avaient un, il passait par une
	//  table. Une route rangée dans une table reste une route recopiée.

	//  Profondeur d'historique sous une ligne dépliée. UNE constante : elle était
	//  écrite trois fois — dans `SOURCE.limite`, qui n'était même pas lue, dans
	//  l'URL des tâches à source commune, et dans le `slice` des tables propres.
	//  Portée de 4 à 10 le 11/08/2026 en supprimant les deux cartes de détail qui
	//  montraient l'historique complet (#299) : les retirer sans compenser aurait
	//  réduit en silence ce qu'un administrateur peut voir.
	const PROFONDEUR = 10;

	//  Ce que fait une tâche, quand sa ligne seule ne le dit pas. Repris des deux
	//  cartes supprimées avec #299 : elles faisaient double emploi pour
	//  l'historique, mais portaient ces informations-là, et rien d'autre ne les
	//  donnait. Les supprimer sans les déplacer aurait perdu la seule mention du
	//  lieu de stockage des archives.
	const AIDE_TACHE: Record<string, string> = {
		backup: 'Stockage des archives : /backups, dans le conteneur de l’API',
		telemetrie:
			'Automatique chaque nuit à 2 h. Agrège les événements bruts en données ' +
			'journalières puis mensuelles, et purge les données expirées.',
		//  Pas de sous-ligne par nœud : le poste l'exécute, et le nœud nommé est
		//  celui d'où vient l'archive du jour (`_TACHES_HORS_DES_NOEUDS`).
		export_hors_site:
			'Lancée depuis le poste, pas par un nœud. Le nœud affiché est celui d’où vient ' +
			'l’archive du jour ; les archives de l’autre nœud sont rattrapées au même passage.',
	};

	let historiques: Record<string, ExecutionTache[]> = {};
	let enChargement: Record<string, boolean> = {};

	/**  L'échec de chargement, PAR tâche — une table comme `enChargement`.
	 *
	 *   ⚠️ Par tâche et non globale : deux historiques peuvent être ouverts, et
	 *   l'échec de l'un ne doit rien dire de l'autre. */
	let erreursTache: Record<string, string> = {};

	async function chargerHistorique(tache: string, force = false) {
		if (historiques[tache] && !force) return;
		enChargement = { ...enChargement, [tache]: true };
		erreursTache = { ...erreursTache, [tache]: '' };
		try {
			const lignes = await adminApi.historiqueTache(tache, PROFONDEUR);
			//  Les tables propres à une tâche ne savent pas se limiter côté serveur :
			//  on tronque ici, à la même profondeur que les autres.
			historiques = { ...historiques, [tache]: (lignes ?? []).slice(0, PROFONDEUR) };
		} catch (e) {
			//  🔴 `catch { historiques[tache] = [] }` était le motif de #519 écrit une
			//  SECONDE fois dans ce fichier : un échec devenait « aucune exécution
			//  enregistrée pour cette tâche », sur l'écran qui sert justement à
			//  vérifier qu'elle s'exécute. `lint:etat-liste` ne l'avait pas vu — il
			//  ne cherche que `.empty-state`, et ce vide-ci tenait en une ligne.
			historiques = { ...historiques, [tache]: [] };
			erreursTache = {
				...erreursTache,
				[tache]: messageErreur(e, 'Historique illisible'),
			};
		} finally {
			enChargement = { ...enChargement, [tache]: false };
		}
	}

	//  Une seule ligne ouverte à la fois — pattern des cartes expansibles du projet.
	let ouverte: string | null = null;
	function basculer(tache: string) {
		ouverte = ouverte === tache ? null : tache;
		if (ouverte) chargerHistorique(ouverte);
	}

	//  Seules ces trois tâches savent se lancer à la main : les autres n'ont pas
	//  d'équivalent in-process. Ne montrer le bouton que là où il agit.
	//  ⚠️ Ce bouton ne lance PAS `maintenance.sh`. Il appelle
	//  `POST /admin/maintenance/lancer` → `run_maintenance`, exécuté DANS le
	//  process de l'API : purges applicatives + VACUUM, sur le seul nœud qui
	//  répond. Le script hebdomadaire fait cela ET l'hygiène locale du standby
	//  (images Docker, cache de build, rotation des journaux) — que rien ici ne
	//  déclenche. Deux choses différentes : le libellé et l'aide le disent
	//  désormais, faute de quoi un clic ici laisse croire que l'hebdomadaire a
	//  été rattrapée.
	//
	//  Le retour à l'utilisateur avait été perdu en extrayant ce composant : ni
	//  succès ni erreur n'étaient signalés, et un clic sans effet visible se lit
	//  comme un bouton mort. La tâche part en arrière-plan (202), donc le succès
	//  annoncé est celui de la PRISE EN COMPTE, pas du ménage — le tableau, lui,
	//  dira ce qui s'est réellement passé.
	async function declencher(tache: string) {
		if (!adminApi.tacheLancable(tache)) return;
		enCours = tache;
		try {
			await adminApi.lancerTache(tache);
			toast('success', `${LIBELLE_TACHE[tache]} lancée en arrière-plan.`);
			//  La tâche part en arrière-plan (202) : le succès annoncé est celui de
			//  la PRISE EN COMPTE. C'est l'historique rechargé qui dira ce qui s'est
			//  réellement passé — d'où le rechargement différé.
			setTimeout(charger, 4000);
		} catch (e) {
			toast('error', messageErreur(e, `Impossible de lancer ${LIBELLE_TACHE[tache]}`));
		} finally {
			enCours = null;
		}
	}

	onMount(charger);
</script>

<section class="card config-section">
	<h2 class="config-section-title">
		<Icon name="clipboard-list" size={17} />Santé des tâches planifiées
	</h2>
	<p class="muted texte-md">
		Synthèse : <strong>une ligne par tâche</strong>, portant la
		<strong>dernière exécution réelle</strong>{SEPARATEUR.tiret}quel que soit le nœud qui l'a faite.
		En dessous,
		<strong>une sous-ligne par nœud ayant rendu compte</strong> : un nœud sain ne compense pas un
		nœud muet, et l'on voit lequel décroche sans avoir à cliquer. La copie hors site n'en a pas :
		c'est le poste qui l'exécute, pas un nœud. Sans ce contrôle, une absence de ligne se lirait
		comme « tout va bien ».
		<br />
		⚠️ Une tâche qui n'affiche <strong>qu'une seule</strong> sous-ligne n'a été rapportée que par ce nœud-là.
		Selon la tâche, c'est normal (elle ne tourne que sur l'actif) ou c'est le signe que l'autre nœud ne
		rend pas compte.
	</p>
	{#if santeLoading || erreur || !sante || sante.taches.length === 0}
		<EtatListe
			chargement={santeLoading}
			{erreur}
			vide={!sante || sante.taches.length === 0}
			titreErreur="Impossible d’afficher l’état des tâches"
			titreVide="Aucune donnée"
			messageVide="Aucune exécution n'a encore été enregistrée."
		/>
	{:else}
		<div class="card carte-taches">
			<table class="table texte-md">
				<thead><tr><th>Tâche</th><th>Nœud</th><th>État</th><th>Dernier rapport</th></tr></thead>
				<tbody>
					{#each sante.taches as t (t.tache)}
						<tr
							class="cliquable"
							role="button"
							tabindex="0"
							aria-expanded={ouverte === t.tache}
							on:click={() => basculer(t.tache)}
							on:keydown={(e) =>
								(e.key === 'Enter' || e.key === ' ') && (e.preventDefault(), basculer(t.tache))}
						>
							<td>
								<!--  Affordance de dépliement DEVANT le libellé, pas au bout de la
								      ligne : à droite, gris et petit, il n'était pas vu — l'utilisateur
								      ignorait que les lignes s'ouvraient (11/08/2026). -->
								<span class="chevron" class:open={ouverte === t.tache} aria-hidden="true"
									>&#x25B8;</span
								>
								{LIBELLE_TACHE[t.tache] ?? t.tache}
							</td>
							<td class="muted">
								<!--  ⚠️ « Aucune exécution » se teste EN PREMIER (#542).
								      `noeud_enregistre` vaut faux dans ce cas aussi — faute
								      d'exécution, il n'y a pas de nœud à enregistrer — et l'ordre
								      inverse faisait afficher « non enregistré » à une tâche qui
								      n'avait jamais tourné. Deux états distincts, un seul libellé :
								      celui qui alarme le moins gagnait.

								      Et il n'y a plus qu'UNE branche « non enregistré ». Il y en
								      avait deux, avec deux infobulles qui se contredisaient (« avant
								      la v2.53.0 » / « avant la v2.32.0 ») — la seconde était
								      inatteignable. Une explication fausse mais jamais lue reste
								      fausse le jour où on la lit. -->
								{#if t.statut === 'aucune_execution'}
									—
								{:else if !t.noeud_enregistre}
									<span
										class="non-enregistre"
										title="Cette exécution est antérieure à la migration 0137, qui a ajouté la colonne : on ne sait pas quel nœud l'a faite. Afficher le nœud qui répond aujourd'hui serait faux — le rôle alterne chaque nuit. La colonne se remplit à chaque exécution depuis."
										>non enregistré</span
									>
								{:else}
									<!-- Le nœud de la DERNIÈRE exécution. Les autres ont leur propre
									     sous-ligne ci-dessous : plus rien n'est élu ni masqué (#331). -->
									<span
										title={t.noeuds?.length
											? `Nœud de la dernière exécution. L'état de chaque nœud est détaillé sous cette ligne.`
											: ''}>{t.noeud?.toUpperCase()}</span
									>
								{/if}
							</td>
							<td>
								<Badge
									teinte={CLASSE_STATUT[t.statut] ?? 'badge-red'}
									title={AIDE_STATUT[t.statut] ?? ''}
								>
									{LIBELLE_STATUT[t.statut] ?? t.statut}
								</Badge>
								{#if t.noeud_en_retard}
									<!-- La dernière exécution est saine, mais un nœud décroche. L'ancien
									     écran le disait en remplaçant l'état ET la date par ceux du
									     retardataire — ce qui faisait mentir « Dernier rapport ». -->
									<span
										class="badge badge-orange retard-noeud"
										title="Ce nœud n'a pas exécuté la tâche dans le délai attendu. La dernière exécution, elle, s'est bien passée sur l'autre nœud."
									>
										{t.noeud_en_retard.toUpperCase()} en retard
									</span>
								{/if}
							</td>
							<td class="muted">{t.derniere ? fmtDatetime(t.derniere) : '—'}</td>
						</tr>
						{#if t.noeuds?.length}
							<!--  UNE SOUS-LIGNE PAR NŒUD, toujours visible (#331).
							      C'est elle, et non l'état de synthèse, qui garantit qu'un nœud sain
							      ne compense pas un nœud muet. Toujours visible et non dépliable : ce
							      qu'il faut voir sans cliquer ne se range pas derrière un clic.

							      🔴 RENDUE MÊME POUR UN SEUL NŒUD depuis le 20/08/2026, demandé à
							      l'écran : *« Uniformise le visuel à toutes les tâches »*. La règle
							      d'avant — « au-delà d'un nœud, sinon c'est du bruit » — reposait sur
							      une idée juste et une conclusion fausse.

							      Juste : une sous-ligne unique répète la synthèse. Fausse : elle
							      n'en est pas moins une INFORMATION, et c'est même la plus utile du
							      tableau. « Sauvegarde quotidienne · RPI2 » seul ne dit pas
							      « tout va bien sur rpi2 » — il dit *« rpi1 n'a JAMAIS rendu compte
							      de cette tâche »*. Le masquer faisait disparaître le seul indice
							      d'un nœud qui ne parle pas, exactement ce que #331 voulait empêcher.

							      ⚠️ Et l'écran ne peut pas encore dire quels nœuds étaient ATTENDUS :
							      rien ne le déclare. Un nœud qui n'a jamais écrit reste donc absent
							      du tableau plutôt qu'affiché en creux. C'est #488, et c'est ce qui
							      reste à faire. -->
							{#each t.noeuds as n (n.noeud)}
								<tr class="par-noeud">
									<td></td>
									<td class="muted">↳ {n.noeud.toUpperCase()}</td>
									<td>
										<Badge
											teinte={CLASSE_STATUT[n.statut] ?? 'badge-red'}
											title={AIDE_STATUT[n.statut] ?? ''}
										>
											{LIBELLE_STATUT[n.statut] ?? n.statut}
										</Badge>
									</td>
									<td class="muted">{n.derniere ? fmtDatetime(n.derniere) : '—'}</td>
								</tr>
							{/each}
						{/if}
						{#if ouverte === t.tache}
							{@const lignes = historiques[t.tache] ?? []}
							<tr class="detail">
								<td colspan="4">
									{#if AIDE_TACHE[t.tache]}
										<p class="aide">{AIDE_TACHE[t.tache]}</p>
									{/if}
									{#if enChargement[t.tache] || erreursTache[t.tache] || lignes.length === 0}
										<!--  `compact` : ce vide vit DANS une ligne de tableau dépliée, un
										      bloc `.empty-state` y prendrait toute la place. L'échec y
										      reste visuellement distinct du vide — c'est toute la raison
										      d'être du composant. -->
										<EtatListe
											compact
											chargement={enChargement[t.tache]}
											erreur={erreursTache[t.tache] ?? ''}
											vide={lignes.length === 0}
											messageVide="Aucune exécution enregistrée pour cette tâche."
										/>
									{:else}
										<TableExecutionsTache {lignes} />
									{/if}
									{#if adminApi.tacheLancable(t.tache)}
										<!--  Bouton à DROITE, comme dans les deux cartes supprimées avec #299
										      et comme partout ailleurs dans le projet : action primaire à
										      droite (`ux-patterns` §9). Collé à gauche sous le tableau, il se
										      lisait comme une cellule de plus. Signalé par l'utilisateur le
										      11/08/2026. La note de la maintenance reste à gauche : elle se lit
										      AVANT le geste qu'elle nuance, pas après. -->
										<div class="lancement">
											{#if t.tache === 'maintenance'}
												<span class="muted note-lancement">
													part applicative seulement{SEPARATEUR.tiret}l'hygiène du nœud en veille
													reste au script hebdomadaire
												</span>
											{/if}
											<button
												class="btn btn-primary btn-lancer"
												on:click|stopPropagation={() => declencher(t.tache)}
												disabled={enCours === t.tache}
												title={t.tache === 'maintenance'
													? "Purges et VACUUM, sur ce nœud uniquement. Ne remplace pas le script hebdomadaire, qui fait en plus l'hygiène du nœud en veille."
													: ''}
											>
												{enCours === t.tache ? 'En cours...' : libelleBouton(t.tache)}
											</button>
										</div>
									{/if}
								</td>
							</tr>
						{/if}
					{/each}
				</tbody>
			</table>
		</div>
		{#if sante.anomalies_recentes.length > 0}
			<p class="muted bilan-anomalies">
				<strong>{sante.anomalies_recentes.length}</strong> exécution(s) en échec ces
				{fmtNombre(sante.anomalies_fenetre_jours)} derniers jours.
			</p>
		{/if}
	{/if}
</section>

<ConfigSauvegarde />

<style>
	/*  Ligne de synthèse dépliable. Le détail vit SOUS la ligne qui l'annonce :
	    c'est ce qui remplace les trois tableaux séparés que l'utilisateur a
	    jugés illisibles le 11/08/2026. */
	tr.cliquable {
		cursor: pointer;
	}
	@media (hover: hover) and (pointer: fine) {
		tr.cliquable:hover {
			background: var(--color-bg);
		}
	}
	tr.cliquable:focus-visible {
		outline: 2px solid var(--color-primary);
		outline-offset: -2px;
	}
	tr.detail > td {
		background: var(--color-bg);
		padding: 0.25rem 0 0.75rem;
	}
	/*  Sous-ligne par nœud : rattachée visuellement à sa tâche sans devenir une
	    ligne de plein droit, sinon on relit un tableau à double granularité —
	    exactement ce qui avait été corrigé le 11/08/2026. */
	tr.par-noeud > td {
		padding-top: 0.15rem;
		padding-bottom: 0.15rem;
		font-size: 0.95em;
	}
	/*  Écart assumé : plus petit et en couleur primaire — il ouvre une ligne
	    de tableau, pas une carte, et doit se voir (il était invisible avant
	    le 11/08, cf. #299). */
	/*  Le chevron d'une tache est plus petit et de la couleur primaire : il annonce
	    une action, pas un depliage neutre (#607, 28/08/2026). */
	.chevron {
		font-size: var(--fs-base);
		color: var(--color-primary);
		margin-right: 0.4rem;
	}
	/*  Action primaire à droite. `margin-right:auto` sur la note plutôt que
	    `space-between` : sans note, le bouton doit rester à droite quand même. */
	.lancement {
		display: flex;
		align-items: center;
		justify-content: flex-end;
		gap: 0.75rem;
		margin: 0.5rem 0 0.25rem;
		padding: 0 0.75rem;
	}
	.note-lancement {
		font-size: var(--fs-xs);
		margin-right: auto;
	}
	.texte-md {
		font-size: var(--fs-md);
	}
	.carte-taches {
		overflow: auto;
		margin-top: 1rem;
	}
	.non-enregistre {
		font-style: italic;
	}
	.retard-noeud {
		margin-left: 0.35rem;
	}
	.btn-lancer {
		font-size: var(--fs-sm);
		padding: 0.3rem 0.7rem;
	}
	.bilan-anomalies {
		margin-top: 0.75rem;
		font-size: var(--fs-md);
	}
</style>
