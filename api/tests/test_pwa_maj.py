"""Garde-fou préventif : le client doit apprendre qu'une nouvelle version existe.

POURQUOI (26/07/2026) : le front est une PWA dont le service worker met l'app shell
en cache et ne cherche une mise à jour qu'au chargement de la page. Un onglet resté
ouvert sert donc indéfiniment la version qu'il a chargée. Le jour de la MEP v2.23.0
— un correctif de sécurité — le footer d'un onglet ouvert annonçait encore
`v2.22.8-050e91c` une heure après le déploiement : ce n'était pas un affichage
trompeur, c'était l'ancien code qui tournait toujours.

Trois pièces rendent ce cas visible et corrigeable, et aucune n'est visible sans
rouvrir le fichier concerné — donc chacune est testée ici plutôt que confiée à une
consigne :

1. le service worker attend au lieu de prendre la main (sinon la page se recharge
   d'elle-même, formulaire en cours compris) ;
2. le bandeau est monté dans le layout racine (sinon personne n'est averti) ;
3. un contrôle périodique interroge le serveur (sinon l'onglet ouvert ne cherche
   jamais, et 1 et 2 ne se déclenchent pas).

Le test lit `front/` depuis `api/tests/` comme le fait déjà `test_documentation.py` :
la CI n'exécute pytest qu'ici, et un contrôle sans exécution est un contrôle absent.
"""

import pathlib
import re

_RACINE = pathlib.Path(__file__).resolve().parents[2]
_VITE_CONFIG = _RACINE / "front" / "vite.config.ts"
_LAYOUT_RACINE = _RACINE / "front" / "src" / "routes" / "+layout.svelte"
_COMPOSANT = _RACINE / "front" / "src" / "lib" / "components" / "MajDisponible.svelte"


def _lire(chemin: pathlib.Path) -> str:
    assert chemin.exists(), f"{chemin.relative_to(_RACINE)} est introuvable"
    return chemin.read_text(encoding="utf-8-sig")


def test_le_service_worker_attend_au_lieu_de_recharger_seul():
    """`registerType: 'prompt'` — jamais `autoUpdate`.

    En `autoUpdate`, workbox pose `skipWaiting` + `clientsClaim` : la page se
    recharge sans prévenir dès qu'une version est trouvée, et une saisie en cours
    est perdue. Le rechargement doit rester une décision de l'utilisateur.
    """
    config = _lire(_VITE_CONFIG)
    assert re.search(r"registerType:\s*'prompt'", config), (
        "vite.config.ts : `registerType` doit valoir 'prompt' — en 'autoUpdate' le "
        "rechargement est imposé à l'utilisateur, formulaire en cours compris."
    )


def test_le_service_worker_est_enregistre_en_url_absolue():
    """`base` et `scope` explicites — sinon l'enregistrement échoue hors racine.

    Sans eux, `vite-plugin-pwa` hérite du `base` de Vite (vide sous SvelteKit) et
    génère `new Workbox('./sw.js', { scope: './' })` : depuis `/auth/connexion`, le
    navigateur demande `/auth/sw.js` et reçoit un 404. Constaté en production le
    26/07/2026 (v2.24.0) — plus aucun service worker enregistré, en silence.

    Le contrôle décisif porte sur le bundle construit (`npm run lint:sw`) ; celui-ci
    vérifie qu'il est toujours branché dans la CI et que l'intention reste écrite.
    """
    config = _lire(_VITE_CONFIG)
    assert re.search(r"base:\s*'/'", config) and re.search(r"scope:\s*'/'", config), (
        "vite.config.ts : VitePWA doit fixer `base: '/'` et `scope: '/'`, sinon "
        "l'enregistrement du service worker échoue en 404 hors de la racine."
    )
    ci = _lire(_RACINE / ".github" / "workflows" / "ci.yml")
    assert "lint:sw" in ci, (
        "ci.yml n'exécute plus `npm run lint:sw` : le seul contrôle qui inspecte "
        "l'artefact livré est débranché."
    )


def test_le_bandeau_de_mise_a_jour_est_monte_dans_le_layout_racine():
    """Monté à la racine : le bandeau doit couvrir aussi l'écran de connexion.

    Placé dans `(app)/+layout.svelte`, il ne s'afficherait que pour les pages
    authentifiées — or une version périmée l'est pour tout le monde.
    """
    layout = _lire(_LAYOUT_RACINE)
    assert "MajDisponible" in layout, (
        "front/src/routes/+layout.svelte ne monte pas <MajDisponible /> : plus rien "
        "n'avertit l'utilisateur qu'une nouvelle version est déployée."
    )
    _lire(_COMPOSANT)  # le composant lui-même doit exister


