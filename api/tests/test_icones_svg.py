"""Garde-fou : un tracé SVG n'est dessiné qu'à un seul endroit du dépôt.

## Ce que ce fichier empêche

Le logo WhatsApp a été dessiné **six fois**, avec **deux tracés différents**. On
l'a consolidé côté site le 08/08/2026 — et la consolidation s'est arrêtée à la
frontière `front/` / `api/` : une copie survivait dans `utils/fiche_arrivant.py`,
avec deux caractères d'écart, et personne ne le savait. Le 14/08/2026, le même
examen a trouvé le **logo 5Hostachy** dessiné deux fois côté serveur, alors que
`CLAUDE.md` désigne `utils/pdf_theme.py` comme sa source unique depuis toujours.

Une consigne écrite n'a donc empêché ni la première recopie, ni la deuxième, ni
la troisième. C'est le sens de `standards/05-tests-et-garde-fous.md` : un défaut
corrigé sans garde-fou revient. Celui-ci échoue, et c'est tout ce qui compte.

## Pourquoi deux catalogues et non un seul fichier

Les contextes de build Docker sont `./api` et `./front` (`docker-compose.yml`) :
un fichier posé à la racine du dépôt n'entre dans **aucune** des deux images.
« Une source lue des deux côtés » supposerait d'élargir les deux contextes, donc
de toucher la chaîne de déploiement des deux RPi pour un sujet d'affichage.

Le catalogue est donc copié, et c'est ce fichier-ci qui rend la copie sûre : elle
ne peut pas diverger d'un octet sans que la CI le dise. Même pattern que
`docs/manuel-utilisateur.html` → `front/static/`.

Régénérer la copie après avoir modifié la source :

    cp front/src/lib/icones-svg.json api/app/utils/icones-svg.json
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parents[2]
CATALOGUE_FRONT = RACINE / "front" / "src" / "lib" / "icones-svg.json"
CATALOGUE_API = RACINE / "api" / "app" / "utils" / "icones-svg.json"

#: Les arbres de code où un tracé recopié serait une duplication évitable.
#:
#: `front/static/` en est **exclu** volontairement : un fichier servi tel quel au
#: navigateur (favicon, image d'installation PWA) est un format de livraison, pas
#: une recopie qu'on pourrait factoriser avec du Python.
SOURCES = (
    (RACINE / "front" / "src", ("*.svelte", "*.ts")),
    (RACINE / "api" / "app", ("*.py",)),
)

#: Un attribut `d="…"` de chemin SVG, dès qu'il est assez long pour être un
#: dessin et non un fragment (`d="M 0 0"` d'un test, par exemple).
_TRACE = re.compile(r'\sd="(M[^"]{24,})"')


def _fichiers_source():
    for racine, motifs in SOURCES:
        for motif in motifs:
            for chemin in racine.rglob(motif):
                if "node_modules" in chemin.parts or "__pycache__" in chemin.parts:
                    continue
                yield chemin


def _exige(chemin: Path) -> str:
    """Lit un fichier attendu, ou fait **échouer** le test s'il manque.

    Jamais `pytest.skip` : un contrôle qui ne peut pas s'exécuter renvoie INCONNU,
    pas OK (`standards/04-fiabilite-des-controles.md`). Un catalogue disparu doit
    faire rougir la CI, pas la laisser verte sur zéro vérification.
    """
    if not chemin.is_file():
        pytest.fail(f"Fichier attendu introuvable : {chemin.relative_to(RACINE)}")
    return chemin.read_text(encoding="utf-8")


def test_les_deux_catalogues_sont_identiques():
    """La copie serveur ne diverge pas de la source, fût-ce d'un octet."""
    front = CATALOGUE_FRONT.read_bytes() if CATALOGUE_FRONT.is_file() else None
    api = CATALOGUE_API.read_bytes() if CATALOGUE_API.is_file() else None
    assert front is not None, f"Catalogue source absent : {CATALOGUE_FRONT}"
    assert api is not None, f"Copie serveur absente : {CATALOGUE_API}"
    assert front == api, (
        "Les deux catalogues d'icônes ont divergé. Régénérer la copie :\n"
        "    cp front/src/lib/icones-svg.json api/app/utils/icones-svg.json"
    )


def test_le_catalogue_est_un_json_utf8_sans_bom_ni_crlf():
    """Un BOM ou des CRLF casseraient l'égalité octet pour octet au premier commit."""
    brut = CATALOGUE_FRONT.read_bytes()
    assert not brut.startswith(b"\xef\xbb\xbf"), "BOM dans le catalogue d'icônes"
    assert b"\r\n" not in brut, "Fins de ligne CRLF dans le catalogue d'icônes"
    assert json.loads(brut.decode("utf-8")), "Catalogue d'icônes vide"


