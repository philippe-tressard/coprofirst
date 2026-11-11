"""Un lien d'e-mail qui MÈNE quelque part peut rester MORT pour son destinataire.

`test_liens_front.py` relie les deux moitiés d'un lien : l'API l'émet, le front
doit avoir la page. Ce fichier-ci pose la question d'après, et c'est une autre
question — d'où un fichier à part plutôt que soixante lignes de plus là-bas :

> la page existe, mais celui qui REÇOIT le message peut-il l'ouvrir ?

Un modèle d'e-mail ne connaît pas ses destinataires : ils sont choisis au point
d'appel, et le même modèle sert souvent plusieurs audiences.
"""

import pathlib
import re
from collections.abc import Iterable

import pytest

from tests.aides_liens_email import (
    BASE,
    LienModele,
    extraire_liens,
    liens_des_modeles_email,
)
from tests.aides_routes_front import _page_du_lien
from tests.aides_sources import modules_app

_API_DIR = pathlib.Path(__file__).resolve().parents[1]
_RACINE = _API_DIR.parent
_ROUTES = _RACINE / "front" / "src" / "routes"


# ── Un lien qui MÈNE quelque part peut rester MORT pour son destinataire ──────
#
# POURQUOI (01/09/2026, #480) : le modèle d'e-mail `annonce_hall` finissait par un
# bouton « Voir l'historique des annonces » vers `/espace-cs?onglet=annonces-hall`.
# La page existe — les tests ci-dessus étaient donc verts — mais le front y pose une
# garde : `if (!$isCS) goto('/tableau-de-bord')`. Tant que ce courriel n'allait qu'au
# conseil syndical, personne ne pouvait le voir. En ouvrant le canal « syndic », le
# même bouton s'est mis à renvoyer la moitié de ses destinataires au tableau de bord.
#
# La leçon est celle des liens front⇄API, d'un cran plus loin : vérifier que la page
# existe ne suffit pas, il faut que le DESTINATAIRE puisse l'ouvrir. Et c'est
# précisément ce qu'un e-mail ne peut pas savoir : il part à une liste, la garde
# s'applique à chacun.

#: Routes que le front REFUSE à qui n'a pas le rôle, en redirigeant ailleurs.
#: Détectées, pas recopiées — une liste tenue à la main se périmerait à la
#: première garde ajoutée, et c'est le lien nouvellement mort qu'on cherche.
#:
#: ⚠️ Le motif a dû apprendre une SECONDE forme le 20/09/2026 : une garde attend
#: désormais que l'authentification soit résolue avant de refuser —
#: `$: if ($authResolue && !$isCS) goto(…)` — et l'ancien motif, qui exigeait que
#: la négation suive immédiatement la parenthèse, ne trouvait plus rien. Son cas
#: zéro a correctement rendu INCONNU plutôt que vert : c'est ce qui a permis de
#: le voir (#1083).
_MOTIF_GARDE = re.compile(r"if\s*\([^)]*!\$(?:is|est)[A-Z][A-Za-z]*\)\s*\{?\s*(?:\r?\n\s*)?goto\(")


def _pages_gardees() -> set[pathlib.Path]:
    """Les `+page.svelte` qui redirigent qui n'a pas le rôle.

    Des PAGES et non des adresses depuis #1496 : un onglet a son URL
    (`/espace-cs/annonces-hall`) sans avoir de dossier, et la comparer à
    `/espace-cs` la laissait passer. Le lien est résolu vers la page qui le rend
    (`aides_routes_front._page_du_lien`, `reroute` compris), puis confronté ici.

    Une garde posée par un `+layout.svelte` vaut pour toutes les pages de son
    dossier : c'est ainsi que `/admin` est réservé, et le balayage des seules
    pages ne le voyait pas (#1505, 01/10/2026).
    """

    def garde(fichier: pathlib.Path) -> bool:
        return bool(_MOTIF_GARDE.search(fichier.read_text(encoding="utf-8-sig")))

    layouts = [layout.parent for layout in _ROUTES.rglob("+layout.svelte") if garde(layout)]
    return {
        page
        for page in _ROUTES.rglob("+page.svelte")
        if garde(page) or any(page.parent.is_relative_to(dossier) for dossier in layouts)
    }


