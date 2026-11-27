"""Aucun nom de personne réelle dans le dépôt PUBLIC (#1493, 01/10/2026).

## Le constat

L'audit de pertinence des tests (30/09/2026) a trouvé, dans ce dépôt public, les
noms du personnel du syndic, de résidents et de l'auteur, recopiés depuis l'écran
ou le fichier d'import qui avait motivé un test ou un commentaire : trente-trois
fichiers, code et tests. Une donnée personnelle publiée est un défaut de rang 1
(`standards/14`), et l'historique git la conserve.

Arbitré le 01/10/2026 : l'arbre courant est nettoyé, l'historique est accepté tel
quel — une réécriture serait incomplète, GitHub gardant les références des PR.

## Ce que ce contrôle tient

Une liste BLANCHE, jamais une liste noire : écrire les vrais noms dans un
contrôle les republierait, compilés cette fois. Tout nom de personne repéré dans
le code ou les tests doit figurer dans `FICTIFS` — l'y ajouter, c'est AFFIRMER
qu'il est inventé. Un mot repéré qui n'est pas un nom (« STOCK », « Témoin »)
va dans `PAS_DES_NOMS`. Une entrée qui ne sert plus fait échouer le contrôle.

Formes repérées :
- une civilité suivie d'un nom en toute casse, avec ou sans prénom ni
  particule (« Mme DUPONT », « Madame Hélène Dupont », « M. de LeRoy »),
  partout ;
- « Prénom NOM » ou « NOM Prénom » en littéral entier ou entre guillemets
  français, partout — et un prénom composé suivi d'un nom à casse mixte
  (« Jean-Hervé ForT »), qui avait échappé au premier passage ;
- la valeur d'un champ de nom (`nom=`, `prenom=`, `auteur_nom:`…), dans les
  tests et l'e2e — dans l'application, ces champs portent des libellés ;
- un mot en CAPITALES seul entre parenthèses (« … rouge (ZORGLUB) »), partout,
  quand ce mot ne s'écrit nulle part ailleurs dans le dépôt comme un mot
  ordinaire : c'est la forme d'un récit d'arbitrage qui citait deux comptes réels
  dans une docstring (#2560). Un sigle (« (SMTP) ») s'écrit aussi en minuscules
  ou se déclare dans `PAS_DES_NOMS`.

Portée : TOUT fichier texte suivi par git (`git ls-files`), moins des exclusions
nommées (`NON_LUS`), comme `test_hotes_fictifs.py` (#2961, 24/11/2026). Elle était
une liste de dossiers : 137 fichiers texte lui échappaient (`whatsapp-bridge/`,
`deploiement/`, `api/alembic_plateforme/`, `Caddyfile`…), et un dossier neuf
n'était lu que si quelqu'un pensait à l'ajouter — le mécanisme même de #1544, où
une docstring de migration nommait deux employées du syndic hors de toute
portée. Un dossier de premier niveau ni lu ni exclu nommément fait échouer
(`test_chaque_dossier_suivi_est_lu_ou_exclu`).

⚠️ Ce qu'il ne voit pas : un nom isolé hors de ces formes — « Prénom Nom » sans
civilité ni capitales, par exemple : à casse mixte, la forme attraperait chaque
paire de mots entre guillemets —, un nom dans un IDENTIFIANT (`test_zorglub_…` :
les deux noms de #2560 nommaient aussi des tests), ni ce qui est public sans être un fichier :
messages de commit, tickets et PR GitHub. La consigne qui couvre le reste :
`.claude/skills/security-audit`. L'attribution légale (`NOTICE.md`,
`LICENSE`, SPDX) est hors de sa portée, et c'est voulu : elle doit
nommer l'auteur.
"""

from __future__ import annotations

import pathlib
import re
import subprocess
import unicodedata
from collections import defaultdict

RACINE = pathlib.Path(__file__).resolve().parents[2]
CE_FICHIER = "api/tests/test_identites_fictives.py"

#: Ce qui n'est pas lu, chacun avec sa raison :
#: - l'attribution légale (`NOTICE.md`, `LICENSE`, `LICENSES/`, `REUSE.toml`) nomme
#:   l'auteur, et c'est voulu ;
#: - `package-lock.json` : écrit par npm, il ne porte que des paquets et des
#:   empreintes, des milliers de lignes qu'aucune personne n'écrit ;
#: - les binaires, par leur suffixe (une image, une police) ; un fichier qui ne se
#:   décode pas en UTF-8 est sauté aussi (`_sources`).
NON_LUS = re.compile(
    r"^(NOTICE\.md|LICENSE|REUSE\.toml)$|^LICENSES/|(^|/)package-lock\.json$"
    r"|\.(png|jpe?g|gif|webp|ico|pdf|woff2?|ttf|otf|heic|zip|gz)$"
)
#: Les dossiers de premier niveau qui ne sont pas lus du tout — exclus NOMMÉMENT.
DOSSIERS_NON_LUS = frozenset({"LICENSES"})

