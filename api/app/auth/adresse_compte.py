"""« Le compte de cette adresse » — la question et la forme d'une adresse, écrites UNE fois.

## Pourquoi ce module (#1550, audit du 02/10/2026)

La question s'écrivait de deux façons, qui divergeaient sur le cas limite :

- **insensible à la casse du stockage** (`func.lower(Utilisateur.email) == …`) —
  inscription, connexion, administration, profil, transfert d'un courriel ;
- **sensible** (`Utilisateur.email == …`) — renvoi du lien de vérification, mot
  de passe oublié, recherche d'un locataire par un bailleur.

Un compte dont l'adresse stockée portait une majuscule se connectait, mais ne
pouvait ni recevoir un nouveau lien ni réinitialiser son mot de passe : 204 muet
(« pas d'énumération de comptes »), et la personne concluait que le courriel
n'arrivait pas. C'est `standards/02` §1 bis : deux copies divergent sur le cas
limite, jamais sur le cas nominal.

L'écriture retenue est la plus disante (`standards/02` §4 bis) : insensible à la
casse ET aux espaces, des deux côtés — la valeur cherchée par
`normaliser_adresse`, la colonne par les mêmes fonctions SQL. Elle tient même si
une adresse ancienne a échappé à la normalisation à l'écriture.

## La forme d'une adresse

`normaliser_adresse` vivait dans `utils/envois_uniques` (la déduplication entre
deux envois), et la même formule était recopiée dans trois validateurs de schéma
et une demi-douzaine de modules. Elle est ici, et tous l'appellent : c'est la
forme sous laquelle une adresse s'ÉCRIT dans un compte comme celle sous laquelle
on la CHERCHE.

## Ce que la base contenait (mesuré le 02/10/2026)

Sur la sauvegarde hors site du 30/09/2026 (archive close, lue sur le poste) :
27 comptes, **aucune** adresse hors de la forme
normalisée, aucun couple de comptes qui ne diffèrent que par la casse. Aucune
migration de normalisation n'a donc été écrite : il n'y avait rien à migrer, et
les écritures passent toutes par cette forme depuis ce lot.

🔒 `tests/test_adresse_compte_source_unique.py` refuse une comparaison sur
`Utilisateur.email` ou une normalisation d'adresse recopiée hors d'ici.
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy import func
from sqlmodel import Session, select

from app.models.core import Utilisateur


def normaliser_adresse(adresse: Optional[str]) -> str:
    """La forme sous laquelle une adresse s'écrit dans un compte, et se compare.

    ⚠️ Minuscules et espaces retirés, **et rien de plus**. Pas de retrait des
    points ni de la partie après `+` : `jean.dupont@` et `jeandupont@` sont deux
    adresses distinctes pour la plupart des serveurs, et les « normaliser »
    ensemble ferait de deux personnes une seule — un compte retrouvé à tort, un
    destinataire supprimé à tort. C'est le mauvais côté de l'erreur.
    """
    return (adresse or "").strip().lower()


def adresse_masquee(adresse: Optional[str]) -> str:
    """`p***@domaine.fr` — assez pour reconnaître quelqu'un, pas assez pour ficher.

    Écrit une fois pour deux lecteurs : le journal des envois (#777), et la
    recherche d'un locataire par un bailleur (#2153), où l'adresse entière
    servait d'annuaire à tout copropriétaire. Une chaîne vide si l'adresse l'est,
    `***` si elle n'a pas de domaine.
    """
    if not adresse:
        return ""
    tete, _, domaine = adresse.strip().partition("@")
    if not domaine:
        return "***"
    return f"{tete[:1]}***@{domaine}"


def compte_par_adresse(
    session: Session, adresse: Optional[str], *, actif_seulement: bool = False
) -> Optional[Utilisateur]:
    """Le compte de cette adresse, ou None — sans égard à la casse ni aux espaces.

    `actif_seulement` — seulement un compte autorisé à se connecter : c'est la
    question du transfert d'un courriel (un compte désactivé ne verse rien).

    ⚠️ La décision de RÉVÉLER ou non que le compte existe reste à l'appelant :
    le renvoi du lien et le mot de passe oublié répondent 204 dans les deux cas,
    l'inscription dit « déjà utilisée ». Ce module répond à « lequel ? », pas à
    « que dire ? ».
    """
    cherchee = normaliser_adresse(adresse)
    if not cherchee:
        return None
    requete = select(Utilisateur).where(func.lower(func.trim(Utilisateur.email)) == cherchee)
    if actif_seulement:
        requete = requete.where(Utilisateur.actif == True)  # noqa: E712  (colonne SQL)
    return session.exec(requete).first()
