"""Le HTML d'un utilisateur n'entre dans un courriel qu'échappé ou assaini (#2150).

## Ce que ces tests tiennent

1. **Le comportement de l'assainisseur** (`utils/html_sur`) : la mise en forme
   de l'éditeur passe, tout le reste est retiré — script, gestionnaire
   d'événement, `javascript:`, formulaire.
2. **Sa liste blanche est celle du front** (`front/src/lib/sanitize.ts`) : un
   texte s'affiche de la même façon à l'écran et dans un courriel. Deux listes
   recopiées divergent au premier ajout.
3. **Ce qui PART** : chaque modèle du seed, rendu par `composer_email` avec une
   charge hostile dans CHAQUE variable, ne contient ni script, ni gestionnaire,
   ni `javascript:`, ni formulaire. C'est le courriel qu'on lit, pas le fait
   qu'il part (`standards/03` §2 bis).
4. **Le contexte d'une affaire** : la description d'un résident arrive au
   conseil assainie, sa mise en forme conservée.
5. **Les portes** : nul ne marque sûr (`Markup(x)`) une valeur hors de
   `html_sur`, et nul ne rend un gabarit Jinja hors de `utils/email/rendu`.

## 🔴 Pourquoi

Le corps des courriels n'était PAS échappé, et `| safe` reposait sur un
assainissement « côté front » que l'API ne faisait pas. Un résident envoyait
au conseil et au syndic, depuis le domaine de la résidence et signé DKIM, le HTML
de son choix. Aucun test ne lisait le corps rendu.
"""

from __future__ import annotations

import ast
import pathlib
import re
from html.parser import HTMLParser

import pytest

from app.utils.html_sur import ATTRIBUTS, BALISES, assainir_html, filtre_safe, html_riche
from tests.aides_sources import modules_app

API = pathlib.Path(__file__).resolve().parents[1]
SANITIZE_TS = API.parent / "front" / "src" / "lib" / "sanitize.ts"

CHARGE = (
    '<script>alert(1)</script><a href="javascript:alert(2)">lien</a>'
    '<img src=x onerror=alert(3)><form action="https://tiers.example/vol">'
    '<input name="mdp"></form><iframe src="https://tiers.example"></iframe>'
)

#: Les balises qu'aucun courriel ne doit porter, une fois rendu.
BALISES_INTERDITES = {"script", "form", "input", "iframe", "object", "embed", "style"}


class _Releve(HTMLParser):
    """Ce que le HTML rendu CONTIENT vraiment — analysé, pas lu comme du texte.

    Un `&lt;script&gt;` échappé est du texte : il s'affiche, il ne s'exécute pas.
    Chercher « javascript: » dans la chaîne le compterait comme une faille.
    """

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.fautes: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag in BALISES_INTERDITES:
            self.fautes.append(f"<{tag}>")
        for nom, valeur in attrs:
            if nom.startswith("on"):
                self.fautes.append(f"{tag}[{nom}]")
            if nom in ("href", "src") and (valeur or "").strip().lower().startswith(
                ("javascript:", "data:", "vbscript:")
            ):
                self.fautes.append(f"{tag}[{nom}={valeur}]")


def fautes(html: str) -> list[str]:
    releve = _Releve()
    releve.feed(str(html))
    return releve.fautes


# ── 1. L'assainisseur ────────────────────────────────────────────────────────


def test_la_mise_en_forme_passe_et_le_reste_est_retire():
    sortie = assainir_html(f"<p><strong>Fuite</strong> au <em>2ᵉ</em></p>{CHARGE}")
    assert "<strong>Fuite</strong>" in sortie and "<em>2ᵉ</em>" in sortie
    assert not fautes(sortie)


def test_un_lien_garde_son_adresse_et_recoit_rel():
    sortie = assainir_html('<a href="https://exemple.fr/x" rel="opener">voir</a>')
    assert sortie == '<a href="https://exemple.fr/x" rel="noopener noreferrer">voir</a>'


def test_un_texte_simple_reste_du_texte():
    assert assainir_html("Loyer < 900 & charges") == "Loyer &lt; 900 &amp; charges"
    assert assainir_html(None) == "" and assainir_html("") == ""


def test_une_balise_coupee_par_la_troncature_est_refermee():
    assert assainir_html("<p><strong>Début") == "<p><strong>Début</strong></p>"


def test_le_filtre_safe_assainit_et_respecte_ce_qui_est_deja_sur():
    assert not fautes(filtre_safe(CHARGE))
    deja = html_riche("<em>ok</em>")
    assert filtre_safe(deja) is deja


# ── 2. La même liste que le front ────────────────────────────────────────────


def _liste_ts(nom: str) -> set[str]:
    source = SANITIZE_TS.read_text(encoding="utf-8")
    bloc = re.search(rf"const {nom} = \[(.*?)\];", source, re.DOTALL)
    assert bloc, f"{nom} introuvable dans {SANITIZE_TS} — le contrôle ne lit plus rien"
    sans_commentaires = re.sub(r"//[^\n]*", "", bloc.group(1))
    return set(re.findall(r"'([a-z0-9]+)'", sans_commentaires))


def test_les_balises_sont_celles_du_front():
    assert BALISES == _liste_ts("ALLOWED_TAGS")


