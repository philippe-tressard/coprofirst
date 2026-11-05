"""Ce que la validation d'un compte — ou la relance de son appariement — annonce.

## Pourquoi au serveur (#2522, 05/11/2026)

`POST /admin/comptes/{id}/traiter` rendait `auto_match`, que le FRONT traduisait en
phrase (`annonceValidation`, `annonceLocataire`, `#lib/comptes.ts`) : « 3 lot(s)
résolu(s) automatiquement », « ⚠️ Aucun lot trouvé dans l'import », aidé non trouvé…
L'app iOS ne recompose aucune règle du site : elle disait « Compte activé. » et
perdait l'avertissement — un copropriétaire sans lot validé sans que personne le
sache, le défaut même que `#lib/comptes.ts` avait supprimé de l'espace CS (#889).

La phrase se compose donc ICI, et les deux clients la LISENT (`annonce`). Les
textes sont ceux du site, au caractère près : ce que lisait le conseil syndical ne
change pas (`standards/09` §8, règle 1).
"""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel

from app.utils.noms import nom_affiche
from app.utils.valeurs import valeur


class Annonce(BaseModel):
    """Un message à afficher, et le ton sur lequel le dire."""

    ton: Literal["success", "warning", "error", "info"]
    texte: str


def _annonce_locataire(auto: dict[str, Any], statut) -> Optional[Annonce]:
    """Ce que l'appariement a fait d'un LOCATAIRE — `None` pour tout autre statut.

    Lue par la validation ET par la relance : un locataire resté sans lot se
    taisait, et l'administration le rattachait à la main sans savoir pourquoi (#2267).
    """
    if valeur(statut) != "locataire":
        return None
    office = auto.get("lots_d_office") or 0
    if office > 0:
        return Annonce(
            ton="success",
            texte=f"rattaché d'office à {office} lot(s) du fichier des lots, badges remis.",
        )
    badges = auto.get("badges_remis") or 0
    if badges > 0:
        return Annonce(ton="success", texte=f"{badges} badge(s) de ses lots remis.")
    if (auto.get("baux") or 0) > 0 or (auto.get("rattache") or 0) > 0:
        return Annonce(ton="success", texte="rattaché à son bail ou à son bailleur.")
    return Annonce(
        ton="warning",
        texte="⚠️ aucun lot désigné sans ambiguïté : il le déclarera dans « Mes lots », "
        "ou à rattacher à la main.",
    )


def _annonce_aide(aide: dict[str, Any], utilisateur) -> Annonce:
    """L'aidé d'un compte d'aidant ou de mandataire : retrouvé, et ce qui a suivi."""
    if aide.get("aide_trouve"):
        parts = [f"aidé(e) : {aide.get('aide_nom', '')}"]
        if aide.get("lots", 0) > 0:
            parts.append(f"{aide['lots']} lot(s)")
        if aide.get("tc", 0) > 0:
            parts.append(f"{aide['tc']} TC")
        if aide.get("vigik", 0) > 0:
            parts.append(f"{aide['vigik']} vigik")
        if aide.get("delegation"):
            parts.append("délégation créée")
        return Annonce(ton="success", texte=" — ".join(parts))
    nom = nom_affiche(utilisateur.prenom_aide, utilisateur.nom_aide)
    return Annonce(
        ton="warning",
        texte=f"⚠️ Copropriétaire aidé(e) « {nom} » non trouvé(e). Affectation manuelle requise.",
    )


def _prefixer(prefixe: str, annonce: Annonce) -> Annonce:
    return Annonce(ton=annonce.ton, texte=f"{prefixe} — {annonce.texte}")


def annonce_validation(auto: dict[str, Any], utilisateur) -> Annonce:
    """La validation d'un compte, traduite en une phrase « Compte activé — … ».

    ⚠️ Un copropriétaire sans lot est un AVERTISSEMENT, pas un succès : il ne
    pourra rien consulter.
    """
    auto = auto or {}
    if auto.get("aide_match") is not None:
        return _prefixer("Compte activé", _annonce_aide(auto["aide_match"], utilisateur))
    locataire = _annonce_locataire(auto, utilisateur.statut)
    if locataire:
        return _prefixer("Compte activé", locataire)
    resolus = auto.get("lots_resolus") or 0
    if resolus > 0:
        return Annonce(
            ton="success", texte=f"Compte activé — {resolus} lot(s) résolu(s) automatiquement."
        )
    trouves = auto.get("lots") or 0
    if trouves > 0:
        return Annonce(
            ton="success", texte=f"Compte activé — {trouves} lot(s) trouvé(s) dans l'import."
        )
    if (valeur(utilisateur.statut) or "").startswith("copropriétaire"):
        return Annonce(ton="warning", texte="Compte activé — ⚠️ Aucun lot trouvé dans l'import.")
    return Annonce(ton="success", texte="Compte activé.")


def annonce_relance(auto: dict[str, Any], utilisateur) -> Annonce:
    """« Relancer l'appariement » d'un compte déjà validé, sous son nom."""
    auto = auto or {}
    nom = nom_affiche(utilisateur.prenom, utilisateur.nom)
    locataire = _annonce_locataire(auto, utilisateur.statut)
    if locataire:
        return _prefixer(nom, locataire)
    resolus = auto.get("lots_resolus") or 0
    if resolus > 0:
        return Annonce(ton="success", texte=f"{nom} — {resolus} lot(s) résolu(s) automatiquement.")
    trouves = auto.get("lots") or 0
    if trouves > 0:
        return Annonce(
            ton="success",
            texte=f"{nom} — {trouves} lot(s) matché(s) (en attente de résolution).",
        )
    return Annonce(ton="info", texte=f"{nom} — Aucun import trouvé pour ce nom.")


__all__ = ["Annonce", "annonce_relance", "annonce_validation"]