def test_aucun_trace_du_catalogue_n_est_recopie_dans_le_code():
    """Une icône du catalogue ne se redessine nulle part — ni côté site, ni côté serveur."""
    catalogue = json.loads(_exige(CATALOGUE_FRONT))
    #  Une icône du catalogue est une suite d'éléments (`<path/><circle/>…`) : on
    #  y ré-applique la même expression que sur le code, pour comparer des choses
    #  de même nature — des attributs `d`, et non une chaîne d'éléments entière.
    connus: dict[str, str] = {}
    for nom, elements in catalogue.items():
        for trace in _TRACE.findall(elements):
            connus[trace] = nom

    fautes = []
    for chemin in _fichiers_source():
        for trace in _TRACE.findall(chemin.read_text(encoding="utf-8", errors="ignore")):
            if trace in connus:
                fautes.append(f"{chemin.relative_to(RACINE)} redessine l'icône « {connus[trace]} »")

    assert not fautes, (
        "Des icônes du catalogue sont redessinées en dur :\n  - "
        + "\n  - ".join(fautes)
        + "\nUtiliser `<Icon name=… />` côté site, `pdf_theme.icone_svg(…)` côté serveur."
    )


def test_aucun_trace_n_est_dessine_dans_deux_fichiers():
    """Le contrôle général : deux fichiers qui portent le même tracé, c'est une copie.

    C'est ainsi que le logo 5Hostachy s'est retrouvé dans `pdf_theme.py` **et**
    dans `email/gabarit.py` — deux logos le jour où l'un des deux bouge, sans que
    rien ne le signale. Ce test ne connaît ni le logo ni les icônes : il ne
    connaît que la duplication.
    """
    origines: dict[str, set[str]] = {}
    for chemin in _fichiers_source():
        for trace in _TRACE.findall(chemin.read_text(encoding="utf-8", errors="ignore")):
            origines.setdefault(trace, set()).add(str(chemin.relative_to(RACINE)))

    doublons = {t: sorted(f) for t, f in origines.items() if len(f) > 1}
    assert not doublons, "Tracés SVG présents dans plusieurs fichiers :\n" + "\n".join(
        f"  - {' , '.join(fichiers)} → {trace[:48]}…" for trace, fichiers in doublons.items()
    )


#: Les grilles d'icônes offertes en administration (`GrilleIcones`) : le fichier
#: qui porte la liste, et son nom. La grille des équipements (#2442) n'était lue
#: par aucun contrôle — `lint:icones` ne lit pas les champs `nom:`.
GRILLES_PROPOSEES = (
    (("perimetres", "libelles.ts"), "ICONES_PERIMETRE"),
    (("equipements.ts",), "ICONES_EQUIPEMENT"),
)


@pytest.mark.parametrize(
    ("chemin", "liste"), GRILLES_PROPOSEES, ids=[g[1] for g in GRILLES_PROPOSEES]
)
def test_toutes_les_icones_proposees_existent_dans_le_catalogue(chemin, liste):
    """Une icône offerte au choix en administration doit pouvoir se dessiner.

    Sans quoi la pastille tombe sur le repli `help-circle` à l'écran et, sur un
    document imprimé, sur rien du tout.
    """
    catalogue = json.loads(_exige(CATALOGUE_FRONT))
    source = _exige(RACINE.joinpath("front", "src", "lib", *chemin))
    bloc = source.split(f"{liste}:", 1)[1].split("];", 1)[0]
    proposees = re.findall(r"nom:\s*'([a-z0-9-]+)'", bloc)

    assert proposees, f"Aucune icône lue dans {liste} — le format a changé"
    manquantes = [n for n in proposees if n not in catalogue]
    assert not manquantes, f"Icônes proposées absentes du catalogue : {manquantes}"
    doublons = sorted({n for n in proposees if proposees.count(n) > 1})
    assert not doublons, f"{liste} propose deux fois la même icône : {doublons}"


def test_toutes_les_icones_du_seed_existent_dans_le_catalogue():
    """Même exigence pour les icônes posées d'office par le seed — patrimoine et équipements."""
    catalogue = json.loads(_exige(CATALOGUE_FRONT))
    from app.seed.equipements import EQUIPEMENTS
    from app.seed.patrimoine import ICONES_GABARIT, ICONES_INITIALES

    posees = set(ICONES_INITIALES.values()) | set(ICONES_GABARIT.values()) | {"building-2"}
    posees |= {e["icone"] for e in EQUIPEMENTS}
    manquantes = sorted(n for n in posees if n and n not in catalogue)
    assert not manquantes, f"Icônes du seed absentes du catalogue : {manquantes}"


def test_les_icones_utilisees_par_les_documents_existent():
    """Les documents imprimables nomment leurs icônes en dur : elles doivent exister."""
    catalogue = json.loads(_exige(CATALOGUE_FRONT))
    for nom in ("globe", "whatsapp"):
        assert nom in catalogue, f"Icône « {nom} » attendue par les documents imprimables"
