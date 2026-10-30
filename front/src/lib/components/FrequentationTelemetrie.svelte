<script lang="ts">
	/**
	 * **Indicateurs et fréquentation** — la section de l'onglet Télémétrie dépliée
	 * par défaut (03/10/2026) : les nombres clés de la vue, puis le graphe des vues
	 * (par heure, jour, mois ou année), les top pages et les utilisateurs les plus
	 * actifs. Ils répondent à la même question — qui lit quoi, et quand — dans UNE
	 * section, comme demandé : « fusionner les sections Indicateurs & Fréquentation
	 * (qui devient la section par défaut dépliée) ».
	 *
	 * Extrait d'`OngletTelemetrie` avec ses deux cents lignes de style de graphe :
	 * l'onglet gagnait quatre vues, un filtre et cinq sections pliables, et le
	 * plafond de modularité ne laissait pas tout cela dans un seul fichier.
	 *
	 * 🔴 Les `class:` du gabarit remplacent des ternaires INTERPOLÉS (#810) :
	 * devant `class="tl-bar {cond ? 'x' : ''}"`, Svelte cesse de déclarer les
	 * sélecteurs inutilisés pour tout le fichier.
	 */
	import PanneauTelemetrie from '#lib/components/PanneauTelemetrie.svelte';
	import TopPages from '#lib/components/TopPages.svelte';
	import EcransNonVisites from '#lib/components/EcransNonVisites.svelte';
	import type { TableauTelemetrie } from '#lib/api/index.ts';
	import { fmtDate, fmtDatetimeShort as fmt, fmtMoisCourt } from '#lib/date.ts';

	export let donnees: TableauTelemetrie;
	/** Section dépliée ? L'onglet décide, et reçoit `basculer` (`PanneauTelemetrie`). */
	export let ouvert = false;
	/** « Pages vues aujourd'hui », « Pages vues (30 j) »… : la vue consultée le dit. */
	export let libelleVues = 'Pages vues';

	$: kpi = donnees.kpi;
	//  Ce que couvrent les pages vues, pour les deux vues assez longues pour que
	//  « non visité » veuille dire quelque chose ; vide sinon, et le bloc se tait.
	$: periodeEcrans =
		donnees.scope === 'mois'
			? '30 derniers jours'
			: donnees.scope === 'annee'
				? '12 derniers mois'
				: '';

	//  Un bâton par mois ou par année est plus large qu'un bâton par heure ou
	//  par jour : il y en a douze ou dix, pas vingt-quatre ou trente.
	$: large = donnees.scope === 'annee' || donnees.scope === 'total';
	$: maxVal = Math.max(...donnees.chart.map((x) => x.total), 1);
	//  🔴 `tick` est une clé SÛRE, et ça se démontre plutôt que ça ne se suppose
	//  — une clé dupliquée fait planter Svelte à l'exécution. `step` vaut
	//  `Math.ceil(maxVal / 4 / u) * u` avec `maxVal >= 1` et `u >= 1` : le
	//  quotient est > 0, donc `Math.ceil` rend au moins 1, donc `step >= 1`.
	//  Les cinq multiples sont alors distincts.
	$: unite = maxVal < 10 ? 1 : maxVal < 50 ? 5 : maxVal < 200 ? 10 : maxVal < 1000 ? 50 : 100;
	$: step = Math.ceil(maxVal / 4 / unite) * unite;
	$: yTicks = [4, 3, 2, 1, 0].map((i) => i * step);

	//  Vue Mois : le bâton est un JOUR (`label` « MM-JJ »). La légende dit le numéro
	//  du jour, et le mois seulement au premier bâton et au changement de mois — des
	//  dates complètes se superposaient sur trente bâtons (04/10/2026). Le jour le plus
	//  actif (`kpi.jour_pointe`, en utilisateurs et non en vues : ce n'est pas
	//  forcément le plus haut) porte le 🏆 sur SON bâton, plus une ligne à part.
	$: parJour = donnees.scope === 'mois';
	$: jourPic = parJour ? String(kpi.jour_pointe?.jour ?? '').slice(5) : '';
	$: batons = donnees.chart.map((d, i) => {
		const [mois, jour] = parJour ? d.label.split('-').map(Number) : [0, 0];
		return {
			d,
			etiquette: parJour ? String(jour) : d.label,
			mois: parJour && (i === 0 || jour === 1) ? fmtMoisCourt(mois) : '',
			pic: parJour && d.label === jourPic,
			date: parJour ? `${jour} ${fmtMoisCourt(mois)}` : '',
			//  À droite de la moitié du graphe, la bulle s'accroche au bord droit du
			//  bâton : à gauche elle ferait défiler la zone vers la droite.
			aDroite: i >= donnees.chart.length / 2,
			//  Un bâton haut ne laisse pas la place d'une bulle AU-DESSUS de lui, et un
			//  bâton collé au sommet pas même celle du 🏆 : ils se posent sur le bâton.
			haut: d.total / (yTicks[0] || 1) > 0.55,
			colle: d.total / (yTicks[0] || 1) > 0.9,
		};
	});
