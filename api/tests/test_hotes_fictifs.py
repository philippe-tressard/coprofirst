"""Un hôte fictif se prend dans un nom RÉSERVÉ, jamais dans un domaine qui existe (#2767).

## Le constat (15/11/2026)

Un test d'interface de l'app Android envoyait, après la connexion, ses requêtes et ses
cookies vers `residence.exemple.fr` au lieu du serveur local (coprofirst-android#57).
`exemple.fr` est un VRAI domaine tiers : il répond en DNS. Le même nom figurait dans
46 fichiers de ce dépôt — tests, fixtures, documentation et placeholders d'écran, où un
utilisateur qui copie l'exemple envoie ses identifiants chez un inconnu.

Règle du socle : `standards/03` §8 quater.

## Ce que ce contrôle tient

Une liste BLANCHE. Tout hôte repéré dans un fichier suivi est :
- un nom réservé, qui ne mène nulle part : `example.com`, `example.org`, `example.net`
  (RFC 2606) et leurs sous-domaines, les suffixes `.test`, `.example`, `.invalid`,
  `.localhost` (RFC 6761) ;
- ou un VRAI domaine, déclaré dans `REELS` avec sa raison : un domaine du projet, un
  service que le code appelle, un fournisseur que le code nomme, une référence citée.

Un hôte inventé n'entre jamais dans `REELS` : il se renomme en `.test` (forme majoritaire
du dépôt, `exemple.test`). Une entrée de `REELS` qui ne sert plus fait échouer le contrôle.

Formes repérées (`hotes_dans`) :
- l'hôte d'une URL (`https://hote/…`, `ws://`, `smtp://`…) ;
- le domaine d'une adresse (`quelquun@hote`) ;
- un nom nu en `.fr`, `.com`, `.org`, `.net` ou `.eu` (`--hote residence.fr`, « le site
  exemple.fr ») — pas les autres suffixes nus, que le code emploie comme attributs
  (`self.app`, `logger.info`) ou comme noms de fichiers (`bascule.sh`).

⚠️ Ce qu'il ne voit pas : un hôte nu dans un autre suffixe (`residence.io`), un hôte
assemblé à l'exécution, et ce qui est public sans être un fichier (commits, tickets).
"""

from __future__ import annotations

import pathlib
import re
import subprocess
from collections import defaultdict

RACINE = pathlib.Path(__file__).resolve().parents[2]
CE_FICHIER = "api/tests/test_hotes_fictifs.py"

#: Les fichiers suivis qui ne sont pas lus : produits par un outil, ou textes légaux.
NON_LUS = re.compile(
    r"(^|/)package-lock\.json$|^LICENSES/|\.(png|jpe?g|gif|webp|ico|pdf|woff2?|ttf|otf|heic|zip|gz)$"
)

#: RFC 2606 et RFC 6761 : les seuls noms qui ne mènent nulle part.
RESERVES_EXACTS = ("example.com", "example.org", "example.net")
RESERVES_SUFFIXES = (".test", ".example", ".invalid", ".localhost")

