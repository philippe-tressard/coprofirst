"""Nom d'un fichier téléversé sur disque — écrit une seule fois.

Deux routeurs construisaient ce nom chacun de leur côté (`uploads.py`,
`documents.py`) : même préfixe UUID, même assainissement, deux écritures. La
règle est de sécurité (elle protège `/app/uploads`, servi en statique) : elle
n'a pas à exister en double.

L'extension est un **paramètre** et non une déduction du nom fourni, parce que
les deux appelants n'ont pas la même contrainte :

  - `uploads.py` sert des fichiers en statique → l'extension décide du
    `Content-Type` renvoyé au navigateur, elle doit donc venir du type MIME
    validé, jamais de l'appelant ;
  - `documents.py` sert par un endpoint authentifié qui impose lui-même le
    `media_type` → il conserve l'extension d'origine, utile au diagnostic.
"""

import os
import re
import unicodedata
import uuid
from dataclasses import dataclass

from app.utils.demo import refuser_fichier_recu
from app.utils.stockage import DOSSIER_PRIVE, stockage

#: Les fichiers qui ne doivent JAMAIS être servis en statique vivent sous
#: `stockage.DOSSIER_PRIVE` — le pourquoi (48 fichiers exposés le 03/08/2026, un
#: sous-dossier du volume plutôt qu'un volume neuf) est écrit à côté de la
#: constante, et le blocage dans le `Caddyfile`.

# Assez long pour rester lisible dans une URL, assez court pour ne pas buter sur
# la limite de longueur de nom de fichier une fois le préfixe UUID ajouté.
_LONGUEUR_MAX_RADICAL = 60
_LONGUEUR_MAX_EXTENSION = 8


def radical_assaini(nom_origine: str | None) -> str:
    """Nom fourni par l'appelant → radical sûr : sans chemin, sans extension, ASCII.

    Les accents sont translittérés plutôt que remplacés par des `_` : « été.pdf »
    donne « ete » et non « _t_ ». Tout ce qui n'est ni lettre, ni chiffre, ni
    `-`/`_` disparaît — séparateurs de chemin compris, d'où l'absence de
    traversée possible.
    """
    brut = os.path.basename(nom_origine or "")
    radical = os.path.splitext(brut)[0]
    radical = unicodedata.normalize("NFKD", radical).encode("ascii", "ignore").decode()
    radical = re.sub(r"[^A-Za-z0-9_\-]", "_", radical)[:_LONGUEUR_MAX_RADICAL]
    return radical.strip("_") or "fichier"


def extension_assainie(nom_origine: str | None) -> str:
    """Extension du nom fourni, ramenée à `.xxx` alphanumérique minuscule.

    Réservée aux fichiers qui ne sont PAS servis en statique. Pour les autres,
    passer l'extension déduite du type MIME validé.
    """
    brute = os.path.splitext(os.path.basename(nom_origine or ""))[1]
    ext = re.sub(r"[^a-z0-9]", "", brute.lower())[:_LONGUEUR_MAX_EXTENSION]
    return f".{ext}" if ext else ""


#: Préfixe technique posé par `nom_stocke` : 32 caractères hexadécimaux et `_`.
#: Il rend l'URL non devinable et n'a aucun sens pour un lecteur.
_PREFIXE_UUID = re.compile(r"^[0-9a-f]{32}_", re.IGNORECASE)


def nom_lisible(chemin_ou_url: str | None) -> str:
    """Nom d'origine d'une pièce jointe, débarrassé du préfixe technique.

    Pendant Python de `nomFichier()` (front/src/lib/fichiers.ts) : même règle, deux
    langages. `api/tests/test_pieces_jointes.py` vérifie qu'elles ne divergent pas.

    Sans elle, une pièce jointe d'e-mail s'affiche « 0d41107a6c…lasseurs.pdf » dans
    la messagerie du destinataire — le nom que le client tronque par le milieu est
    justement celui qui portait le sens. Constaté le 03/08/2026 sur un e-mail réel.

    Les fichiers téléversés avant cette date sont nommés `{uuid}.pdf` : il n'y a
    aucun nom d'origine à restituer, on rend le nom tel quel.
    """
    base = os.path.basename(chemin_ou_url or "")
    return _PREFIXE_UUID.sub("", base) or base


