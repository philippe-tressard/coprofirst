"""Photos stockées en tableau JSON — lecture et filtrage, une seule fois.

Trois routeurs désérialisaient le même champ chacun de leur côté (flux, calendrier,
uploads), et le modèle porte déjà trois noms pour la même notion (`photos_urls`,
`photos_json`, `images_json`). On ne peut pas renommer les colonnes sans migration
de données, mais rien n'oblige à dupliquer la logique par-dessus.
"""

import json
from typing import Optional

from app.utils.fichiers import est_image


def parse_photos(raw: Optional[str]) -> list[str]:
    """Tableau JSON stocké → liste d'URLs.

    Ne lève jamais : une valeur illisible en base ne doit pas faire échouer
    l'affichage de l'élément qui la porte. Le pire cas est une galerie vide.
    """
    if not raw:
        return []
    try:
        val = json.loads(raw) if isinstance(raw, str) else raw
        return [str(u) for u in val] if isinstance(val, list) else []
    except Exception:
        return []


#: 🔴 Les dossiers où vivent les photos et les pièces jointes d'un objet (#2157).
#:
#: `photos_internes` gardait toute adresse « des nôtres » — `prive/` (les
#: documents de la copropriété, servis par un endpoint qui juge `document_visible`),
#: `annonces-hall/`, `logo/`, `avatars/` compris. Une clé glissée dans les pièces
#: jointes d'une affaire partait alors en copie par courriel, contournant Caddy et
#: la règle de lecture. `tickets`, `publications` et `evenements` sont les dossiers
#: des pièces jointes d'avant `/fichier` : les affaires anciennes les citent encore.
DOSSIERS_DES_PIECES_JOINTES = frozenset(
    {"fichiers", "annonces", "residence", "tickets", "publications", "evenements"}
)

#: Les colonnes qui CITENT un fichier par son adresse (tableau JSON d'URLs).
COLONNES_DE_FICHIERS = ("photos_urls", "fichiers_urls", "images_json")


def _dans_les_pieces_jointes(cle: str | None) -> bool:
    return bool(cle) and cle.split("/", 1)[0] in DOSSIERS_DES_PIECES_JOINTES


def cles_citees(session) -> set[str]:
    """Les clés de fichier que la base cite encore, toutes tables confondues.

    Lues sur chaque colonne de `COLONNES_DE_FICHIERS` des tables déclarées : une
    table neuve qui joint des fichiers sous ce nom est couverte d'elle-même.
    """
    from sqlalchemy import select
    from sqlmodel import SQLModel

    from app.utils.stockage import cle_de_url

    cles: set[str] = set()
    for table in SQLModel.metadata.tables.values():
        for nom in COLONNES_DE_FICHIERS:
            if nom in table.c:
                for (valeur,) in session.execute(select(table.c[nom])):
                    cles.update(c for u in parse_photos(valeur) if (c := cle_de_url(u)))
    return cles


def photos_internes(urls: list[str]) -> list[str]:
    """Ne conserve que les URLs produites par notre propre endpoint d'upload.

    Sans ce filtre, une requête de modification pourrait injecter une URL
    arbitraire, servie ensuite dans un `<img src>` : au premier affichage, chaque
    résident révélerait son adresse IP à un tiers, avec un contenu hors de notre
    contrôle. Les champs de photos exposés en écriture ne servent qu'à RETIRER des
    images déjà téléversées — tout le reste est écarté sans discussion.
    """
    #  La règle d'une adresse « des nôtres » vit dans `stockage.cle_de_url` (#1748).
    from app.utils.stockage import cle_de_url

    return [str(u) for u in urls if _dans_les_pieces_jointes(cle_de_url(str(u)))]


def premiere_photo(raw: Optional[str]) -> Optional[str]:
    """Première photo de la galerie, ou None.

    Certains canaux ne portent QU'UNE image : le message WhatsApp, l'affiche de
    hall, l'en-tête d'un PDF. Avant l'unification du 10/08/2026, la publication
    portait pour cela une colonne `image_url` distincte — une seconde notion pour
    la même chose, que `Ticket` et `Evenement` n'avaient pas. Elle est devenue une
    galerie comme les autres ; « l'image du canal mono-image » se lit ici, une
    fois, et non dans chacun des six appelants.
    """
    urls = parse_photos(raw)
    return urls[0] if urls else None


def premiere_image(urls: Optional[list[str]]) -> Optional[str]:
    """Première IMAGE interne d'une liste d'URLs mêlant photos et documents, ou None.

    Une Suite ne connaît qu'une liste `fichiers_urls` : les photos y sont mêlées
    aux PDF, et le canal mono-image (WhatsApp) ne prend qu'une image. Les
    documents joints ne partent pas — d'où le filtre sur le type.
    """
    return next((u for u in photos_internes(urls or []) if est_image(u)), None)


def photos_json(urls: Optional[list]) -> str:
    """Liste reçue d'un client → colonne texte, filtrée. Contrepartie de `parse_photos`.

    Toujours passer par ici pour ÉCRIRE : le filtre `photos_internes` n'est pas
    une précaution de confort, c'est ce qui empêche une requête forgée de faire
    servir une URL étrangère dans un `<img src>` chez chaque résident. Écrite deux
    fois dans le même routeur, elle aurait fini par n'être filtrée qu'une fois.
    """
    return json.dumps(photos_internes([str(u) for u in (urls or [])]), ensure_ascii=False)
