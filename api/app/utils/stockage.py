"""Les fichiers d'une copropriété — une seule porte, derrière une interface (#1748).

Chantier multi-copropriétés, lot P2-6 (spec §4.4) : *un chemin de fichier ne se
construit jamais à partir d'une donnée de la requête*, et les fichiers de chaque
copropriété vivent sous SON préfixe.

## Ce que ce module remplace

L'adresse publique d'un fichier (`/uploads/<clé>`) se traduisait en chemin à
trois endroits, chacun à sa façon : `"/app" + url` (`fichiers.chemins_locaux`),
`Path("/app") / url` (`pdf_theme`, sans aucune borne), et une racine résolue au
CHARGEMENT de quatre modules — donc figée sur une copropriété pour la vie du
processus. Ici, la racine se demande au contexte à chaque appel, et toute clé est
bornée sous elle.

## L'interface et son implémentation

`Stockage` dit ce qu'un stockage sait faire ; `StockageDisque` est la seule
implémentation de la phase 2 (le volume `uploads`, répliqué et sauvegardé). Un
stockage objet viendra en phase 3, avec l'hébergeur. `chemin()` est propre au
disque : les appelants qui en dépendent encore (pièce jointe d'un courriel,
`FileResponse`, rendu PDF) passeront par `lire()` ce jour-là.

## Le service

Caddy sert `/uploads/*` depuis le volume après avoir demandé à l'API si CE
fichier se lit (`forward_auth`) : le droit de lire l'objet qui le cite, depuis
#2154 (arbitrage du 23/10/2026, `utils/visibility/fichiers`) — la session seule
suffisait jusque-là. Le choix entre service par l'API et URL signées se fera en
phase 3, avec l'hébergeur dont il dépend.

🔒 `tests/test_stockage_source_unique.py` refuse une racine de fichiers lue hors
d'ici, et `test_televersement_source_unique.py` une écriture sur disque.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import BinaryIO, Protocol

from app import contexte

#: Le préfixe de l'adresse publique d'un fichier.
PREFIXE_URL = "/uploads/"

#: Les fichiers qui ne se servent JAMAIS en direct : bibliothèque documentaire,
#: rapports de diagnostic, relevés de compteurs. Le `Caddyfile` refuse
#: `/uploads/prive/*` ; `test_uploads_prives.py` le vérifie.
DOSSIER_PRIVE = "prive"

#: Les PDF d'affiche de hall : servis par `/annonces-hall/{id}/pdf`, réservé au CS et à
#: l'admin — jamais en direct (le `Caddyfile` refuse `/uploads/annonces-hall/*`).
DOSSIER_AFFICHES = "annonces-hall"

#: Les dossiers qu'AUCUN service direct ne sert — Caddy (`Caddyfile`) comme l'API
#: d'une installation commune (`installation_commune/fichiers`, #2053).
JAMAIS_SERVIS = frozenset({DOSSIER_PRIVE, DOSSIER_AFFICHES})


class CleInvalide(ValueError):
    """Une clé qui sortirait du préfixe de la copropriété, ou qui n'en est pas une."""


class Stockage(Protocol):
    def ecrire(self, cle: str, octets: bytes) -> None: ...
    def ecrire_flux(self, cle: str, flux: BinaryIO) -> None: ...
    def lire(self, cle: str) -> bytes: ...
    def supprimer(self, cle: str) -> None: ...
    def existe(self, cle: str) -> bool: ...
    def url(self, cle: str) -> str: ...


def cle_valide(cle: str) -> str:
    """La clé, normalisée en « a/b.ext », ou `CleInvalide`.

    Lexicale, sans toucher au disque : ni vide, ni absolue, ni `..`, ni `\\`. Une
    clé est un chemin RELATIF au préfixe de la copropriété, jamais autre chose.
    """
    if not isinstance(cle, str) or not cle or "\\" in cle or "\x00" in cle:
        raise CleInvalide(f"clé de fichier invalide : {cle!r}")
    parties = PurePosixPath(cle).parts
    if cle.startswith("/") or not parties or ".." in parties:
        raise CleInvalide(f"clé de fichier invalide : {cle!r}")
    return "/".join(parties)


def cle_de_url(url: object) -> str | None:
    """`/uploads/a/b.jpg` → `a/b.jpg`, ou `None` si l'adresse n'est pas l'une des nôtres."""
    if not isinstance(url, str) or not url.startswith(PREFIXE_URL):
        return None
    try:
        return cle_valide(url[len(PREFIXE_URL) :])
    except CleInvalide:
        return None