def test_une_verification_periodique_cherche_les_nouvelles_versions():
    """Sans contrôle actif, un onglet ouvert ne découvre jamais la mise à jour.

    C'est exactement le cas constaté : l'onglet ne redemandait rien au serveur, donc
    ni le service worker ni le bandeau n'avaient de raison de se déclencher.
    """
    composant = _lire(_COMPOSANT)
    assert "setInterval" in composant and "registration.update()" in composant, (
        "MajDisponible.svelte ne contrôle plus périodiquement l'arrivée d'une "
        "nouvelle version (setInterval + registration.update())."
    )
    assert "visibilitychange" in composant, (
        "MajDisponible.svelte ne contrôle plus au retour sur l'onglet — c'est le cas "
        "principal : un onglet laissé ouvert en arrière-plan toute la nuit."
    )
    assert "onNeedRefresh" in composant, (
        "MajDisponible.svelte n'écoute plus `onNeedRefresh` : la mise à jour ne "
        "serait jamais appliquée."
    )


def test_la_mise_a_jour_s_applique_sans_action_de_l_utilisateur():
    """Elle doit se poser d'elle-même aux moments où un rechargement ne coûte rien.

    Demander un clic, c'est demander à l'utilisateur de comprendre un mécanisme qui
    ne le concerne pas — et laisser tourner l'ancienne version tant qu'il ne clique
    pas, correctif de sécurité compris. Deux moments sûrs, tous deux nécessaires :
    l'onglet passé en arrière-plan (personne ne regarde) et le changement d'écran
    (le contenu précédent est de toute façon quitté). Le bandeau ne reste que pour le
    cas rare d'un écran laissé ouvert au premier plan, où recharger d'autorité
    effacerait une saisie en cours.
    """
    composant = _lire(_COMPOSANT)
    assert "afterNavigate" in composant, (
        "MajDisponible.svelte n'applique plus la mise à jour au changement d'écran : "
        "l'utilisateur devrait de nouveau cliquer pour l'obtenir."
    )
    assert "visibilityState === 'hidden'" in composant, (
        "MajDisponible.svelte n'applique plus la mise à jour quand l'onglet passe en "
        "arrière-plan — le moment le plus discret possible."
    )
    assert "sessionStorage" in composant and "MAX_AUTO" in composant, (
        "le garde-fou anti-boucle a disparu : une version qui ne parvient pas à "
        "prendre la main rechargerait la page sans fin, sous les yeux de "
        "l'utilisateur et sans échappatoire."
    )


def test_un_import_qui_echoue_sur_une_version_retiree_se_rattrape():
    """Un morceau de code retiré par un déploiement ne laisse plus l'écran amputé (04/10/2026).

    Le 03/10, « Importing a module script failed. » a été relevé trois fois par
    la télémétrie après deux déploiements : un onglet ouvert avant chargeait à
    la demande un morceau du build précédent, disparu. SvelteKit rattrape ce cas
    pendant une navigation, pas pour un import lancé par un composant
    (DOMPurify, l'éditeur riche). Vite signale chacun (`vite:preloadError`) ;
    le composant demande à SvelteKit si le site a changé, et n'applique alors
    qu'aux moments sans risque — jamais de rechargement d'autorité devant
    l'utilisateur.

    ⚠️ Contrôle de FORME : en `vite dev` (les e2e), `updated.check()` répond
    toujours faux, et ce comportement ne s'y éprouve pas.
    """
    composant = _lire(_COMPOSANT)
    assert "'vite:preloadError'" in composant, (
        "MajDisponible.svelte n'écoute plus `vite:preloadError` : un import échoué "
        "après un déploiement laisse de nouveau l'écran amputé, sans recours."
    )
    assert "updated" in composant and ".check()" in composant, (
        "l'échec d'import n'est plus confronté à `version.json` : une panne réseau "
        "passagère déclencherait un rechargement inutile."
    )
    assert "beforeNavigate" in composant and "to.url.href" in composant, (
        "une version retirée ne charge plus la page suivante en entier : elle "
        "resterait sur l'ancien code."
    )


def test_le_service_worker_s_enregistre_apres_l_ouverture():
    """Il précachait tout le build (≈ 776 Ko, 333 fichiers) dès l'hydratation (#1839).

    À la première visite et après chaque MEP — les seules fois où l'on télécharge
    vraiment —, ces requêtes disputaient le lien aux données de l'écran et aux
    morceaux chargés au geste. L'enregistrement attend donc la fin du chargement de
    la page, un délai, puis un moment d'inactivité. Le hors-ligne est inchangé : le
    précache est le même, il part plus tard.
    """
    composant = _lire(_COMPOSANT)
    assert "function apresOuverture(" in composant, (
        "MajDisponible.svelte ne diffère plus l'enregistrement du service worker."
    )
    corps = composant[composant.index("function apresOuverture(") :]
    corps = corps[: corps.index("\n\t}\n")]
    for attendu in ("'load'", "requestIdleCallback", "DELAI_ENREGISTREMENT_MS"):
        assert attendu in corps, f"apresOuverture n'attend plus {attendu}"
    assert composant.index("apresOuverture(() =>") < composant.index(
        "import('virtual:pwa-register')"
    ), "l'import du module d'enregistrement n'est plus dans apresOuverture"


