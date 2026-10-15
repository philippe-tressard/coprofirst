"""Un fil de courriels TRANSFÉRÉ, découpé en messages — sans IA, sans base (29/09/2026).

## Demandé le 29/09/2026

> « Si plusieurs mails du même fil, alors je récupère le dernier et je crée
>   autant de suites que nécessaire en extrayant le bon contenu »

Un membre du conseil reçoit les échanges du conseil dans sa boîte personnelle et
les transfère à l'adresse des affaires. Le dernier message cite les précédents :
ce module les SÉPARE, chacun avec son auteur et sa date. Le versement dans une
affaire vit dans `courriel_transfert`.

## Le code découpe, jamais le modèle

Arbitré le 25/09/2026 pour la ligne d'en-tête d'une Suite : un nom et une date
lus dans un en-tête ne s'inventent pas. L'assistant ne voit ensuite que le texte
d'UN message, pour en retirer la signature.

## Illisible = rien, jamais à moitié

Un message cité dont on ne lit ni l'auteur ni la date lève `FilIllisible` : le
fil entier est refusé, et qui l'a transféré en est prévenu. Verser la moitié
d'un fil, ou un message daté du jour de la relève, écrirait un historique faux
qui a l'air juste.

## Les formes reconnues

| Client | En-tête d'un message cité |
|---|---|
| Outlook, Orange, Apple (transfert) | bloc « De : … / Envoyé : … (ou Date :) / Objet : … » |
| Gmail, Apple (réponse) | « Le sam. 26 sept. 2026, 08:58, Nom <adresse> a écrit : » |
| en anglais | « From: … / Sent: … », « On …, Name <addr> wrote: » |

Les chevrons (« > ») sont retirés avant tout : la profondeur de citation ne dit
rien que les en-têtes ne disent déjà, et un fil lu depuis le HTML en porte
partout.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from app.utils.courriel_decodage import (
    CLE_ENTETE,
    MESSAGE_DU,
    _ADRESSE,
    _MARQUE_TRANSFERT,
    _SEPARATEUR,
    Transfert,
    _sans_citation,
    sans_chevrons,
    valeur_d_entete,
)
from app.utils.horloge import TZ_PARIS


class FilIllisible(ValueError):
    """Un message cité dont l'auteur ou la date ne se lit pas : le fil est refusé."""


@dataclass(frozen=True)
class MessageDuFil:
    """Un message du fil, tel que son en-tête et son texte le disent."""

    nom: str
    #: « » quand l'en-tête ne donne qu'un nom (Outlook interne, parfois).
    adresse: str
    #: L'envoi, en UTC naïf — la forme des dates en base.
    envoye_le: datetime
    #: Le texte du message SEUL, sans citation ni IA.
    texte: str
    #: Le texte tel que découpé, gardé comme « Message d'origine ».
    brut: str

    @property
    def expediteur(self) -> str:
        """« Nom <adresse> », la forme que `contenu_de_la_suite` sait lire."""
        return f"{self.nom} <{self.adresse}>" if self.adresse else ""


# ── Les dates écrites par les clients de messagerie ───────────────────────────

