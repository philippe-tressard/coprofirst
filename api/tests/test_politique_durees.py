"""Le gabarit légal : ses durées viennent du code, son balisage tient, ses constantes servent (#2959).

## Pourquoi (audit du 23/11/2026)

Trois défauts d'entretien de `seed/contenus_legaux.py`, aucun vu par un contrôle :

- **sept durées écrites en clair** (« conservés 30 jours », « 12 mois », « 10 ans »,
  « 7 jours glissants »), justes ce jour-là, mais qu'aucun test ne liait à la purge
  qui les applique — deux seulement l'étaient (courriels, comptes) ;
- **neuf `<li>` hors de toute liste** : « 2. Données collectées » se fermait avant
  ses neuf dernières entrées ;
- **six constantes sans lecteur**, dont une seconde rédaction de la section 4
  (`AJOUTS_1034`) qui avait déjà divergé du gabarit : les migrations qui les
  lisaient avaient été fondues dans le schéma initial.

⚠️ Ce contrôle lit le GABARIT, pas le texte servi (en base, retouché par l'éditeur).
"""

from __future__ import annotations

import ast
import pathlib
import re
from html.parser import HTMLParser

from app.config import Settings
from app.seed import contenus_legaux as gabarit
from app.utils.dates_fr import duree_conservation
from app.utils.erreurs_navigateur import CONSERVATION_JOURS
from app.utils.telemetry_aggregation import (
    RETENTION_DAILY_JOURS,
    RETENTION_EVENEMENTS_JOURS,
    RETENTION_MONTHLY_JOURS,
)

_API = pathlib.Path(__file__).resolve().parents[1]
_SEED = _API / "app" / "seed"
NBSP = "\xa0"


def _politique() -> str:
    return gabarit.DEFAULT_LEGAL["politique_confidentialite"]


# ── 1. Chaque durée est celle de la purge ────────────────────────────────────


def test_les_mesures_sans_compte_annoncent_la_duree_de_leur_purge():
    """Erreurs, durées d'affichage, formulaires : une seule constante, `erreurs_navigateur`."""
    attendu = f"conservé{{}} {duree_conservation(CONSERVATION_JOURS, NBSP)}"
    assert attendu.format("s") in gabarit.TELEMETRIE_ERREURS
    assert attendu.format("s") in gabarit.TELEMETRIE_PERFORMANCE
    assert attendu.format("") in gabarit.TELEMETRIE_GESTES


def test_l_arrivee_par_notification_vit_ce_que_vit_la_page_vue():
    assert f"conservé {duree_conservation(RETENTION_EVENEMENTS_JOURS, NBSP)}" in (
        gabarit.TELEMETRIE_ARRIVEES
    )


def test_la_mesure_d_audience_annonce_les_durees_de_ses_purges():
    texte = gabarit.TELEMETRIE_CONSERVATION
    for jours in (RETENTION_EVENEMENTS_JOURS, RETENTION_DAILY_JOURS, RETENTION_MONTHLY_JOURS):
        assert duree_conservation(jours, NBSP) in texte, (
            f"la puce de la mesure d'audience n'annonce plus {jours} jours, que la purge applique"
        )


def test_la_derniere_visite_s_efface_avec_les_agregats_par_jour():
    assert f"effacé après <strong>{duree_conservation(RETENTION_DAILY_JOURS)}</strong>" in (
        gabarit.TELEMETRIE_DERNIERE_VISITE
    )


def test_les_jetons_annoncent_le_defaut_du_reglage():
    defaut = Settings.model_fields["refresh_token_expire_days"].default
    assert f": {duree_conservation(defaut)} glissants" in gabarit.JETONS_RAFRAICHISSEMENT
    assert gabarit.JETONS_RAFRAICHISSEMENT in _politique()


def test_chaque_puce_de_duree_est_servie_par_le_gabarit():
    for puce in (
        gabarit.TELEMETRIE_ERREURS,
        gabarit.TELEMETRIE_PERFORMANCE,
        gabarit.TELEMETRIE_ARRIVEES,
        gabarit.TELEMETRIE_GESTES,
        gabarit.TELEMETRIE_CONSERVATION,
        gabarit.TELEMETRIE_DERNIERE_VISITE,
    ):
        assert puce in _politique()


#: Une durée écrite en clair dans une chaîne du gabarit : un nombre suivi d'une unité.
_DUREE_EN_CLAIR = re.compile(r"\b\d+(?:\\xa0|\xa0| )(?:jours?|mois|ans)\b")

#: Les durées qui ne sont PAS des conservations, et n'ont donc pas de purge à lire.
_PAS_DES_CONSERVATIONS = {
    #  La fenêtre de détection d'une récidive (#1647), dite à l'assistant.
    "24 mois",
    #  L'ancre d'une phrase d'avant, que `CONSERVATION_COMPTES_ANCIEN` garde pour le test
    #  de la politique : elle ne doit plus figurer dans le texte, elle y est cherchée.
    "2 ans",
}