def test_les_attributs_sont_ceux_du_front_rel_excepte():
    #  `rel` : posé par `nh3` sur chaque lien, et refusé par lui en attribut permis.
    assert ATTRIBUTS == _liste_ts("ALLOWED_ATTR") - {"rel"}


# ── 3. Ce qui part : chaque modèle, charge hostile partout ──────────────────


class _Hostile:
    """N'importe quelle variable, n'importe quel champ : la charge, en texte."""

    def __getattr__(self, nom):
        if nom.startswith("_"):
            raise AttributeError(nom)
        return _Hostile()

    def __getitem__(self, _cle):
        return _Hostile()

    def __iter__(self):
        return iter([_Hostile()])

    def __len__(self):
        return 1

    def __add__(self, _autre):
        return self

    __radd__ = __add__

    def __gt__(self, _autre):
        return True

    __lt__ = __ge__ = __le__ = __gt__

    def __str__(self):
        return CHARGE


def _modeles():
    from app.seed.emails import EMAIL_TEMPLATES

    return [(code, sujet, corps) for code, _l, sujet, corps, _d in EMAIL_TEMPLATES]


@pytest.mark.parametrize("code,sujet,corps", _modeles(), ids=lambda v: v[:30])
def test_aucun_modele_ne_laisse_passer_le_html_d_une_variable(code, sujet, corps):
    from app.models.exploitation import ModeleEmail
    from app.utils.email.rendu import composer_email
    from app.utils.email.variables import VARIABLES_DU_GABARIT, variables_de

    modele = ModeleEmail(code=code, libelle=code, sujet=sujet, corps_html=corps)
    ctx = {nom: _Hostile() for nom in variables_de(sujet, corps) | VARIABLES_DU_GABARIT}
    ctx["annee"] = 2026
    _objet, html = composer_email(
        modele, ctx, site_nom="Résidence", site_url="https://exemple.fr", email_footer=""
    )
    assert not fautes(html), f"{code} : {fautes(html)}"


def test_le_corps_s_echappe_et_l_objet_reste_du_texte():
    from app.models.exploitation import ModeleEmail
    from app.utils.email.rendu import composer_email

    modele = ModeleEmail(code="x", libelle="x", sujet="{{ t }}", corps_html="<p>{{ t }}</p>")
    objet, html = composer_email(
        modele,
        {"t": "Tom & Jerry <b>", "annee": 2026},
        site_nom="R",
        site_url="https://exemple.fr",
        email_footer="",
    )
    assert objet == "Tom & Jerry <b>"
    assert "<p>Tom &amp; Jerry &lt;b&gt;</p>" in html


# ── 4. Le contexte d'une affaire ─────────────────────────────────────────────


def test_la_description_d_une_affaire_arrive_assainie_au_conseil():
    from types import SimpleNamespace

    from app.models.exploitation import ModeleEmail
    from app.routers.tickets.courriels import _contexte_ticket
    from app.utils.email.rendu import composer_email

    code, sujet, corps = next(m for m in _modeles() if m[0] == "ticket_nouveau_cs")
    ticket = SimpleNamespace(
        id=1,
        numero="T-1",
        titre="Fuite",
        description=f"<p><strong>Eau</strong> au sous-sol</p>{CHARGE}",
        categorie="panne",
        perimetre_cible=None,
    )
    ctx = {
        "ticket": _contexte_ticket(ticket),
        "auteur": {"affiche": "Résident"},
        "urgent": False,
        "annee": 2026,
        "residence": {"nom": "R"},
        "app": {"url": "https://exemple.fr"},
    }
    modele = ModeleEmail(code=code, libelle=code, sujet=sujet, corps_html=corps)
    _objet, html = composer_email(
        modele, ctx, site_nom="R", site_url="https://exemple.fr", email_footer=""
    )
    assert "<strong>Eau</strong>" in html
    assert not fautes(html)


# ── 5. Les portes ────────────────────────────────────────────────────────────


def _modules_app():
    for m in modules_app():
        yield f"app/{m.rel}", m.arbre


def _nom_appele(noeud: ast.Call) -> str | None:
    f = noeud.func
    if isinstance(f, ast.Name):
        return f.id
    if isinstance(f, ast.Attribute):
        return f.attr
    return None


def test_seul_html_sur_marque_sure_une_valeur():
    """`Markup("<br>")` — une constante — est permis ; `Markup(x)` ne l'est qu'ici."""
    fautes = []
    vus = 0
    for chemin, arbre in _modules_app():
        for n in ast.walk(arbre):
            if isinstance(n, ast.Call) and _nom_appele(n) == "Markup":
                vus += 1
                constant = n.args and isinstance(n.args[0], ast.Constant)
                if not constant and chemin != "app/utils/html_sur.py":
                    fautes.append(f"{chemin}:{n.lineno}")
    assert vus >= 2, "aucun Markup( relevé : le contrôle ne lit plus rien"
    assert not fautes, f"Markup(<variable>) hors de utils/html_sur : {fautes}"


def test_seul_le_moteur_des_courriels_rend_un_gabarit():
    fautes = [
        f"{chemin}:{n.lineno}"
        for chemin, arbre in _modules_app()
        for n in ast.walk(arbre)
        if isinstance(n, ast.Call)
        and _nom_appele(n) == "from_string"
        and chemin != "app/utils/email/rendu.py"
    ]
    assert not fautes, f"un gabarit rendu hors de utils/email/rendu : {fautes}"
