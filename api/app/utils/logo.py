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
(`images.carres_png`, aux `CRANS`) : aucun fichier produit n'est écrit à côté, donc rien à
tenir à jour quand le logo change.

## La variante SOMBRE (09/11/2026)

Un logo composé sur fond blanc porte ce fond avec lui : au thème sombre, le site
le pose sur une carte claire (`--color-fond-logo`), et l'on voit un cadre blanc.
L'administration peut donc téléverser une SECONDE image, dessinée pour le fond
sombre (traits clairs, fond transparent) : `site_logo_sombre`. Elle sert PARTOUT où
le logo se pose sur un fond sombre : l'écran au thème sombre, l'en-tête des
courriels, de la fiche arrivant et des affiches de hall, la page de garde et le
menu du manuel. L'onglet, l'icône de l'application et les rapports sur fond blanc
gardent le logo. Elle l'ACCOMPAGNE : sans logo, pas de variante — la retirer avec
lui évite une marque à moitié réglée.

Sans aucun logo téléversé, le fond sombre reçoit le dessin neutre « Ivoire »
(`logo-neutre-sombre.svg`, sans tuile blanche). Un logo téléversé SANS sa variante
reste lui-même sur fond sombre : on ne devine pas le dessin d'une résidence.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from sqlmodel import Session

from app.utils.config_site import config_site
from app import contexte
from app.utils.images import carres_png
from app.utils.liens import base_site
from app.utils.stockage import stockage

#: La clé de configuration qui porte le NOM du fichier stocké — publique : le
#: front s'en sert pour savoir qu'un logo existe et pour invalider son cache.
CLE_LOGO = "site_logo"

#: La variante d'un logo : celui de la résidence, ou son dessin pour le thème sombre.
Variante = Literal["clair", "sombre"]

#: La clé de configuration de chaque variante — publiques toutes deux.
CLE_LOGO_SOMBRE = "site_logo_sombre"
CLES: dict[str, str] = {"clair": CLE_LOGO, "sombre": CLE_LOGO_SOMBRE}

#: Le sous-dossier du volume des téléversements.
DOSSIER = "logo"

#: Les tailles servies — BORNÉES : la route est publique, et une taille libre
#: ferait redimensionner n'importe quoi à la demande de n'importe qui. Une borne
#: plutôt qu'une liste : chaque écran demande la sienne (22 px dans le menu, en
#: double densité), sans liste à recopier côté front.
TAILLE_MIN, TAILLE_MAX = 16, 512

#: Les tailles RÉELLEMENT produites : une demande prend le cran égal ou supérieur,
#: que l'écran réduit à sa taille d'affichage (`width`/`height`). Depuis #2396, le
#: logo se décode hors du process de l'API — un enfant par décodage : avec une
#: taille libre, une route publique ferait démarrer un process par valeur demandée.
#: Les crans se rendent tous ensemble, une fois par logo, puis se servent de mémoire.
CRANS = (16, 32, 48, 64, 96, 128, 192, 256, 384, 512)

#: Le logo neutre en PNG 512 px — le rendu de `logo-neutre.svg`, fait une fois (les
#: icônes de l'application installée et les courriels ne prennent pas de SVG).
#: 🔒 `test_logo_neutre.py` : il reste le rendu du dessin, et l'icône du front aussi.
NEUTRE_PNG = Path(__file__).with_name("logo-neutre.png")

#: Le même, dessiné pour un fond sombre — le rendu de `logo-neutre-sombre.svg`.
NEUTRE_SOMBRE_PNG = Path(__file__).with_name("logo-neutre-sombre.png")


def fichier_logo(session: Session, variante: Variante = "clair") -> Path | None:
    """Le fichier du logo téléversé, ou None s'il n'y en a pas (ou plus sur disque).

    ⚠️ Le nom vient de la base : il est ramené à son dernier segment, si bien
    qu'une valeur forgée (`../…`) ne peut pas sortir du dossier du logo.
    """
    cle_config = CLES[variante]
    nom = (config_site(session, cle_config).get(cle_config) or "").strip()
    if not nom or Path(nom).name != nom:
        return None
    st = stockage()
    cle = f"{DOSSIER}/{nom}"
    return st.chemin(cle) if st.existe(cle) else None


def cran(taille: int) -> int:
    """Le cran servi pour une taille demandée : le plus petit qui la couvre."""
    return next((c for c in CRANS if c >= taille), CRANS[-1])


def _carres(source: Path, place: str) -> dict[int, bytes] | None:
    """Les crans du fichier `source`, rendus une fois puis gardés en mémoire — None
    s'il est illisible.

    La clé est le NOM du fichier : un logo remplacé porte un nom neuf
    (`nom_stocke`), donc le cache ne sert jamais l'ancien. Un seul logo par
    copropriété : chaque `place` (« televerse », « neutre ») ne garde que son
    fichier courant, échec compris — sans quoi un fichier illisible referait
    démarrer un enfant à chaque requête publique.
    """
    memoire = contexte.etat("logo_carres")
    cle = str(source)
    courant = memoire.get(place)
    if courant is None or courant[0] != cle:
        try:
            rendus = carres_png(source.read_bytes(), CRANS)
        except ValueError:
            rendus = None
        courant = (cle, rendus)
        memoire[place] = courant  # un seul geste : jamais une clé sans ses rendus
    return courant[1]


def logo_png(session: Session, taille: int, variante: Variante = "clair") -> bytes:
    """Le logo en PNG carré au cran de `taille` — celui de la résidence, sinon le neutre.

    Un fichier devenu illisible ne doit pas casser un document ni un courriel :
    le neutre prend sa place. La variante sombre, absente ou illisible, rend le
    logo téléversé lui-même ; sans aucun logo, le neutre du fond sombre.
    """
    sombre = variante == "sombre"
    rendus = None
    if sombre and (chemin_sombre := fichier_logo(session, "sombre")):
        rendus = _carres(chemin_sombre, "televerse_sombre")
    chemin = fichier_logo(session)
    rendus = rendus or (_carres(chemin, "televerse") if chemin else None)
    if rendus is None and sombre:
        rendus = _carres(NEUTRE_SOMBRE_PNG, "neutre_sombre")
    rendus = rendus or _carres(NEUTRE_PNG, "neutre")
    if rendus is None:
        raise ValueError("le logo neutre est illisible")
    return rendus[cran(taille)]


def logo_televerse_png(session: Session, variante: Variante = "clair") -> bytes | None:
    """Le logo téléversé en PNG carré 512 px, ou None — à passer aux documents.

    Les documents (fiche arrivant, affiche de hall, manuel PDF) le reçoivent en
    PARAMÈTRE et le rendent par `pdf_theme.logo_html`, à la taille de leur
    gabarit : ils se composent sans session, et l'affiche choisit sa taille de
    logo selon son format.

    Un document qui pose le logo sur un fond SOMBRE demande `"sombre"` ici, et
    `sombre=True` à `logo_html` (le dessin neutre de ce fond, quand ceci rend None).
    """
    if fichier_logo(session) is None:
        return None
    return logo_png(session, 512, variante)


def adresse_logo(site_url: str | None, taille: int, variante: Variante = "clair") -> str:
    """L'adresse PUBLIQUE du logo, pour ce qui le charge hors du site : un courriel.

    `/api` est le préfixe que Caddy retire avant l'API (`Caddyfile`, `handle
    /api/*`) — la même forme que `courriel_arrivee.FICHE_CONSIGNES`.
    """
    suffixe = "&variante=sombre" if variante == "sombre" else ""
    return f"{base_site(site_url)}/api/config/logo.png?taille={taille}{suffixe}"
