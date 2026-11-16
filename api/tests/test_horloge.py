"""`horloge.maintenant()` rend ce que rendait `datetime.utcnow` — ni plus, ni moins (#1047).

🔴 Le piège que ce test verrouille : `datetime.now(timezone.utc)`, le
remplacement que suggère la documentation de Python, rend une date CONSCIENTE.
Toutes les dates lues en base sont NAÏVES, et Python refuse de comparer les
deux — la première comparaison « expiré ? » aurait levé une `TypeError`, en
production, sur un geste que les tests unitaires n'exercent pas tous.

Et depuis #1565, le JOUR : `horloge.aujourd_hui()` est le jour de Paris, quel
que soit le fuseau du conteneur — voir la seconde moitié du fichier.
"""

import ast
from datetime import date, datetime, timedelta, timezone

from app.models.core import Utilisateur
from app.utils import horloge
from tests.aides_sources import module_app, modules_app


def test_maintenant_est_naif():
    """Pas de fuseau : c'est la forme de toutes les dates en base."""
    assert horloge.maintenant().tzinfo is None


def test_maintenant_est_en_utc():
    """Naïf, mais UTC — pas l'heure locale du serveur."""
    reference = datetime.now(timezone.utc).replace(tzinfo=None)
    assert abs(horloge.maintenant() - reference) < timedelta(seconds=5)


def test_maintenant_se_compare_a_une_date_de_modele():
    """Le cas qui aurait levé : comparer « maintenant » à un `default_factory`."""
    u = Utilisateur(nom="N", prenom="P", email="n@p.test")
    assert u.cree_le <= horloge.maintenant()


def test_aucune_reference_a_utcnow_dans_app():
    """Ruff `DTZ003` ne voit que les APPELS — pas `default_factory=datetime.utcnow`.

    Sur les 162 écritures remplacées, 51 étaient des références sans
    parenthèses, en `default_factory` de modèle : exactement celles que le
    prochain modèle recopiera, et que Ruff laisserait passer. Ce test lit l'arbre
    et refuse toute mention de l'attribut `utcnow`, appelé ou non.
    """
    fautes = []
    for module in modules_app():
        for noeud in ast.walk(module.arbre):
            if isinstance(noeud, ast.Attribute) and noeud.attr in ("utcnow", "utcfromtimestamp"):
                fautes.append(f"app/{module.rel}:{noeud.lineno}")
    assert not fautes, (
        "`datetime.utcnow` est déprécié (Python 3.12) — `horloge.maintenant` :\n"
        + "\n".join(f"  {f}" for f in fautes)
    )


def test_toute_colonne_de_date_est_naive():
    """Chaque colonne de date d'une table est `DateTime(timezone=False)` (#1412).

    Depuis sqlmodel 0.0.45, un champ annoté `datetime` devient une colonne
    CONSCIENTE du fuseau, qui REFUSE à l'écriture la date naïve que rend
    `horloge.maintenant()` — « Datetime values must have timezone information ».
    Un champ oublié ne se verrait qu'au premier enregistrement, en production.
    La date d'un modèle s'annote donc `NaiveDatetime` (pydantic).
    """
    import app.models.core  # noqa: F401 — enregistre toutes les tables
    from sqlalchemy import DateTime
    from sqlmodel import SQLModel

    conscientes = [
        f"{table.name}.{colonne.name}"
        for table in SQLModel.metadata.tables.values()
        for colonne in table.columns
        if isinstance(colonne.type, DateTime) and colonne.type.timezone
    ]
    dates = [
        colonne
        for table in SQLModel.metadata.tables.values()
        for colonne in table.columns
        if isinstance(colonne.type, DateTime)
    ]
    assert dates, "aucune colonne de date lue : le contrôle ne mesure rien"
    assert not conscientes, f"colonnes de date conscientes du fuseau : {conscientes}"


# ══════════════════════════════════════════════════════════════════════════════
#  Le jour civil — « quel jour est-on pour le résident » (#1565)
# ══════════════════════════════════════════════════════════════════════════════
#
#  Deux « aujourd'hui » coexistaient : `date.today()` (le jour du CONTENEUR, que
#  `TZ=Europe/Paris` rendait parisien en production et que rien ne rendait
#  parisien ailleurs) et `horloge.maintenant().date()` (le jour UTC). Entre minuit
#  et deux heures à Paris, ils différaient d'un jour : une délégation commencée
#  « aujourd'hui » était comparée au jour UTC, une actualité périmait deux heures
#  après minuit.


