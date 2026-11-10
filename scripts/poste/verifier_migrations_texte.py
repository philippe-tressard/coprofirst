#!/usr/bin/env python3
"""Point 0h du pré-check : une migration de texte légal du lot a-t-elle prise sur le texte SERVI ? (#2571, piste 3)

## Pourquoi (10/11/2026)

La politique de confidentialité vit en base, et l'administration peut la reprendre :
une migration ne change un passage que s'il figure TEL QUEL (`utils/textes_livres`).
La 0329 posait la puce des notifications sur téléphone après celle de la réception
des courriels — que la référence avait renseignée : l'ancre n'a pas été trouvée, la
puce n'est pas partie, et l'intitulé disait « Cinq fonctions » devant quatre puces.
Les essais de CI jouent la migration sur le GABARIT : ils ne pouvaient pas le voir.
Le post-check l'a vu, après la mise en production. La 0327 était née du même défaut.

## Ce que fait ce contrôle

Il lit les textes légaux SERVIS (`GET /api/config/legal`, public), puis joue en
mémoire chaque migration AJOUTÉE par le lot qui nomme une clé légale, ses appels à
`textes_livres` remplacés par des doublures qui opèrent sur ces textes. Chaque
passage visé — gabarit et forme de l'éditeur réunis — doit avoir pris, ou être déjà
servi ; sinon : ÉCHEC, avec le passage. Aucune écriture, aucune base, rien que la
lecture d'une page publique.

## Ce qu'il ne mesure pas

Les migrations d'autres textes (FAQ, modèles de courriel) : ils ne sont pas servis
publiquement. Elles sont nommées dans le détail, hors de la portée du point.

    python scripts/poste/verifier_migrations_texte.py [--site URL] [--base origin/main]
    python scripts/poste/verifier_migrations_texte.py --selftest

Sortie : une ligne `VERDICT|détail` (OK, FAIL ou INCONNU), lue par `lib-precheck-lot.sh`.
"""

from __future__ import annotations

import importlib.util
import json
import os
import pathlib
import subprocess
import sys
import types
import urllib.request

RACINE = pathlib.Path(__file__).resolve().parents[2]
VERSIONS = "api/alembic/versions"

#: Les textes que la page publique `/api/config/legal` sert, donc mesurables ici.
CLES_SERVIES = ("politique_confidentialite", "mentions_legales")

#: Les gestes de `utils/textes_livres` qu'une migration de texte appelle.
GESTES = ("remplacer_passage", "inserer_apres", "lire_texte", "remplacer_si_intact")


def normaliser(texte: str) -> str:
    """Le gabarit et la forme de l'éditeur (`<li><p>…&nbsp;…</p></li>`) rapprochés."""
    return (
        texte.replace("&nbsp;", "\xa0")
        .replace("<li><p>", "<li>")
        .replace("</p></li>", "</li>")
    )


class TextesEnMemoire:
    """Les doublures des gestes de `textes_livres`, sur les textes servis, journalisées."""

    def __init__(self, textes: dict[str, str]):
        self.textes = dict(textes)
        self.journal: list[
            tuple[str, str, str, bool]
        ] = []  # (clé, avant, après, effet)

    @staticmethod
    def _cle(cle: dict) -> str:
        return cle.get("cle", "")

    def lire_texte(self, conn, table, cle, colonne):
        return self.textes.get(self._cle(cle)) if table == "config_site" else None

    def remplacer_passage(self, conn, table, cle, colonne, avant, apres):
        nom = self._cle(cle)
        actuel = self.textes.get(nom) if table == "config_site" else None
        effet = bool(actuel) and avant in actuel
        if effet:
            self.textes[nom] = actuel.replace(avant, apres)
        if table == "config_site":
            self.journal.append((nom, avant, apres, effet))
        return int(effet)

    def inserer_apres(self, conn, table, cle, colonne, ancre, ajout):
        actuel = self.lire_texte(conn, table, cle, colonne)
        if actuel and ancre + ajout in actuel:
            self.journal.append((self._cle(cle), ancre, ancre + ajout, True))
            return 0
        return self.remplacer_passage(conn, table, cle, colonne, ancre, ancre + ajout)

    def remplacer_si_intact(self, conn, table, avant, apres):
        return 0  # une ligne entière (FAQ, modèles) : hors des textes servis ici


def passages_sans_prise(journal, textes_finaux: dict[str, str]) -> list[str]:
    """Les passages visés qui n'ont ni pris ni ne sont déjà servis — gabarit et éditeur
    réunis : une seule de leurs deux formes doit prendre."""
    groupes: dict[tuple[str, str, str], bool] = {}
    for cle, avant, apres, effet in journal:
        nouveau = apres.replace(avant, "", 1) if avant in apres else apres
        g = (cle, normaliser(avant), normaliser(nouveau))
        deja = normaliser(nouveau) in normaliser(textes_finaux.get(cle, ""))
        groupes[g] = groupes.get(g, False) or effet or deja
    return [
        f"{cle} : « {nouveau[:70]}… »"
        for (cle, _, nouveau), pris in groupes.items()
        if not pris
    ]


