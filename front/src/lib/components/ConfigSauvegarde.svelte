<script lang="ts">
	import EncartDemo from '#lib/components/EncartDemo.svelte';
	import SectionFormulaire from './SectionFormulaire.svelte';
	/**
	 * Réglage de la sauvegarde quotidienne — heure et rétention.
	 *
	 * ## Ce qui vivait avant sur `/admin/sauvegardes`, et ne marchait pas
	 *
	 * Cet écran portait aussi « Sauvegarde immédiate » et « Historique des
	 * sauvegardes », **strictement redondants** avec l'onglet Maintenance : mêmes
	 * points d'accès (`POST /admin/sauvegardes/maintenant`,
	 * `GET /admin/sauvegardes/historique`), déjà appelés par `TachesPlanifiees`
	 * sous la ligne « Sauvegarde quotidienne ». C'était la duplication que #299
	 * avait supprimée dans l'autre sens. **Maintenance est désormais le seul
	 * endroit qui montre et déclenche les tâches planifiées.**
	 *
	 * Surtout, son formulaire n'enregistrait presque rien :
	 * `PUT /admin/sauvegardes/config` applique `if hasattr(cfg, k)`, or il envoyait
	 * `heure` et `nb_versions` quand le modèle porte `heure_execution` et
	 * `nb_versions_conservees` — **les deux champs étaient ignorés en silence**.
	 * Les valeurs affichées venaient de l'initialisation locale, pas du serveur.
	 * Et son option « Désactivée » n'existe pas dans `FrequenceSauvegarde`.
	 *
	 * ## Pourquoi il n'y a plus de choix de fréquence
	 *
	 * `quotidienne` / `hebdomadaire` / `mensuelle` sont EXCLUSIFS : choisir
	 * « hebdomadaire » ne s'ajoute pas au quotidien, il le remplace. Sur une base
	 * de quelques mégaoctets, espacer les sauvegardes n'apporte rien et coûte des
	 * jours de données en cas de perte. Le choix est retiré (13/08/2026) et la
	 * migration `0139` ramène les installations existantes au quotidien.
	 *
	 * À ne pas confondre avec la **Maintenance hebdomadaire** (`maintenance.sh`,
	 * cron du dimanche 3 h : purges, VACUUM, rotation des logs, cache Docker) :
	 * deux tâches distinctes, deux ordonnanceurs — celle-ci tourne dans l'API.
	 */
	import { onMount } from 'svelte';
	import { admin } from '#lib/api/index.ts';
	import { messageErreur } from '#lib/erreurs.ts';
	import { toast } from '#lib/components/Toast.svelte';
	import EtatListe from '#lib/components/EtatListe.svelte';
	import { SEPARATEUR } from '#lib/separateurs.ts';

	//  Les NOMS DU MODÈLE, pas des noms inventés : c'est ce qui manquait.
	let heure_execution = 3;
	let nb_versions_conservees = 7;
	let chargement = true;
	let enregistrement = false;

	onMount(async () => {
		const cfg = await admin.backupConfig().catch(() => null);
		if (cfg) {
			heure_execution = cfg.heure_execution ?? heure_execution;
			nb_versions_conservees = cfg.nb_versions_conservees ?? nb_versions_conservees;
		}
		chargement = false;
	});

	async function enregistrer() {
		enregistrement = true;
		try {
			await admin.updateBackupConfig({
				heure_execution: Number(heure_execution),
				nb_versions_conservees: Number(nb_versions_conservees),
			});
			toast('success', 'Réglage enregistré');
		} catch (e) {
			toast('error', messageErreur(e, 'Erreur à l’enregistrement'));
		} finally {
			enregistrement = false;
		}
	}
</script>

