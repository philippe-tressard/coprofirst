"""La longueur minimale d'un mot de passe : une source au serveur, une copie au front (#2763).

## Pourquoi ce test existe (16/11/2026)

Le serveur porte la règle une fois — `app/utils/mots_de_passe.LONGUEUR_MIN_MOT_DE_PASSE`,
publiée aux apps dans `app/contrat/constantes-clients.json` (`longueurMinMotDePasse`).
Le site l'écrivait « 8 » en dur à neuf endroits : la condition et le message du
changement de mot de passe, le critère et le libellé de la jauge de robustesse, et
l'attribut `minlength` des champs de l'inscription, de la réinitialisation et du
profil. La monter à 10 au serveur aurait laissé le site annoncer « 8 », accepter
l'envoi, puis le serveur refuser.

Front et API ne partagent aucun fichier (contextes de build `./api` et `./front`,
#335) : le front tient UNE copie nommée, `front/src/lib/mots-de-passe.ts`, et ce
test la compare au serveur — le motif de `test_avis_seuils_front.py`.

## Ce qu'il tient, dans les deux sens (`standards/05` §9 bis)

1. la copie du front dit la valeur du serveur ;
2. aucun fichier de `front/src` ne réécrit la règle en chiffres : `longueurMini={8}`,
   `pwd.length < 8`, « 8 caractères minimum ». Le seuil et ses messages se lisent
   dans la constante.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from app.utils.mots_de_passe import LONGUEUR_MIN_MOT_DE_PASSE

_SRC = Path(__file__).resolve().parents[2] / "front" / "src"
_SOURCE = _SRC / "lib" / "mots-de-passe.ts"
_NOM = "LONGUEUR_MIN_MOT_DE_PASSE"

#: Les formes d'une longueur minimale de mot de passe écrite en chiffres. Une
#: comparaison à zéro (« le champ est-il vide ? ») n'en est pas une.
_FORMES_FAUTIVES = (
    #  La prop de `ChampMotDePasse`, qui pose l'attribut `minlength`.
    re.compile(r"longueurMini\s*=\s*[{\"']\s*\d+"),
    #  Une saisie de mot de passe comparée à un nombre non nul.
    re.compile(
        r"\w*(?:password|pwd|mdp|motdepasse)\w*\s*\.\s*length\s*(?:[<>]=?|[!=]==?)\s*[1-9]\d*",
        re.IGNORECASE,
    ),
    #  Le message : « 8 caractères minimum », « 8 caractères au minimum »,
    #  « minimum 8 caractères », « au minimum de 8 caractères ».
    re.compile(r"\d+\s*caractères\s+(?:au\s+)?minimum", re.IGNORECASE),
    re.compile(r"minimum\s+(?:de\s+)?\d+\s*caractères", re.IGNORECASE),
)

_COMMENTAIRES = re.compile(r"<!--.*?-->|/\*.*?\*/|(?<![:'\"\w])//[^\n]*", re.DOTALL)


def _sans_commentaires(texte: str) -> str:
    """Les commentaires blanchis, sauts de ligne gardés : les numéros restent justes.

    Un en-tête qui raconte la forme refusée n'est pas une copie.
    """
    return _COMMENTAIRES.sub(lambda m: re.sub(r"[^\n]", " ", m.group(0)), texte)


def _fautes(texte: str) -> list[int]:
    """Les numéros des lignes qui écrivent la règle en chiffres, hors commentaires."""
    return [
        n
        for n, ligne in enumerate(_sans_commentaires(texte).split("\n"), start=1)
        if any(f.search(ligne) for f in _FORMES_FAUTIVES)
    ]


def _fichiers_front() -> list[Path]:
    return sorted(p for p in _SRC.rglob("*") if p.suffix in {".svelte", ".ts", ".js"})


def test_la_copie_du_front_est_la_valeur_du_serveur():
    source = _SOURCE.read_text(encoding="utf-8")
    trouve = re.search(rf"export const {_NOM} = (\d+);", source)
    assert trouve, f"{_NOM} introuvable dans {_SOURCE.name} : le contrôle ne mesure plus rien"
    assert int(trouve.group(1)) == LONGUEUR_MIN_MOT_DE_PASSE, (
        f"Le front annonce {trouve.group(1)} caractères, le serveur en exige "
        f"{LONGUEUR_MIN_MOT_DE_PASSE} : corriger `front/src/lib/mots-de-passe.ts`."
    )


def test_aucun_ecran_n_ecrit_la_longueur_minimale_en_chiffres():
    fichiers = _fichiers_front()
    #  Cas zéro (`standards/04` §2) : rien lu n'est pas « aucune copie ».
    assert len(fichiers) > 100, f"{len(fichiers)} fichier(s) lu(s) sous {_SRC} : INCONNU"
    copies = [
        f"{p.relative_to(_SRC.parent)}:{n}"
        for p in fichiers
        if p != _SOURCE
        for n in _fautes(p.read_text(encoding="utf-8"))
    ]
    assert not copies, (
        "Longueur minimale d'un mot de passe écrite en chiffres :\n  "
        + "\n  ".join(copies)
        + f"\nLire `{_NOM}` (`#lib/mots-de-passe.ts`), seuil ET message."
    )


def test_la_constante_est_lue_par_les_ecrans_qui_la_portaient():
    """Le témoin : sans lecteur, une constante juste ne protège rien."""
    lecteurs = {
        p.relative_to(_SRC).as_posix()
        for p in _fichiers_front()
        if p != _SOURCE and _NOM in p.read_text(encoding="utf-8")
    }
    attendus = {
        "lib/components/ChangementMotDePasse.svelte",
        "lib/components/PasswordStrength.svelte",
        "routes/auth/inscription/+page.svelte",
        "routes/auth/reinitialisation-mdp/+page.svelte",
    }
    assert attendus <= lecteurs, f"ne lisent pas {_NOM} : {sorted(attendus - lecteurs)}"


@pytest.mark.parametrize(
    ("ligne", "attendu"),
    [
        #  Les neuf écritures d'avant #2763, une par forme.
        ("\t\t\t\tlongueurMini={8}", 1),
        ("\t\t\t: pwdNouv.length < 8", 1),
        ("\t$: hasLength = password.length >= 8;", 1),
        ("\t\t\t\t? 'Le nouveau mot de passe doit faire 8 caractères au minimum.'", 1),
        ("\t\t{ label: '8 caractères minimum', ok: hasLength },", 1),
        #  Les variantes qu'un écran neuf écrirait.
        ('<ChampMotDePasse longueurMini="10" />', 1),
        ("if (nouveauMdp.length <= 9) return;", 1),
        ("'Au minimum 8 caractères.'", 1),
        #  La forme voulue, jamais signalée.
        ("\t\t\t\tlongueurMini={LONGUEUR_MIN_MOT_DE_PASSE}", 0),
        ("\t$: hasLength = password.length >= LONGUEUR_MIN_MOT_DE_PASSE;", 0),
        ("\t\t{ label: `${LONGUEUR_MIN_MOT_DE_PASSE} caractères minimum`, ok: hasLength },", 0),
        #  Un champ vide n'est pas une longueur minimale.
        ("\t$: confirmationDivergente = confirmMdp.length > 0 && a !== b;", 0),
        ("\tpwdActuel.length === 0", 0),
        #  Un nombre de photos n'est pas un mot de passe.
        ("{#if photos.length <= 8}", 0),
        #  Un commentaire qui cite la forme refusée.
        ("// on écrivait longueurMini={8} ici", 0),
        ("<!-- « 8 caractères minimum » -->", 0),
    ],
)
def test_les_formes_fautives_sont_reconnues(ligne, attendu):
    assert len(_fautes(ligne)) == attendu