def jouer(
    module: types.ModuleType, textes: dict[str, str]
) -> tuple[list[str], str | None]:
    """Joue `upgrade()` du module sur les textes servis : (passages sans prise, erreur)."""
    doublures = TextesEnMemoire(textes)
    for geste in GESTES:
        if hasattr(module, geste):
            setattr(module, geste, getattr(doublures, geste))
    module.op = types.SimpleNamespace(get_bind=lambda: None)
    try:
        module.upgrade()
    except Exception as exc:  # une migration qui fait autre chose que du texte
        return [], f"{type(exc).__name__} : {exc}"
    return passages_sans_prise(doublures.journal, doublures.textes), None


def migrations_du_lot(base: str) -> list[pathlib.Path]:
    sortie = subprocess.run(
        ["git", "diff", "--name-only", "--diff-filter=A", base, "--", VERSIONS],
        capture_output=True,
        text=True,
        cwd=RACINE,
        check=True,
    ).stdout
    return [RACINE / nom for nom in sortie.split() if nom.endswith(".py")]


def nomme_un_texte_servi(chemin: pathlib.Path) -> bool:
    source = chemin.read_text(encoding="utf-8")
    return any(cle in source for cle in CLES_SERVIES)


def charger(chemin: pathlib.Path) -> types.ModuleType:
    spec = importlib.util.spec_from_file_location(f"migration_{chemin.stem}", chemin)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def textes_servis(site: str) -> dict[str, str] | None:
    try:
        #  Un agent nommé : celui de Python par défaut est refusé (403) par le réseau
        #  qui achemine le site. Générique, sans aucune donnée personnelle.
        requete = urllib.request.Request(
            f"{site}/api/config/legal",
            headers={"User-Agent": "coprofirst-precheck/1.0"},
        )
        with urllib.request.urlopen(requete, timeout=15) as r:
            corps = json.loads(r.read().decode("utf-8"))
    except Exception:
        return None
    if not isinstance(corps, dict) or not corps.get("politique_confidentialite"):
        return None  # cas zéro : une réponse qui n'est pas la page n'a rien mesuré
    return {cle: corps.get(cle) or "" for cle in CLES_SERVIES}


def verdict(candidates, textes, resultats, hors_portee) -> str:
    """La ligne `VERDICT|détail`. (PURE)
    candidates : noms des migrations de texte légal du lot · textes : servis ou None ·
    resultats : {nom: (passages sans prise, erreur)} · hors_portee : noms non mesurables."""
    hors = (
        f" ; hors portée (texte non servi) : {', '.join(hors_portee)}"
        if hors_portee
        else ""
    )
    if not candidates:
        return f"OK|aucune migration de texte légal dans le lot{hors}"
    if textes is None:
        return f"INCONNU|textes servis illisibles — {len(candidates)} migration(s) non jouée(s){hors}"
    erreurs = [f"{n} ({e})" for n, (_, e) in resultats.items() if e]
    if erreurs:
        return f"INCONNU|non jouée(s) en mémoire : {'; '.join(erreurs)}{hors}"
    manques = [f"{n} → {p}" for n, (ps, _) in resultats.items() for p in ps]
    if manques:
        return f"FAIL|sans prise sur le texte servi : {' | '.join(manques)}{hors}"
    return f"OK|{len(candidates)} migration(s) de texte légal : chaque passage prend ou est déjà servi{hors}"


def principal(site: str, base: str) -> str:
    sys.path.insert(0, str(RACINE / "api"))
    #  L'import de `app` exige une configuration : des valeurs d'emprunt, propres à ce
    #  processus, qui n'ouvrent rien — aucune base n'est jamais jointe ici. Le `.env`
    #  du poste n'est pas lu (`FICHIER_ENV`), comme dans les tests.
    os.environ.setdefault(
        "DATABASE_URL", "postgresql+psycopg://verification@localhost/sans_base"
    )
    os.environ.setdefault("SECRET_KEY", "verification-hors-base-" + "x" * 24)
    os.environ.setdefault("FICHIER_ENV", os.devnull)
    chemins = migrations_du_lot(base)
    candidates = [c for c in chemins if nomme_un_texte_servi(c)]
    hors_portee = [
        c.stem
        for c in chemins
        if c not in candidates and "textes_livres" in c.read_text(encoding="utf-8")
    ]
    textes = textes_servis(site) if candidates else None
    resultats = {}
    if textes is not None:
        for c in candidates:
            try:
                resultats[c.stem] = jouer(charger(c), textes)
            except Exception as exc:  # import impossible
                resultats[c.stem] = ([], f"chargement : {type(exc).__name__}")
    return verdict([c.stem for c in candidates], textes, resultats, hors_portee)