def _figer(monkeypatch, instant_utc: datetime) -> None:
    """Fige `horloge.maintenant()` — et donc tout ce qui en découle."""
    monkeypatch.setattr(horloge, "maintenant", lambda: instant_utc)


def test_a_00h30_a_paris_l_ete_aujourd_hui_est_deja_le_lendemain(monkeypatch):
    """22:30 UTC le 1er octobre = 00:30 le 2 à Paris (UTC+2) : on est le 2."""
    _figer(monkeypatch, datetime(2026, 10, 1, 22, 30))
    assert horloge.aujourd_hui() == date(2026, 10, 2)


def test_a_00h30_a_paris_l_hiver_aussi(monkeypatch):
    """23:30 UTC le 15 janvier = 00:30 le 16 à Paris (UTC+1) : le décalage suit l'heure d'hiver."""
    _figer(monkeypatch, datetime(2026, 1, 15, 23, 30))
    assert horloge.aujourd_hui() == date(2026, 1, 16)
    _figer(monkeypatch, datetime(2026, 1, 15, 22, 30))
    assert horloge.aujourd_hui() == date(2026, 1, 15), "23:30 à Paris : encore le 15"


def test_jour_civil_d_un_instant_de_la_base():
    """Un horodatage lu en base (UTC naïf) se lit au jour de Paris, pas au jour UTC."""
    assert horloge.jour_civil(datetime(2026, 7, 14, 22, 15)) == date(2026, 7, 15)
    assert horloge.jour_civil(datetime(2026, 7, 14, 21, 59)) == date(2026, 7, 14)
    #  Une date est déjà un jour civil : rendue telle quelle, jamais décalée.
    assert horloge.jour_civil(date(2026, 7, 14)) == date(2026, 7, 14)


def test_a_paris_rend_l_heure_murale_consciente():
    """L'instant de la base à l'heure de Paris — conscient, pour ne pas être repris pour de l'UTC."""
    vu = horloge.a_paris(datetime(2026, 7, 25, 8, 5))
    assert (vu.hour, vu.minute, vu.tzinfo) == (10, 5, horloge.TZ_PARIS)


# ── Le garde-fou : aucun autre « aujourd'hui » ni « maintenant » local ─────────

#: Le seul module qui a le droit de lire l'horloge du système.
_HORLOGE = "utils/horloge.py"


def _receveur(noeud: ast.AST) -> str:
    """`datetime.date.today` → `datetime.date` ; `date.today` → `date`."""
    if isinstance(noeud, ast.Name):
        return noeud.id
    if isinstance(noeud, ast.Attribute):
        return f"{_receveur(noeud.value)}.{noeud.attr}"
    return ""


def _sans_fuseau(appel: ast.Call) -> bool:
    """`datetime.now()`, `datetime.now(None)`, `tz=None` : l'heure du conteneur."""
    if appel.args:
        return isinstance(appel.args[0], ast.Constant) and appel.args[0].value is None
    tz = next((k.value for k in appel.keywords if k.arg == "tz"), None)
    return tz is None or (isinstance(tz, ast.Constant) and tz.value is None)


def _fautes_d_horloge(arbre: ast.AST) -> list[tuple[int, str]]:
    """Ce qui lit l'horloge du système sans passer par `horloge` — appelé OU référencé.

    Ruff `DTZ011`/`DTZ005` ne voient que les APPELS : `default_factory=date.today`
    — la forme des modèles, celle que le suivant recopiera — leur échappe. Ce
    contrôle lit l'arbre, comme celui de `utcnow` ci-dessus.

    ⚠️ Le `.date()` d'un instant UTC n'est reconnu que sur `maintenant` (appelé ou
    variable) : un horodatage lu en base ne se distingue pas, dans l'arbre, d'une
    date murale saisie (`ticket.debut`). Ce cas-là relève de `horloge.jour_civil`.
    """
    appels = {id(n.func): n for n in ast.walk(arbre) if isinstance(n, ast.Call)}
    fautes = []
    for n in ast.walk(arbre):
        if not isinstance(n, ast.Attribute):
            continue
        receveur = _receveur(n.value)
        horloge_systeme = receveur.split(".")[-1] in ("date", "datetime")
        if n.attr == "today" and horloge_systeme:
            fautes.append((n.lineno, f"{receveur}.today — le jour du conteneur"))
        elif n.attr == "now" and horloge_systeme:
            appel = appels.get(id(n))
            if appel is None or _sans_fuseau(appel):
                fautes.append((n.lineno, f"{receveur}.now sans fuseau — l'heure du conteneur"))
        elif n.attr == "date" and id(n) in appels and not appels[id(n)].args:
            cible = n.value.func if isinstance(n.value, ast.Call) else n.value
            if _receveur(cible).split(".")[-1] == "maintenant":
                fautes.append((n.lineno, "maintenant.date() — le jour UTC, pas celui de Paris"))
    return fautes


