<script lang="ts">
	/**  La référence de la copropriété chez son syndic — clé `ConfigSite`,
	 *   remontée par la page comme le reste de la configuration. */
	export let referenceCopro = '';
	/**  L'adresse publique de l'installation — dérivée, jamais saisie (#2058) ; lue
	     par la page avec le paramétrage. Montrée dans l'Identité depuis #2062. */
	export let urlPublique = '';
	import { onMount } from 'svelte';
	import {
		config as configApi,
		copropriete as coproprieteApi,
		type Copropriete,
	} from '#lib/api/index.ts';
	import { toast } from '#lib/components/Toast.svelte';
	import { nomResidenceEnregistre, siteNomStore } from '#lib/stores/pageConfig.ts';
	import Icon from '#lib/components/Icon.svelte';
	import ChampLogo from '#lib/components/ChampLogo.svelte';
	import ChampPalette from '#lib/components/ChampPalette.svelte';
	import SectionFormulaire from '#lib/components/SectionFormulaire.svelte';
	import SectionContratReference from '#lib/components/SectionContratReference.svelte';
	import ChampsIdentiteCopropriete, {
		chargeIdentite,
		identiteDepuis,
	} from '#lib/components/ChampsIdentiteCopropriete.svelte';
	import { fmtDateShort as fmtDate } from '#lib/date.ts';
	import EtatListe from '#lib/components/EtatListe.svelte';
	import { REGLE_PAR_L_EXPLOITANT } from '#lib/portee.ts';
	import { estAbsent, messageErreur } from '#lib/erreurs.ts';
	import { SEPARATEUR } from '#lib/separateurs.ts';

	$: _siteNom = $siteNomStore;

	//  UNIQUEMENT les champs que `CoproprieteUpdate` accepte. Sept autres
	//  figuraient ici — `code_postal`, `ville`, les quatre du syndic et
	//  `assurance_numero` — qui n'existent ni dans le schéma ni dans le modèle :
	//  Pydantic les jetait en silence, et le formulaire promettait donc un
	//  enregistrement qui n'avait pas lieu (signalé à l'usage le 13/08/2026).
	//  `assurance_numero` était le plus traître : le champ existe, sous le nom
	//  `assurance_numero_police`. Une lettre de plus et il ne s'enregistrait pas.
	//
	//  🔴 Les TROIS champs d'assurance ont quitté ce formulaire (#490) : ils
	//  décrivaient un contrat avec un prestataire, notion que le projet possède
	//  déjà. Les laisser ici referait exactement la faute décrite ci-dessus —
	//  un formulaire qui promet un enregistrement que le serveur n'accepte plus.
	//
	//  L'identité vient d'`identiteDepuis`, comme sur l'écran Résidence : la copie
	//  écrite ici avait perdu `mois_debut_exercice` (#1643), jamais chargé (08/10).
	const formulaireDepuis = (data: Copropriete | null) => ({
		...identiteDepuis(data),
		//  Non affiché : relu, et renvoyé tel quel.
		nb_parkings_communs: data?.nb_parkings_communs ?? '',
		//  Les deux DÉSIGNATIONS, seuls champs que la fiche écrit sur une section
		//  adossée à un contrat. `null` = aucun contrat désigné.
		assurance_contrat_id: data?.assurance_contrat_id ?? null,
		syndic_contrat_id: data?.syndic_contrat_id ?? null,
	});
	let form = formulaireDepuis(null);
	/**  Ce que la fiche AFFICHE des deux sections adossées à un contrat.
	 *
	 *   🔴 Lu, jamais réécrit — sauf la DÉSIGNATION (`*_contrat_id`), qui dit
	 *   lequel des contrats existants fait foi. Saisir ici la compagnie ou le
	 *   cabinet recréerait le doublon que #490 a supprimé.
	 *
	 *   ⚠️ Un seul objet pour les deux sections : deux objets auraient donné deux
	 *   façons de lire la même réponse. */
	let fiche: Partial<Copropriete> = {};
	let loading = true;
	let erreur = '';
	let saving = false;

	onMount(async () => {
		try {
			const data = await coproprieteApi.get();
			if (data) {
				form = formulaireDepuis(data);
				//  Lu, jamais réécrit — cf. le commentaire de `fiche`.
				fiche = data;
			}
		} catch (e) {
			//  Seul un 404 dit « pas encore de fiche » : le formulaire vide est alors
			//  juste. Tout autre échec n'a rien lu, et un formulaire vide enregistré
			//  écraserait la fiche (#1459) — on ne l'affiche donc pas.
			if (!estAbsent(e)) erreur = messageErreur(e);
		} finally {
			loading = false;
		}
	});

	async function save() {
		saving = true;
		try {
			//  Un nombre vide part à `null` : la règle vit avec les champs (#779).
			const payload = chargeIdentite(form);
			//  ⚠️ La réponse du PATCH est RELUE, pas ignorée : changer le contrat
			//  désigné change tout ce que les deux sections affichent. Garder
			//  l'ancien affichage montrerait l'assureur précédent sous le nouveau
			//  choix, jusqu'au prochain rechargement de page.
			const lue = await coproprieteApi.update(payload);
			fiche = lue;
			nomResidenceEnregistre(lue.nom);
			//  ⚠️ DEUX destinations pour un seul bouton : la fiche est une entité, la
			//  référence chez le syndic une clé de configuration. L'écran ne le montre
			//  pas — ce serait exposer notre découpage —, mais il enregistre les deux
			//  ou aucune : un « Enregistré » qui n'aurait sauvé que la moitié serait
			//  pire qu'une erreur.
			await configApi.save({ reference_copro: referenceCopro });
			toast('success', 'Fiche enregistrée');
		} catch {
			toast('error', 'Erreur lors de la sauvegarde');
		} finally {
			saving = false;
		}
	}