# ── Autotest : la décision et la doublure, sans réseau ni base ────────────────
def _migration(corps) -> types.ModuleType:
    """Une migration d'essai : `corps(m)` appelle les gestes du module comme une vraie."""
    m = types.ModuleType("migration_essai")
    for geste in GESTES:
        setattr(m, geste, None)
    m.upgrade = lambda: corps(m)
    return m


def autotest() -> int:
    echecs = 0

    def attendu(cond, libelle):
        nonlocal echecs
        print(("PASS  " if cond else "FAIL  ") + libelle)
        echecs += 0 if cond else 1

    cle = {"cle": "politique_confidentialite"}
    gabarit = "<li>Réception\xa0: à renseigner.</li>"
    renseignee = "<li><p>Réception&nbsp;: OVH SAS.</p></li>"
    puce = "<li>Notifications sur téléphone.</li>"
    servi_renseigne = {
        "politique_confidentialite": "<ul>" + renseignee + "</ul>",
        "mentions_legales": "",
    }

    def inserer_deux_formes(m):  # le motif de la 0329
        m.inserer_apres(None, "config_site", cle, "valeur", gabarit, puce)
        m.inserer_apres(
            None,
            "config_site",
            cle,
            "valeur",
            normaliser_inverse(gabarit),
            normaliser_inverse(puce),
        )

    def normaliser_inverse(p):
        return "<li><p>" + p[4:-5].replace("\xa0", "&nbsp;") + "</p></li>"

    # 1. Le cas du 10/11/2026 : l'ancre est reformulée, la puce absente → sans prise.
    ps, err = jouer(_migration(inserer_deux_formes), servi_renseigne)
    attendu(
        err is None and len(ps) == 1 and "Notifications" in ps[0],
        "0329 : ancre renseignée, puce absente → sans prise",
    )
    # 2. La même migration sur le gabarit intact : une des deux formes prend → rien.
    ps, _ = jouer(
        _migration(inserer_deux_formes),
        {"politique_confidentialite": "<ul>" + gabarit + "</ul>"},
    )
    attendu(
        ps == [],
        "gabarit intact : la forme du gabarit prend, celle de l'éditeur non → rien à dire",
    )
    # 3. Le passage est déjà servi (posé par une autre voie) → rien.
    deja = {
        "politique_confidentialite": "<ul>"
        + renseignee
        + "<li><p>Notifications sur téléphone.</p></li></ul>"
    }
    ps, _ = jouer(_migration(inserer_deux_formes), deja)
    attendu(ps == [], "puce déjà servie, sous la forme de l'éditeur → rien à dire")
    # 4. Un remplacement qui prend.
    remplace = _migration(
        lambda m: m.remplacer_passage(
            None, "config_site", cle, "valeur", "Quatre", "Cinq"
        )
    )
    ps, _ = jouer(remplace, {"politique_confidentialite": "Quatre fonctions"})
    attendu(ps == [], "remplacement qui prend → rien")
    # 5. Une migration qui fait autre chose : erreur nommée, jamais un OK silencieux.
    autre = _migration(lambda m: m.op.add_column("t", "c"))
    _, err = jouer(autre, servi_renseigne)
    attendu(err is not None, "migration hors texte : erreur nommée")
    # 6. Les verdicts.
    attendu(
        verdict([], None, {}, []).startswith("OK|aucune"),
        "cas zéro : aucune migration de texte → OK, et il le dit",
    )
    attendu(
        verdict(["0329"], None, {}, []).startswith("INCONNU|"),
        "textes servis illisibles → INCONNU, jamais OK",
    )
    attendu(
        verdict(["0329"], {}, {"0329": (["x"], None)}, []).startswith("FAIL|"),
        "un passage sans prise → FAIL",
    )
    attendu(
        verdict(["0330"], {}, {"0330": ([], None)}, ["0331"]).startswith(
            "OK|1 migration"
        ),
        "tout prend → OK, hors portée nommé",
    )
    attendu(
        "0331" in verdict(["0330"], {}, {"0330": ([], None)}, ["0331"]),
        "le hors-portée est nommé dans le détail",
    )
    attendu(
        verdict(["0329"], {}, {"0329": ([], "AttributeError")}, []).startswith(
            "INCONNU|"
        ),
        "non jouée → INCONNU",
    )
    print("== TOUS OK ==" if echecs == 0 else "== ÉCHECS ==")
    return echecs


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(1 if autotest() else 0)
    args = sys.argv[1:]
    site = (
        args[args.index("--site") + 1] if "--site" in args else "https://5hostachy.fr"
    )
    base = args[args.index("--base") + 1] if "--base" in args else "origin/main"
    print(principal(site, base))
