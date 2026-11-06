"""Du MIME au texte lisible — le DÉCODAGE d'une réponse par courriel.

Extrait de `courriel_boite.py` le 09/09/2026, sur refus du contrôle de
modularité : ce fichier était à 500 lignes pile et devait recevoir la
distinction passager/persistant (#858).

La coupe suit une couture qui existait déjà. `courriel_boite` est le **tuyau** —
il ouvre la boîte, lit, applique un verdict. Ces fonctions-ci ne connaissent
ni IMAP, ni la base, ni le ticket : on leur donne un message `email.message`, elles
rendent du texte. Elles s'éprouvent sur des messages écrits à la main, y compris
mal formés, sans réseau.

⚠️ Les trois premières gardent leur préfixe `_` : ce n'est pas une surface
publique, c'est le même module vu de plus près.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from email.header import decode_header, make_header
from html.parser import HTMLParser

#: Un corps de réponse dépasse rarement quelques lignes utiles ; au-delà c'est la
#: citation du message précédent. Tronqué pour ne pas recopier tout un fil dans le
#: ticket à chaque échange. Vient avec `_sans_citation`, sa seule lectrice.
MAX_CORPS = 4000


def _texte(valeur) -> str:
    """Un en-tête décodé, quel que soit son encodage MIME."""
    if not valeur:
        return ""
    try:
        return str(make_header(decode_header(valeur)))
    except Exception:
        return str(valeur)


class _TexteDuHtml(HTMLParser):
    """Le TEXTE d'un corps HTML — jamais son balisage.

    Les blocs deviennent des lignes, `<br>` un saut de ligne, et une ligne citée
    (`<blockquote>`) est préfixée de « > » comme dans un courriel en texte brut :
    `_sans_citation` la reconnaît alors sans règle de plus.
    """

    _BLOCS = {"p", "div", "tr", "li", "h1", "h2", "h3", "h4", "h5", "h6", "table", "blockquote"}
    _MUETS = {"style", "script", "head", "title"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.lignes: list[str] = [""]
        self.cite = 0
        self.muet = 0

    def _saut(self):
        if self.lignes[-1].strip():
            self.lignes.append("")

    def handle_starttag(self, tag, attrs):
        if tag in self._MUETS:
            self.muet += 1
        elif tag == "br":
            self.lignes.append("")
        elif tag in self._BLOCS:
            self._saut()
            if tag == "blockquote":
                self.cite += 1

    def handle_endtag(self, tag):
        if tag in self._MUETS:
            self.muet = max(0, self.muet - 1)
        elif tag in self._BLOCS:
            self._saut()
            if tag == "blockquote":
                self.cite = max(0, self.cite - 1)

    def handle_data(self, data):
        if self.muet:
            return
        morceau = re.sub(r"\s+", " ", data.replace("\xa0", " "))
        if not morceau.strip():
            return
        if not self.lignes[-1] and self.cite:
            self.lignes[-1] = "> "
        self.lignes[-1] += morceau.lstrip() if not self.lignes[-1].strip() else morceau


def _html_en_texte(html: str) -> str:
    lecteur = _TexteDuHtml()
    lecteur.feed(html)
    lecteur.close()
    return "\n".join(ligne.strip() for ligne in lecteur.lignes).strip()


def _charge(partie) -> str:
    brut = partie.get_payload(decode=True) or b""
    return brut.decode(partie.get_content_charset() or "utf-8", "replace")


def _parties(message) -> tuple[list, list]:
    """Les parties du message LUI-MÊME, et à part les messages qu'il JOINT.

    `message.walk()` descend dans un `message/rfc822` : le texte d'un message
    joint aurait pu passer pour celui du message, selon l'ordre des parties.
    """
    propres, joints = [], []

    def parcourir(partie) -> None:
        if partie.get_content_type() == "message/rfc822":
            charge = partie.get_payload()
            joints.extend(charge if isinstance(charge, list) else [charge])
        elif partie.is_multipart():
            for sous in partie.get_payload():
                parcourir(sous)
        else:
            propres.append(partie)

    parcourir(message)
    return propres, joints


def _corps_lisible(message) -> str:
    """Le texte de la réponse, en clair.

    On préfère la partie `text/plain` : elle existe presque toujours. À défaut —
    ou quand elle est APLATIE (`_aplati`) —, le
    `text/html` est réduit à son TEXTE — jamais conservé comme balisage : un fil
    de ticket qui accepterait du HTML venu d'un courriel ouvrirait une porte que
    `lint:html` ne surveille pas.

    🔴 **Ce repli manquait jusqu'au 28/09/2026.** L'application Mail d'Orange
    n'envoie QUE du HTML : son corps était lu vide, et la réponse d'un membre du
    conseil a été ignorée sans un mot.

    Un message JOINT (« transférer en tant que pièce jointe » d'Outlook ou de
    Thunderbird, #1471) suit le texte, précédé de l'en-tête qu'un transfert en
    ligne aurait écrit : le découpage le lit alors comme tout autre transfert.
    """
    propres, joints = _parties(message)
    brut = next((_charge(p) for p in propres if p.get_content_type() == "text/plain"), None)
    html = next((p for p in propres if p.get_content_type() == "text/html"), None)
    if html is not None and (brut is None or _aplati(brut)):
        texte = _html_en_texte(_charge(html))
    else:
        texte = brut or ""
    for joint in joints:
        texte += "\n\n" + _en_tete_du_joint(joint) + _corps_lisible(joint)
    return texte


def _en_tete_du_joint(joint) -> str:
    """L'en-tête d'un transfert en ligne, écrit d'après celui du message joint."""
    return (
        "-------- Message transféré --------\n"
        f"De : {_texte(joint.get('From'))}\n"
        f"Date : {_texte(joint.get('Date'))}\n"
        f"Objet : {_texte(joint.get('Subject'))}\n\n"
    )


#: Au-delà, une ligne n'est plus une ligne : c'est un corps dont on a ôté les sauts.
_LIGNE_APLATIE = 300


def _aplati(texte: str) -> bool:
    """La partie texte a-t-elle perdu ses sauts de ligne ?

    🔴 Le webmail iCloud (29/09/2026) envoie un transfert dont la partie
    `text/plain` tient sur UNE ligne — « Début du message réexpédié : De : …
    Objet : … » bout à bout. Aucun en-tête ne s'y repère, et le premier
    transfert réel a été refusé ; sa partie HTML, elle, était intacte.
    """
    lignes = [ligne for ligne in texte.splitlines() if ligne.strip()]
    return len(lignes) <= 2 and any(len(ligne) > _LIGNE_APLATIE for ligne in lignes)


#: Un séparateur de réponse : une ligne faite de tirets ou de soulignés seuls
#: (« ---------------- » d'Orange, « ________ » d'Outlook).
_SEPARATEUR = re.compile(r"^[-_]{8,}$")
#: L'en-tête d'un message cité à la manière d'Outlook : « De : … <adresse> »
#: suivi, dans les lignes qui viennent, d'« Envoyé : » ou « Date : ».
_DE = re.compile(r"^\*?(De|From)\s*:\*?\s*.*@", re.I)
#: « Envoyé le : » est celui de Courrier pour Windows 10 (#1471).
_DATE_CITEE = re.compile(r"^\*?(Envoyé(\s+le)?|Sent|Date(\s+d'envoi)?)\s*:", re.I)
#: TOUTES les clés d'un bloc d'en-tête cité, quel que soit le client — la seule
#: liste : `courriel_fil` la lit ici (#1471). « Pour » et « Sujet » sont de
#: Thunderbird, « Copie à » d'Orange, « Envoyé le » de Courrier pour Windows.
CLE_ENTETE = re.compile(
    r"^\*?(De|From|Envoyé(?:\s+le)?|Sent|Date(?:\s+d'envoi)?|À|A|To|Pour|Cc|Cci|Bcc"
    r"|Copie à|Objet|Subject|Sujet|Importance|Répondre à|Reply-To)\s*:",
    re.I,
)
#: « Message du 29/09/26 08:43 » : Orange annonce ainsi le message cité, sans
#: ligne « Date : » dans le bloc qui suit (#1471).
MESSAGE_DU = re.compile(r"^Message du\s+(.*\d{1,2}\s*[:h]\s*\d{2}.*)$", re.I)
#: La ligne qui ouvre le message transféré, selon le client (#1471) : Apple
#: (français, anglais), Gmail, Outlook, Thunderbird, Yahoo, Samsung, Proton,
#: Free (« Mail transféré »), La Poste et SFR (« Message original »).
_MARQUE_TRANSFERT = re.compile(
    r"^(D[ée]but du message r[ée]exp[ée]di[ée]\s*:?|Begin forwarded message\s*:?"
    r"|-{2,}\s*(Message transf[ée]r[ée]|Forwarded message|Original Message|Message d'origine"
    r"|Message original|Mail transf[ée]r[ée]|Mail original)\s*-*)$",
    re.I,
)
#: La signature qu'ajoute l'APPAREIL ou l'application — pas un mot de l'auteur
#: (#1471). Bornée en longueur : « Envoyé depuis hier, le devis… » est du texte.
_SIGNATURE_APPAREIL = re.compile(
    r"^(Envoy[ée] (de|depuis) mon |Envoy[ée] à partir de |Sent from (my )?"
    r"|Obtenir Outlook pour |Get Outlook for )",
    re.I,
)
_SIGNATURE_LONGUEUR = 70


def _sans_citation(texte: str) -> str:
    """La réponse, sans le message cité en dessous.

    Une réponse par courriel recopie tout l'échange précédent. Le laisser
    entrerait dans le ticket une copie du ticket, à chaque échange, et le fil
    deviendrait illisible en trois messages.
    """
    source = texte.splitlines()
    lignes = []
    for n, ligne in enumerate(source):
        nue = ligne.strip()
        if nue.startswith(">") or nue.startswith("-- ") or _SEPARATEUR.match(nue):
            break
        if _MARQUE_TRANSFERT.match(nue.strip("*")) or MESSAGE_DU.match(nue):
            break
        if len(nue) <= _SIGNATURE_LONGUEUR and _SIGNATURE_APPAREIL.match(nue):
            break
        if nue.startswith("Le ") and nue.endswith("écrit :"):
            break
        if _DE.match(nue) and any(_DATE_CITEE.match(s.strip()) for s in source[n + 1 : n + 4]):
            break
        lignes.append(ligne)
    return "\n".join(lignes).strip()[:MAX_CORPS]


# ── Un TRANSFERT : le message d'un autre, sous une note ───────────────────────

#: « TR : », « Fwd: », « Fw: » en tête de l'objet.
_OBJET_TRANSFERT = re.compile(r"^\s*(tr|fwd?|transf\.?)\s*:", re.I)
_ADRESSE = re.compile(r"[\w.+-]+@[\w-]+(\.[\w-]+)+")
#: L'objet d'un message cité : « Objet : … », « Subject: … ».
_OBJET_CITE = re.compile(r"^\*?(Objet|Subject|Sujet)\s*:\*?", re.I)
#: Les chevrons d'une citation en texte brut (« > > texte »).
_CHEVRONS = re.compile(r"^(\s*>)+ ?")


def sans_chevrons(ligne: str) -> str:
    """La ligne sans ses chevrons de citation — un transfert lu depuis le HTML
    (`_TexteDuHtml`) préfixe de « > » tout ce qui était dans un `<blockquote>`,
    marque de transfert comprise."""
    return _CHEVRONS.sub("", ligne)


def valeur_d_entete(ligne: str) -> str:
    """« *Envoyé :* mardi … » → « mardi … » : la valeur d'une ligne d'en-tête citée."""
    return ligne.split(":", 1)[1].strip().strip("*").strip() if ":" in ligne else ""


@dataclass(frozen=True)
class Transfert:
    """Un message transféré : la note de qui transfère, puis le message d'origine."""

    note: str
    #: L'en-tête « De : » du message d'origine, tel qu'écrit (« Nom <adresse> »).
    de: str
    adresse: str
    corps: str
    #: Sa date et son objet, tels qu'écrits — lus par `courriel_fil` (29/09/2026).
    date: str = ""
    objet: str = ""


def est_objet_de_transfert(sujet: str | None) -> bool:
    """L'objet annonce-t-il un transfert (« TR : », « Fwd: ») ?"""
    return bool(_OBJET_TRANSFERT.match(sujet or ""))


def _debut_d_entete(lignes: list[str], n: int) -> int | None:
    """La ligne où commence l'en-tête du message transféré, s'il commence à `n`.

    Trois formes (29/09/2026) :

    - une MARQUE (« Début du message réexpédié : », « ---- Message transféré ---- »)
      ou une ligne de SOULIGNÉS (Outlook, Mail pour Windows), suivie de « De : » ;
    - un bloc « De : … / Envoyé : … » SANS marque : Mail pour Windows l'écrit
      ainsi quand le HTML est réduit en texte, la ligne de soulignés étant un
      `<hr>` qui ne laisse rien. 🔴 Le premier transfert réel de Mail pour
      Windows a été lu comme une simple réponse, faute de cette forme.
    """
    nue = lignes[n].strip().strip("*")
    if _MARQUE_TRANSFERT.match(nue):
        #  Thunderbird écrit « Sujet : » et « Date : » AVANT « De : » (#1471).
        proches = [lg.strip().strip("*") for lg in lignes[n + 1 : n + 9]]
        return n + 1 if any(_DE.match(lg) for lg in proches) else None
    if _SEPARATEUR.match(nue):
        suivantes = [lg.strip().strip("*") for lg in lignes[n + 1 : n + 4] if lg.strip()]
        return n + 1 if suivantes and _DE.match(suivantes[0]) else None
    if MESSAGE_DU.match(nue):
        return n if any(_DE.match(lg.strip()) for lg in lignes[n + 1 : n + 4]) else None
    if _DE.match(nue) and any(_DATE_CITEE.match(lg.strip()) for lg in lignes[n + 1 : n + 6]):
        return n
    return None


def transfert_dans(sujet: str, texte: str, *, objet_exige: bool = True) -> Transfert | None:
    """Le message transféré, si ce courriel en est un — sinon None.

    L'objet décide d'abord : une RÉPONSE à un transfert (« RE: TR : … ») cite la
    marque de transfert dans son historique, et n'est pas un transfert.

    `objet_exige=False` : le corps seul décide — quand un membre du conseil CLASSE
    à la main un courriel dont il a réécrit l'objet (#2555, 06/11/2026 : « trou
    sur le mur à gauche du portillon ? » portait le message d'une résidente).
    """
    if objet_exige and not est_objet_de_transfert(sujet):
        return None
    lignes = [sans_chevrons(ligne) for ligne in texte.splitlines()]
    for n in range(len(lignes)):
        debut = _debut_d_entete(lignes, n)
        if debut is None:
            continue
        de, date, objet, fin = "", "", "", debut
        #  Le bloc d'en-têtes du message d'origine, jusqu'à la première ligne vide
        #  qui le suit.
        while fin < len(lignes) and (not lignes[fin].strip() or ":" in lignes[fin]):
            nue = lignes[fin].strip().strip("*")
            if not nue and de:
                break
            date_du = MESSAGE_DU.match(nue)
            if date_du:
                date = date or date_du.group(1)
            elif _DE.match(nue):
                de = de or valeur_d_entete(nue)
            elif _DATE_CITEE.match(nue):
                date = date or valeur_d_entete(nue)
            elif _OBJET_CITE.match(nue):
                objet = objet or valeur_d_entete(nue)
            fin += 1
        adresse = _ADRESSE.search(de)
        if not adresse:
            return None
        return Transfert(
            note="\n".join(lignes[:n]).strip(),
            de=de,
            adresse=adresse.group(0).lower(),
            corps="\n".join(lignes[fin:]).strip(),
            date=date,
            objet=objet,
        )
    return None