def chemins_locaux(urls: list[str]) -> list[str]:
    """URLs internes `/uploads/…` → chemins locaux existants, pour les joindre à un e-mail.

    Écrite deux fois à l'identique (`tickets.py`, `publications.py`) et attendue
    une troisième pour le calendrier. Trois vérifications, toutes nécessaires :
    l'URL doit être l'une des nôtres, le chemin résolu doit rester SOUS la racine
    des téléversements (sans quoi `/uploads/../../etc/passwd` sortirait du bac à
    sable et partirait en pièce jointe), et le fichier doit exister — une URL
    orpheline ne doit pas faire échouer l'envoi.
    """
    #  Les trois vérifications vivent dans `stockage.fichier_de_url` (#1748). Elle
    #  traduisait ici l'adresse en `"/app" + url` : une racine écrite en dur, fausse
    #  dès que le volume est monté ailleurs — et pour toute autre copropriété.
    st = stockage()
    return [str(chemin) for url in urls if (chemin := st.fichier_de_url(url)) is not None]


def nom_stocke(nom_origine: str | None, extension: str) -> str:
    """`{uuid}_{radical}{extension}` — collision impossible, nom d'origine lisible.

    Le préfixe UUID rend l'URL non devinable ; le radical conserve un nom
    parlant, sans quoi une pièce jointe s'affiche « a3f8…c2.pdf » partout où on
    la référence.
    """
    ext = extension if (not extension or extension.startswith(".")) else f".{extension}"
    return f"{uuid.uuid4().hex}_{radical_assaini(nom_origine)}{ext}"


#  Même expression que `EXTENSIONS_IMAGE` dans front/src/lib/fichiers.ts : une
#  règle, deux langages, et `tests/test_pieces_jointes.py` vérifie qu'elles ne
#  divergent pas — comme pour `nom_lisible` / `nomFichier`.
_EXTENSIONS_IMAGE = re.compile(r"\.(jpe?g|png|webp|gif|avif|bmp|tiff?|heic|heif)$", re.IGNORECASE)


def est_image(chemin_ou_url: str | None) -> bool:
    """Une pièce jointe est-elle une image ?

    Sert à annoncer la NATURE des pièces jointes dans le sommaire d'un e-mail :
    « 1 photo » plutôt que « 1 pièce jointe » quand on peut le dire. Le
    destinataire sait alors s'il doit ouvrir la pièce ou s'il l'a déjà vue dans
    le corps du message.
    """
    return bool(_EXTENSIONS_IMAGE.search(chemin_ou_url or ""))


def libelle_pieces_jointes(noms: list[str]) -> str:
    """« 1 photo », « 2 documents », « 1 photo et 2 documents »…

    Le décompte seul (« 3 pièces jointes ») oblige à ouvrir pour savoir de quoi
    il s'agit. La nature est déductible de l'extension : autant la donner.
    """
    photos = sum(1 for n in noms if est_image(n))
    docs = len(noms) - photos
    morceaux = []
    if photos:
        morceaux.append(f"{photos} photo" + ("s" if photos > 1 else ""))
    if docs:
        morceaux.append(f"{docs} document" + ("s" if docs > 1 else ""))
    if not morceaux:
        return ""
    return " et ".join(morceaux)


#  Les signatures de fichier vivent dans `signatures_fichiers` (31/10/2026, #2388) :
#  ce module tenait sa limite de 500 lignes. Ré-exportée pour les appelants.
from app.utils.signatures_fichiers import signature_incoherente  # noqa: E402


#  ── Les familles de téléversement : trois règles, une table ─────────────────
#
#  🔴 LE DÉFAUT QUE CETTE TABLE SUPPRIME (#1026, 19/09/2026). Le téléversement
#  avait TROIS écritures sur disque, et elles n'appliquaient pas les mêmes
#  règles :
#
#  | Chemin | Types | Plafond | Signature |
#  |---|---|---|---|
#  | documents privés (ici) | AUCUN | AUCUN | oui |
#  | images (`routers/uploads`) | oui | oui | réencodage PIL |
#  | documents joints (`routers/uploads`) | oui | oui | oui, **recopiée d'ici** |
#
#  Et trois imports Excel n'avaient **aucun** contrôle : ni type, ni taille.
#
#  ⚠️ Une duplication de règle de sécurité ne produit **aucun signal**. Un
#  fichier accepté à tort ne fait pas de bruit : il est stocké, servi, et
#  personne ne se plaint. On ne l'apprend que le jour où quelqu'un s'en sert.
#
#  C'est aussi ce qui rendait le défaut invisible : il n'existait **aucune
#  table** où lire ce que chaque chemin acceptait. Les trois règles vivent
#  maintenant côte à côte, et `test_televersement_source_unique.py` refuse
#  qu'une famille en oublie une.