<EncartDemo />
<section class="card config-section">
	<!--  L'en-tête est celui du bloc voisin, à l'identique : `config-section-title`
	      et un tracé du catalogue. Il portait un émoji 💾 et une classe `.titre`
	      locale, à trois centimètres d'un « Santé des tâches planifiées » rendu
	      par le motif partagé — deux blocs du même onglet, deux façons de titrer.
	      Un émoji dépend en plus de la police du système. -->
	<!--  🔴 Titre par `SectionFormulaire` (12/09/2026) : ce `<h3>` local était la
	      deuxième des trois façons de titrer un bloc de cet onglet. Le composant
	      partagé porte l'intitulé, le filet et l'espacement — et l'icône. -->
	<SectionFormulaire titre="Réglage de la sauvegarde quotidienne" icone="sliders-horizontal" />
	<p class="aide">
		La sauvegarde s’exécute <strong>tous les jours</strong>. Son historique et son déclenchement
		manuel sont dans le tableau ci-dessus, avec les autres tâches.
	</p>

	{#if chargement}
		<EtatListe chargement />
	{:else}
		<form id="config-sauvegarde" on:submit|preventDefault={enregistrer} class="grille">
			<label class="field champ-en-ligne">
				<span>Heure d’exécution</span>
				<select bind:value={heure_execution}>
					<!--  La clé est l'heure elle-même : 0 à 23, distinctes par construction.
					      Ce n'est pas l'index déguisé — `h` EST la valeur rendue. -->
					{#each Array.from({ length: 24 }, (_, h) => h) as h (h)}
						<option value={h}>{String(h).padStart(2, '0')} h 00</option>
					{/each}
				</select>
			</label>
			<label class="field champ-en-ligne">
				<span>Versions conservées</span>
				<input type="number" min="1" max="99" bind:value={nb_versions_conservees} />
			</label>
		</form>
		<p class="aide note">
			Au-delà de {nb_versions_conservees} versions, la plus ancienne est effacée.
		</p>
		{#if heure_execution === 2 || heure_execution === 3}
			<p class="avertissement">
				⚠️ <strong>{String(heure_execution).padStart(2, '0')} h</strong> croise une autre tâche : la
				<strong>bascule</strong>
				entre les deux Raspberry Pi tourne à 02 h, et la <strong>maintenance hebdomadaire</strong>
				(purge et VACUUM de la base) le dimanche à 03 h. Une sauvegarde qui démarre pendant l’une ou l’autre
				lit une base en cours de réorganisation. Préférez une heure creuse{SEPARATEUR.tiret}01 h ou
				04 h.
			</p>
		{/if}
		<!--  🔴 `.form-actions` — barre de soumission alignée à DROITE, comme partout
		      (`ux-patterns` §9 quinquies). Le bouton vivait DANS la grille des
		      champs, donc collé au dernier champ et calé à gauche : il ne se lisait
		      pas comme la validation du formulaire mais comme un troisième champ.
		      Et il n'avait que `btn-primary`, sans `btn` : tout le style vit dans la
		      base, il sortait en bouton natif gris. Signalé à l'écran le 20/08/2026.
		      `form="config-sauvegarde"` le rattache au formulaire qu'il soumet — il
		      n'est plus dedans, la soumission au clavier doit le rester.

		      ⚠️ Et il vient EN DERNIER, après les deux explications : on lit ce que
		      les champs font, puis on valide. Placé juste sous la grille, il coupait
		      la note qui explique le champ qu'on vient de régler. -->
		<div class="form-actions">
			<button
				class="btn btn-primary"
				type="submit"
				form="config-sauvegarde"
				disabled={enregistrement}
			>
				{enregistrement ? 'Enregistrement…' : 'Enregistrer'}
			</button>
		</div>
	{/if}
</section>

<style>
	/*  `.config-sauvegarde` est partie avec son balisage (12/09/2026) : elle
	    dessinait à la main le filet et l'espacement qu'une SECTION porte — c'est
	    `card config-section` qui les donne maintenant, comme aux deux blocs
	    voisins. Une règle de séparation écrite par chaque bloc, c'est trois
	    séparations qui finissent par ne plus se ressembler. */
	/*  Seule la marge reste ici : cette aide est un paragraphe de tête, pas une
	    note collée à un groupe de cases. La typographie vient de la charte. */
	.note {
		margin: 0.7rem 0 0;
	}
	.avertissement {
		font-size: var(--fs-md);
		line-height: 1.5;
		margin: 0.7rem 0 0;
		padding: 0.6rem 0.7rem;
		border-left: 3px solid var(--color-warning);
		background: var(--color-bg);
	}
	.grille {
		display: flex;
		flex-wrap: wrap;
		gap: 0.8rem;
		align-items: flex-end;
	}
</style>