</script>

<svelte:head><title>Admin — Identité — {_siteNom}</title></svelte:head>

{#if loading || erreur}
	<EtatListe chargement={loading} {erreur} titreErreur="Impossible d’afficher la fiche" />
{:else}
	<section class="card config-section">
		<h2 class="config-section-title">
			<Icon name="building-2" size={17} />Fiche de la copropriété
		</h2>
		<form on:submit|preventDefault={save}>
			<SectionFormulaire premiere icone="settings" titre="Identité">
				<div class="form-grid largeur-saisie">
					<ChampsIdentiteCopropriete bind:valeurs={form} />
					<!--  Le logo et l'adresse publique vivaient dans « Paramétrage site » :
					      ils disent QUI est la copropriété, ils rejoignent son identité
					      (#2062). Le logo se téléverse seul (`ChampLogo`), la palette se choisit
					      seule (`ChampPalette`, #2379), l'adresse ne se saisit pas — aucun ne
					      part avec ce formulaire. -->
					<ChampLogo />
					<ChampPalette />
					<label class="field">
						URL publique
						<input type="url" value={urlPublique} readonly />
						<span class="aide"
							>L’adresse de l’installation, celle des liens des courriels et des pages légales. {REGLE_PAR_L_EXPLOITANT}</span
						>
					</label>
				</div>
			</SectionFormulaire>

			<!--  🔴 DEUX SECTIONS, UN SEUL COMPOSANT (#553).
	      L'assurance et le syndic posent la même question — lequel des contrats
	      existants cette fiche désigne-t-elle ? — et affichent la même chose.
	      Les écrire deux fois aurait donné deux sections libres de diverger au
	      premier enrichissement demandé d'un seul côté.

	      ⚠️ On DÉSIGNE ici, on MODIFIE dans Prestataires → Contrats. Le
	      sélecteur ne crée ni ne modifie un contrat : il dit lequel fait foi. -->
			<SectionContratReference
				titre="Assurance"
				icone="shield"
				section="assurance"
				bind:contratId={form.assurance_contrat_id}
				documentId={fiche.assurance_document_id ?? null}
				lignes={[
					['Compagnie', fiche.assurance_compagnie],
					['Téléphone', fiche.assurance_telephone],
					['Courriel', fiche.assurance_email],
					['N° de police', fiche.assurance_numero_police],
					['Début', fiche.assurance_debut ? fmtDate(fiche.assurance_debut) : null],
					[
						'Échéance',
						fiche.assurance_echeance
							? fmtDate(fiche.assurance_echeance) +
								(fiche.assurance_reconduit ? ' (reconduit tacitement)' : '')
							: null,
					],
				]}
			>
				<svelte:fragment slot="renvoi">
					L'assurance est un <strong>contrat</strong> : elle se modifie dans
					<a href="/prestataires/contrats">Prestataires{SEPARATEUR.fleche}Contrats</a>, avec son
					prestataire, son échéance et son attestation.
				</svelte:fragment>
			</SectionContratReference>

			<!--  ⚠️ L'INTERLOCUTEUR ne vient PAS du prestataire, mais de l'annuaire
	      (`MembreSyndic`). Le prestataire porte le CABINET, l'annuaire garde les
	      PERSONNES — et c'est de l'annuaire que partent les courriels, lu par dix
	      modules côté serveur. Recopier ces personnes dans les contacts du
	      prestataire aurait donné deux listes des mêmes gens : la faute de #490
	      transposée au circuit des notifications, où elle ne se verrait que le
	      jour où un message ne partirait pas. -->
			<!--  ⚠️ L'ICÔNE EST VÉRIFIÉE DANS LE CATALOGUE avant d'être écrite.
	      `briefcase` — le premier choix — n'existe pas dans
	      `#lib/icones-svg.json` : `Icon` serait retombé EN SILENCE sur
	      `help-circle`, et la section aurait porté un point d'interrogation sans
	      qu'aucun contrôle ne le dise. `users-round` dit « un cabinet, des
	      gens », et il est là. -->
			<SectionContratReference
				titre="Syndic"
				icone="users-round"
				section="syndic"
				bind:contratId={form.syndic_contrat_id}
				documentId={fiche.syndic_document_id ?? null}
				lignes={[
					['Cabinet', fiche.syndic_cabinet],
					['Téléphone', fiche.syndic_telephone],
					['Courriel', fiche.syndic_email],
					['N° de mandat', fiche.syndic_numero_mandat],
					['Début', fiche.syndic_debut ? fmtDate(fiche.syndic_debut) : null],
					//  Un mandat ne se reconduit pas : échu, il appelle une AG (#628).
					[
						'Mandat',
						fiche.syndic_echeance
							? fmtDate(fiche.syndic_echeance) +
								(fiche.syndic_echu ? ' — ÉCHU, à renouveler en AG' : '')
							: null,
					],
					['Interlocuteur', fiche.syndic_interlocuteur],
					['Courriel direct', fiche.syndic_interlocuteur_email],
				]}
			>
				<svelte:fragment slot="complement">
					<!--  🔴 Elle vivait dans admin → SMTP (11/09/2026, signalé à l'écran) :
					      « ne serait-il pas logique de la positionner dans Fiche copropriété,
					      section Syndic ? ». Si. Elle décrit le dossier de la copropriété
					      CHEZ le syndic — elle se lit avec le cabinet et le mandat, pas avec
					      un serveur d'envoi.

					      ⚠️ La valeur reste dans `ConfigSite` : c'est là que vit toute la
					      configuration du site, et la déplacer en base n'aurait rien changé à
					      l'endroit où on la LIT. On déplace l'écran, pas le schéma. -->
					<label class="field champ-moyen">
						Référence syndic de la copropriété
						<input type="text" bind:value={referenceCopro} placeholder="00213" />
						<span class="aide">
							Le numéro de dossier de la copropriété chez son syndic. Il préfixe les sujets des
							courriels qui lui sont envoyés.
						</span>
					</label>
				</svelte:fragment>
				<svelte:fragment slot="renvoi">
					Le cabinet et son mandat se modifient dans
					<a href="/prestataires/contrats">Prestataires{SEPARATEUR.fleche}Contrats</a>. Ses
					<strong>membres</strong>, eux, vivent dans
					<a href="/espace-cs">Espace CS &rsaquo; Annuaire</a>{SEPARATEUR.tiret}c'est de là que
					partent les courriels au cabinet.
				</svelte:fragment>
			</SectionContratReference>

			<!--  🔴 `.form-actions` — l'action principale va à DROITE (app.css,
	      `justify-content: flex-end`). Le bouton était dans un `<div>` NU, donc
	      collé à gauche : c'est ce que #501 signalait.

	      ⚠️ Pas de bouton « Annuler » ici, et c'est délibéré : AUCUN onglet
	      d'administration n'en porte. En ajouter un sur celui-ci recréerait la
	      divergence que ce lot corrige — l'écran rejoint les autres, il ne les
	      devance pas. -->
			<div class="largeur-saisie form-actions">
				<button class="btn btn-primary" type="submit" disabled={saving}>
					{saving ? 'Enregistrement…' : 'Enregistrer'}
				</button>
			</div>
		</form>
	</section>
{/if}

<style>
	/*  L'assurance en LECTURE : une liste de définitions, pas un formulaire.
	    La forme dit le régime — on lit ici, on modifie ailleurs (#490). */
	/*  ⚠️ Sur téléphone, deux colonnes serrent les valeurs longues (un nom de
	    compagnie, un numéro de police) au point de les couper mot à mot. La
	    liste passe alors en une colonne — `standards/11` §10. */
	/*  `.form-section` et `.section-title` vivaient ici : ils REDÉFINISSAIENT la
	    carte et le titre de sous-section que `card` / `config-section-title` et
	    `SectionFormulaire` portent déjà (anatomie v2.94.0). Deux définitions d'un
	    même objet ne sont pas livrables — cet écran était simplement resté hors
	    du lot qui a aligné les huit autres onglets (#501). `.form-grid` aussi :
	    sa colonne de 220px était celle de `champs.css`, recopiée — à `auto-fill`
	    près (tolérance de `lint:charte`), sans effet pour six champs qui
	    remplissent leurs rangées (#779). */
</style>