def _vers_une_page_reservee(
    liens: Iterable[LienModele], gardees: set[pathlib.Path]
) -> dict[LienModele, pathlib.Path]:
    """{lien: page gardée} — les liens que le front refuse à qui n'a pas le rôle."""
    fautifs = {}
    for lien in liens:
        if lien.chemin is None:
            continue  # mailto:, racine, chemin fourni par une variable (EMPLACEMENTS)
        page = _page_du_lien(lien.chemin)
        if page in gardees:
            fautifs[lien] = page
    return fautifs


#: Modèles qui visent `/admin` ET n'ont qu'un destinataire : le gestionnaire du
#: site, administrateur par construction (`destinataires.site_manager_user_id`),
#: ou à défaut l'« E-mail administrateur ». Arbitré le 01/10/2026 (#1505) : le
#: bouton mène au geste à faire, et seul un administrateur peut le faire.
#: Chaque entrée est tenue dans les deux sens : elle doit encore viser une page
#: réservée, et ne partir que par `get_site_manager_notification_email`.
_RESERVES_AU_GESTIONNAIRE = {
    "alerte_systeme": "alerte du contrôle de santé — à traiter dans Admin",
    "compte_en_attente": "un compte à valider — Admin › Utilisateurs",
    "etage_divergent": "un étage qui contredit le lot — Admin › Audit des lots",
    "acces_apparies_auto": "des badges créés à relire — Admin › Import",
}


@pytest.mark.skipif(not _ROUTES.is_dir(), reason="front/ absent de ce checkout")
def test_aucun_modele_email_ne_vise_une_route_reservee():
    """Un bouton d'e-mail doit s'ouvrir pour TOUS ceux qui reçoivent le message.

    Un modèle d'e-mail ne connaît pas ses destinataires — ils sont choisis au point
    d'appel, et le même modèle sert souvent plusieurs audiences (le CS et le syndic
    pour l'annonce de hall). Viser une page réservée à l'une d'elles est donc un
    défaut par construction, pas un cas particulier à arbitrer.

    Le remède appliqué à `annonce_hall` : pointer l'OBJET (l'actualité d'origine),
    et n'afficher le bouton que lorsqu'il y en a un. Un lien vers un objet vaut pour
    tout le monde ; un lien vers un écran d'administration ne vaut que pour ses
    administrateurs.
    """
    gardees = _pages_gardees()
    assert gardees, (
        "aucune garde de rôle détectée dans front/src/routes — le motif a dû "
        "changer de forme, et ce test ne mesure plus rien (INCONNU, pas OK)"
    )
    fautifs = [
        f"modèle « {lien.modele} » → {lien.adresse}  (gardée : {page.relative_to(_ROUTES)})"
        for lien, page in _vers_une_page_reservee(liens_des_modeles_email(), gardees).items()
        if lien.modele not in _RESERVES_AU_GESTIONNAIRE
    ]
    assert not fautifs, (
        "modèle(s) d'e-mail visant une page que le front réserve à un rôle — "
        "leurs destinataires sans ce rôle seront redirigés :\n  " + "\n  ".join(fautifs)
    )


# ── Il lisait les sources, et ne voyait plus aucun bouton (#1496) ─────────────
#
# POURQUOI (30/09/2026) : ce contrôle cherchait `href="{{ app.url }}/…"` dans
# `app/seed/emails/*.py`. Depuis la factorisation #959, un bouton s'écrit
# `bouton("{{ app.url }}/calendrier", …)` : plus aucun `href=` dans la source.
# Il ne relevait que quatre liens, tous vers `/admin` — ni `/calendrier`, ni un
# seul lien de `tickets.py` ou de `vie_collective.py`. Vert, et aveugle.
#
# Il lit désormais les modèles COMPOSÉS (`aides_liens_email`), et les deux tests
# ci-dessous tiennent ce qu'il doit voir et ce qu'il doit refuser.