def test_aucun_autre_aujourd_hui_dans_app():
    """Un jour civil = `horloge.aujourd_hui()` ; un instant = `horloge.maintenant()`."""
    fautes = [
        f"app/{m.rel}:{ligne} — {motif}"
        for m in modules_app()
        if m.rel != _HORLOGE
        for ligne, motif in _fautes_d_horloge(m.arbre)
    ]
    assert not fautes, (
        "L'horloge du système se lit dans `app/utils/horloge.py`, nulle part ailleurs :\n"
        "  jour civil (calendrier, échéance, date affichée) → `horloge.aujourd_hui()`,\n"
        "  instant pour la base → `horloge.maintenant()`, heure de Paris → `horloge.a_paris`.\n"
        + "\n".join(f"  {f}" for f in fautes)
    )


def test_le_controle_d_horloge_sait_REFUSER():
    """Chaque forme refusée est reconnue — sinon le contrôle ci-dessus serait vert sur rien."""
    forges = {
        "x = date.today()": 1,
        "x = datetime.date.today()": 1,
        "x = datetime.today()": 1,
        "d: date = Field(default_factory=date.today)": 1,
        "x = datetime.now()": 1,
        "x = datetime.now(tz=None)": 1,
        "f = datetime.now": 1,
        "x = horloge.maintenant().date()": 1,
        "x = maintenant.date()": 1,
        #  Ce qui reste permis : un fuseau explicite, le jour d'un champ saisi.
        "x = datetime.now(timezone.utc)": 0,
        "x = datetime.now(TZ_PARIS)": 0,
        "x = ticket.debut.date()": 0,
        "x = horloge.aujourd_hui()": 0,
    }
    ecarts = {
        source: (trouvees, attendu)
        for source, attendu in forges.items()
        if (trouvees := len(_fautes_d_horloge(ast.parse(source)))) != attendu
    }
    assert not ecarts, f"(trouvées, attendues) : {ecarts}"


def test_le_fuseau_de_paris_s_ecrit_une_fois():
    """`"Europe/Paris"` ne s'écrit que dans `horloge` (`TZ_PARIS`).

    Il s'écrivait dans six modules, dont le planificateur (`backup.py`) qui
    interprète les `run_date` : changer l'un sans les autres, ce sont deux heures
    de décalage que rien ne signale.
    """
    fautes = [
        f"app/{m.rel}:{n.lineno}"
        for m in modules_app()
        if m.rel != _HORLOGE
        for n in ast.walk(m.arbre)
        if isinstance(n, ast.Constant) and n.value == "Europe/Paris"
    ]
    assert not fautes, "`horloge.TZ_PARIS`, jamais le nom du fuseau recopié :\n" + "\n".join(
        f"  {f}" for f in fautes
    )
    assert '"Europe/Paris"' in module_app(_HORLOGE).source, "le témoin a disparu : contrôle vide"


# ── Le garde-fou : le début du jour de Paris, en UTC, s'écrit une fois (#1617) ─
#
#  « Minuit de Paris exprimé en UTC naïf » — la borne d'une requête sur une
#  colonne `_le` — se calculait en trois copies (`routers/telemetry`,
#  `telemetry_aggregation`, `whatsapp_scheduler`). Une conversion de fuseau
#  recopiée diverge au premier changement d'heure mal traité. `horloge.
#  debut_du_jour_utc` est la seule.


def _minuit_local(noeud: ast.AST) -> bool:
    """`x.replace(hour=0, …)` ou `datetime.combine(…, time.min)` : un minuit recomposé."""
    if not (isinstance(noeud, ast.Call) and isinstance(noeud.func, ast.Attribute)):
        return False
    if noeud.func.attr == "replace":
        return any(
            k.arg == "hour" and isinstance(k.value, ast.Constant) and k.value.value == 0
            for k in noeud.keywords
        )
    if noeud.func.attr == "combine":
        return any(
            isinstance(a, ast.Attribute) and a.attr == "min" and _receveur(a.value).endswith("time")
            for a in noeud.args
        )
    return False