_FRONT = _RACINE / "front"
_GARDE = _FRONT / "src" / "garde-demarrage.js"


def test_une_page_qui_ne_se_dessine_pas_est_gardee():
    """Le garde de démarrage est branché, de bout en bout (#1993, 17/10/2026).

    Une page restée blanche au premier chargement après une MEP ne disait rien :
    le bandeau de mise à jour vit DANS l'application, qui ne démarrait pas. Le
    garde est un script inline, premier de `<head>` — quatre pièces, dont aucune
    ne se voit sans rouvrir son fichier, et dont chacune, absente, le désarme en
    silence :

    1. le repère de `app.html`, AVANT `%sveltekit.head%` (donc avant les feuilles) ;
    2. son remplacement par `hooks.server.ts`, avec le contenu du fichier ;
    3. le condensat de ce même fichier dans la CSP (`vite.config.ts`) — sans
       lui, le navigateur refuse le script ;
    4. le marqueur « démarrée », posé par le layout racine et lu par le garde
       sous le même nom — sans lui, toute page saine dirait « pas fini de se
       charger ».

    Le comportement, lui, est éprouvé dans un navigateur : `e2e/garde-demarrage.spec.ts`.
    """
    garde = _lire(_GARDE)
    app_html = _lire(_FRONT / "src" / "app.html")
    assert "<!-- garde-demarrage" in app_html, "app.html : le repère du garde a disparu"
    assert app_html.index("<!-- garde-demarrage") < app_html.index("%sveltekit.head%"), (
        "app.html : le garde doit précéder %sveltekit.head%, qui porte les feuilles de style "
        "— placé après, il attendrait la feuille même qu'il doit surveiller."
    )

    hooks = _lire(_FRONT / "src" / "hooks.server.ts")
    assert "garde-demarrage.js?raw" in hooks and "transformPageChunk" in hooks, (
        "hooks.server.ts n'injecte plus le garde de démarrage dans la page."
    )

    config = _lire(_FRONT / "vite.config.ts")
    assert "src/garde-demarrage.js" in config and "GARDE_DEMARRAGE" in config, (
        "vite.config.ts ne calcule plus le condensat du garde : la CSP le bloquerait."
    )
    assert re.search(r"'script-src':\s*\[[^\]]*GARDE_DEMARRAGE", config), (
        "le condensat du garde n'est plus dans `script-src`."
    )

    module = _lire(_FRONT / "src" / "lib" / "garde-demarrage.ts")
    nom = re.search(r"ATTRIBUT_DEMARRAGE = '([^']+)'", module).group(1)
    valeur = re.search(r"VALEUR_DEMARREE = '([^']+)'", module).group(1)
    assert f"getAttribute('{nom}') === '{valeur}'" in garde, (
        f'le garde ne lit plus `{nom}="{valeur}"` : le nom posé par l\'application et '
        "celui qu'il lit ont divergé — il prendrait toute page pour une page qui ne démarre pas."
    )
    assert "signalerDemarrage" in _lire(_LAYOUT_RACINE), (
        "le layout racine ne signale plus le démarrage de l'application au garde."
    )

    #  5. la variable témoin de la feuille principale (24/10/2026) : le garde la
    #  lit dans le style calculé, `socle.css` la pose. Renommée d'un seul côté,
    #  toute page saine passerait pour une page sans mise en forme.
    temoin = re.search(r"TEMOIN_FEUILLE = '([^']+)'", garde).group(1)
    assert f"{temoin}:" in _lire(_FRONT / "src" / "styles" / "socle.css"), (
        f"`socle.css` ne pose plus `{temoin}`, que le garde lit pour juger la mise en forme."
    )


def test_un_rechargement_de_secours_se_mesure():
    """La cause de #1993 n'est pas trouvée : chaque secours se COMPTE (arbitré le 17/10/2026).

    Le garde note son motif dans l'onglet avant de recharger ; l'application, une
    fois démarrée, le signale au journal des erreurs du navigateur. La clé et
    les motifs sont écrits deux fois — le garde est inline et n'importe rien — :
    une divergence ferait taire la mesure sans un mot. Le signalement lui-même
    est éprouvé par `e2e/garde-demarrage.spec.ts`.
    """
    garde = _lire(_GARDE)
    module = _lire(_FRONT / "src" / "lib" / "garde-demarrage.ts")
    cle = re.search(r"CLE_MOTIF = '([^']+)'", module).group(1)
    assert f"CLE_MOTIF = '{cle}'" in garde, f"le garde n'écrit plus le motif sous `{cle}`"
    motifs = re.findall(r"'([a-z-]+)'", re.search(r"MOTIFS = \[([^\]]+)\]", module).group(1))
    assert sorted(motifs) == ["non-demarree", "non-dessinee", "non-stylee"], motifs
    for motif in motifs:
        assert f"'{motif}'" in garde, f"le garde n'écrit plus le motif `{motif}`"
    assert "signalerErreur" in module and "envoyerMaintenant" in module, (
        "le démarrage ne signale plus le rechargement de secours au journal des erreurs."
    )