#: Où vivent les jeux de données : les champs de nom y portent des personnes.
#: `api/app/demo/` est le jeu de la démo publique (spec `mode-demo.md` §6.3, #1904).
DONNEES = ("api/tests/", "front/e2e/", "api/app/demo/")

#: Les noms inventés. En ajouter un, c'est affirmer qu'il ne désigne personne
#: de la résidence, du syndic ni de ses prestataires.
FICTIFS = frozenset(
    """
    ADELE ALAIN ALEX ALICE ALIX ANNE BERNARD BLONDEL BRUNO CAMILLE CARON CATHERINE
    CHLOE CHRISTINE CHRISTOPHE CLAIRE COLLARD DELMAS DUPONT DUPRE DURAND DURANDAL ELISE
    ELODIE FAURE FORT HELENE INES ITO JEAN JEAN-BAPTISTE JEAN-CHRISTOPHE JEAN-HERVE JEANNE KERBRAT
    LAMBERT LEROY LUC LYON MARC MARCEL MARCO MARTIN MARTIN-LEROY MARTINEAU MERCIER
    MOI MOREL MORIN-LEGRAND NADIA ODILE PAUL PERRIN PHILIPPE PIERRE REINE RENARD RENEE
    ROBIN ROSSI ROUSSEL ROY SIDENTE SOPHIE SOREL SYLVIE VERDIERE ZELLER ZOE
    """.split()
)

#: Les mots que les formes ci-dessus attrapent sans qu'ils nomment quelqu'un :
#: entreprises, lieux, rôles, mots d'interface.
PAS_DES_NOMS = frozenset(
    """
    ADMIN AMIANTE ANCIEN EXEMPLE FICTIF APERCU APPROVED ASCENSEURS ASSUREUR AULNAY AUTRE BAILLEUR BEARER
    BONJOUR BSD CABINET CAS CLE COMPTEURS CONSEIL CONSTATE COPRO COPROPRIETE CORPS COTE CRAYON CSS
    DEGAT DEJA DEMANDEUR DUREE ENTREE ENVIRONNEMENTS ESPACES ESSAI EXTERNE FAQ GEST HALL HTML INCENDIE
    INCONNU LES LICENSE LIE LOC LOCATAIRE MIS MIT MIXTE MME NOM NOUVEAU NOUVEL NOUVELLE
    NOYAU OSI OTIS PARC PARTI PDF PLANS PLOMBERIE PRENOM PROPRIO REGLEMENT
    REJEU RESIDENCE RESIDENT SANS SANSBAT SCAN SECURITE SERIE SERVICES SICLI SITE
    SONDAGE SOURCE STOCK SYNDIC TEMOIN TEST TILLEULS UNUSED VERTS
    AAAA-MM-JJ AAAAMMJJ ANAH DAPP DSFR ECONNREFUSED EINVAL ERESOLVE HSTS ISC ISCL LCEN
    LGPL ONDE RGESN SAMU SIGKILL SIGPIPE SSRF WSAENOBUFS WYSIWYG ENF FCP MVP OOM PWA RGPD
    SCA TTI
    """.split()
)

_MAJ = "A-ZÀÂÄÇÉÈÊËÎÏÔÖÙÛÜ"
_MIN = "a-zàâäçéèêëîïôöùûü"
_PRENOM = rf"[{_MAJ}][{_MIN}]+(?:-[{_MAJ}][{_MIN}]+)?"
_NOM = rf"[{_MAJ}][{_MAJ}'-]+[{_MAJ}]"
#: Un prénom COMPOSÉ annonce une personne même quand le nom suit à casse mixte
#: (« Jean-Hervé ForT ») : la forme exacte d'une saisie signalée à l'écran.
_PRENOM_COMPOSE = rf"[{_MAJ}][{_MIN}]+-[{_MAJ}][{_MIN}]+"
_PERSONNE = (
    rf"(?:{_PRENOM}\**\s+{_NOM})|(?:{_NOM}\s+{_PRENOM})"
    rf"|(?:{_PRENOM_COMPOSE}\s+[{_MAJ}][{_MAJ}{_MIN}'-]+)"
)

