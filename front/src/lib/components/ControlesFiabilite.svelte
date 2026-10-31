<!--
  Les **contrôles de fiabilité** (`check-reliability.sh`, C1 à C40), nœud par
  nœud, avec leurs constats en cours — et, par `tache="audit_securite"`, la même
  carte pour l'**audit de sécurité nocturne** (`audit-securite.sh`, S1 à S6,
  30/10/2026) : même canal (`lib-notification.sh`), même forme de constats, une
  seule carte à tenir. Ce qui diffère — titre, phrase d'introduction, cadence —
  se lit dans `TEXTES` ci-dessous.

  🔴 Pourquoi cette carte (27/09/2026). Ces contrôles tournent toutes les quinze
  minutes sur les deux Raspberry Pi — split-brain, tunnel, parité de code, disque,
  sudo, en-têtes de sécurité, mises à jour système… — et leurs verdicts n'allaient
  qu'à un journal et à des courriels. L'écran de maintenance ne pouvait donc dire
  ni ce qui était en vigilance, ni si le contrôleur tournait encore. C'est ainsi
  que rpi2 est resté cinq mois sans correctif de sécurité (#1377) : rien, ici, ne
  regardait ce qui se met à jour.

  ⚠️ Deux heures par nœud, et elles ne disent pas la même chose (#1396). Le script
  n'envoie un RAPPORT que quand l'ensemble des constats change (la table n'en garde
  que vingt par tâche) : `cree_le` est donc « constats depuis ». Entre deux, chaque
  passage envoie un BATTEMENT qui avance `terminee_le` : « dernier contrôle » — et
  qui remplace les constats par ceux du passage, chiffres compris (#1805). On
  n'affichait que la première, et le 27/09 on a cru le contrôleur mort — « rapport
  de 17:06 » lu à 17:29.

  Chaque constat ne s'affiche qu'une fois (#1396) : sous le nœud qu'il nomme seul,
  ou sous « Les deux nœuds » quand il porte sur les deux — ceux-là, c'est l'actif
  qui les dit (`porte_communs`). Un rapport d'avant #1396 n'a pas ce champ : ses
  constats restent tous sous son nœud, comme avant.
-->
<script lang="ts">
	import { onMount } from 'svelte';
	import SectionFormulaire from './SectionFormulaire.svelte';
	import EtatListe from './EtatListe.svelte';
	import ListeConstats from './ListeConstats.svelte';
	import { admin as adminApi, type RapportFiabilite } from '#lib/api/index.ts';
	import { messageErreur } from '#lib/erreurs.ts';
	import { fmtDate, fmtDatetime, fmtTime } from '#lib/date.ts';
	//  Le titre est le NOM de la tâche dans la synthèse : une seule écriture,
	//  sinon la ligne de la synthèse cesse de renvoyer à cette carte.
	import { LIBELLE_TACHE } from '#lib/taches.ts';
	import { SEPARATEUR } from '#lib/separateurs.ts';

	/** La tâche rendue : les contrôles du quart d'heure, ou l'audit de la nuit. */
	export let tache: 'reliability' | 'audit_securite' = 'reliability';

	//  Ce qui change d'une tâche à l'autre, et rien d'autre.
	const TEXTES = {
		reliability: {
			script: 'check-reliability',
			intro:
				'toutes les 15 minutes sur chaque Raspberry Pi : site public, split-brain, tunnel, parité du code, disque, rotation des journaux, droits sudo, en-têtes de sécurité, mises à jour système…',
			vide: 'Les nœuds rendent compte au premier passage de check-reliability (15 min au plus) après leur mise à jour.',
			passage: 'dernier contrôle',
		},
		audit_securite: {
			script: 'audit-securite',
			intro:
				'chaque nuit sur chaque Raspberry Pi, en root : arbre déployé identique au dépôt, comptes et groupes qui valent root, points de persistance (cron, systemd, clés SSH, sudo, apt) comparés à une référence acceptée, conteneurs sans privilège et images de la CI, durcissement réellement servi (sshd, ufw, fail2ban), sondes de scanners et forçage de comptes dans les journaux de la nuit.',
			vide: 'Chaque nœud rend compte à son premier audit, lancé par check-reliability après 4 h.',
			passage: 'dernier audit',
		},
	} as const;
	$: textes = TEXTES[tache];

	let rapports: RapportFiabilite[] = [];
	let chargement = true;
	let erreur = '';

	//  Le plus récent de chaque nœud — l'API les rend du plus récent au plus ancien.
	$: parNoeud = rapports.reduce<RapportFiabilite[]>(
		(acc, r) => (r.noeud && !acc.some((x) => x.noeud === r.noeud) ? [...acc, r] : acc),
		[],
	);

	//  Le dernier passage connu : le battement s'il y en a eu un, sinon le rapport.
	const vuLe = (r: RapportFiabilite) => r.terminee_le ?? r.cree_le;

	//  Les constats communs viennent du nœud qui les porte — l'actif. Si les deux
	//  les portent (pair muet, rôle illisible), le plus récent fait foi.
	$: porteur = parNoeud
		.filter((r) => r.details?.porte_communs)
		.sort((a, b) => vuLe(b).localeCompare(vuLe(a)))[0];

	//  Les badges comptent ce qui s'affiche SOUS le nœud, pas les communs.
	const compte = (constats: string[], niveau: string) =>
		constats.filter((c) => c.startsWith(`[${niveau}]`)).length;

	//  « 17:36 » aujourd'hui, la date complète sinon — un contrôleur arrêté depuis
	//  la veille ne doit pas se lire comme un passage de l'après-midi.
	const heure = (d: string) =>
		fmtDate(d) === fmtDate(new Date().toISOString()) ? fmtTime(d) : fmtDatetime(d);

	onMount(async () => {
		try {
			rapports = await adminApi.controlesFiabilite(tache);
		} catch (e) {
			erreur = messageErreur(e);
		} finally {
			chargement = false;
		}
	});
</script>

<section class="card config-section">
	<SectionFormulaire titre={LIBELLE_TACHE[tache]} icone="shield-check" />
	<p class="muted config-section-intro">
		Les vérifications de <strong>{textes.script}</strong>, {textes.intro} Un échec est envoyé par courriel
		dans l’heure, les points de vigilance en un résumé quotidien. Ci-dessous, les constats
		<strong>en cours</strong> de chaque nœud, puis ceux qui portent sur les deux.
	</p>

	<EtatListe
		{chargement}
		{erreur}
		vide={parNoeud.length === 0}
		titreErreur="Impossible d’afficher les contrôles"
		titreVide="Aucun rapport reçu"
		messageVide={textes.vide}
	>
		{#each parNoeud as r (r.noeud)}
			{@const constats = r.details?.constats ?? []}
			{@const nFail = compte(constats, 'FAIL')}
			{@const nWarn = compte(constats, 'WARN')}
			<div class="noeud">
				<div class="noeud-entete">
					<strong>{r.noeud?.toUpperCase()}</strong>
					{#if nFail}
						<span class="badge badge-red">{nFail} en échec</span>
					{/if}
					{#if nWarn}
						<span class="badge badge-orange">{nWarn} en vigilance</span>
					{/if}
					{#if !nFail && !nWarn}
						<span class="badge badge-green">Tout est vert</span>
					{/if}
					<span class="muted date"
						>{textes.passage}
						{heure(vuLe(r))}{SEPARATEUR.point}constats depuis {fmtDatetime(r.cree_le)}</span
					>
				</div>
				<ListeConstats {constats} />
			</div>
		{/each}

		{#if porteur?.details?.communs?.length}
			<div class="noeud">
				<div class="noeud-entete">
					<strong>Les deux nœuds</strong>
					<span class="muted date"
						>vu par {porteur.noeud?.toUpperCase()}{SEPARATEUR.point}{textes.passage}
						{heure(vuLe(porteur))}</span
					>
				</div>
				<ListeConstats constats={porteur.details.communs} />
			</div>
		{/if}
	</EtatListe>
</section>

<style>
	.noeud + .noeud {
		margin-top: 1rem;
		padding-top: 1rem;
		border-top: 1px solid var(--color-border);
	}
	.noeud-entete {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.4rem 0.6rem;
	}
	.date {
		font-size: var(--fs-sm);
	}
</style>
