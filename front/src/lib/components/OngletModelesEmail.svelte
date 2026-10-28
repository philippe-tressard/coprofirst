<!--
  L'onglet **Modèles e-mail** de l'administration : la liste des gabarits, leur
  édition, la réinitialisation des designs, et l'historique des envois.

  ## Il en existait DEUX jusqu'au 19/08/2026

  `admin/templates-email` — « Designs des modèles d'e-mail » — montrait la même
  donnée sous un autre angle. Le doublon était connu depuis #299, déclaré en
  tolérance dans `lint:routes`, et son arbitrage attendait dans #307 : *« les
  fusionner est une décision fonctionnelle »*. Elle a été prise à l'écran.

  🔴 **La fusion est une UNION, pas un remplacement.** Chacun savait faire ce que
  l'autre ignorait :

  | Capacité | Venait de |
  |---|---|
  | table Code · Nom · Sujet · Actif, historique des envois | l'onglet |
  | corps texte (repli) | l'onglet |
  | **intention** (le bandeau attendu du destinataire) | Designs |
  | **aperçu** du corps rendu | Designs |
  | **variables disponibles** du gabarit | Designs |
  | **réinitialiser tous les designs** | Designs |

  ⚠️ Une seule chose n'a pas été reprise : le **regroupement par domaine**.
  `ModeleEmail` n'a ni `domaine` ni `categorie` — l'écran rangeait donc tout dans
  un unique groupe « général ». Ce n'était pas une capacité, c'était une promesse
  vide.

  ⚠️ Et une capacité a été **réparée en la reprenant** : « variables disponibles »
  découpait sur les virgules un champ qui est un **tableau JSON**, et affichait
  `{{ ["civilite" }}`. Recopier le geste aurait recopié le défaut.