#: Des liens posés par `fragments.bouton()` — un par fichier de modèles que le
#: contrôle ne voyait pas. S'ils disparaissent de l'extraction, c'est qu'elle ne
#: lit plus les boutons, pas qu'ils ont cessé d'exister.
_TEMOINS_BOUTONS = {
    ("calendrier_evenement_cree", "/calendrier"),
    ("ticket_nouveau_cs", "/tickets/{{ ticket.id }}"),
}


def test_le_controle_lit_les_liens_des_boutons():
    """Cas zéro (`standards/04` §2) : l'extraction rend des liens, boutons compris."""
    lus = {(lien.modele, lien.chemin) for lien in liens_des_modeles_email() if lien.chemin}
    assert lus, "aucun chemin lu dans les modèles d'e-mail — ce contrôle ne mesure rien"
    manquants = sorted(_TEMOINS_BOUTONS - lus)
    assert not manquants, (
        f"lien(s) de bouton non relevés : {manquants} — l'extraction ne voit plus "
        "les ancres composées par `fragments.bouton()`"
    )


@pytest.mark.skipif(not _ROUTES.is_dir(), reason="front/ absent de ce checkout")
def test_les_exceptions_servent_encore():
    """Une exception qui ne vise plus de page réservée est un oubli : on la retire."""
    reserves = {
        lien.modele for lien in _vers_une_page_reservee(liens_des_modeles_email(), _pages_gardees())
    }
    mortes = sorted(set(_RESERVES_AU_GESTIONNAIRE) - reserves)
    assert not mortes, f"exception(s) qui ne servent plus — à retirer : {mortes}"


def test_les_exceptions_ne_partent_qu_au_gestionnaire():
    """La raison déclarée doit rester VRAIE : l'envoi lit le gestionnaire du site.

    Un module qui envoie l'un de ces modèles sans passer par
    `get_site_manager_notification_email` l'adresserait à quelqu'un d'autre —
    un résident, le CS — que le bouton renverrait au tableau de bord.
    """
    fautifs = []
    for modele in _RESERVES_AU_GESTIONNAIRE:
        envoyeurs = [m for m in modules_app() if f'code="{modele}"' in m.source]
        if not envoyeurs:
            fautifs.append(f"{modele} : aucun envoi trouvé (cas zéro)")
        fautifs += [
            f"{modele} : {m.rel} ne passe pas par get_site_manager_notification_email"
            for m in envoyeurs
            if "get_site_manager_notification_email(" not in m.source
        ]
    assert not fautifs, "\n  ".join(["envoi(s) hors du gestionnaire du site :", *fautifs])


@pytest.mark.skipif(not _ROUTES.is_dir(), reason="front/ absent de ce checkout")
def test_une_garde_de_layout_couvre_ses_pages():
    """`/admin` n'a aucune garde dans sa page : elle vit dans `admin/+layout.svelte`."""
    assert _page_du_lien("/admin") in _pages_gardees(), (
        "/admin n'est pas vue comme réservée — les gardes posées par un "
        "`+layout.svelte` ne sont plus lues (#1505)"
    )


@pytest.mark.skipif(not _ROUTES.is_dir(), reason="front/ absent de ce checkout")
def test_le_controle_refuse_un_bouton_vers_une_page_reservee():
    """Un modèle FORGÉ, composé par le vrai `bouton()`, qui rejoue #480."""
    from app.seed.emails.fragments import bouton

    forges = [
        ("forge_onglet", "", bouton(f"{BASE}/espace-cs/annonces-hall", "Voir")),
        ("forge_parametre", "", bouton(f"{BASE}/espace-cs?onglet=annonces-hall", "Voir")),
        ("forge_ouvert", "", bouton(f"{BASE}/calendrier", "Voir")),
    ]
    fautifs = _vers_une_page_reservee(extraire_liens(forges), _pages_gardees())
    refuses = {lien.modele for lien in fautifs}
    assert refuses == {"forge_onglet", "forge_parametre"}, (
        f"attendu : les deux boutons vers /espace-cs refusés, /calendrier admis — obtenu {fautifs}"
    )