#: Après une civilité, le nom s'écrit en toute casse : capitales, « Zorglub »,
#: « LeZorglub » (majuscule intérieure), précédé ou non d'un prénom et d'une
#: particule — qui reste hors des groupes : elle n'est pas un nom (#1544).
CIVILITE = re.compile(
    rf"\b(?:M\.|Mme|Madame|Monsieur)\s+(?:({_PRENOM})\s+)?(?:(?:de|du)\s+|d')?"
    rf"([{_MAJ}][{_MAJ}{_MIN}'-]*[{_MAJ}{_MIN}])"
)
LITTERAL = re.compile(rf"[\"']({_PERSONNE})[\"']")
GUILLEMETS = re.compile(rf"«\s*\**({_PERSONNE})")
CHAMP = re.compile(
    r"\b(?:nom|prenom|nom_complet|nom_proprietaire|nom_locataire|nom_coproprietaire"
    r"|auteur_nom|porteur_nom)\s*[=:]\s*[\"']([^\"'{}\n]+)[\"']"
)
_MOT = re.compile(rf"[{_MAJ}{_MIN}][{_MAJ}{_MIN}'-]{{2,}}")
#: Un mot en capitales seul entre parenthèses (#2560).
PARENTHESES = re.compile(rf"\(\s*({_NOM})\s*\)")
#: Un identifiant à tiret bas (`test_zorglub_x`) : ses morceaux ne sont pas des
#: mots ORDINAIRES, ils ne blanchissent pas un nom.
_IDENTIFIANT = re.compile(r"\b\w*_\w*\b")

#: Occurrences repérées sur l'arbre du 01/10/2026 : environ 330. Sous ce
#: plancher, une portée ou un motif a cassé, et le contrôle ne lit plus rien.
PLANCHER = 200


def capitales_entre_parentheses(source: str) -> list[str]:
    """Les mots en CAPITALES seuls entre parenthèses, normalisés (#2560)."""
    return [_normaliser(m.group(1)) for m in PARENTHESES.finditer(source)]


def mots_ordinaires(source: str) -> set[str]:
    """Les mots écrits autrement qu'en capitales, hors identifiants, normalisés."""
    texte = _IDENTIFIANT.sub(" ", source)
    return {_normaliser(m) for m in _MOT.findall(texte) if not m.isupper()}


def _normaliser(mot: str) -> str:
    sans_accent = unicodedata.normalize("NFD", mot)
    return "".join(c for c in sans_accent if unicodedata.category(c) != "Mn").upper()


def noms_dans(source: str, *, donnees: bool) -> list[str]:
    """Les mots repérés comme des noms de personne, normalisés, avec répétitions."""
    motifs = (CIVILITE, LITTERAL, GUILLEMETS) + ((CHAMP,) if donnees else ())
    return [
        _normaliser(mot)
        for motif in motifs
        for trouve in motif.finditer(source)
        for groupe in trouve.groups()
        if groupe
        for mot in _MOT.findall(groupe)
    ]


def _git_ls_files() -> list[str]:
    sortie = subprocess.run(
        ["git", "ls-files", "-z"], cwd=RACINE, capture_output=True, text=True, check=True
    ).stdout
    return [f for f in sortie.split("\0") if f]


def _sources() -> list[tuple[str, str, bool]]:
    """(chemin relatif, texte, est-ce un jeu de données) pour tout fichier texte suivi."""
    lus = []
    for rel in _git_ls_files():
        if rel == CE_FICHIER or NON_LUS.search(rel):
            continue
        try:
            texte = (RACINE / rel).read_text(encoding="utf-8")
        except (UnicodeDecodeError, FileNotFoundError, IsADirectoryError):
            continue  # un binaire sans suffixe connu, ou un fichier retiré non encore committé
        lus.append((rel, texte, rel.startswith(DONNEES)))
    assert len(lus) > 1000, f"{len(lus)} fichiers lus — cas zéro, la lecture a échoué"
    return lus


def _premier_niveau(rel: str) -> str:
    """Le dossier de premier niveau d'un chemin, ou `""` pour un fichier de la racine."""
    return rel.split("/", 1)[0] if "/" in rel else ""


def _releve() -> dict[str, set[str]]:
    vus: dict[str, set[str]] = defaultdict(set)
    total = 0
    sources = _sources()
    ordinaires = set().union(*(mots_ordinaires(source) for _, source, _ in sources))
    for rel, source, donnees in sources:
        entre_parentheses = [m for m in capitales_entre_parentheses(source) if m not in ordinaires]
        for nom in noms_dans(source, donnees=donnees) + entre_parentheses:
            vus[nom].add(rel)
            total += 1
    assert total >= PLANCHER, (
        f"{total} nom(s) repéré(s), plancher {PLANCHER} : un motif ou une portée a "
        "cassé, et le contrôle est vert sur rien."
    )
    return vus


