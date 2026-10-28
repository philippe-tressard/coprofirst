<!--
  Le **contrôle de santé quotidien**, relancé à la demande (#852).

  🔴 Pourquoi ce bouton existe. Le 09/09/2026, ce contrôle a émis une alerte dont
  la cause était fausse ; le correctif est parti le matin même, et **rien ne
  permettait de le vérifier avant le lendemain 06:00**. Un contrôle qu'on ne peut
  pas rejouer ne sert pas à constater sa propre correction : on livre, et on
  attend de voir si l'alerte revient.

  C'est aussi ce qui rend le job **observable** : son seul signe de vie est un
  e-mail envoyé *quand il y a un problème*. Le silence d'un ordonnanceur mort et
  celui d'une installation saine sont exactement le même silence.

  ⚠️ Aucun e-mail n'est envoyé ici. L'alerte est le geste du job de 06:00, qui
  s'adresse au gestionnaire du site ; quelqu'un est déjà devant l'écran.
-->
<script lang="ts">
	import SectionFormulaire from './SectionFormulaire.svelte';
	import { admin as adminApi } from '#lib/api/index.ts';
	import { messageErreur } from '#lib/erreurs.ts';
	import { fmtDatetime } from '#lib/date.ts';
	import { toast } from '#lib/components/Toast.svelte';

	type Probleme = { titre: string; details: string[] };

	let chargement = false;
	let erreur = '';
	//  `null` = pas encore lancé. À distinguer d'un tableau vide, qui veut dire
	//  « lancé, et rien trouvé » — c'est toute la différence entre INCONNU et OK,
	//  et l'écran ne doit pas les rendre pareils.
	let problemes: Probleme[] | null = null;
	let lanceLe: string | null = null;

	async function lancer() {
		chargement = true;
		erreur = '';
		try {
			const res = await adminApi.relancerControleSante();
			problemes = res.problemes ?? [];
			lanceLe = new Date().toISOString();
			toast(
				problemes.length ? 'error' : 'success',
				problemes.length
					? `${problemes.length} problème(s) détecté(s).`
					: 'Aucun problème détecté.',
			);
		} catch (e) {
			erreur = messageErreur(e);
			problemes = null;
		} finally {
			chargement = false;
		}
	}
</script>

<!--  🔴 Le titre passe par `SectionFormulaire` (12/09/2026, signalé à l'écran) :
      les blocs de cet onglet titraient chacun à sa façon — un `<h3>` nu ici,
      un `<h3 class="config-section-title">` dans `ConfigSauvegarde`. Des blocs
      voisins, des typographies différentes, aucun filet entre eux.

      C'est la règle la plus déployée qui l'emporte : `SectionFormulaire` porte
      l'intitulé, le filet et l'espacement pour tout le site. -->
<section class="card config-section">
	<div class="entete config-section-entete">
		<div>
			<SectionFormulaire titre="Contrôle de santé" icone="activity" />
			<p class="muted">
				Les mêmes vérifications que le contrôle automatique de 6&nbsp;h&nbsp;00 — base, WhatsApp,
				sauvegardes, copie hors site, disque, référence de copropriété et modèles d’e-mail. Aucun
				message n’est envoyé&nbsp;: le résultat s’affiche ici.
			</p>
		</div>
		<button class="btn btn-primary" type="button" on:click={lancer} disabled={chargement}>
			{chargement ? 'Contrôle en cours…' : 'Relancer le contrôle'}
		</button>
	</div>

	{#if erreur}
		<p class="resultat resultat-erreur">Le contrôle n’a pas pu s’exécuter&nbsp;: {erreur}</p>
	{:else if problemes === null}
		<p class="muted resultat">Jamais lancé depuis cet écran.</p>
	{:else if problemes.length === 0}
		<p class="resultat resultat-ok">
			Aucun problème détecté — contrôle lancé le {fmtDatetime(lanceLe)}.
		</p>
	{:else}
		<p class="resultat resultat-erreur">
			{problemes.length} problème(s) — contrôle lancé le {fmtDatetime(lanceLe)}.
		</p>
		<ul class="liste">
			{#each problemes as p, i (i)}
				<li>
					<strong>{p.titre}</strong>
					{#each p.details as d, j (j)}
						<span class="detail">{d}</span>
					{/each}
				</li>
			{/each}
		</ul>
	{/if}
</section>

<style>
	/*  Le `<h3>` local a cédé la place à `SectionFormulaire`, et sa règle de
	    typographie avec lui : elle redisait ce que la charte dit déjà. */
	.entete p {
		margin: 0;
		max-width: 60ch;
		font-size: var(--fs-md);
	}
	/*  44 px : une cible tactile est une taille PHYSIQUE, celle d'un pouce (#839). */
	.entete button {
		min-height: 44px;
	}
	.resultat {
		margin: 1rem 0 0;
		font-size: var(--fs-base);
	}
	.resultat-ok {
		color: var(--color-success);
		font-weight: 600;
	}
	.resultat-erreur {
		color: var(--color-danger);
		font-weight: 600;
	}
	.liste {
		margin: 0.5rem 0 0;
		padding-left: 1.2rem;
		font-size: var(--fs-base);
	}
	.liste li {
		margin-bottom: 0.75rem;
	}
	.detail {
		display: block;
		font-weight: 400;
		color: var(--color-text-muted);
		font-size: var(--fs-md);
	}
</style>
