"""Les signataires DÉLÉGUÉS — un domaine qui signe pour un autre, admis par l'administrateur (#2554).

## Le besoin

Un cabinet sous Microsoft 365 qui n'a pas configuré la signature de son propre
domaine voit ses messages signés du domaine de son ABONNEMENT : `From:
…@iff-gestion.fr`, `d=iffgestion.onmicrosoft.com`. La signature est valide, mais
pas alignée (`courriel_authenticite.aligne`) : depuis le 26/10/2026, aucune réponse
directe du syndic n'était entrée. Demander au cabinet de corriger son DNS a été
écarté (arbitrage du 05/11/2026 : on ne s'ingère pas dans leur informatique).

## La règle : une correspondance EXACTE, déclarée

L'administrateur déclare, une par ligne, `domaine de l'expéditeur = signataire`
(Admin › Services › Courriel, réception). Le signataire est admis pour CE domaine
et lui seul, au libellé près :

- jamais un suffixe — `onmicrosoft.com` couvrirait tous les abonnements Microsoft,
  et n'importe qui peut en ouvrir un ; le nom d'UN abonnement n'appartient qu'à
  son titulaire ;
- jamais un signataire PARTAGÉ (`SIGNATAIRES_PARTAGES`) : `d=gmail.com` signe pour
  tout compte Gmail — l'admettre pour le syndic laisserait n'importe quel compte
  Gmail écrire « de » lui.

Chaque changement de la liste s'inscrit au journal de sécurité : c'est un tiers de
plus à qui l'on confie l'authenticité des réponses.
"""

from __future__ import annotations

import re

from sqlmodel import Session

from app.models.core import ConfigSite

#: La clé du réglage (onglet « reception » de `utils/reglages`).
CLE_DELEGATIONS = "courriel_signataires_delegues"

#: Les domaines qui signent pour une FOULE de comptes : messageries grand public et
#: plateformes d'envoi. Un message qu'ils signent prouve qu'il vient de l'un de
#: leurs clients, pas duquel. Un domaine de plus s'ajoute ici, avec sa famille.
SIGNATAIRES_PARTAGES = frozenset(
    {
        #  Les messageries grand public.
        "gmail.com",
        "googlemail.com",
        "google.com",
        "outlook.com",
        "hotmail.com",
        "hotmail.fr",
        "live.com",
        "live.fr",
        "yahoo.com",
        "yahoo.fr",
        "icloud.com",
        "me.com",
        "orange.fr",
        "wanadoo.fr",
        "free.fr",
        "sfr.fr",
        "laposte.net",
        "gmx.fr",
        "gmx.com",
        "protonmail.com",
        "proton.me",
        #  Les racines des abonnements et des plateformes d'envoi.
        "onmicrosoft.com",
        "amazonses.com",
        "sendgrid.net",
        "mailchimpapp.net",
        "mcsv.net",
        "sendinblue.com",
        "brevo.com",
        "mailjet.com",
    }
)

_SEPARATEUR = re.compile(r"\s*(?:=|→|->)\s*")
_DOMAINE = re.compile(r"^(?=.{4,253}$)([a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$")


def _lignes(texte: str) -> list[str]:
    return [ligne.strip() for ligne in (texte or "").splitlines() if ligne.strip()]


def _paire(ligne: str) -> tuple[str, str] | str:
    """`(domaine, signataire)` en minuscules, ou le motif du refus de la ligne."""
    morceaux = _SEPARATEUR.split(ligne)
    if len(morceaux) != 2:
        return f"« {ligne} » : écrire « domaine de l'expéditeur = signataire »"
    domaine, signataire = (m.strip().lower().rstrip(".") for m in morceaux)
    for valeur in (domaine, signataire):
        if not _DOMAINE.match(valeur):
            return f"« {ligne} » : « {valeur} » n'est pas un nom de domaine"
    if signataire == domaine:
        return f"« {ligne} » : un domaine signe déjà pour lui-même"
    if signataire in SIGNATAIRES_PARTAGES:
        return (
            f"« {ligne} » : {signataire} signe pour une foule de comptes — l'admettre "
            "laisserait n'importe lequel écrire au nom de ce domaine. Indiquer le "
            "signataire propre à l'organisme (par exemple son abonnement)"
        )
    return domaine, signataire


def refus_des_delegations(texte: str) -> str | None:
    """Le motif du refus de la liste saisie, ou None si chaque ligne est admise."""
    for ligne in _lignes(texte):
        paire = _paire(ligne)
        if isinstance(paire, str):
            return f"Signataires délégués — {paire}."
    return None


def normaliser_delegations(texte: str) -> str:
    """La forme écrite en base : `domaine = signataire`, une par ligne, triées, sans doublon."""
    paires = {p for p in map(_paire, _lignes(texte)) if not isinstance(p, str)}
    return "\n".join(f"{d} = {s}" for d, s in sorted(paires))


def delegations(texte: str) -> frozenset[tuple[str, str]]:
    """Les paires admises d'une liste écrite. Une ligne illisible ne vaut rien."""
    return frozenset(p for p in map(_paire, _lignes(texte)) if not isinstance(p, str))


def delegations_du_site(session: Session) -> frozenset[tuple[str, str]]:
    """Les délégations réglées par l'administrateur — la lecture unique."""
    ligne = session.get(ConfigSite, CLE_DELEGATIONS)
    return delegations(ligne.valeur if ligne else "")


def apres_ecriture(session: Session, cle: str, valeur: str, acteur_id: int | None) -> None:
    """Appelée par `PUT /config` pour chaque clé écrite : un changement de la liste
    se journalise. Les domaines d'organismes ne sont pas des données personnelles."""
    if cle != CLE_DELEGATIONS:
        return
    from app.utils.journal_securite import journaliser_securite

    nombre = len(delegations(valeur))
    journaliser_securite(
        "signataires_delegues_modifies",
        acteur_id=acteur_id,
        detail=f"{nombre} délégation(s) : {'; '.join(_lignes(valeur)) or 'aucune'}",
    )
