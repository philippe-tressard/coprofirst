"""Les PROFILS de lecteurs et les noms de leurs combinaisons — la pastille de lecture.

Porté de `front/src/lib/lecture.ts` le 11/11/2026 (#2633) : le site composait ce
vocabulaire dans son front, l'app iOS n'avait rien. La nomenclature est celle
arbitrée le 25/09/2026 (`ux-patterns` §2 bis) ; l'ordre est celui de l'affichage.

`statut` est celui du compte (`StatutUtilisateur`) : c'est par lui que
`test_lecture_pastille.py` confronte ce résumé à la règle qui DÉCIDE
(`ticket_visible`). Les « Bailleurs » sont les comptes mandataires — agence,
gestionnaire — qui louent par délégation d'un copropriétaire.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Profil:
    code: str
    statut: str
    court: str
    long: str
    icone: str


PROFILS: tuple[Profil, ...] = (
    Profil(
        "occupants", "copropriétaire_résident", "Occupants", "Copropriétaires occupants", "home"
    ),
    Profil(
        "copro_bailleurs",
        "copropriétaire_bailleur",
        "Copro-bailleurs",
        "Copropriétaires bailleurs",
        "building-2",
    ),
    Profil("bailleurs", "mandataire", "Bailleurs", "Bailleurs (mandataires)", "heart-handshake"),
    Profil("locataires", "locataire", "Locataires", "Locataires", "user"),
)

TOUS_PROFILS: list[str] = [p.code for p in PROFILS]

#: Ce que chaque code de Destinataires fait LIRE — miroir de `public_cible_visible`.
#: Un code inconnu ne fait lire personne ; `conseil_syndical` non plus — le conseil
#: lit TOUT, ce n'est pas un profil qu'on ajoute.
PROFILS_DU_CODE: dict[str, list[str]] = {
    "résidents": TOUS_PROFILS,
    "copropriétaires": ["occupants", "copro_bailleurs"],
    "copropriétaires_occupants": ["occupants"],
    "bailleurs": ["copro_bailleurs"],
    "mandataires": ["bailleurs"],
    "locataires": ["locataires"],
}

#: Une affaire suivie : les COPROPRIÉTAIRES seuls, occupants et bailleurs (#1311).
PROFILS_AFFAIRE: list[str] = ["occupants", "copro_bailleurs"]


@dataclass(frozen=True)
class Vocable:
    cle: str
    icones: list[str] = field(default_factory=list)
    court: str = ""
    long: str = ""
    #: « les copropriétaires occupants et les locataires » — une combinaison composée.
    qui: str = ""


#: Les combinaisons qui ont un NOM ; les autres se composent. « Copropriétaires »
#: nomme UN ensemble (#1311) : les actualités et les affaires le disent pareil.
NOMMEES: tuple[tuple[list[str], Vocable], ...] = (
    (TOUS_PROFILS, Vocable("tous", ["users-round"], "Tous", "Tous")),
    (
        ["occupants", "locataires"],
        Vocable("residents", ["home", "user"], "Résidents", "Résidents (occupants et locataires)"),
    ),
    (
        PROFILS_AFFAIRE,
        Vocable(
            "coproprietaires",
            ["key-round"],
            "Copropriétaires",
            "Copropriétaires (occupants et bailleurs)",
        ),
    ),
    #  Une Panne sans choix du conseil (standard du 30/09/2026).
    (
        [*PROFILS_AFFAIRE, "locataires"],
        Vocable(
            "copro_locataires",
            ["key-round", "user"],
            "Copropriétaires + locataires",
            "Copropriétaires et locataires",
        ),
    ),
)

CS = Vocable("cs", ["shield-check"], "CS", "Conseil syndical seul")

#: « Résident concerné » — une affaire confidentielle ou fermée par sa catégorie
#: (#1436) : les mêmes lecteurs que « CS », et l'auteur que ce mot nomme.
CONCERNE = Vocable("concerne", ["lock"], "Concerné", "Résident concerné")


def minuscule(texte: str) -> str:
    """La première lettre en minuscule — un libellé repris au milieu d'une phrase."""
    return texte[:1].lower() + texte[1:]


def vocable_de(profils: list[str]) -> Vocable:
    """Le nom d'un ensemble de profils : le sien s'il en a un, sinon composé."""
    cle = sorted(profils)
    for membres, nommee in NOMMEES:
        if sorted(membres) == cle:
            return nommee
    ps = [p for p in PROFILS if p.code in profils]
    return Vocable(
        cle="+".join(p.code for p in ps),
        icones=[p.icone for p in ps],
        court=" + ".join(p.court for p in ps),
        long=" et ".join(p.long if i == 0 else minuscule(p.long) for i, p in enumerate(ps)),
        qui="les " + " et les ".join(minuscule(p.long) for p in ps),
    )


def qui_de(profils: list[str]) -> str:
    """« les copropriétaires (occupants et bailleurs) », « les locataires »…"""
    v = vocable_de(profils)
    return v.qui or "les " + minuscule(v.long)