</script>

<PanneauTelemetrie
	titre="📊 Indicateurs et fréquentation"
	{ouvert}
	vide={(kpi.vues ?? 0) === 0 && donnees.chart.length === 0}
	videLibelle="aucune vue sur la période"
	on:basculer
>
	<div class="tl-kpi-row">
		<div class="tl-kpi">
			<div class="tl-kpi-value">{kpi.vues ?? 0}</div>
			<div class="tl-kpi-label">{libelleVues}</div>
		</div>
		{#if kpi.utilisateurs != null}
			<div class="tl-kpi">
				<div class="tl-kpi-value">{kpi.utilisateurs}</div>
				<div class="tl-kpi-label">
					{donnees.scope === 'jour'
						? "Utilisateurs actifs aujourd'hui"
						: 'Utilisateurs uniques (pic)'}
				</div>
			</div>
		{/if}
		<div class="tl-kpi">
			<div class="tl-kpi-value">{kpi.pages ?? 0}</div>
			<div class="tl-kpi-label">Pages distinctes visitées</div>
		</div>
		{#if kpi.heure_pointe}
			<div class="tl-kpi">
				<div class="tl-kpi-value">{kpi.heure_pointe}</div>
				<div class="tl-kpi-label">🔺 Heure de pointe</div>
			</div>
		{/if}
		{#if kpi.moy_vues_utilisateur != null}
			<div class="tl-kpi">
				<div class="tl-kpi-value">{kpi.moy_vues_utilisateur}</div>
				<div class="tl-kpi-label">Moy. vues / utilisateur</div>
			</div>
		{/if}
		{#if kpi.moy_vues_jour != null}
			<div class="tl-kpi">
				<div class="tl-kpi-value">{kpi.moy_vues_jour}</div>
				<div class="tl-kpi-label">Moy. vues / jour</div>
			</div>
		{/if}
		{#if kpi.moy_utilisateurs_jour != null}
			<div class="tl-kpi">
				<div class="tl-kpi-value">{kpi.moy_utilisateurs_jour}</div>
				<div class="tl-kpi-label">Moy. utilisateurs / jour</div>
			</div>
		{/if}
		{#if kpi.mois_actifs != null}
			<div class="tl-kpi">
				<div class="tl-kpi-value">{kpi.mois_actifs}</div>
				<div class="tl-kpi-label">Mois avec activité</div>
			</div>
		{/if}
		{#if kpi.moy_vues_mois != null}
			<div class="tl-kpi">
				<div class="tl-kpi-value">{kpi.moy_vues_mois}</div>
				<div class="tl-kpi-label">Moy. vues / mois</div>
			</div>
		{/if}
		{#if kpi.annees_actives != null}
			<div class="tl-kpi">
				<div class="tl-kpi-value">{kpi.annees_actives}</div>
				<div class="tl-kpi-label">Années avec activité</div>
			</div>
		{/if}
		{#if kpi.moy_vues_an != null}
			<div class="tl-kpi">
				<div class="tl-kpi-value">{kpi.moy_vues_an}</div>
				<div class="tl-kpi-label">Moy. vues / an</div>
			</div>
		{/if}
	</div>

	<!--  Records (Année et Total). Le pic de la vue Mois n'a pas de bloc : c'est déjà le
	      « Utilisateurs uniques (pic) » de la première ligne, et son jour porte le 🏆
	      et sa bulle sur le graphe. -->
	{#if kpi.record_jour || kpi.record_mois}
		<div class="tl-kpi-row tl-kpi-row-suite">
			{#if kpi.record_jour}
				<div class="tl-kpi">
					<div class="tl-kpi-value">
						{kpi.record_jour.uniques}
						<span class="tl-kpi-unite">utilisateurs</span>
					</div>
					<div class="tl-kpi-label">🏆 Record jour — {fmtDate(kpi.record_jour.jour)}</div>
				</div>
			{/if}
			{#if kpi.record_mois}
				<div class="tl-kpi">
					<div class="tl-kpi-value">
						{kpi.record_mois.uniques}
						<span class="tl-kpi-unite">utilisateurs</span>
					</div>
					<div class="tl-kpi-label">🏆 Record mois — {kpi.record_mois.mois}</div>
				</div>
			{/if}
		</div>
	{/if}

	<PanneauTelemetrie titre={donnees.chart_label} niveau="bloc">
		<div class="tl-chart-wrap" class:tl-double={parJour}>
			<div class="tl-y-axis">
				{#each yTicks as tick (tick)}
					<div class="tl-y-tick" style="bottom:{(tick / (yTicks[0] || 1)) * 100}%">{tick}</div>
				{/each}
			</div>
			<div class="tl-chart-inner">
				{#each yTicks as tick (tick)}
					<div
						class="tl-y-gridline"
						style="bottom:calc({tick / (yTicks[0] || 1)} * var(--tl-zone) + var(--tl-etiq))"
					></div>
				{/each}
				<div class="tl-chart">
					{#each batons as b, i (b.d.label)}
						<div
							class="tl-bar-col"
							class:tl-bar-col-large={large}
							title="{b.d.label} — {b.d.total} vues{b.d.uniques != null
								? `, ${b.d.uniques} uniques`
								: ''}{b.pic ? ' — jour le plus actif' : ''}"
						>
							<div class="tl-bar-zone">
								<div
									class="tl-bar"
									class:tl-bar-large={large}
									class:tl-bar-pic={b.pic}
									style="height:{Math.max(4, (b.d.total / (yTicks[0] || 1)) * 100)}%"
								>
									{#if b.pic}
										<div class="tl-pic" class:tl-pic-colle={b.colle}>
											<span
												class="tl-bulle"
												class:tl-bulle-droite={b.aDroite}
												class:tl-bulle-dedans={b.haut}
											>
												{b.date} · {kpi.jour_pointe?.uniques} utilisateurs
											</span>
											<span aria-hidden="true">🏆</span>
										</div>
									{/if}
								</div>
							</div>
							<div class="tl-bar-label">{b.etiquette}</div>
							{#if parJour}
								<div class="tl-bar-mois" class:tl-bar-mois-fin={i >= batons.length - 2}>
									{b.mois}
								</div>
							{/if}
						</div>
					{/each}
				</div>
			</div>
		</div>
	</PanneauTelemetrie>

	<TopPages pages={donnees.top_pages} vuesNonAttribuees={donnees.kpi.vues_non_attribuees ?? 0} />

	<!--  Mois et Année seulement (#1630) : sur une journée, presque tout écran est « non visité ». -->
	{#if periodeEcrans}
		<EcransNonVisites pages={donnees.top_pages} periode={periodeEcrans} />
	{/if}

	{#if donnees.top_users.length > 0}
		<PanneauTelemetrie titre="🏅 Utilisateurs les plus actifs" niveau="bloc">
			<div class="table-wrap">
				<table class="table">
					<thead>
						<tr>
							<th>Utilisateur</th><th>Type</th><th>Bâtiment</th><th class="nombre">Vues</th>
							<th class="nombre">Pages diff.</th><th class="nombre">Dernière connexion</th>
						</tr>
					</thead>
					<tbody>
						{#each donnees.top_users as u (u.nom)}
							<tr>
								<td>{u.nom}</td>
								<td class="text-muted-sm">{u.statut ?? '—'}</td>
								<td class="text-muted-sm">{u.batiment_id ? `Bât. ${u.batiment_id}` : '—'}</td>
								<td class="nombre">{u.total}</td>
								<td class="nombre text-muted-sm">{u.pages}</td>
								<td class="nombre text-muted-sm">
									{u.derniere_connexion ? fmt(u.derniere_connexion) : '—'}
								</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		</PanneauTelemetrie>
	{/if}
</PanneauTelemetrie>

<style>
	/*  🔴 CES RÈGLES SONT RESTÉES DANS `admin/+page.svelte` À L'EXTRACTION de
	    l'onglet, et le panneau est parti NU en production (v2.95.0) : le graphe
	    en colonne de chiffres. Svelte scope ses styles au FICHIER. Déplacer du
	    balisage sans ses règles est la régression que ce dépôt cite dans une
	    dizaine de commentaires depuis la v2.67.11 ; `npm run lint:classes-nues`
	    est le contrôle qui échoue. Elles voyagent ici avec le graphe. */
	.tl-kpi-row {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(min(160px, 100%), 1fr));
		gap: 1rem;
		margin: 0 1rem 1rem;
	}
	.tl-kpi-row-suite {
		margin-top: 0;
	}
	.tl-kpi {
		background: var(--color-surface);
		border: 1px solid var(--color-border);
		border-radius: var(--radius);
		padding: 1.25rem 1rem;
		text-align: center;
	}
	.tl-kpi-value {
		font-size: 2rem;
		font-weight: 700;
		color: var(--color-primary);
		line-height: 1.1;
	}
	.tl-kpi-unite {
		font-size: var(--fs-sm);
		font-weight: 400;
	}
	.tl-kpi-label {
		font-size: var(--fs-md);
		color: var(--color-text-muted);
		margin-top: 0.3rem;
	}
	.tl-chart-wrap {
		display: flex;
		gap: 0;
		position: relative;
		margin: 0.5rem 1rem 0;
	}
	/*  `--tl-etiq` : la hauteur de la légende sous les bâtons — une ligne, deux en
	    vue Mois (jour puis mois). L'axe et les repères en dépendent. */
	.tl-chart-wrap {
		--tl-etiq: 18px;
		--tl-zone: 130px;
	}
	.tl-double {
		--tl-etiq: 34px;
	}
	.tl-y-axis {
		position: relative;
		width: 32px;
		flex-shrink: 0;
		height: var(--tl-zone);
		margin-bottom: var(--tl-etiq);
	}
	.tl-y-tick {
		position: absolute;
		right: 4px;
		font-size: var(--fs-xs);
		color: var(--color-text-muted);
		transform: translateY(50%);
		line-height: 1;
		text-align: right;
	}
	.tl-chart-inner {
		position: relative;
		flex: 1;
		min-width: 0;
		display: flex;
		flex-direction: column;
	}
	.tl-chart-inner .tl-y-gridline {
		position: absolute;
		left: 0;
		right: 0;
		height: 1px;
		background: var(--color-border);
		opacity: 0.5;
		pointer-events: none;
		z-index: 0;
	}
	.tl-chart {
		display: flex;
		align-items: flex-end;
		gap: 2px;
		height: 120px;
		padding: 0 0.25rem 0 0;
		overflow-x: auto;
		position: relative;
		z-index: 1;
		flex: 1;
	}
	.tl-bar-col {
		display: flex;
		flex-direction: column;
		align-items: center;
		flex: 1;
		min-width: 16px;
		height: 100%;
		justify-content: flex-end;
	}
	/*  La zone des bâtons a une hauteur FIXE, la légende dessous aussi : un bâton
	    ne peut plus déborder sur elle, et les repères tombent juste. */
	.tl-bar-zone {
		display: flex;
		align-items: flex-end;
		flex-shrink: 0;
		width: 100%;
		height: var(--tl-zone);
	}
	.tl-bar {
		position: relative;
		background: var(--color-primary);
		border-radius: 3px 3px 0 0;
		width: 100%;
		min-height: 4px;
		transition: height var(--duree-apparition) var(--ease-out);
	}
	/*  Le bâton LARGE (Année, Total) est plus léger que celui du jour, sans
	    disparaître : la première série du Suivi tient 3:1 sur la carte dans les
	    deux thèmes — `--color-primary-light` y faisait 1,1 (#2296). */
	.tl-bar-large {
		background: var(--serie-1);
	}
	.tl-bar-label {
		font-size: var(--fs-xs);
		color: var(--color-text-muted);
		flex-shrink: 0;
		height: 18px;
		line-height: 18px;
		white-space: nowrap;
	}
	.tl-bar-col-large {
		min-width: 32px;
	}
	/*  Le mois ne s'écrit qu'au premier bâton et au 1ᵉʳ du mois : il part du bord
	    gauche de son bâton et déborde vers la droite — sauf aux deux derniers, qui
	    débordent vers la gauche (sinon la zone défilerait). */
	.tl-bar-mois {
		align-self: flex-start;
		flex-shrink: 0;
		height: 16px;
		font-size: var(--fs-xs);
		font-weight: 600;
		color: var(--color-text);
		white-space: nowrap;
	}
	.tl-bar-mois-fin {
		align-self: flex-end;
	}
	.tl-bar-pic {
		background: var(--color-warning);
	}
	/*  Posés sur le bâton sans prendre de place dans la mise en page. */
	.tl-pic {
		position: absolute;
		bottom: 100%;
		left: 0;
		right: 0;
		height: 1rem;
		text-align: center;
		line-height: 1rem;
		font-size: var(--fs-md);
	}
	.tl-pic-colle {
		bottom: auto;
		top: 2px;
	}
	/*  La bulle dit la date et le pic : c'est ce que disait la ligne supprimée. */
	.tl-bulle {
		position: absolute;
		bottom: calc(100% + 2px);
		left: -4px;
		padding: 0 0.4rem;
		background: var(--color-surface);
		border: 1px solid var(--color-warning);
		border-radius: 6px;
		color: var(--color-text);
		font-size: var(--fs-xs);
		line-height: 1.4rem;
		white-space: nowrap;
		pointer-events: none;
	}
	.tl-bulle-droite {
		left: auto;
		right: -4px;
	}
	/*  Bâton haut : pas la place au-dessus, la bulle se pose sur le bâton. */
	.tl-bulle-dedans {
		bottom: auto;
		top: calc(100% + 2px);
	}
</style>