def _noeuds_du_scope(scope: ast.AST):
    """Les nœuds d'une fonction (ou du module), sans entrer dans les fonctions imbriquées."""
    pile = list(ast.iter_child_nodes(scope))
    while pile:
        n = pile.pop()
        yield n
        if not isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            pile.extend(ast.iter_child_nodes(n))


def _fautes_de_minuit_converti(arbre: ast.AST) -> list[int]:
    """Les lignes où un minuit recomposé est converti de fuseau dans la MÊME fonction.

    `replace(hour=0)` seul est banal (début de mois, planificateur) ; `.astimezone`
    seul aussi (un en-tête de courriel). C'est leur **conjonction** qui est la
    borne « début du jour de Paris en UTC », et qui appartient à `horloge`.
    """
    fautes = set()
    scopes = [arbre] + [
        n for n in ast.walk(arbre) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]
    for scope in scopes:
        noeuds = list(_noeuds_du_scope(scope))
        if any(isinstance(n, ast.Attribute) and n.attr == "astimezone" for n in noeuds):
            fautes.update(n.lineno for n in noeuds if _minuit_local(n))
    return sorted(fautes)


def test_le_debut_du_jour_utc_s_ecrit_une_fois():
    """Hors `horloge`, aucun minuit recomposé n'est converti de fuseau."""
    fautes = [
        f"app/{m.rel}:{ligne}"
        for m in modules_app()
        if m.rel != _HORLOGE
        for ligne in _fautes_de_minuit_converti(m.arbre)
    ]
    assert not fautes, (
        "Le début du jour de Paris en UTC naïf se demande à `horloge.debut_du_jour_utc`,\n"
        "  il ne se recompose pas (`replace(hour=0…)` + `astimezone`) :\n"
        + "\n".join(f"  {f}" for f in fautes)
    )
    assert "astimezone" in module_app(_HORLOGE).source, "le témoin a disparu : contrôle vide"


def test_le_controle_du_minuit_converti_sait_REFUSER():
    """Chaque recomposition est reconnue ; ce qui reste permis ne l'est pas."""
    forges = {
        "def f(d):\n  m = d.replace(hour=0, minute=0)\n  return m.astimezone(utc)": 1,
        "def f(d):\n  return d.replace(hour=0).astimezone(ZoneInfo('UTC'))": 1,
        "def f(d):\n  m = datetime.combine(d, time.min)\n  return m.astimezone(utc)": 1,
        "m = d.replace(hour=0)\nn = m.astimezone(utc)": 1,
        #  Permis : un minuit sans conversion, une conversion sans minuit,
        #  et les deux dans des fonctions DISTINCTES (aucun lien entre eux).
        "def f(d):\n  return d.replace(day=1, hour=0, minute=0)": 0,
        "def f(d):\n  return d.astimezone(utc)": 0,
        "def f(d):\n  return d.replace(hour=12).astimezone(utc)": 0,
        "def f(d):\n  return d.replace(hour=0)\ndef g(d):\n  return d.astimezone(utc)": 0,
        "x = horloge.debut_du_jour_utc()": 0,
    }
    ecarts = {
        source: (trouvees, attendu)
        for source, attendu in forges.items()
        if (trouvees := len(_fautes_de_minuit_converti(ast.parse(source)))) != attendu
    }
    assert not ecarts, f"(trouvées, attendues) : {ecarts}"


# ── Caractérisation : la fonction rend, octet pour octet, ce que rendaient les trois copies ──


def _ancien_telemetry(maintenant_utc: datetime) -> datetime:
    """Copie littérale de `routers/telemetry.dashboard` avant #1617."""
    from zoneinfo import ZoneInfo

    now_paris = horloge.a_paris(maintenant_utc)
    return (
        now_paris.replace(hour=0, minute=0, second=0, microsecond=0)
        .astimezone(ZoneInfo("UTC"))
        .replace(tzinfo=None)
    )


def _ancien_aggregation(dt_paris: datetime) -> datetime:
    """Copie littérale de `telemetry_aggregation._paris_midnight` avant #1617."""
    from zoneinfo import ZoneInfo

    midnight = dt_paris.replace(hour=0, minute=0, second=0, microsecond=0)
    return midnight.astimezone(ZoneInfo("UTC")).replace(tzinfo=None)


def _ancien_whatsapp(now: datetime) -> datetime:
    """Copie littérale de `whatsapp_scheduler._debut_du_jour_utc` avant #1617."""
    minuit_local = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return minuit_local.astimezone(timezone.utc).replace(tzinfo=None)


