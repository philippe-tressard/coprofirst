"""La saisie d'une affaire, Essentielle ou Complète — le choix et son défaut (#2595).

## Ce que c'est

Deux façons d'ouvrir le même formulaire : **Complète** (toutes les sections) et
**Essentielle** (les champs qu'il faut, les autres rangés dans « Plus de détails »).
La préférence est celle du COMPTE, pas de l'appareil : la saisie ne doit pas
différer entre le téléphone et l'ordinateur.

## Le défaut ne se stocke pas, il se calcule

`Utilisateur.saisie_affaire` vaut `NULL` tant que la personne n'a pas choisi : le
mode est alors **Essentielle, pour tout le monde**, conseil syndical compris (arbitré
le 08/11/2026 : « selon mon rôle » est retiré du Profil). Le défaut reste calculé, pas
écrit à l'inscription : le changer un jour ne demande aucune migration de données.

C'est une règle d'affichage que le site ET l'app iOS montrent : elle se calcule
ici et se sert dans `UserRead.saisie_affaire_effective`, le front la LIT
(`standards/09` §8, `lint:regles-partagees`).
"""

from __future__ import annotations

from fastapi import HTTPException

from app.models.core import Utilisateur

ESSENTIELLE = "essentielle"
COMPLETE = "complete"

#: Les deux modes qui s'enregistrent.
MODES: tuple[str, ...] = (ESSENTIELLE, COMPLETE)

#: Le mode de qui n'a rien choisi — le même pour tous les rôles.
DEFAUT = ESSENTIELLE


def mode_effectif(user: Utilisateur) -> str:
    """Le mode qui s'applique à cette personne : son choix, sinon le défaut."""
    if user.saisie_affaire in MODES:
        return user.saisie_affaire
    return DEFAUT


def choix_a_enregistrer(demande: str) -> str:
    """La valeur à écrire pour ce que le profil demande.

    Lève 400 sur tout autre mot : une préférence se poste directement, sans l'écran.
    """
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