@dataclass(frozen=True)
class FamilleFichier:
    """Ce qu'une famille de fichiers reçus accepte, et sous quelle taille.

    Les trois champs sont **obligatoires** : une famille sans plafond est un
    téléversement sans plafond, et c'est précisément ce qui existait pour les
    documents privés.
    """

    #: Types MIME annoncés par le client. Ils ne prouvent rien — c'est la
    #: signature qui tranche —, mais ils écartent d'emblée ce qui n'a rien à
    #: faire là, et ils choisissent l'extension.
    types: dict[str, str]
    #: Plafond, en mégaoctets. La raison de chaque valeur est en commentaire.
    plafond_mo: int
    #: Les extensions que la famille peut produire, dérivées de `types`. Le nom
    #: fourni par le client ne décide JAMAIS de l'extension écrite sur disque :
    #: `/uploads/*` est servi en statique, et Caddy pose le `Content-Type`
    #: d'après l'extension du fichier.
    extensions: tuple[str, ...]


_TYPES_IMAGE = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
    #  Ajoutés le 31/10/2026 (#2388) : toute image se joint, et toutes repartent
    #  en JPEG (`images.enregistrer_image_recue`), métadonnées retirées. HEIC et
    #  HEIF (iPhone) le 31/10/2026 (#2389), en décodage seul : libheif + libde265
    #  (LGPL), sans l'encodeur x265 (GPLv2) des roues PyPI — `api/Dockerfile`.
    #  🔴 Le SVG est REFUSÉ et doit le rester : c'est un document, qui porte du
    #  script, et servi depuis `/uploads/` il s'exécuterait sur notre origine.
    "image/avif": ".avif",
    "image/bmp": ".bmp",
    "image/tiff": ".tiff",
    "image/heic": ".heic",
    "image/heif": ".heif",
}

_TYPES_DOCUMENT = {
    "application/pdf": ".pdf",
    "application/msword": ".doc",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "application/vnd.ms-excel": ".xls",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
    #  Texte brut accepté le 16/08/2026 : l'écran le proposait, le serveur le
    #  refusait en 400. `.zip` n'est PAS accepté et ne doit pas l'être — une
    #  archive transporte un contenu arbitraire que rien n'inspecte, et le
    #  fichier est ensuite servi aux résidents. Décision explicite.
    "text/plain": ".txt",
}

_TYPES_TABLEUR = {
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
    "application/vnd.ms-excel": ".xls",
}


def _famille(types: dict[str, str], plafond_mo: int) -> "FamilleFichier":
    """Dérive `extensions` de `types` — deux listes recopiées divergeraient."""
    return FamilleFichier(
        types=types,
        plafond_mo=plafond_mo,
        extensions=tuple(sorted(set(types.values()))),
    )


FAMILLES: dict[str, FamilleFichier] = {
    #  Une photo est réencodée en JPEG : le plafond porte sur ce qui ARRIVE.
    "image": _famille(_TYPES_IMAGE, plafond_mo=5),
    #  Une pièce jointe de commentaire ou d'actualité.
    "document": _famille(_TYPES_DOCUMENT, plafond_mo=15),
    #  🔴 Les documents de la copropriété — PV d'assemblée, plans, rapports de
    #  diagnostic. Ils n'avaient AUCUN plafond jusqu'au 19/09/2026.
    #
    #  ⚠️ 30 Mo est un **changement de comportement** : un document plus gros
    #  était accepté avant, et sera refusé. La valeur est choisie au-dessus de
    #  ce que produit un scan de PV d'assemblée générale (10 à 20 Mo observés),
    #  et elle borne un envoi accidentel ou malveillant — elle ne filtre pas un
    #  usage réel. La relever est une décision d'une ligne ; ne pas en avoir du
    #  tout n'en était pas une.
    #
    #  Le Markdown en plus : le règlement de copropriété se joint en `.md`, que
    #  l'assistant lit (`question_reglement/texte.EXTENSIONS_LUES`) — accepté
    #  depuis toujours, puisque cette famille n'était pas appliquée avant #2156.
    "document_prive": _famille(
        _TYPES_DOCUMENT | _TYPES_IMAGE | {"text/markdown": ".md"}, plafond_mo=30
    ),
    #  Un fichier d'import d'accès est une LISTE, pas un scan — et il est lu
    #  intégralement en mémoire par l'analyseur. Le plafond y protège la mémoire
    #  du Raspberry Pi autant qu'il contrôle l'entrée.
    "tableur": _famille(_TYPES_TABLEUR, plafond_mo=5),
    #  Le logo de la résidence (#1728) : PNG ou JPEG SEULEMENT, arbitré le
    #  08/10/2026. Un SVG peut porter du script, et le logo est servi
    #  publiquement et inséré dans les documents et les courriels.
    "logo": _famille({"image/png": ".png", "image/jpeg": ".jpg"}, plafond_mo=2),
}


