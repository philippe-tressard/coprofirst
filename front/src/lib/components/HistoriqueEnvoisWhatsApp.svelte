<!--
  L'historique des envois WhatsApp — les derniers messages et leur verdict.

  Extrait de `OngletWhatsApp.svelte` le 28/09/2026 (#1329). Le rendu lui-même
  est dans `JournalVerdicts` depuis le même jour (#1447) : la relève des
  réponses par courriel montre la même chose, et ce composant ne fait plus que
  dire ce qu'un envoi WhatsApp donne à lire.
-->
<script lang="ts">
	import type { JournalEnvoiWhatsApp } from '#lib/api/index.ts';
	import JournalVerdicts, {
		type EntreeJournal,
		type TonVerdict,
	} from '#lib/components/JournalVerdicts.svelte';

	export let journaux: JournalEnvoiWhatsApp[] = [];
	export let erreur = '';
	export let recharger: () => unknown = () => {};

	//  Un seuil employé pour couper ET pour comparer se nomme : écrit deux fois,
	//  il donne un aperçu tronqué à une longueur et une décision prise à une autre
	//  le jour où l'un des deux bouge (#1076).
	const MAX_APERCU_MESSAGE = 120;

	//  Un envoi a trois issues, pas deux : réussi, échoué, ou sans réponse du
	//  bridge. Ce dernier cas s'affichait « ❌ échec » alors que le message était
	//  le plus souvent bien arrivé dans le groupe — c'est cette lecture qui a
	//  fait renvoyer trois fois le message des encombrants le 14/08/2026.
	function icone(statut: string): string {
		if (statut === 'envoyé') return '✅';
		if (statut === 'incertain') return '⚠️';
		if (statut === 'en cours') return '⏳';
		return '❌';
	}
	function ton(statut: string): TonVerdict {
		if (statut === 'envoyé') return 'succes';
		if (statut === 'incertain' || statut === 'en cours') return 'attention';
		return 'danger';
	}

	$: entrees = journaux.map((log): EntreeJournal => ({
		cle: log.id,
		titre: log.label,
		sousTitre: log.canal ? `Canal : ${log.canal}` : undefined,
		verdict: `${icone(log.statut)} ${log.statut}`,
		ton: ton(log.statut),
		date: log.envoye_le,
		texte:
			log.message.length > MAX_APERCU_MESSAGE
				? log.message.slice(0, MAX_APERCU_MESSAGE) + '…'
				: log.message,
		alerte: log.erreur ?? undefined,
	}));
</script>

<JournalVerdicts
	{entrees}
	{erreur}
	{recharger}
	vide="Aucun message envoyé."
	libelleRecharger="Rafraîchir l'historique"
/>
