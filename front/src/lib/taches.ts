import { parAttribut } from '#lib/table-statuts.ts';

//  Nom de chaque tâche planifiée — SOURCE UNIQUE.
//
//  Pourquoi un module et pas une constante dans l'écran : le nom d'une tâche
//  apparaissait à trois endroits qui ne se voyaient pas les uns les autres — la
//  synthèse « Santé des tâches planifiées », la colonne Tâche du journal, et le
//  titre de la carte de détail propre à cette tâche. Ils avaient divergé : la
//  synthèse disait « Sauvegarde quotidienne » quand la carte s'appelait
//  « Système — Sauvegardes ». On ne pouvait donc pas relier une ligne de la
//  synthèse au tableau qui la détaille. Signalé par l'utilisateur le 11/08/2026.
//
//  Les cartes de détail ont disparu avec #299 — le détail vit désormais SOUS la
//  ligne qui l'annonce, donc le titre n'a plus à être reconstruit ailleurs et
//  `titreDetail()` est parti avec elles. Ce module reste la source unique pour
//  les deux emplacements restants, qui sont dans deux fichiers différents.
//
//  Les clés sont celles que rend l'API (`tache` dans `historique_maintenance`,
//  plus `backup` et `telemetrie` qui ont leur propre table).
export const LIBELLE_TACHE: Record<string, string> = {
	maintenance: 'Maintenance hebdomadaire',
	backup: 'Sauvegarde quotidienne',
	bascule: 'Bascule actif/standby',
	telemetrie: 'Agrégation télémétrie',
	health_watch: 'Surveillance du site',
	reliability: 'Contrôles de fiabilité',
	auto_deploy: 'Déploiement automatique',
	//  Seule tâche lancée à la main depuis le poste : le libellé le dit, sinon une
	//  « exécution manquante » se lirait comme une panne alors qu'il s'agit d'un oubli.
	export_hors_site: 'Copie hors site (manuelle)',
	mise_a_jour: 'Mise à jour de la version',
	remise_a_zero_demo: 'Remise à zéro de la démo',
	conservation_affaires: 'Conservation des affaires',
	correctifs_systeme: 'Correctifs du système',
	audit_securite: 'Audit de sécurité nocturne',
};

//  Libellé du BOUTON qui lance une tâche à la main — quand il diffère du nom de
//  la tâche. Le nom d'une tâche planifiée et le nom de l'action déclenchable ne
//  sont pas la même chose : le bouton de la maintenance annonçait « Lancer
//  maintenance hebdomadaire » alors qu'il n'exécute que la part applicative
//  in-process (purges + VACUUM, sur le nœud qui répond). Le script hebdomadaire
//  fait cela ET l'hygiène du nœud en veille, que rien dans l'interface ne
//  déclenche.
//
//  Le 11/08/2026, l'utilisateur a cliqué ce bouton en croyant relancer la tâche
//  entière — et le rapport ainsi inséré a fait passer le badge au vert, masquant
//  le symptôme qu'un contrôle en cours d'observation attendait. La nuance était
//  écrite : en petit, à côté. Le libellé est ce qu'on lit avant d'agir ; une note
//  posée à côté ne corrige pas une promesse portée par le bouton lui-même.
export const LIBELLE_ACTION: Record<string, string> = {
	maintenance: 'Lancer la purge applicative',
};

/*  ── Les STATUTS d'une tâche planifiée ───────────────────────────────────────
    Remontés de `TachesPlanifiees.svelte` le 20/08/2026 (#488).

    🔴 Ils y ont grossi de trois à cinq états, et le garde-fou de modularité a
    refusé la croissance du fichier. Trois réponses possibles — découper,
    remonter la règle d'un cran, raboter (jamais) : c'est la deuxième, parce que
    ces tables ne disent rien de PROPRE à cet écran. Ce sont des données sur les
    statuts, et les libellés de TÂCHES vivaient déjà ici pour exactement cette
    raison — les redéfinir dans un écran est ce qui les fait diverger.  */
/*  Les huit états d'une tâche, chacun déclaré UNE fois avec ses trois attributs.

    ⚠️ Ils étaient six clés répétées dans trois tables parallèles — et l'ordre
    différait de l'une à l'autre, ce qui rendait la comparaison à l'œil presque
    impossible. L'aide contextuelle est le cas qui le montre : elle est ce qu'on
    lit quand le libellé ne suffit pas, donc l'attribut qu'on oublie.          */
const { libelle, aide, classe } = parAttribut({
	ok: {
		libelle: 'À jour',
		aide: 'Un rapport est arrivé dans le délai attendu.',
		classe: 'badge-green',
	},
	en_cours: {
		libelle: 'En cours',
		aide: 'La tâche a signalé son démarrage et n’a pas encore rendu son compte rendu.',
		classe: 'badge-green',
	},
	//  Les tâches de l'ACTIF seul (bascule, sauvegarde, télémétrie) : un nœud n'y
	//  agit qu'à son tour, et un failover le laisse hors du rôle deux nuits de
	//  suite (#2072). Gris : ni « À jour », qui mentirait sur sa date, ni rouge,
	//  puisque la tâche a tourné. Au-delà de trois nuits, l'API le repasse au rouge.
	pas_actif: {
		libelle: 'Pas actif à l’heure',
		aide:
			'Ce nœud n’a pas exécuté la tâche depuis plus de deux nuits, mais l’autre ' +
			'nœud l’a fait : la tâche ne tourne que sur le nœud actif, et après un ' +
			'failover un nœud peut ne pas être actif deux nuits de suite. Au-delà de ' +
			'trois nuits, ou si la tâche elle-même est en retard, la ligne passe au rouge.',
		classe: 'badge-gray',
	},
	rapport_perdu: {
		libelle: 'Rapport non reçu',
		aide:
			'La tâche a DÉMARRÉ — elle a écrit son battement de début — mais son ' +
			"compte rendu n'est jamais arrivé. Le ménage a donc bien eu lieu ; c'est " +
			'la chaîne de remontée qui est rompue. Chercher du côté du réseau, de la ' +
			'clé de maintenance ou du format de la charge utile, pas du côté de la tâche.',
		classe: 'badge-orange',
	},
	//  Les contrôles de fiabilité ont tourné et relèvent des WARN, sans FAIL
	//  (27/09/2026). Orange : ni « À jour », qui les tairait, ni rouge, qui
	//  crierait sur un point de confort. Leur liste est dans la carte voisine.
	vigilance: {
		libelle: 'Points de vigilance',
		aide:
			'Le dernier rapport relève des points à surveiller, sans échec. ' +
			'Leur liste est dans « Contrôles de fiabilité », plus bas.',
		classe: 'badge-orange',
	},
	manquante: {
		libelle: 'Exécution manquante',
		aide: 'Aucun rapport depuis plus longtemps que la périodicité de la tâche.',
		classe: 'badge-red',
	},
	erreur: {
		libelle: 'En échec',
		aide: 'Le dernier rapport signale un échec.',
		classe: 'badge-red',
	},
	aucune_execution: {
		libelle: 'Aucun rapport reçu',
		aide:
			"Aucun rapport en base pour cette tâche. Cela ne prouve pas qu'elle n'a pas " +
			'tourné : un rapport peut avoir échoué à remonter, ou avoir été purgé. ' +
			'Vérifier le journal du nœud avant de conclure.',
		classe: 'badge-red',
	},
});

export const LIBELLE_STATUT: Record<string, string> = libelle;
export const AIDE_STATUT: Record<string, string> = aide;
export const CLASSE_STATUT: Record<string, string> = classe;