#: Les types qu'un navigateur annonce quand il ne sait pas : sous Windows, un `.md`
#: ou un `.docx` part souvent sans type, ou en `application/octet-stream`.
TYPES_INDETERMINES = frozenset({"", "application/octet-stream"})


def type_annonce(content_type: str | None, nom: str | None, famille: str) -> str | None:
    """Le type à juger : celui du client, ou — s'il est INDÉTERMINÉ — celui que
    l'extension désigne parmi les types de la famille (#2156).

    L'extension retenue reste celle du type, que la signature du contenu confronte ;
    une extension hors de la famille reste refusée.
    """
    if (content_type or "") not in TYPES_INDETERMINES:
        return content_type
    extension = extension_assainie(nom or "")
    par_extension = {ext: t for t, ext in FAMILLES[famille].types.items()}
    return par_extension.get(extension, content_type)


def lire_fichier_recu(fichier, famille: str) -> bytes:
    """Les octets d'un fichier reçu — au plus le plafond de sa famille (#2164).

    🔴 Le corps entier était lu AVANT d'être comparé au plafond : rien ne bornait la
    mémoire d'une requête sur le Raspberry Pi. Un octet de trop suffit à refuser (413).
    """
    from fastapi import HTTPException

    regles = FAMILLES.get(famille)
    if regles is None:
        raise ValueError(f"Famille de fichier inconnue : {famille!r}")
    plafond = regles.plafond_mo * 1024 * 1024
    octets = fichier.file.read(plafond + 1)
    if len(octets) > plafond:
        raise HTTPException(413, f"Fichier trop volumineux (max {regles.plafond_mo} Mo).")
    return octets


def verifier_fichier_recu(
    octets: bytes,
    nom_origine: str | None,
    content_type: str | None,
    famille: str,
    user=None,
) -> str:
    """Applique les TROIS règles de la famille, et rend l'extension à écrire.

    Lève une `HTTPException` au premier refus — 400 pour un type ou un contenu
    incohérent, 413 pour un dépassement de taille.

    ⚠️ Rend l'**extension dérivée du type**, jamais celle du nom fourni :
    `/uploads/*` est servi en statique, et Caddy pose le `Content-Type` d'après
    l'extension du fichier sur disque. Un `.html` téléversé sous un type MIME
    autorisé s'exécuterait sur notre origine.
    """
    import logging

    from fastapi import HTTPException

    regles = FAMILLES.get(famille)
    #  Une famille inconnue est une faute de programmation, pas une entrée
    #  utilisateur : lever tôt vaut mieux que de deviner un défaut permissif.
    if regles is None:
        raise ValueError(f"Famille de fichier inconnue : {famille!r}")

    if content_type not in regles.types:
        attendus = ", ".join(sorted(regles.extensions))
        raise HTTPException(400, f"Format non supporté : {content_type}. Attendu : {attendus}.")

    plafond = regles.plafond_mo * 1024 * 1024
    if len(octets) > plafond:
        raise HTTPException(413, f"Fichier trop volumineux (max {regles.plafond_mo} Mo).")

    extension = regles.types[content_type]

    #  🔴 LE CONTENU DOIT CORRESPONDRE À CE QU'IL PRÉTEND ÊTRE (#773). Le
    #  `content_type` vient du client : seule la signature du fichier tranche.
    motif = signature_incoherente(octets[:16], extension)
    if motif:
        logging.getLogger("app").warning(
            "Téléversement refusé (utilisateur %s) : %s", getattr(user, "id", "?"), motif
        )
        raise HTTPException(400, f"Fichier refusé : {motif}.")

    return extension


