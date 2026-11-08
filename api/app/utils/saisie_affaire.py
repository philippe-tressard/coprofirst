"""La saisie d'une affaire, Essentielle ou Complète — le choix et son défaut (#2595).

## Ce que c'est

Deux façons d'ouvrir le même formulaire : **Complète** (toutes les sections) et
**Essentielle** (les champs qu'il faut, les autres rangés dans « Plus de détails »).
La préférence est celle du COMPTE, pas de l'appareil : la saisie ne doit pas
différer entre le téléphone et l'ordinateur.

## Le défaut ne se stocke pas, il se calcule

`Utilisateur.saisie_affaire` vaut `NULL` tant que la personne n'a pas choisi : le
mode est alors celui de son rôle — Complète pour qui modère (`est_moderateur`),
Essentielle pour les autres. Un résident élu au conseil passe donc en Complète sans
rien faire, ce qu'un défaut écrit à l'inscription n'aurait pas permis.

C'est une règle d'affichage que le site ET l'app iOS montrent : elle se calcule
ici et se sert dans `UserRead.saisie_affaire_effective`, le front la LIT
(`standards/09` §8, `lint:regles-partagees`).
"""

from __future__ import annotations

from typing import Optional

from fastapi import HTTPException

from app.auth.deps import est_moderateur
from app.models.core import Utilisateur

ESSENTIELLE = "essentielle"
COMPLETE = "complete"

#: Les deux modes qui s'enregistrent.
MODES: tuple[str, ...] = (ESSENTIELLE, COMPLETE)

#: Ce que le profil envoie pour revenir au défaut « selon mon rôle » : rien ne
#: s'enregistre, la colonne repasse à `NULL`.
SELON_LE_ROLE = "role"


def mode_effectif(user: Utilisateur) -> str:
    """Le mode qui s'applique à cette personne : son choix, sinon celui de son rôle."""
    if user.saisie_affaire in MODES:
        return user.saisie_affaire
    return COMPLETE if est_moderateur(user) else ESSENTIELLE


def choix_a_enregistrer(demande: str) -> Optional[str]:
    """La valeur à écrire pour ce que le profil demande — `None` = selon le rôle.

    Lève 400 sur tout autre mot : une préférence se poste directement, sans l'écran.
    """
    if demande == SELON_LE_ROLE:
        return None
    if demande in MODES:
        return demande
    raise HTTPException(400, "Valeur invalide pour saisie_affaire")


# ── Les sections de la saisie Essentielle ──────────────────────────────────────

#: Toujours montrées, quelle que soit la catégorie : ce qu'une affaire ne peut pas
#: se passer de dire. Les identifiants sont ceux de `SECTIONS_ORDRE` (front).
SECTIONS_DE_BASE: tuple[str, ...] = ("titre", "nature", "perimetre", "description")

#: Ce que chaque catégorie ajoute — ce qu'on FAIT de l'affaire (arbitré le 08/11/2026) :
#: la photo est la preuve d'une panne ou d'un dégât (et sinistre court sous cinq jours
#: ouvrés) ; une visite ou un dossier a une date ; une actualité dit quand, à qui, par où.
#: Une catégorie absente de la table n'ajoute rien : question, bogue.
#: Tout le reste part à sa valeur par défaut et se range dans « Plus de détails ».
SECTIONS_ESSENTIELLES_PAR_CATEGORIE: dict[str, tuple[str, ...]] = {
    "panne": ("pieces_jointes", "mise_en_avant"),
    "sinistre": ("pieces_jointes", "mise_en_avant"),
    "nuisance": ("pieces_jointes",),
    "espaces_verts": ("pieces_jointes",),
    "acces_accueil": ("pieces_jointes",),
    "entretien": ("quand",),
    "etude_travaux": ("quand",),
    "actualite": ("quand", "destinataires", "diffusion"),
}


def sections_essentielles(categorie: str) -> list[str]:
    """Les sections que la saisie Essentielle montre pour cette catégorie."""
    return [*SECTIONS_DE_BASE, *SECTIONS_ESSENTIELLES_PAR_CATEGORIE.get(categorie, ())]