-->
<script lang="ts">
	import IconeAction from '#lib/components/IconeAction.svelte';
	import { messageErreur } from '#lib/erreurs.ts';
	import FormulaireCreation from '#lib/components/FormulaireCreation.svelte';
	import PiedFormulaire from '#lib/components/PiedFormulaire.svelte';
	import { onMount } from 'svelte';
	import { admin as adminApi, type EnvoiEmail, type ModeleEmail } from '#lib/api/index.ts';
	import { toast } from '#lib/components/Toast.svelte';
	import { confirmer } from '#lib/confirmation.ts';
	import { safeHtml } from '#lib/sanitize.ts';
	import EtatListe from '#lib/components/EtatListe.svelte';
	import HistoriqueEnvoisEmail from '#lib/components/HistoriqueEnvoisEmail.svelte';

	let emailTemplates: ModeleEmail[] = [];
	let emailsLoading = true;
	let emailEdit: ModeleEmail | null = null;
	let emailSujet = '';
	let emailCorpsHtml = '';
	let emailActif = true;
	let emailIntention = '';
	let emailApercu = false;

	//  L’INTENTION — ce que le message attend de son destinataire, rendu en
	//  bandeau au-dessus du corps par le gabarit commun. Les valeurs sont celles
	//  d’`app/utils/email.INTENTIONS`, que le serveur vérifie en liste blanche et
	//  refuse en 422 si elles divergent : c’est lui qui fait foi, pas cette liste.
	const INTENTIONS = [
		{ valeur: '', label: 'Aucun bandeau' },
		{ valeur: 'information', label: 'Pour information' },
		{ valeur: 'action_requise', label: 'Action requise' },
		{ valeur: 'reponse_attendue', label: 'Réponse attendue' },
		{ valeur: 'archive', label: 'À conserver' },
	];
	//  `variables_disponibles` est un tableau JSON en base — `'["civilite", "nom"]'`.
	//  L’écran « Designs » le découpait sur les VIRGULES et affichait donc
	//  `{{ ["civilite" }}`, crochets et guillemets compris. Le défaut est corrigé
	//  en le fusionnant ici (19/08/2026) plutôt que recopié : on analyse le JSON, et
	//  on ne retombe sur la virgule que pour une valeur ancienne écrite à plat.
	//  🔴 Le dédoublonnage n'est PAS un artifice pour satisfaire `lint:each-key`.
	//  Annoncer deux fois la même variable disponible est un défaut d'affichage à
	//  part entière — et c'est ce qui rendait la clé impossible : `variables_disponibles`
	//  est du texte libre en base (JSON, ou liste à plat pour les valeurs héritées),
	//  donc rien n'y garantissait l'unicité. Le corriger à la source rend la clé
	//  sûre en même temps, au lieu de choisir entre les deux.
	const unique = (v: string[]): string[] => [...new Set(v)];

	function variablesDeModele(brut: string | null | undefined): string[] {
		const texte = (brut ?? '').trim();
		if (!texte) return [];
		try {
			const lu = JSON.parse(texte);
			if (Array.isArray(lu)) return unique(lu.map((v) => String(v).trim()).filter(Boolean));
		} catch {
			/* valeur héritée, écrite à plat */
		}
		return unique(
			texte
				.split(',')
				.map((v) => v.trim())
				.filter(Boolean),
		);
	}

	const labelIntention = (v: string | null | undefined) =>
		INTENTIONS.find((i) => i.valeur === (v ?? ''))?.label ?? '';
	let emailSaving = false;
	let emailHistory: EnvoiEmail[] = [];
	let emailHistoryLoading = true;

	/*  🔴 Ce chargement n'avait AUCUN `catch` (#816). Une erreur remontait sans
	    être vue, les deux listes restaient vides, et l'écran annonçait « Aucun
	    modèle trouvé » — sur la page qui sert à vérifier que les courriels du
	    site sont bien configurés. Le pire endroit pour affirmer une absence
	    qu'on n'a pas constatée. */
	let erreurModeles = '';
	let erreurHistorique = '';

	async function loadEmails() {
		emailsLoading = true;
		emailHistoryLoading = true;
		erreurModeles = '';
		erreurHistorique = '';
		//  ⚠️ `allSettled` et non `all` : avec `all`, l'échec de l'UNE annule
		//  l'autre, et une panne de l'historique effacerait les modèles. Les deux
		//  listes sont indépendantes, leurs échecs doivent l'être aussi.
		const [modeles, historique] = await Promise.allSettled([
			adminApi.emailTemplates(),
			adminApi.emailsHistorique(),
		]);
		if (modeles.status === 'fulfilled') emailTemplates = modeles.value;
		else erreurModeles = messageErreur(modeles.reason, 'Chargement impossible');
		if (historique.status === 'fulfilled') emailHistory = historique.value;
		else erreurHistorique = messageErreur(historique.reason, 'Chargement impossible');
		emailsLoading = false;
		emailHistoryLoading = false;
	}

	function openEmailEdit(tpl: ModeleEmail) {
		emailEdit = tpl;
		emailSujet = tpl.sujet ?? '';
		emailCorpsHtml = tpl.corps_html ?? '';
		emailActif = tpl.actif ?? true;
		//  `?? ''` et non `?? undefined` : `undefined` ne correspondrait à aucune
		//  option du sélecteur, qui s’afficherait vide au lieu d’« Aucun bandeau ».
		emailIntention = tpl.intention ?? '';
		emailApercu = false;
	}

	async function saveEmailEdit() {
		if (!emailEdit) return;
		const id = emailEdit.id;
		emailSaving = true;
		try {
			const updated = await adminApi.updateEmailTemplate(id, {
				sujet: emailSujet,
				corps_html: emailCorpsHtml,
				intention: emailIntention,
				//  La case n'existe pas pour un modèle non désactivable : rien à écrire.
				...(emailEdit.desactivable ? { actif: emailActif } : {}),
			});
			emailTemplates = emailTemplates.map((t) => (t.id === id ? updated : t));
			toast('success', 'Modèle mis à jour.');
			emailEdit = null;
		} catch (e) {
			toast('error', messageErreur(e));
		} finally {
			emailSaving = false;
		}
	}

	//  Remettre CE modèle-là au texte du code, sans toucher aux autres (#852).
	//  Seule la remise à zéro globale existait : réparer un modèle dont le Jinja
	//  a été cassé d’un caractère imposait de détruire les textes choisis pour
	//  les vingt-trois autres.
	let emailResetOne = false;
	async function resetCeModele() {
		if (!emailEdit) return;
		const ok = await confirmer({
			message: `Remettre « ${emailEdit.code} » au texte livré avec l’application ? Les modifications faites sur CE modèle seront perdues.`,
			libelleConfirmer: 'Remettre par défaut',
			danger: true,
		});
		if (!ok) return;
		const id = emailEdit.id;
		emailResetOne = true;
		try {
			const updated = await adminApi.resetEmailTemplate(id);
			emailTemplates = emailTemplates.map((t) => (t.id === id ? updated : t));
			openEmailEdit(updated);
			toast('success', 'Modèle remis par défaut.');
		} catch (e) {
			toast('error', messageErreur(e));
		} finally {
			emailResetOne = false;
		}
	}

	//  Remettre TOUS les modèles à leur design par défaut. Venait de l’écran
	//  « Designs des modèles d’e-mail », fusionné ici le 19/08/2026 : il montrait
	//  la même donnée sous un autre angle, et cette action était la seule qu’il
	//  portait seul (#307).
	let emailResetting = false;
	async function resetEmailTemplates() {
		//  Converti de `confirm()` natif le 09/09/2026, en même temps que le
		//  bouton d’à côté : la boîte native donne le même aspect à « remettre un
		//  modèle » et à « écraser les vingt-quatre ».
		const ok = await confirmer({
			message:
				'Remettre TOUS les modèles à leur design par défaut ? Les textes personnalisés seront perdus.',
			libelleConfirmer: 'Tout remettre par défaut',
			danger: true,
		});
		if (!ok) return;
		emailResetting = true;
		try {
			const res = await adminApi.resetEmailTemplates();
			toast('success', res?.message ?? 'Designs réinitialisés.');
			await loadEmails();
		} catch (e) {
			toast('error', messageErreur(e));
		} finally {
			emailResetting = false;
		}
	}

	onMount(loadEmails);
