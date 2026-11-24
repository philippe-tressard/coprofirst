"""La politique dit qui lit quoi, les personnes sans compte, et ce qui part vers un téléphone.

Audit de cohérence du 23/11/2026 — #2917, #2957, #2981. Chaque entrée de `ACCES` lie une
phrase de la politique à un DÉCLENCHEUR dans le code, comme `EXIGENCES` dans
`test_politique_confidentialite_couvre_le_code.py` : tant que le code fait la chose, la
phrase doit être là ; le jour où il cesse, le test le dit, et la phrase se relit.

⚠️ Il lit le GABARIT ; le texte servi se corrige par migration (0349).
"""

from __future__ import annotations

import pathlib
import re

from app.seed import contenus_legaux_destinataires as destinataires
from app.seed.contenus_legaux import DEFAULT_LEGAL

_API = pathlib.Path(__file__).resolve().parents[1]
_APP = _API / "app"
_CONTRAT = _API.parent / "docs" / "contrat-sous-traitance-modele.md"


def _politique() -> str:
    return DEFAULT_LEGAL["politique_confidentialite"]


def _texte() -> str:
    """La politique en minuscules, sans balises ni espaces insécables."""
    sans = re.sub(r"<[^>]+>", " ", _politique()).replace("\xa0", " ")
    return re.sub(r"\s+", " ", sans).lower()


#: (ce que le code fait, déclencheur (fichier, motif), phrase exigée dans la politique)
ACCES = [
    (
        "un résident lit le nom de l'auteur d'une annonce, et son adresse par défaut",
        ("routers/annonces.py", "contact_visible: bool = True"),
        "une annonce, avec votre nom et votre adresse électronique, sauf si vous décochez",
    ),
    (
        "un résident lit le bâtiment et la qualité de l'auteur d'une réponse",
        ("utils/reponses.py", "batiment"),
        "votre bâtiment et votre qualité",
    ),
    (
        "l'annonce d'arrivée part à toute la copropriété",
        ("utils/annonce_arrivee.py", "public_cible=None"),
        "l'annonce de votre arrivée",
    ),
    (
        "le locataire lit l'adresse et le téléphone de son bailleur",
        ("routers/bailleur/acces.py", "bailleur_telephone="),
        "votre locataire lit votre nom, votre adresse électronique et votre téléphone",
    ),
    (
        "un copropriétaire retrouve un compte de locataire, adresse masquée",
        ("routers/bailleur/baux.py", "email_masque=adresse_masquee"),
        "dont il ne voit qu'une forme masquée",
    ),
    (
        "le bailleur saisit l'identité d'un locataire qui peut n'avoir pas de compte",
        ("models/bailleur.py", "locataire_email"),
        "personnes sans compte",
    ),
    (
        "un bail part avec le compte du bailleur, et pas avant",
        ("utils/suppression_compte.py", "LocationBail.bailleur_id == user_id"),
        "conservés tant que le compte du bailleur existe",
    ),
    (
        "seule l'alerte d'une actualité urgente part vers un téléphone",
        ("utils/push/porte.py", 'TYPE_POUSSE = "urgence"'),
        "seule l'alerte d'une actualité marquée urgente",
    ),
    (
        "un téléphone part avec le compte, et après 60 jours sans renouvellement",
        ("utils/push/appareils.py", "def purger_abandonnes"),
        "sans que l'application l'ait renouvelé",
    ),
]


def _declencheur(fichier: str, motif: str) -> bool:
    chemin = _APP / fichier
    return chemin.exists() and motif in chemin.read_text(encoding="utf-8")


def test_chaque_acces_du_code_est_dit_par_la_politique():
    texte = _texte()
    assert len(texte) > 1500, "la politique lue est trop courte : INCONNU"
    manquants = [
        f"  {quoi} — attendu : « {phrase} »"
        for quoi, (fichier, motif), phrase in ACCES
        if _declencheur(fichier, motif) and phrase.lower() not in texte
    ]
    assert not manquants, "La politique ne dit pas ce que le code ouvre :\n" + "\n".join(manquants)