#: Les vrais domaines, par raison. Un hôte est admis s'il y figure EXACTEMENT : un
#: sous-domaine inventé sous un vrai domaine (`pirate.onmicrosoft.com`) est un vrai nom
#: possible, il se déclare donc un à un, dans `FORMES_D_UN_SERVICE`.
_PAR_RAISON: dict[str, tuple[str, ...]] = {
    "le projet": (
        "5hostachy.fr",
        "coprofirst.fr",
        "demo.coprofirst.fr",
        "registre.coprofirst.fr",
        "push.coprofirst.fr",
    ),
    "un service que le code ou l'exploitation appelle": (
        "github.com",
        "api.github.com",
        "users.noreply.github.com",
        "fcm.googleapis.com",  # FCM HTTP v1 (#2789)
        "www.googleapis.com",  # la portée OAuth de FCM (#2789)
        "ghcr.io",
        "api.anthropic.com",
        "api.openai.com",
        "g.us",
        "s.whatsapp.net",
        "chat.whatsapp.com",
        "apps.apple.com",
        "api.push.apple.com",
        "api.sandbox.push.apple.com",
        "archive.raspberrypi.com",
        "archive.ubuntu.com",
        "azure.archive.ubuntu.com",
        "security.ubuntu.com",
        "cloudapp.azure.com",
        "cloud-mirror-lb.swedencentral.cloudapp.azure.com",
        "deb.debian.org",
        "docker.com",
        "get.docker.com",
        "pkg.cloudflare.com",
        "region1.v2.argotunnel.com",
        "argotunnel.com",
        "www.cloudflare.com",
        "playwright.azureedge.net",
        "playwright.download.prss.microsoft.com",
        "golang.org",
    ),
    "une messagerie que le code reconnaît (authenticité, alertes, hygiène)": (
        "mail.ovh.net",
        "mx.ovh.net",
        "ssl0.ovh.net",
        "orange.fr",
        "icloud.com",
        "smtp.mailgun.org",
    ),
    "un traceur que le contrôle de conformité refuse": (
        "static.cloudflareinsights.com",
        "googletagmanager.com",
        "google-analytics.com",
        "fonts.googleapis.com",
    ),
    "une référence citée (documentation, licence, outil)": (
        "www.w3.org",
        "lucide.dev",
        "simpleicons.org",
        "toolbox.marketingtools.apple.com",
        "www.cnil.fr",
        "www.legifrance.gouv.fr",
        "claude.ai",
        "docs.claude.com",
        "anthropic.com",
        "platform.openai.com",
        "fastapi.tiangolo.com",
        "sqlmodel.tiangolo.com",
        "kit.svelte.dev",
        "caddyserver.com",
        "docs.docker.com",
        "developers.cloudflare.com",
        "playwright.dev",
        "img.shields.io",
        "api.reuse.software",
        "editorconfig.org",
        "fsf.org",
        "www.gnu.org",
        "www.tpgi.com",
    ),
}

#: Un nom inventé SOUS un vrai domaine, quand la FORME de ce domaine est l'objet du code :
#: jamais contacté, il se déclare un à un, avec sa raison.
FORMES_D_UN_SERVICE: dict[str, str] = {
    "cabinetgestion.onmicrosoft.com": "délégation DKIM d'un abonnement Microsoft 365 (#2554)",
    "pirate.onmicrosoft.com": "délégation DKIM : un autre abonnement est refusé (#2554)",
    "cabinet.onmicrosoft.com": "placeholder : la forme du signataire délégué (#2554)",
    "mon-instance.openai.azure.com": "placeholder : la forme d'une adresse Azure OpenAI",
    "x.openai.azure.com": "test : la forme d'une adresse Azure OpenAI",
}


def _signataires_partages() -> frozenset[str]:
    """Les messageries partagées, lues dans leur module : la liste n'est pas recopiée."""
    from app.utils.courriel_delegation import SIGNATAIRES_PARTAGES

    return SIGNATAIRES_PARTAGES


REELS: dict[str, str] = {h: raison for raison, hotes in _PAR_RAISON.items() for h in hotes}
REELS |= FORMES_D_UN_SERVICE


def est_reserve(hote: str) -> bool:
    return (
        hote in RESERVES_EXACTS
        or hote.endswith(tuple("." + r for r in RESERVES_EXACTS))
        or hote.endswith(RESERVES_SUFFIXES)
    )


_ETIQUETTE = r"[a-z0-9](?:[a-z0-9-]*[a-z0-9])?"
_HOTE = rf"(?:{_ETIQUETTE}\.)+[a-z][a-z0-9-]*[a-z]"
_URL = re.compile(rf"\b[a-z][a-z0-9+.-]*://(?:[^/\s@'\"`<>]*@)?({_HOTE})", re.I)
_ADRESSE = re.compile(rf"[\w.+%-]@({_HOTE})(?![\w-])", re.I)
_NU = re.compile(
    rf"(?<![\w./-])({_HOTE}\.(?:fr|com|org|net|eu)|{_ETIQUETTE}\.(?:fr|com|org|net|eu))(?![\w-]|\.\w)",
    re.I,
)


_PREFIXES = re.compile(r"\*\.|(?<!\w)_[\w-]*\.")