</script>

<p class="muted intro-modeles">Modeles utilises pour les notifications automatiques.</p>
{#if emailsLoading || erreurModeles || emailTemplates.length === 0}
	<EtatListe
		chargement={emailsLoading}
		erreur={erreurModeles}
		vide={emailTemplates.length === 0}
		titreErreur="Impossible d’afficher les modèles d’e-mail"
		titreVide="Aucun modèle trouvé"
	/>
{:else}
	<div class="card">
		<div class="action-row actions-modeles">
			<button
				class="btn btn-outline btn-sm"
				on:click={resetEmailTemplates}
				disabled={emailResetting}
				title="Remet tous les modèles au design par défaut"
			>
				{emailResetting ? 'Réinitialisation…' : '🔄 Réinitialiser les designs'}
			</button>
		</div>
		<table class="table">
			<thead>
				<tr
					><th>Code</th><th>Nom</th><th>Sujet</th><th>Intention</th><th>Actif</th><th>Action</th
					></tr
				>
			</thead>
			<tbody>
				{#each emailTemplates as tpl (tpl.code)}
					<tr>
						<td><code class="texte-sm">{tpl.code}</code></td>
						<td class="libelle-modele">{tpl.libelle ?? '—'}</td>
						<td class="text-muted-sm">{tpl.sujet}</td>
						<td>
							{#if tpl.intention}<span class="badge badge-blue"
									>{labelIntention(tpl.intention)}</span
								>
							{:else}<span class="muted texte-sm">—</span>{/if}
						</td>
						<td>
							<!--  Un modèle non désactivable part toujours (#2054) : sa colonne ne
							      dit ni « Oui » ni « Non », elle dit qu'il n'y a pas de case. -->
							{#if !tpl.desactivable}<span
									class="badge badge-green"
									title="Ce courriel ne se désactive pas">Toujours</span
								>
							{:else if tpl.actif}<span class="badge badge-green">Oui</span>
							{:else}<span class="badge badge-gray">Non</span>{/if}
						</td>
						<td>
							<!--  Le mode se lit sur l'icône qui a ouvert la boîte
							      (`ux-patterns` §13 bis), et le second clic la referme. -->
							<button
								class="btn-icon-edit"
								aria-label="Modifier ce modèle"
								title="Modifier"
								aria-pressed={emailEdit?.code === tpl.code}
								on:click={() =>
									emailEdit?.code === tpl.code ? (emailEdit = null) : openEmailEdit(tpl)}
								><IconeAction icone="pencil" /></button
							>
						</td>
					</tr>
					{#if emailEdit?.code === tpl.code}
						<!--  🔴 LA CORRECTION S'OUVRE SOUS LA LIGNE DU MODÈLE (10/09/2026, #889).

						      C'était une `<Modale edition>` : une fenêtre qui sortait le modèle
						      de son tableau. `ux-patterns` §14 ter — la boîte s'ouvre là où est
						      le geste, et le geste est le crayon de cette ligne.

						      ⚠️ Dans un TABLEAU, « à la place du corps » se rend par une rangée
						      qui couvre toutes les colonnes : la ligne du modèle reste lisible
						      au-dessus, comme l'en-tête d'une carte reste au-dessus de son
						      formulaire. Un `<div>` glissé entre deux `<tr>` serait sorti du
						      tableau par le navigateur — le balisage d'un tableau n'admet que
						      des rangées. -->
						<tr class="ligne-edition">
							<td colspan="6">
								<FormulaireCreation titre="Modifier le modèle {tpl.code}" encadre={false}>
									<div class="champs-modele">
										<div class="field">
											<label for="email-sujet">Sujet</label>
											<input
												id="email-sujet"
												type="text"
												bind:value={emailSujet}
												class="texte-code"
											/>
										</div>
										<div class="field">
											<label for="email-intention"
												>Intention — ce que le message attend du destinataire</label
											>
											<select id="email-intention" bind:value={emailIntention}>
												{#each INTENTIONS as i (i.valeur)}<option value={i.valeur}>{i.label}</option
													>{/each}
											</select>
											<span class="aide"
												>Affichée en bandeau au-dessus du corps, pour que le lecteur sache d'emblée
												s'il doit agir. « Aucun bandeau » n'affiche rien.</span
											>
										</div>
										<div class="field">
											<div class="entete-corps">
												<label for="email-corps-html">Corps HTML</label>
												<button
													class="btn btn-outline btn-sm"
													type="button"
													on:click={() => (emailApercu = !emailApercu)}
												>
													{emailApercu ? '✏️ Code' : '👁️ Aperçu'}
												</button>
											</div>
											{#if emailApercu}
												<div class="apercu-email">{@html safeHtml(emailCorpsHtml)}</div>
											{:else}
												<textarea
													id="email-corps-html"
													rows="10"
													bind:value={emailCorpsHtml}
													class="saisie-corps"></textarea>
											{/if}
										</div>
										<!--  🔴 « Corps texte (fallback) » a été RETIRÉ le 08/09/2026, sur
				      arbitrage. Il était stocké, affiché, modifiable — et envoyé
				      NULLE PART : aucun code ne lisait `corps_texte`, le gabarit
				      produit toujours du HTML. On y rédigeait donc un texte que
				      personne ne recevait, et celui de `nouvel_arrivant_bal`
				      contredisait son propre HTML sans conséquence visible.

				      La colonne reste en base — quatre migrations l'écrivent — mais
				      l'écran ne la montre plus et le PATCH ne l'envoie plus : la
				      laisser dans la charge utile l'aurait écrasée d'une chaîne
				      vide au premier enregistrement. -->
										{#if tpl.desactivable}
											<label class="case">
												<input type="checkbox" bind:checked={emailActif} />
												Actif
											</label>
										{:else}
											<p class="aide-modele">
												Toujours envoyé : ce courriel ne se désactive pas (sécurité d’un compte,
												message au syndic ou préavis avant effacement).
											</p>
										{/if}
										{#if tpl.variables_disponibles}
											<p class="variables-modele">
												<strong>Variables disponibles :</strong>
												{#each variablesDeModele(tpl.variables_disponibles) as v (v)}
													<code>{`{{ ${v} }}`}</code>
												{/each}
											</p>
										{/if}
									</div>
									<!--  « Par défaut » n'est PAS une soumission : c'est un geste à
									      part, qui remet le modèle au texte livré. Il ne rejoint donc
									      pas la paire Annuler / Enregistrer, que `PiedFormulaire`
									      porte seule (`lint:pied-formulaire`). -->
									<div class="remise-defaut">
										<button
											class="btn btn-outline btn-sm"
											type="button"
											on:click={resetCeModele}
											disabled={emailSaving || emailResetOne}
											title="Remettre ce modèle au texte livré avec l’application"
										>
											{emailResetOne ? 'Remise par défaut…' : '↩️ Par défaut'}
										</button>
									</div>
									<PiedFormulaire
										enCours={emailSaving}
										soumission={false}
										on:annule={() => (emailEdit = null)}
										on:enregistre={saveEmailEdit}
									/>
								</FormulaireCreation>
							</td>
						</tr>
					{/if}
				{/each}
			</tbody>
		</table>
	</div>
{/if}

<HistoriqueEnvoisEmail
	historique={emailHistory}
	chargement={emailHistoryLoading}
	erreur={erreurHistorique}
/>

<style>
	/*  La rangée qui porte le formulaire — elle appartient au tableau, et se
	    distingue de la ligne du modèle sans devenir une carte. */
	.ligne-edition > td {
		background: var(--color-primary-light);
		padding: 0.75rem;
	}
	.remise-defaut {
		display: flex;
		justify-content: flex-start;
		margin-top: 0.25rem;
	}

	/*  Même cause que la télémétrie : ces règles étaient restées dans la page à
	    l'extraction. Le style part AVEC le balisage — `lint:classes-nues`. */
	.apercu-email {
		border: 1px solid var(--color-border);
		border-radius: var(--radius);
		padding: 0.75rem;
		background: var(--color-surface);
		max-height: 340px;
		overflow: auto;
	}
	.variables-modele {
		font-size: var(--fs-sm);
		color: var(--color-text-muted);
		margin: 0.25rem 0 0;
		line-height: 1.8;
	}
	.variables-modele code {
		margin-left: 0.25rem;
	}
	.aide-modele {
		font-size: var(--fs-sm);
		color: var(--color-text-muted);
		margin: 0;
	}
	.intro-modeles {
		margin-bottom: 1rem;
	}
	.actions-modeles {
		margin-bottom: 0.75rem;
	}
	.texte-sm {
		font-size: var(--fs-sm);
	}
	.libelle-modele {
		font-size: var(--fs-base);
	}
	.champs-modele {
		display: flex;
		flex-direction: column;
		gap: 0.6rem;
	}
	.entete-corps {
		display: flex;
		align-items: center;
		justify-content: space-between;
	}
	.saisie-corps {
		font-family: monospace;
		resize: vertical;
	}
</style>