def test_chaque_forme_est_reperee():
    """🔴 Le cas fautif d'abord : chaque forme attrape un nom inventé pour l'occasion."""
    assert noms_dans('nom="ZORGLUB"', donnees=True) == ["ZORGLUB"]
    assert noms_dans('nom="ZORGLUB"', donnees=False) == [], "un libellé d'écran n'est pas un nom"
    assert noms_dans("« Remplace Mme ZORGLUB »", donnees=False) == ["ZORGLUB"]
    assert noms_dans("Monsieur Zorglub,", donnees=False) == ["ZORGLUB"]
    assert noms_dans("const A = 'Hélène ZORGLUB';", donnees=False) == ["HELENE", "ZORGLUB"]
    assert noms_dans("« ZORGLUB Hélène » à la lettre Z", donnees=False) == ["ZORGLUB", "HELENE"]
    #  Prénom composé + nom à casse mixte : la forme d'un signalement à l'écran,
    #  « Prénom NomMalSaisi » — elle avait échappé au premier passage (01/10/2026).
    assert noms_dans("« Jean-Hervé ZorgluB », signalé", donnees=False) == ["JEAN-HERVE", "ZORGLUB"]
    #  Civilité + nom en casse mixte : la forme d'une formule d'appel recopiée
    #  dans une docstring de migration (#1544) — prénom, particule, majuscule
    #  intérieure. « Mme LeZorglub » ne rendait que « Le », trop court pour compter.
    assert noms_dans("« Madame Hélène Zorglub, »", donnees=False) == ["HELENE", "ZORGLUB"]
    assert noms_dans("Mme LeZorglub a répondu", donnees=False) == ["LEZORGLUB"]
    assert noms_dans("Madame de Zorglub,", donnees=False) == ["ZORGLUB"]
    assert noms_dans("M. Paul d'Zorglub", donnees=False) == ["PAUL", "ZORGLUB"]
    #  Un nom en capitales seul entre parenthèses, dans le récit d'un arbitrage
    #  (#2560) : il n'est pas un mot ordinaire du texte, il est relevé.
    recit = "un « TC » rouge (ZORGLUB), un sigle (SMTP), et smtp en minuscules"
    assert capitales_entre_parentheses(recit) == ["ZORGLUB", "SMTP"]
    assert "SMTP" in mots_ordinaires(recit) and "ZORGLUB" not in mots_ordinaires(recit)
    assert "ZORGLUB" not in mots_ordinaires("def test_zorglub_sans_parking(): ...")


def test_aucun_nom_reel_dans_le_code_ni_les_tests():
    vus = _releve()
    inconnus = sorted(n for n in vus if n not in FICTIFS | PAS_DES_NOMS)
    assert not inconnus, (
        "Nom(s) de personne non déclaré(s) fictif(s) — le dépôt est PUBLIC (#1493) :\n"
        + "\n".join(f"  • {n} — {', '.join(sorted(vus[n]))}" for n in inconnus)
        + "\nUn nom tiré d'un écran, d'un import ou d'un courriel est une donnée "
        "personnelle : le remplacer par un nom inventé de même forme. Un nom déjà "
        "inventé s'ajoute à `FICTIFS` ; un mot qui n'est pas un nom, à `PAS_DES_NOMS`."
    )


def test_chaque_dossier_suivi_est_lu_ou_exclu():
    """Un dossier de premier niveau suivi par git est lu, ou exclu nommément (#2961)."""
    sources = _sources()
    suivis = {_premier_niveau(f) for f in _git_ls_files()} - {""}
    lus = {_premier_niveau(rel) for rel, _, _ in sources} - {""}
    muets = sorted(suivis - lus - DOSSIERS_NON_LUS)
    assert not muets, (
        f"dossier(s) suivi(s) dont aucun fichier n'est lu : {muets} — les lire, ou les "
        "déclarer dans DOSSIERS_NON_LUS avec leur raison"
    )
    morts = sorted(DOSSIERS_NON_LUS - suivis)
    assert not morts, f"DOSSIERS_NON_LUS nomme un dossier que git ne suit plus : {morts}"
    assert not DOSSIERS_NON_LUS & lus, "un dossier exclu est pourtant lu : l'exclusion ment"
    for donnees in DONNEES:
        assert any(rel.startswith(donnees) and d for rel, _, d in sources), (
            f"`{donnees}` ne rend aucun fichier lu comme jeu de données : il a bougé."
        )


def test_chaque_entree_declaree_sert_encore():
    vus = _releve()
    morts = sorted((FICTIFS | PAS_DES_NOMS) - set(vus))
    assert not morts, (
        f"Entrée(s) qui ne servent plus : {morts}. Les retirer — une liste blanche qui "
        "ne décroît pas finit par couvrir le prochain vrai nom."
    )
    assert not FICTIFS & PAS_DES_NOMS, "un mot est à la fois un nom et pas un nom"
