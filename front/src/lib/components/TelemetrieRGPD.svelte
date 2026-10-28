<!--
  **Les droits RGPD sur SA télémétrie** — opposition, portabilité, effacement.

  ## Pourquoi ce composant (#835, 08/09/2026)

  Extrait de `profil/+page.svelte` quand le garde-fou de modularité a refusé de
  le laisser grossir (739 → 754 lignes). Le refus disait vrai : cent onze lignes,
  cinq variables d'état, trois appels d'API et aucun lien avec le reste de la
  page — celle-ci en portait pourtant tout l'état.

  Les trois routes servies vivent elles-mêmes à part depuis le même lot
  (`routers/auth_telemetrie.py`), pour la même raison : elles ne parlent pas
  d'authentification.

  ⚠️ **Aucune prop.** Le composant lit l'utilisateur courant dans le store et
  parle directement à l'API. La page n'a rien à lui dire et rien à en apprendre :
  lui passer `opt_out_telemetrie` en prop aurait créé une seconde vérité sur une
  valeur que le serveur détient déjà.
-->
<script lang="ts">
	import { auth as authApi } from '#lib/api/index.ts';
	import { toast } from '#lib/components/Toast.svelte';
	import { currentUser, quandAuthResolue, setUser } from '#lib/stores/auth.ts';
	import { setTelemetryOptOut } from '#lib/telemetry.ts';
	import { enregistrerFichier } from '#lib/fichiers.ts';

	let optOutTelemetrie = false;
	let savingOptOut = false;
	let deletingTelemetrie = false;
	let exportingTelemetrie = false;
	let confirmDeleteTelemetrie = false;

	//  ⚠️ Lu à l'ouverture ET non lié en deux sens au store : la case reflète ce
	//  que le serveur a enregistré, et c'est l'appel qui fait foi. Un `$:` sur le
	//  store la remettrait à la valeur d'avant pendant l'enregistrement.
	//  Pas `onMount` : il précède le layout qui charge l'utilisateur (#1486).
	quandAuthResolue(() => {
		optOutTelemetrie = $currentUser?.opt_out_telemetrie ?? false;
	});
</script>

<!-- Télémétrie opt-out -->
<div class="bloc-telemetrie">
	<label class="checkbox-field case-telemetrie">
		<input
			type="checkbox"
			bind:checked={optOutTelemetrie}
			disabled={savingOptOut}
			on:change={async () => {
				savingOptOut = true;
				try {
					await authApi.toggleOptOutTelemetrie({ opt_out_telemetrie: optOutTelemetrie });
					setTelemetryOptOut(optOutTelemetrie);
					const updated = await authApi.me();
					setUser(updated);
					toast(
						'success',
						optOutTelemetrie
							? 'Collecte de statistiques désactivée.'
							: 'Collecte de statistiques réactivée.',
					);
				} catch {
					optOutTelemetrie = !optOutTelemetrie;
					toast('error', 'Erreur lors de la mise à jour.');
				}
				savingOptOut = false;
			}}
		/>
		Refuser la collecte de statistiques de navigation
	</label>
	<p class="note-telemetrie">
		Ces statistiques anonymisées permettent au gestionnaire d'identifier les fonctionnalités les
		plus utilisées, de détecter d'éventuels problèmes de navigation et d'orienter les améliorations
		futures vers ce qui vous est réellement utile au quotidien. Elles ne contiennent aucune donnée
		personnelle sensible et ne sont jamais partagées avec des tiers. En les désactivant, vous nous
		privez d'informations précieuses pour vous offrir une meilleure expérience.
	</p>

	<div class="actions-telemetrie">
		<button
			type="button"
			class="btn btn-sm btn-telemetrie"
			disabled={exportingTelemetrie}
			on:click={async () => {
				exportingTelemetrie = true;
				try {
					const data = await authApi.exportTelemetrie();
					const json = JSON.stringify(data, null, 2);
					enregistrerFichier(
						new Blob([json], { type: 'application/json' }),
						'mes-donnees-telemetrie.json',
					);
					toast('success', 'Export téléchargé.');
				} catch {
					toast('error', "Erreur lors de l'export.");
				}
				exportingTelemetrie = false;
			}}
		>
			📥 Exporter mes données de navigation
		</button>

		{#if !confirmDeleteTelemetrie}
			<button
				type="button"
				class="btn btn-sm btn-danger btn-telemetrie"
				on:click={() => (confirmDeleteTelemetrie = true)}
			>
				🗑️ Effacer mes données de navigation
			</button>
		{:else}
			<span class="confirmation">
				<strong class="danger">Confirmer ?</strong>
				<button
					type="button"
					class="btn btn-sm btn-danger btn-telemetrie"
					disabled={deletingTelemetrie}
					on:click={async () => {
						deletingTelemetrie = true;
						try {
							await authApi.effacerTelemetrie();
							toast('success', 'Données de navigation effacées.');
						} catch {
							toast('error', 'Erreur lors de la suppression.');
						}
						deletingTelemetrie = false;
						confirmDeleteTelemetrie = false;
					}}
				>
					Oui, effacer
				</button>
				<button
					type="button"
					class="btn btn-sm btn-telemetrie"
					on:click={() => (confirmDeleteTelemetrie = false)}
				>
					Annuler
				</button>
			</span>
		{/if}
	</div>
</div>

<style>
	.bloc-telemetrie {
		margin-top: 1rem;
		padding-top: 0.75rem;
		border-top: 1px solid var(--color-warning-bordure);
	}
	.case-telemetrie {
		margin-bottom: 0.4rem;
	}
	.note-telemetrie {
		font-size: var(--fs-sm);
		color: var(--color-text-muted);
		margin: 0 0 0.75rem;
		padding-left: 1.55rem;
	}
	.actions-telemetrie {
		display: flex;
		gap: 0.5rem;
		flex-wrap: wrap;
	}
	.btn-telemetrie {
		font-size: var(--fs-sm);
	}
	.confirmation {
		display: inline-flex;
		gap: 0.35rem;
		align-items: center;
		font-size: var(--fs-sm);
	}
	.danger {
		color: var(--color-danger);
	}
</style>