def test_aucune_duree_n_est_ecrite_en_clair_dans_une_chaine_du_gabarit():
    """Le défaut exact : sept durées recopiées, que rien ne liait à leur purge."""
    lus, fautes = 0, []
    for fichier in sorted(_SEED.glob("contenus_legaux*.py")):
        for noeud in ast.walk(ast.parse(fichier.read_text(encoding="utf-8"))):
            if isinstance(noeud, ast.Constant) and isinstance(noeud.value, str):
                lus += 1
                fautes += [
                    f"  {fichier.name}:{noeud.lineno} — « {m.group(0)} »"
                    for m in _DUREE_EN_CLAIR.finditer(noeud.value)
                    if m.group(0).replace(NBSP, " ") not in _PAS_DES_CONSERVATIONS
                ]
    assert lus > 100, f"{lus} chaînes lues dans les seeds légaux : INCONNU"
    assert not fautes, (
        "Une durée est écrite en clair dans le gabarit légal ; la composer de la constante "
        "qui l'applique (`dates_fr.duree_conservation`) :\n" + "\n".join(fautes)
    )


def test_le_motif_voit_une_duree_en_clair():
    """Cas témoins (`standards/04` §2), dont l'espace insécable littéral."""
    for avant in ("conservés 30\xa0jours", "<strong>12 mois</strong>", "7 jours glissants"):
        assert _DUREE_EN_CLAIR.search(avant), avant


def test_les_exceptions_servent_encore():
    """Une exception qui ne couvre plus rien se retire (`standards/05` §2)."""
    chaines = " ".join(
        n.value
        for f in _SEED.glob("contenus_legaux*.py")
        for n in ast.walk(ast.parse(f.read_text(encoding="utf-8")))
        if isinstance(n, ast.Constant) and isinstance(n.value, str)
    ).replace(NBSP, " ")
    for exception in _PAS_DES_CONSERVATIONS:
        assert exception in chaines, f"« {exception} » n'est plus écrit : retirer l'exception"


# ── 2. Aucun <li> hors d'une liste ───────────────────────────────────────────


class _Listes(HTMLParser):
    """Compte les `<li>` ouverts hors de toute `<ul>`/`<ol>`."""

    def __init__(self) -> None:
        super().__init__()
        self.profondeur = 0
        self.hors_liste = 0
        self.items = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("ul", "ol"):
            self.profondeur += 1
        elif tag == "li":
            self.items += 1
            self.hors_liste += self.profondeur == 0

    def handle_endtag(self, tag):
        if tag in ("ul", "ol"):
            self.profondeur -= 1


def _hors_liste(html: str) -> tuple[int, int]:
    lecteur = _Listes()
    lecteur.feed(html)
    return lecteur.hors_liste, lecteur.items


def test_aucun_element_de_liste_hors_d_une_liste():
    for cle, html in gabarit.DEFAULT_LEGAL.items():
        hors, items = _hors_liste(html)
        assert hors == 0, f"{cle} : {hors} `<li>` sur {items} hors de toute liste"
    assert _hors_liste(_politique())[1] > 20, "trop peu de `<li>` lus : INCONNU"


def test_le_lecteur_voit_la_liste_fermee_trop_tot():
    """Cas témoin : la section 2 telle qu'elle était."""
    assert _hors_liste("<ul><li>a</li></ul><li>b</li><li>c</li>") == (2, 3)


# ── 3. Chaque constante a un lecteur ─────────────────────────────────────────


def _constantes(fichier: pathlib.Path) -> list[str]:
    arbre = ast.parse(fichier.read_text(encoding="utf-8"))
    return [
        cible.id
        for noeud in arbre.body
        if isinstance(noeud, ast.Assign)
        for cible in noeud.targets
        if isinstance(cible, ast.Name) and cible.id.isupper()
    ]


def test_chaque_constante_des_seeds_legaux_a_un_lecteur():
    """Six constantes ne servaient plus, dont une seconde rédaction de la section 4."""
    sources = {
        f: f.read_text(encoding="utf-8")
        for dossier in ("app", "alembic", "tests")
        for f in (_API / dossier).rglob("*.py")
    }
    seeds = sorted(_SEED.glob("contenus_legaux*.py"))
    assert len(seeds) >= 10, f"{len(seeds)} modules légaux lus : INCONNU"
    orphelines = []
    for fichier in seeds:
        for nom in _constantes(fichier):
            motif = re.compile(rf"\b{nom}\b")
            #  Dans son propre module, la définition compte une fois : il en faut une de plus.
            lectures = sum(len(motif.findall(s)) for s in sources.values())
            lectures -= len(re.findall(rf"^{nom}\s*[:=]", sources[fichier], re.M))
            if lectures == 0:
                orphelines.append(f"  {fichier.name} : {nom}")
    assert not orphelines, (
        "Des constantes des seeds légaux n'ont plus aucun lecteur — gabarit, migration ou "
        "test. Une rédaction qu'on garde sans lecteur diverge sans que rien ne le dise :\n"
        + "\n".join(orphelines)
    )
