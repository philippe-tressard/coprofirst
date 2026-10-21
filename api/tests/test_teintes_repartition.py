"""Les TEINTES des répartitions : une règle au serveur, deux palettes d'accord (#2082).

La règle — quelle tranche prend quelle teinte — vit dans
`utils/suivi_affaires/repartition` ; l'écran (`BarresCroisees`) et le papier
(`pdf_barres`) la reçoivent. Les COULEURS, elles, s'écrivent deux fois, faute de
fichier commun aux deux images : `socle.css` pour l'écran, `pdf_barres.TEINTES`
pour le papier. Ce test les tient d'accord — une couleur changée d'un côté
seulement échoue ici, au lieu d'un PDF qui ne ressemble plus à l'écran.
"""

from __future__ import annotations

import pathlib
import re

from app.utils.suivi_affaires.pdf_barres import TEINTES
from app.utils.suivi_affaires.repartition import (
    Barre,
    Tranche,
    teinte_batiment,
    teinte_categorie,
    teinter,
)

SOCLE = pathlib.Path(__file__).resolve().parents[2] / "front" / "src" / "styles" / "socle.css"

#: La teinte → le jeton de `socle.css` qui la peint à l'écran (`BarresCroisees`).
JETONS = {
    **{f"s{i}": f"--serie-{i}" for i in range(1, 9)},
    **{f"p{i}": f"--palier-{i}" for i in range(1, 5)},
    "autre": "--color-text-muted",
}


def _jetons_de_l_ecran() -> dict[str, str]:
    texte = SOCLE.read_text(encoding="utf-8")
    #  Le premier bloc `:root` : le thème clair, celui que le papier imite.
    bloc = texte[texte.index(":root") :]
    return dict(re.findall(r"(--[\w-]+):\s*(#[0-9a-fA-F]{3,8})\s*;", bloc.split("}", 1)[0]))


def test_le_papier_peint_les_couleurs_de_l_ecran():
    ecran = _jetons_de_l_ecran()
    assert set(TEINTES) == set(JETONS), "une teinte sans couleur, ou une couleur sans teinte"
    ecarts = {
        t: (TEINTES[t], ecran.get(j)) for t, j in JETONS.items() if TEINTES[t] != ecran.get(j)
    }
    assert not ecarts, f"`pdf_barres.TEINTES` diverge de `socle.css` : {ecarts}"


def test_une_teinte_suit_l_entite_jamais_son_rang():
    assert teinte_categorie("panne") == "s1"
    assert teinte_categorie("entretien") == "s8"
    assert teinte_categorie("bug") == "autre"
    ordre = ["racine", "bat:1", "bat:2", "bat:3", "bat:4"]
    assert [teinte_batiment(c, ordre) for c in ordre] == ["p1", "p2", "p3", "p4", "p4"]
    assert teinte_batiment("plusieurs", ordre) == "plusieurs"


def test_teinter_suit_l_ordre_de_par_batiment():
    par_cat = [Barre("panne", "Panne", 2, [Tranche("bat:2", "B", 1), Tranche("bat:1", "A", 1)])]
    par_bat = [
        Barre("bat:2", "B", 1, [Tranche("panne", "Panne", 1)]),
        Barre("bat:1", "A", 1, [Tranche("panne", "Panne", 1)]),
    ]
    cat, bat = teinter(par_cat, par_bat)
    assert [t.teinte for t in cat[0].tranches] == ["p1", "p2"]
    assert bat[0].tranches[0].teinte == "s1"


def test_la_hachure_plusieurs_batiments_est_un_motif_que_weasyprint_rend():
    """21/10/2026 : `repeating-linear-gradient` n'était pas rendu au PDF — la barre
    « Plusieurs bâtiments » restait vide, et la légende sans carré."""
    from app.utils.suivi_affaires.pdf_barres import _fond

    fond = _fond("plusieurs")
    assert "repeating-linear-gradient" not in fond
    assert "data:image/svg+xml" in fond and '"' not in fond, 'il vit dans style="…"'


def test_la_tete_porte_trois_chiffres_dont_les_fusionnees():
    from app.utils.suivi_affaires.pdf import tete_html
    from app.utils.suivi_affaires.releve import Releve

    html = tete_html(Releve(jour=__import__("datetime").date(2026, 10, 21)), "affaires")
    assert html.count('<div class="chiffre') == 4 and "fusionnée" in html  # le conteneur + trois