#: Les mois, sans accent ni point : « sept. » → « sept », « déc. » → « dec ».
_MOIS = {
    **dict.fromkeys(("janv", "janvier", "jan", "january"), 1),
    **dict.fromkeys(("fevr", "fevrier", "fev", "feb", "february"), 2),
    **dict.fromkeys(("mars", "mar", "march"), 3),
    **dict.fromkeys(("avr", "avril", "apr", "april"), 4),
    **dict.fromkeys(("mai", "may"), 5),
    **dict.fromkeys(("juin", "jun", "june"), 6),
    **dict.fromkeys(("juil", "juillet", "jul", "july"), 7),
    **dict.fromkeys(("aout", "aug", "august"), 8),
    **dict.fromkeys(("sept", "septembre", "sep", "september"), 9),
    **dict.fromkeys(("oct", "octobre", "october"), 10),
    **dict.fromkeys(("nov", "novembre", "november"), 11),
    **dict.fromkeys(("dec", "decembre", "december"), 12),
}
#: « 29 septembre 2026 », « 26 sept. 2026 », « 1er octobre 2026 », « 29 Sep 2026 ».
#: Plusieurs points tolérés : la redirection d'OVH DOUBLE le point d'une ligne
#: qui en commence une, et « sept. » coupé en fin de ligne devient « sept.. ».
_JOUR_MOIS_AN = re.compile(r"\b(\d{1,2})(?:er)?\s+([^\W\d_]{3,10})\.*,?\s+(\d{4})\b")
#: « September 29, 2026 » (Outlook en anglais), « September 29th, 2026 » (Proton).
_MOIS_JOUR_AN = re.compile(r"\b([^\W\d_]{3,10})\.*\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4})\b", re.I)
#: « 2026-09-29 » (ISO).
_ISO = re.compile(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b")
#: « 26/09/2026 », « 26/09/26 », « 29.09.2026 ».
_NUMERIQUE = re.compile(r"\b(\d{1,2})[/.](\d{1,2})[/.](\d{2,4})\b")
#: « 08:43 », « 10:12:34 », « 15 h 47 », « 8:43 AM ».
_HEURE = re.compile(r"\b(\d{1,2})\s*(?:h|:)\s*(\d{2})(?::(\d{2}))?(?:\s*([ap]m)\b)?", re.I)
#: « UTC+2 », « GMT+02:00 », « +0200 ». Sans fuseau : l'heure de Paris.
_FUSEAU = re.compile(r"(?:UTC|GMT)\s*([+-])(\d{1,2})(?::?(\d{2}))?|\s([+-])(\d{2})(\d{2})\b")


def _sans_accent(texte: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", texte) if not unicodedata.combining(c))


def _jour_mois_an(texte: str) -> tuple[int, int, int, int] | None:
    """(jour, mois, année, position de fin) de la première date lisible."""
    for motif in (_JOUR_MOIS_AN, _MOIS_JOUR_AN, _ISO, _NUMERIQUE):
        for m in motif.finditer(texte):
            if motif is _ISO:
                an, mois, jour = int(m[1]), int(m[2]), int(m[3])
            elif motif is _NUMERIQUE:
                jour, mois, an = int(m[1]), int(m[2]), int(m[3])
                an += 2000 if an < 100 else 0
            elif motif is _JOUR_MOIS_AN:
                jour, an = int(m[1]), int(m[3])
                mois = _MOIS.get(_sans_accent(m[2]).lower())
            else:
                jour, an = int(m[2]), int(m[3])
                mois = _MOIS.get(_sans_accent(m[1]).lower())
            if mois:
                return jour, mois, an, m.end()
    return None


def date_citee(texte: str) -> datetime | None:
    """La date d'un en-tête cité, en UTC NAÏF — ou None si elle ne se lit pas.

    Sans fuseau écrit, l'heure est celle de Paris : c'est celle qu'affichent
    les clients de messagerie des résidents.
    """
    trouve = _jour_mois_an(texte or "")
    if trouve is None:
        return None
    jour, mois, an, fin = trouve
    h = _HEURE.search(texte, fin)
    if h is None:
        return None
    heure, minute, seconde = int(h[1]), int(h[2]), int(h[3] or 0)
    midi = (h[4] or "").lower()
    if midi == "pm" and heure < 12:
        heure += 12
    elif midi == "am" and heure == 12:
        heure = 0
    try:
        locale = datetime(an, mois, jour, heure, minute, seconde)
    except ValueError:
        return None
    f = _FUSEAU.search(texte, h.end())
    if f is None:
        return locale.replace(tzinfo=TZ_PARIS).astimezone(timezone.utc).replace(tzinfo=None)
    signe, heures, minutes = (f[1], f[2], f[3]) if f[1] else (f[4], f[5], f[6])
    decalage = timedelta(hours=int(heures), minutes=int(minutes or 0))
    return locale - decalage if signe == "+" else locale + decalage


# ── Les en-têtes de messages cités ────────────────────────────────────────────

#: Les clés d'un bloc d'en-tête : `courriel_decodage.CLE_ENTETE`, la seule liste.
_CLES_DE = {"de", "from"}
_CLES_DATE = {"envoyé", "envoyé le", "sent", "date", "date d'envoi"}
_CLES_OBJET = {"objet", "subject", "sujet"}
#: Une liste d'adresses peut continuer sur la ligne suivante.
_CLES_LISTE = {"à", "a", "to", "pour", "cc", "cci", "bcc", "copie à"}
#: « Le … a écrit : » (une à trois lignes : Gmail coupe la sienne).
_A_ECRIT_DEBUT = re.compile(r"^(Le|On)\s+\S", re.I)
_A_ECRIT_FIN = re.compile(r"\s*(a\s+écrit|wrote)\s*:\s*$", re.I)


def _nue(ligne: str) -> str:
    return ligne.replace("*", "").strip()


def _cle(ligne: str) -> str | None:
    m = CLE_ENTETE.match(_nue(ligne))
    return re.sub(r"\s+", " ", m[1]).lower() if m else None


def _bloc_de(lignes: list[str], i: int) -> tuple[dict, int] | None:
    """Un bloc d'en-tête commençant à la ligne `i`, et sa fin — ou None.

    Il commence par N'IMPORTE quelle clé (Thunderbird écrit « Sujet : » et
    « Date : » avant « De : ») ou par « Message du … » (Orange), et n'en est
    un que s'il porte un auteur ET une date : une ligne « Objet : devis » du
    corps n'ouvre rien (#1471).
    """
    date_du = MESSAGE_DU.match(_nue(lignes[i]))
    if not date_du and _cle(lignes[i]) is None:
        return None
    entete = {"date": date_du.group(1)} if date_du else {}
    derniere, fin = None, i + 1 if date_du else i
    while fin < len(lignes) and _nue(lignes[fin]):
        cle = _cle(lignes[fin])
        if cle is None:
            if derniere not in _CLES_LISTE:
                break  # le corps commence sans ligne vide
        else:
            derniere = cle
            valeur = valeur_d_entete(_nue(lignes[fin]))
            if cle in _CLES_DE:
                entete.setdefault("de", valeur)
            elif cle in _CLES_DATE:
                entete.setdefault("date", valeur)
            elif cle in _CLES_OBJET:
                entete.setdefault("objet", valeur)
        fin += 1
    return (entete, fin) if entete.get("de") and entete.get("date") else None


def _a_ecrit(lignes: list[str], i: int) -> tuple[dict, int] | None:
    """« Le …, Nom <adresse> a écrit : » à partir de la ligne `i`, et sa fin."""
    if not _A_ECRIT_DEBUT.match(lignes[i].strip()):
        return None
    joint = ""
    for fin in range(i, min(i + 3, len(lignes))):
        if not lignes[fin].strip():
            return None
        joint = f"{joint} {lignes[fin].strip()}".strip()
        if _A_ECRIT_FIN.search(joint):
            break
    else:
        return None  # trois lignes sans « a écrit : » : une phrase du corps
    if len(joint) > 300:
        return None
    phrase = re.sub(r"^(Le|On)\s+", "", _A_ECRIT_FIN.sub("", joint), flags=re.I)
    trouve = _jour_mois_an(phrase)
    h = _HEURE.search(phrase, trouve[3]) if trouve else None
    if h is None:
        return None
    #  « … 08:43:12 UTC+2, Nom a écrit » (Yahoo) : le fuseau n'est pas le nom.
    reste = phrase[h.end() :].lstrip()
    f = _FUSEAU.match(reste)
    qui = (reste[f.end() :] if f else reste).strip(" ,")
    return {"de": qui, "date": phrase[: h.end()] + (f[0] if f else "")}, fin + 1


def _en_tete(lignes: list[str], i: int) -> tuple[dict, int] | None:
    return _bloc_de(lignes, i) or _a_ecrit(lignes, i)


def _sans_marques_finales(lignes: list[str]) -> list[str]:
    """Retire, en fin de message, les lignes vides, séparateurs et marques de transfert
    qui annoncent le message cité suivant."""
    while lignes and (
        not lignes[-1].strip()
        or _SEPARATEUR.match(lignes[-1].strip())
        or _MARQUE_TRANSFERT.match(lignes[-1].strip().strip("*"))
    ):
        lignes = lignes[:-1]
    return lignes


def _message(entete: dict, lignes: list[str]) -> MessageDuFil:
    de = (entete.get("de") or "").strip()
    trouve = _ADRESSE.search(de)
    adresse = trouve.group(0).lower() if trouve else ""
    nom = re.split(r"[<\[]", de, maxsplit=1)[0].strip().strip("\"'").strip()
    if not nom or nom.lower() == adresse:
        nom = adresse
    if not nom:
        raise FilIllisible(f"un message cité n'indique pas son auteur (« {de} »)")
    envoye_le = date_citee(entete.get("date") or "")
    if envoye_le is None:
        raise FilIllisible(
            f"la date du message de {nom} ne se lit pas (« {entete.get('date') or ''} »)"
        )
    brut = "\n".join(_sans_marques_finales(lignes)).strip()
    return MessageDuFil(
        nom=nom, adresse=adresse, envoye_le=envoye_le, texte=_sans_citation(brut), brut=brut
    )


def messages_du_fil(transfert: Transfert) -> list[MessageDuFil]:
    """Les messages du fil transféré, du plus RÉCENT au plus ancien.

    Le premier est celui qu'on a transféré — son en-tête est dans le bloc de
    transfert —, les suivants sont ceux qu'il cite, dans l'ordre où il les cite.
    Lève `FilIllisible` si l'un d'eux ne dit pas qui l'a écrit ni quand.
    """
    lignes = [sans_chevrons(ligne) for ligne in transfert.corps.splitlines()]
    blocs: list[tuple[dict, list[str]]] = []
    entete = {"de": transfert.de, "date": transfert.date}
    tampon: list[str] = []
    i = 0
    while i < len(lignes):
        suivant = _en_tete(lignes, i)
        if suivant is None:
            tampon.append(lignes[i])
            i += 1
            continue
        blocs.append((entete, tampon))
        (entete, i), tampon = suivant, []
    blocs.append((entete, tampon))
    return [_message(e, t) for e, t in blocs]


# ── Reconnaître un fil, et un message déjà versé ──────────────────────────────

#: « RE: », « TR : », « Fwd: », « AW: »… en tête d'objet, éventuellement répétés.
#: 🔴 « Rép. : » (Apple Mail et Outlook en français) et « Réponse : » manquaient
#: (15/10/2026) : la réponse d'un copropriétaire avait une autre clé de fil, et
#: ouvrait une SECONDE affaire au lieu de rejoindre la sienne. Le « : » est exigé,
#: donc « Réparation », « Repas » ou « Report » restent dans le titre.
_PREFIXES = re.compile(
    r"^\s*((re|r[ée]p\.?|r[ée]ponse|tr|fwd?|fw|transf\.?|réf|aw|wg)\s*(\[\d+\])?\s*:\s*)+", re.I
)
#: Le repère d'une affaire écrit par le conseil (« TK-109008 », « Affaire #TK-… »).
_REPERE = re.compile(r"(?:affaire|ticket)?\s*#?\s*\bTK-[0-9A-Za-z]{4,12}\b", re.I)
_REPERE_SEUL = re.compile(r"#?\s*\b(TK-[0-9A-Za-z]{4,12})\b", re.I)


def repere_ecrit(*textes: str | None) -> str | None:
    """Le numéro d'affaire écrit dans l'objet ou la note, même seul (« TK-109008 »).

    ⚠️ Plus large que `courriel_entrant.numero_dans_sujet`, qui exige « Affaire »
    devant : il ne sert QU'À un transfert d'un membre du conseil authentifié,
    qui désigne l'affaire de lui-même.
    """
    for texte in textes:
        trouve = _REPERE_SEUL.search(texte or "")
        if trouve:
            return trouve.group(1)
    return None


def titre_du_fil(objet: str) -> str:
    """L'objet d'origine, sans « RE: / TR: » ni repère d'affaire — le titre d'une affaire."""
    titre = _REPERE.sub(" ", _PREFIXES.sub("", objet or ""))
    return re.sub(r"\s+", " ", titre).strip(" -—–:")


def cle_du_fil(objet: str) -> str | None:
    """Ce qui reconnaît un fil d'un transfert à l'autre : son objet, normalisé.

    None quand l'objet est trop court pour reconnaître quoi que ce soit : deux
    fils « Info » n'ont rien en commun.
    """
    cle = _sans_accent(titre_du_fil(objet)).lower()
    cle = re.sub(r"[^0-9a-z]+", " ", cle).strip()
    return cle if len(cle.replace(" ", "")) >= 6 else None


def texte_normalise(texte: str) -> str:
    """Le texte réduit à ses lettres et chiffres, sans accent ni casse.

    Deux clients qui citent le même message ne le coupent pas aux mêmes endroits
    et n'y mettent pas les mêmes espaces : seule la suite des mots compte.
    """
    return re.sub(r"[^0-9a-z]+", "", _sans_accent(texte or "").lower())


def empreinte(message: MessageDuFil) -> str:
    """Ce qui reconnaît un message déjà versé, quel que soit le transfert qui le porte."""
    qui = (message.adresse or message.nom).lower()
    return hashlib.sha256(f"{qui}|{texte_normalise(message.texte)}".encode()).hexdigest()


__all__ = [
    "FilIllisible",
    "MessageDuFil",
    "cle_du_fil",
    "date_citee",
    "empreinte",
    "messages_du_fil",
    "repere_ecrit",
    "texte_normalise",
    "titre_du_fil",
]
