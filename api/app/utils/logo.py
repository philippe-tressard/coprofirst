"""Le logo de la RÉSIDENCE — téléversé par l'administration, une seule porte (#1728).

Le logo était écrit en dur : un dessin SVG dans `pdf_theme.logo_svg` (un immeuble
marqué d'une touche dorée), un `favicon.svg` et deux icônes PNG figées au build.
Une autre copropriété aurait porté le logo de celle-ci sur ses affiches, ses
courriels et l'écran d'accueil de ses téléphones.

Arbitré le 08/10/2026 :

| Question | Réponse |
|---|---|
| formats | PNG ou JPEG seulement — famille « logo » de `utils/fichiers` |
| sans logo | le dessin sans la touche dorée, logo neutre de CoproFirst |
| menu, connexion | le logo remplace l'icône du catalogue s'il existe |
| courriels | une image par adresse publique, servie par `GET /config/logo.png` |

Le 09/10/2026, le logo neutre devient celui de CoproFirst : trois
immeubles bleus, une fenêtre allumée en or, sur une tuile blanche. Son dessin
vit dans `logo-neutre.svg` ; ce PNG et les icônes du front en sont les rendus.

Le fichier reçu est stocké tel quel dans le volume (`uploads/logo/`), et son NOM
dans la configuration (`site_logo`). Les tailles se dérivent à la demande
(`images.carre_png`) : aucun fichier produit n'est écrit à côté, donc rien à
tenir à jour quand le logo change.
"""

from __future__ import annotations

from pathlib import Path

from sqlmodel import Session

from app.utils.config_site import config_site
from app.utils.images import carre_png
from app.utils.liens import base_site
from app.utils.stockage import stockage

#: La clé de configuration qui porte le NOM du fichier stocké — publique : le
#: front s'en sert pour savoir qu'un logo existe et pour invalider son cache.
CLE_LOGO = "site_logo"

#: Le sous-dossier du volume des téléversements.
DOSSIER = "logo"

#: Les tailles servies — BORNÉES : la route est publique, et une taille libre
#: ferait redimensionner n'importe quoi à la demande de n'importe qui. Une borne
#: plutôt qu'une liste : chaque écran demande la sienne (22 px dans le menu, en
#: double densité), sans liste à recopier côté front.
TAILLE_MIN, TAILLE_MAX = 16, 512

#: Le logo neutre en PNG 512 px — le rendu de `logo-neutre.svg`, fait une fois (les
#: icônes de l'application installée et les courriels ne prennent pas de SVG).
#: 🔒 `test_logo_neutre.py` : il reste le rendu du dessin, et l'icône du front aussi.
NEUTRE_PNG = Path(__file__).with_name("logo-neutre.png")


def fichier_logo(session: Session) -> Path | None:
    """Le fichier du logo téléversé, ou None s'il n'y en a pas (ou plus sur disque).

    ⚠️ Le nom vient de la base : il est ramené à son dernier segment, si bien
    qu'une valeur forgée (`../…`) ne peut pas sortir du dossier du logo.
    """
    nom = (config_site(session, CLE_LOGO).get(CLE_LOGO) or "").strip()
    if not nom or Path(nom).name != nom:
        return None
    st = stockage()
    cle = f"{DOSSIER}/{nom}"
    return st.chemin(cle) if st.existe(cle) else None


def logo_png(session: Session, taille: int) -> bytes:
    """Le logo en PNG carré de `taille` px — celui de la résidence, sinon le neutre."""
    chemin = fichier_logo(session)
    try:
        return carre_png((chemin or NEUTRE_PNG).read_bytes(), taille)
    except ValueError:
        #  Un fichier devenu illisible ne doit pas casser un document ni un
        #  courriel : le neutre prend sa place.
        return carre_png(NEUTRE_PNG.read_bytes(), taille)


def logo_televerse_png(session: Session) -> bytes | None:
    """Le logo téléversé en PNG carré 512 px, ou None — à passer aux documents.

    Les documents (fiche arrivant, affiche de hall, manuel PDF) le reçoivent en
    PARAMÈTRE et le rendent par `pdf_theme.logo_html`, à la taille de leur
    gabarit : ils se composent sans session, et l'affiche choisit sa taille de
    logo selon son format.
    """
    if fichier_logo(session) is None:
        return None
    return logo_png(session, 512)


def adresse_logo(site_url: str | None, taille: int) -> str:
    """L'adresse PUBLIQUE du logo, pour ce qui le charge hors du site : un courriel.

    `/api` est le préfixe que Caddy retire avant l'API (`Caddyfile`, `handle
    /api/*`) — la même forme que `courriel_arrivee.FICHE_CONSIGNES`.
    """
    return f"{base_site(site_url)}/api/config/logo.png?taille={taille}"