def test_aucune_phrase_ne_survit_au_code_qu_elle_decrit():
    """Le défaut inverse : un accès retiré, une phrase qui le promet encore."""
    orphelins = [
        f"  {quoi} — déclencheur absent : {fichier} / « {motif} »"
        for quoi, (fichier, motif), _ in ACCES
        if not _declencheur(fichier, motif)
    ]
    assert not orphelins, (
        "Le code a changé : relire la phrase de la politique, puis l'entrée d'ACCES :\n"
        + "\n".join(orphelins)
    )


def test_la_politique_ne_reserve_plus_les_donnees_au_conseil():
    """🔴 Le défaut exact : « accessibles uniquement » au conseil et à l'administrateur."""
    assert destinataires.ACCES_ANCIEN not in _politique()
    assert "accessibles uniquement" not in _texte()
    assert destinataires.QUI_LIT_QUOI in _politique()


def test_les_puces_neuves_sont_dans_leur_section():
    politique = _politique()
    s2 = politique.index("<h2>2.")
    s3 = politique.index("<h2>3.")
    s5 = politique.index("<h2>5.")
    s6 = politique.index("<h2>6.")
    assert s2 < politique.index(destinataires.PERSONNES_SANS_COMPTE) < s3
    assert s5 < politique.index(destinataires.CONSERVATION_BAUX) < s6


def test_la_puce_push_ne_dit_plus_que_tout_avis_part():
    """#2981 : « l'envoi porte EN PLUS un niveau urgent » laissait croire que tout part."""
    from app.seed.contenus_legaux_notifications import NOTIFICATIONS_PUSH_ANCIEN

    assert "en plus un niveau" in NOTIFICATIONS_PUSH_ANCIEN  # le témoin
    assert "en plus un niveau" not in _texte()
    assert NOTIFICATIONS_PUSH_ANCIEN not in _politique()


#: Chaque famille de services tiers de la politique (titre de sa puce), et le mot qui la
#: nomme dans l'article 4.5 du contrat de sous-traitance modèle.
FAMILLES_AU_CONTRAT = {
    "diffusion sur une messagerie instantanée": "messagerie instantanée",
    "assistant de rédaction (modèle de langage)": "assistant de rédaction",
    "acheminement des courriels": "envoi et réception des courriels",
    "réception des courriels": "envoi et réception des courriels",
    "notifications sur téléphone (applications ios et android)": "notifications sur téléphone",
}


def _familles_de_la_politique() -> list[str]:
    politique = _politique()
    m = re.search(r"Services tiers qui reçoivent des données\.</strong>", politique)
    assert m, "l'intitulé des services tiers n'est plus dans la politique : INCONNU"
    liste = politique[m.end() :].split("<ul>", 1)[1].split("</ul>", 1)[0]
    titres = re.findall(r"<li><strong>([^<]+)</strong>", liste)
    return [t.replace("\xa0", " ").strip().lower() for t in titres]


def test_le_contrat_modele_nomme_chaque_famille_de_services_tiers():
    """#2957 : la politique en comptait cinq, le contrat modèle trois."""
    familles = _familles_de_la_politique()
    assert len(familles) >= 5, f"{familles} : INCONNU"
    inconnues = [f for f in familles if f not in FAMILLES_AU_CONTRAT]
    assert not inconnues, (
        f"Familles de la politique sans correspondance au contrat modèle : {inconnues} — "
        "l'ajouter à l'article 4.5 et, si l'opérateur la fournit, à l'annexe 3"
    )
    contrat = re.sub(r"\s+", " ", _CONTRAT.read_text(encoding="utf-8")).lower()
    article = contrat.split("## article 5", 1)[0]
    absents = sorted(
        {FAMILLES_AU_CONTRAT[f] for f in familles}
        - {m for m in FAMILLES_AU_CONTRAT.values() if m in article}
    )
    assert not absents, f"Le contrat modèle (art. 4.5) ne nomme pas : {absents}"
    annexe = contrat.split("## annexe 3", 1)[1].split("## annexe 4", 1)[0]
    assert "relais de notifications" in annexe, (
        "l'annexe 3 ne prévoit pas le relais de notifications (#2957, accord du 23/11/2026)"
    )
