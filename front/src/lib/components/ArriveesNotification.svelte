<script lang="ts">
	/**
	 * **Arrivées par notification** (#1634) — par canal et par type de courriel,
	 * combien de visites sont arrivées par le lien d'une notification, rapportées
	 * aux messages envoyés. Une notification que personne n'ouvre est du bruit :
	 * un modèle envoyé et jamais suivi a sa ligne, à zéro.
	 *
	 * L'étiquette du lien, sa lecture et ses limites :
	 * `api/app/utils/arrivees_notification.py` et `#lib/arrivees`.
	 */
	import { fmtNombre } from '#lib/utils.ts';
	import PanneauTelemetrie from '#lib/components/PanneauTelemetrie.svelte';
	import type { ArriveeNotification } from '#lib/api/index.ts';
	import { SEPARATEUR } from '#lib/separateurs.ts';

	export let arrivees: ArriveeNotification[] = [];
	export let periode: string;
	/** Section dépliée ? L'onglet décide, et reçoit `basculer` (`PanneauTelemetrie`). */
	export let ouvert = false;

	const CANAUX = { courriel: 'Courriel', whatsapp: 'WhatsApp' } as const;
	const type = (a: ArriveeNotification) =>
		a.canal === 'whatsapp' ? 'Groupe de la résidence' : (a.libelle ?? a.modele ?? 'Autre');
</script>

<PanneauTelemetrie
	titre="📬 Arrivées par notification"
	{periode}
	{ouvert}
	vide={!arrivees.length}
	videLibelle="aucune notification envoyée ni suivie"
	on:basculer
>
	<div class="table-wrap">
		<table class="table">
			<thead>
				<tr>
					<th>Canal</th><th>Notification</th><th class="nombre">Arrivées</th>
					<th class="nombre">Comptes</th><th class="nombre">Messages envoyés</th>
				</tr>
			</thead>
			<tbody>
				{#each arrivees as a (`${a.canal}|${a.modele ?? ''}`)}
					<tr>
						<td>{CANAUX[a.canal]}</td>
						<td class="text-muted-sm">{type(a)}</td>
						<td class="nombre">{fmtNombre(a.arrivees)}</td>
						<td class="nombre">{fmtNombre(a.comptes)}</td>
						<td class="nombre">{fmtNombre(a.envois)}</td>
					</tr>
				{/each}
			</tbody>
		</table>
	</div>
	<svelte:fragment slot="pied">
		<p>
			Les liens des courriels et des messages du groupe portent leur canal, et pour un courriel son
			type{SEPARATEUR.tiret}jamais l’adresse ni l’identité du destinataire, et jamais un lien à
			usage unique (mot de passe oublié, vérification d’adresse). Une arrivée compte même si la
			personne doit d’abord se connecter. Un courriel envoyé à plusieurs personnes compte pour un
			message. Seuls les liens envoyés depuis la mise en place de l’étiquette sont comptés.
			Conservation : 30 jours.
		</p>
	</svelte:fragment>
</PanneauTelemetrie>