def enregistrer_fichier_recu(
    octets: bytes,
    nom_origine: str | None,
    content_type: str | None,
    famille: str,
    dossier: str,
    user=None,
    extension_forcee: str | None = None,
    session=None,
) -> str:
    """Contrôle **puis** écrit un fichier reçu. Rend le nom stocké.

    Le **seul** endroit où des octets venus du réseau atteignent le disque :
    `test_televersement_source_unique.py` refuse toute autre écriture, hors un
    fichier que l'application a elle-même produit.

    :param dossier: le répertoire (`photos`, `logo`…) du stockage de la copropriété servie.
    :param extension_forcee: celle d'une image réencodée ; le contrôle porte sur le type reçu.
    """
    refuser_fichier_recu()  # la démo publique n'en reçoit aucun (#1901)
    extension = verifier_fichier_recu(octets, nom_origine, content_type, famille, user)
    nom = nom_stocke(nom_origine, extension_forcee or extension)
    from app.models.fichiers_recus import noter_auteur  # différé : cycle via models (#2241)

    noter_auteur(session, user, f"{dossier}/{nom}")  # servi en direct : son auteur (#2154)
    stockage().ecrire(f"{dossier}/{nom}", octets)
    return nom


def enregistrer_televersement(file, raw_name: str, user=None) -> str:
    """Valide un fichier téléversé et l'écrit sur disque. Rend sa CLÉ (`prive/…`).

    ## 🔴 Pourquoi ce geste est ici et non chez les appelants (#825)

    `signature_incoherente` était bien factorisée, et son commentaire l'affirmait
    en toutes lettres : *« la règle vit dans `utils/fichiers` et n'est écrite
    qu'une fois — les quatre points de téléversement l'appellent »*.

    C'était vrai de la RÈGLE, et faux de son EMPLOI. Le geste complet — lire
    seize octets, rembobiner le flux, assainir l'extension, vérifier, journaliser
    le refus, lever une 400, composer le nom de destination, copier — était
    recopié **trois fois** au caractère près : `compteurs.py`, `diagnostics.py`,
    `documents.py`.

    ⚠️ C'est une duplication de SÉCURITÉ, et chaque ligne compte :

    * sans `seek(0)`, le fichier écrit perd ses seize premiers octets — il est
      corrompu, silencieusement, et personne ne s'en aperçoit avant de l'ouvrir ;
    * sans le `raise`, la vérification ne bloque rien : elle journalise et laisse
      passer ;
    * sans `nom_stocke`, le nom fourni par le client atteint le disque.

    Une copie qui oublie l'une des trois n'échoue pas : elle fonctionne, mal.
    C'est exactement ce qu'une règle recopiée finit par produire.

    ⚠️ `user` sert au JOURNAL, et il est optionnel : un appelant sans utilisateur
    identifié doit pouvoir valider quand même. `getattr(user, "id", "?")` plutôt
    que `user.id` — un refus qui plante sur le journal ne refuse plus rien.
    """
    #  🔴 LA FAMILLE « document_prive », enfin appliquée (#2156). Elle était
    #  déclarée — types, plafond de 30 Mo — et n'avait AUCUN appelant : ce geste
    #  ne contrôlait que la cohérence de la signature avec l'extension FOURNIE.
    #  Un fichier de n'importe quel type et de n'importe quelle taille entrait.
    #  Les trois règles, l'extension tirée du TYPE et l'écriture : la porte unique.
    octets = lire_fichier_recu(file, "document_prive")
    nom = enregistrer_fichier_recu(
        octets,
        raw_name,
        type_annonce(file.content_type, raw_name, "document_prive"),
        "document_prive",
        DOSSIER_PRIVE,
        user=user,
    )
    #  La CLÉ, que la ligne de la base garde (`fichier_cle`, #1816) —
    #  `stockage().colonnes(cle)`.
    return f"{DOSSIER_PRIVE}/{nom}"


async def lire_tableur_recu(fichier, user=None) -> bytes:
    """Lit un classeur importé et applique la famille « tableur » AVANT de l'analyser.

    🔴 Les trois règles précèdent la lecture du classeur (#1026). Les imports
    n'avaient AUCUN contrôle : ni type, ni taille — le corps entier était lu en
    mémoire puis passé à l'analyseur. Le plafond de la famille protège donc la
    mémoire du Raspberry Pi autant qu'il contrôle l'entrée : un fichier d'import
    est une LISTE, pas un scan, et rien ne borne le corps d'une requête en amont.

    ⚠️ Rien n'est écrit sur disque, et c'est voulu : le classeur est analysé puis
    jeté. On appelle donc `verifier_fichier_recu`, pas `enregistrer_fichier_recu`.
    Écrit une seule fois pour les trois imports (télécommandes, Vigik, lots) : la
    recopie du geste en était à dix lignes de commentaire par routeur.
    """
    contenu = lire_fichier_recu(fichier, "tableur")
    verifier_fichier_recu(contenu, fichier.filename, fichier.content_type, "tableur", user)
    return contenu