@dataclass(frozen=True)
class StockageDisque:
    """Le volume `uploads` : une racine par copropriété."""

    racine: Path

    def chemin(self, cle: str) -> Path:
        """Le chemin local d'une clé, borné sous la racine — même à travers un lien."""
        chemin = (self.racine / cle_valide(cle)).resolve()
        if not chemin.is_relative_to(self.racine.resolve()):
            raise CleInvalide(f"clé hors du préfixe de la copropriété : {cle!r}")
        return chemin

    def _a_ecrire(self, cle: str) -> Path:
        """Le chemin d'une écriture, ses sous-dossiers créés — jamais la racine.

        ⚠️ La racine n'est PAS créée ici : en production c'est le volume Docker, et
        la créer à chaque écriture masquerait un montage manquant — une panne
        d'infrastructure deviendrait un fichier écrit dans le vide du conteneur,
        perdu au redémarrage (`test_signature_fichiers.py`).
        """
        if not self.racine.is_dir():
            raise FileNotFoundError(f"racine des fichiers absente : {self.racine}")
        chemin = self.chemin(cle)
        chemin.parent.mkdir(parents=True, exist_ok=True)
        return chemin

    def ecrire(self, cle: str, octets: bytes) -> None:
        self._a_ecrire(cle).write_bytes(octets)

    def ecrire_flux(self, cle: str, flux: BinaryIO) -> None:
        with self._a_ecrire(cle).open("wb") as sortie:
            shutil.copyfileobj(flux, sortie)

    def lire(self, cle: str) -> bytes:
        return self.chemin(cle).read_bytes()

    def supprimer(self, cle: str) -> None:
        self.chemin(cle).unlink(missing_ok=True)

    def existe(self, cle: str) -> bool:
        try:
            return self.chemin(cle).is_file()
        except CleInvalide:
            return False

    def url(self, cle: str) -> str:
        return PREFIXE_URL + cle_valide(cle)

    # ── Le fichier d'une LIGNE de la base (#1816) ─────────────────────────────
    #
    #  Le document, le rapport de diagnostic et l'affiche de hall gardent la CLÉ
    #  de leur fichier (`fichier_cle`, `pdf_cle`) : un chemin absolu n'a pas de
    #  sens dans un stockage objet, et il change si le volume est monté ailleurs.
    #  La migration 0283 l'a posée sur chaque ligne d'avant ; le chemin a quitté
    #  la base (0285, second temps de `CONTRACTIONS`). Toute lecture passe par ces
    #  trois gestes.

    def colonnes(self, cle: str, prefixe: str = "fichier") -> dict[str, str]:
        """Ce qu'une ligne garde d'un fichier qu'on vient d'écrire : sa clé, validée."""
        return {f"{prefixe}_cle": cle_valide(cle)}

    def cle_de(self, ligne: object, prefixe: str = "fichier") -> str | None:
        """La clé du fichier d'une ligne, ou `None` — absente, ou hors du préfixe."""
        cle = getattr(ligne, f"{prefixe}_cle", None)
        if not isinstance(cle, str) or not cle:
            return None
        try:
            return cle_valide(cle)
        except CleInvalide:
            return None

    def fichier_de(self, ligne: object, prefixe: str = "fichier") -> Path | None:
        """Le fichier EXISTANT d'une ligne, ou `None` — absent, ou hors du préfixe."""
        cle = self.cle_de(ligne, prefixe)
        if cle is None:
            return None
        try:
            chemin = self.chemin(cle)
        except CleInvalide:
            return None
        return chemin if chemin.is_file() else None

    def supprimer_de(self, ligne: object, prefixe: str = "fichier") -> None:
        """Supprime le fichier d'une ligne — jamais hors de la racine."""
        cle = self.cle_de(ligne, prefixe)
        if cle is not None:
            self.supprimer(cle)

    def fichier_de_url(self, url: object) -> Path | None:
        """Le fichier existant derrière une adresse `/uploads/…`, ou `None`.

        Une adresse étrangère, une clé qui sortirait du préfixe ou un fichier
        disparu rendent `None` : une pièce jointe orpheline ne doit pas faire
        échouer un envoi, et `/uploads/../../etc/passwd` ne doit rien rendre.
        """
        cle = cle_de_url(url)
        if cle is None:
            return None
        try:
            chemin = self.chemin(cle)
        except CleInvalide:
            return None
        return chemin if chemin.is_file() else None


def stockage() -> StockageDisque:
    """Le stockage de la copropriété servie."""
    return StockageDisque(contexte.courante().racine_fichiers)