def _instants_a_risque() -> list[datetime]:
    """Des instants UTC naïfs autour des deux changements d'heure de 2026 — et d'autres."""
    bases = [
        datetime(2026, 3, 28, 22, 59),  # veille de la bascule d'été, 23:59 à Paris
        datetime(2026, 3, 28, 23, 0),  # 00:00 le 29 à Paris (encore UTC+1)
        datetime(2026, 3, 29, 0, 30),  # 01:30 à Paris, avant la bascule
        datetime(2026, 3, 29, 1, 0),  # 03:00 à Paris (UTC+2) — l'heure 02:xx n'existe pas
        datetime(2026, 3, 29, 21, 59),  # 23:59 le 29 (UTC+2)
        datetime(2026, 3, 29, 22, 0),  # 00:00 le 30
        datetime(2026, 10, 24, 21, 59),  # 23:59 le 24 (UTC+2)
        datetime(2026, 10, 24, 22, 0),  # 00:00 le 25 (UTC+2)
        datetime(2026, 10, 25, 0, 30),  # 02:30 CEST, première occurrence
        datetime(2026, 10, 25, 1, 30),  # 02:30 CET, seconde occurrence (fold=1)
        datetime(2026, 10, 25, 22, 59),  # 23:59 le 25 (UTC+1)
        datetime(2026, 10, 25, 23, 0),  # 00:00 le 26 (UTC+1)
        datetime(2026, 1, 15, 23, 30),
        datetime(2026, 7, 14, 21, 59),
        datetime(2026, 7, 14, 22, 0),
        datetime(2025, 12, 31, 23, 0),
        datetime(2028, 2, 29, 12, 0),
    ]
    return bases + [b + timedelta(hours=h) for b in bases for h in (1, 13)]


def test_debut_du_jour_utc_vaut_l_ancien_calcul_des_trois_copies():
    """Même résultat que les trois anciennes copies, sur des instants autour des changements d'heure."""
    instants = _instants_a_risque()
    assert len(instants) > 40, "cas zéro : la grille d'instants est vide ou rabougrie"
    verifies = set()
    for u in instants:
        paris = horloge.a_paris(u)
        attendu = _ancien_telemetry(u)
        assert _ancien_aggregation(paris) == attendu == _ancien_whatsapp(paris)
        #  Les appelants passaient un datetime de Paris (conscient) : même réponse.
        assert horloge.debut_du_jour_utc(paris) == attendu, u
        #  Un instant de la base (UTC naïf), lu au jour de Paris : même réponse.
        assert horloge.debut_du_jour_utc(u) == attendu, u
        #  Un jour (date) : même réponse que l'instant qui le porte.
        assert horloge.debut_du_jour_utc(paris.date()) == attendu, u
        assert horloge.debut_du_jour_utc(u).tzinfo is None
        verifies.add(attendu)
    #  La grille doit réellement toucher les deux décalages (UTC+1 et UTC+2).
    assert {d.hour for d in verifies} == {22, 23}


def test_debut_du_jour_utc_au_fil_des_jours_comme_la_boucle_d_agregation():
    """`telemetry_aggregation` avance de jour en jour (`+ timedelta(days=1)`) : même borne à chaque pas."""
    courant = datetime(2026, 3, 25, tzinfo=horloge.TZ_PARIS)
    for _ in range(10):  # franchit la bascule d'été du 29/03
        assert horloge.debut_du_jour_utc(courant) == _ancien_aggregation(courant)
        courant += timedelta(days=1)
    courant = datetime(2026, 10, 21, tzinfo=horloge.TZ_PARIS)
    for _ in range(10):  # franchit la bascule d'hiver du 25/10
        assert horloge.debut_du_jour_utc(courant) == _ancien_aggregation(courant)
        courant += timedelta(days=1)


def test_debut_du_jour_utc_sans_argument_est_aujourd_hui(monkeypatch):
    """22:30 UTC le 1er octobre = 00:30 le 2 à Paris : la borne est le 2 à 00:00 Paris = 22:00 UTC le 1er."""
    _figer(monkeypatch, datetime(2026, 10, 1, 22, 30))
    assert horloge.debut_du_jour_utc() == datetime(2026, 10, 1, 22, 0)
    _figer(monkeypatch, datetime(2026, 1, 15, 22, 30))  # 23:30 à Paris le 15, UTC+1
    assert horloge.debut_du_jour_utc() == datetime(2026, 1, 14, 23, 0)
