"""Le paragraphe de LICENCE des mentions légales, et ses deux phrases liées.

Le nom du logiciel renvoie à son site, « code source » au dépôt — jamais une
adresse écrite en clair (demande de l'auteur, 18/10/2026). Lus par le gabarit
(`contenus_legaux.DEFAULT_LEGAL`), par la démonstration (`demo/legal`) et par les
migrations 0270 et 0301, qui les posent dans les mentions déjà en base.

Séparé de `contenus_legaux.py`, qui dépassait 500 lignes (modularité, rang 1) :
le découpage suit la notion — ce que le texte dit du LOGICIEL —, pas un
intervalle de lignes.
"""

from app.utils.plateforme import (
    DEPOT_SOURCE,
    LICENCE_NOM,
    LICENCE_SPDX,
    LICENCE_URL,
    NOM_PLATEFORME,
    SITE_PLATEFORME,
)

#: Les deux phrases du paragraphe de licence qui portent un lien (Philippe, 18/10/2026) :
#: le NOM du logiciel renvoie à son site, « code source » au dépôt — jamais une adresse
#: écrite en clair. Lues de `utils/plateforme`, et par la 0301, qui les pose dans les
#: mentions déjà en base.
PHRASE_SERVI_PAR = (
    f'Ce site est servi par <a href="{SITE_PLATEFORME}" target="_blank" '
    f'rel="noopener noreferrer">{NOM_PLATEFORME}</a>,'
)
PHRASE_CODE_SOURCE = (
    f'Son <a href="{DEPOT_SOURCE}" target="_blank" rel="noopener noreferrer">code source</a> '
    "est publié ; celui de la version en service est accessible depuis le pied de chaque page."
)

#: Le paragraphe de licence des mentions légales (#1726, 08/10/2026) — UNE
#: écriture, lue par ce gabarit ET par la migration 0270, qui le pose dans les
#: mentions déjà en base à la place de celui de la Licence 5Hostachy.
PARAGRAPHE_LICENCE = (
    f"<p>{PHRASE_SERVI_PAR} un <strong>logiciel libre</strong> "
    "distribué sous la "
    f'<a href="{LICENCE_URL}" target="_blank" rel="noopener noreferrer">{LICENCE_NOM}</a> '
    f"({LICENCE_SPDX}). Chacun peut l'utiliser, l'étudier, le modifier et le "
    "redistribuer, y compris à titre commercial, à condition de publier ses "
    "modifications sous la même licence — y compris lorsqu'il le fait fonctionner "
    "comme service en ligne. " + PHRASE_CODE_SOURCE + "</p>"
)