def hotes_dans(texte: str) -> set[str]:
    """Les hôtes d'un texte, en minuscules, sans le point final d'une phrase.

    Un joker (`*.zone`) et une étiquette de service (`s1._domainkey.zone`, `_dmarc.zone`)
    s'effacent d'abord : la zone qu'ils préfixent est un hôte, qui échappait au relevé.
    """
    texte = _PREFIXES.sub(lambda m: " " * len(m.group()), texte)
    trouves: set[str] = set()
    for motif in (_URL, _ADRESSE, _NU):
        trouves |= {m.group(1).lower().rstrip(".") for m in motif.finditer(texte)}
    return {h for h in trouves if "." in h}


def _suivis() -> list[str]:
    sortie = subprocess.run(
        ["git", "ls-files", "-z"], cwd=RACINE, capture_output=True, text=True, check=True
    ).stdout
    return [f for f in sortie.split("\0") if f and not NON_LUS.search(f)]


def _releve() -> dict[str, set[str]]:
    """{hôte: fichiers} — ce contrôle-ci exclu : il nomme les formes qu'il refuse."""
    par_hote: dict[str, set[str]] = defaultdict(set)
    fichiers = _suivis()
    assert len(fichiers) > 1000, (
        f"{len(fichiers)} fichiers suivis lus — cas zéro, la lecture a échoué"
    )
    for rel in fichiers:
        if rel == CE_FICHIER:
            continue
        try:
            texte = (RACINE / rel).read_text(encoding="utf-8")
        except (UnicodeDecodeError, FileNotFoundError, IsADirectoryError):
            continue
        for hote in hotes_dans(texte):
            par_hote[hote].add(rel)
    return par_hote


def test_chaque_forme_est_reperee():
    """Autotest : le contrôle voit chaque forme, et ignore ce qui n'est pas un hôte."""
    assert hotes_dans("base = 'https://residence.exemple.fr/api'") == {"residence.exemple.fr"}
    assert hotes_dans('email="gestion@syndic.fr"') == {"syndic.fr"}
    assert hotes_dans("--hote residence.fr [--x]") == {"residence.fr"}
    assert hotes_dans("sur le site exemple.fr de la copropriété.") == {"exemple.fr"}
    assert hotes_dans("smtp://u:p@smtp.exemple.fr:587") == {"smtp.exemple.fr"}
    assert hotes_dans("Voir exemple.fr.") == {"exemple.fr"}
    assert hotes_dans('route dns tunnel "*.exemple.fr"') == {"exemple.fr"}
    assert hotes_dans('b"._domainkey.syndic.fr.": cle') == {"syndic.fr"}
    # Ce qui n'est pas un hôte : attributs, fichiers, décorateurs, paquets npm.
    assert hotes_dans("self.app.get(x); logger.info('y'); bash bascule.sh") == set()
    assert hotes_dans("@router.get('/x')\nimport '@sveltejs/kit'") == set()
    assert hotes_dans("fichier.json, module.ts, a.b.c") == set()
    # Les noms réservés sont admis, un vrai domaine inventé ne l'est pas.
    assert est_reserve("residence.exemple.test") and est_reserve("www.example.com")
    assert est_reserve("syndic.invalid") and est_reserve("acces.example")
    assert not est_reserve("exemple.fr") and not est_reserve("example.com.fr")
    assert not est_reserve("faux-example.com")


def test_aucun_hote_fictif_hors_des_noms_reserves():
    releve = _releve()
    fautifs = {
        h: sorted(f)[:3]
        for h, f in releve.items()
        if not est_reserve(h) and h not in REELS and h not in _signataires_partages()
    }
    assert not fautifs, (
        "hôte(s) hors liste blanche — un hôte inventé se prend dans un nom réservé "
        "(`exemple.test`, `example.com`, `.invalid`…, standards/03 §8 quater) ; un VRAI "
        "domaine se déclare dans `REELS` avec sa raison :\n"
        + "\n".join(f"  {h}  ← {', '.join(f)}" for h, f in sorted(fautifs.items()))
    )


def test_chaque_domaine_reel_sert_encore():
    releve = _releve()
    morts = sorted(h for h in REELS if h not in releve)
    assert not morts, f"entrée(s) de REELS qui ne servent plus, à retirer : {morts}"
