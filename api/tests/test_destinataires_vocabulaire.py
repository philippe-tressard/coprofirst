"""Le vocabulaire des destinataires est le MÊME des deux côtés.

Le sélecteur (`front/src/lib/destinataires.ts`) et la règle d'accès
(`app/utils/visibility.public_cible_visible`) portent chacun leur liste de codes.
Rien, dans le code, n'oblige les deux à rester d'accord — et les conséquences
d'un écart sont silencieuses des deux côtés :

  • un code proposé à l'écran mais inconnu du serveur produit une pastille qui ne
    cible RIEN. Pire : `public_cible_visible` refuse ce qu'elle ne reconnaît pas,
    donc la publication devient invisible de tous, sans message ;
  • un code connu du serveur mais absent du sélecteur est une règle que personne
    ne peut choisir — du code mort qui a l'air vivant.

C'est le couplage implicite entre deux fichiers que `standards/05` §« analyse
statique » décrit : ni Python ni TypeScript ne peuvent le voir, et seul un
contrôle qui lit les deux le tient.

⚠️ Le test ne compare pas deux listes déclaratives, ce qui ne prouverait rien de
plus que leur égalité. Il vérifie AUSSI que chaque code annoncé est réellement
honoré par la règle — autrement, `CODES_PUBLIC_CIBLE` pourrait annoncer un code
que la fonction ignore, et les deux côtés seraient d'accord sur une fiction.
"""

import re
from pathlib import Path

import pytest

from app.models.core import StatutUtilisateur, Utilisateur
from app.utils.visibility import CODES_PUBLIC_CIBLE, LIBELLES_PUBLIC_CIBLE, public_cible_visible

_FRONT = Path(__file__).resolve().parents[2] / "front" / "src" / "lib" / "destinataires.ts"

#: Un porteur possible pour chaque code : le statut (et le rôle) d'un utilisateur
#: qui DOIT le voir. Sert à prouver que la règle connaît vraiment le code.
_TEMOIN = {
    "copropriétaires_occupants": (StatutUtilisateur.copropriétaire_résident, "résident"),
    "bailleurs": (StatutUtilisateur.copropriétaire_bailleur, "résident"),
    "mandataires": (StatutUtilisateur.mandataire, "résident"),
    "locataires": (StatutUtilisateur.locataire, "résident"),
    "conseil_syndical": (StatutUtilisateur.copropriétaire_résident, "conseil_syndical"),
}


def _table_du_front() -> str:
    """Le corps de la table `DESTINATAIRES` du sélecteur."""
    source = _FRONT.read_text(encoding="utf-8")
    bloc = re.search(r"DESTINATAIRES\s*:\s*Destinataire\[\]\s*=\s*\[(.*?)\n\];", source, re.S)
    assert bloc, (
        f"table DESTINATAIRES introuvable dans {_FRONT} : le contrôle ne peut pas "
        "s'exécuter, il ne doit donc pas passer au vert (standards/04 §2)"
    )
    return bloc.group(1)


def _codes_du_front() -> list[str]:
    """Les `code:` de la table `DESTINATAIRES`, dans leur ordre d'affichage."""
    return re.findall(r"code:\s*'([^']+)'", _table_du_front())


def _libelles_du_front() -> dict[str, str]:
    """`code` → `libelle` de la table `DESTINATAIRES`, tels que l'écran les montre."""
    return dict(re.findall(r"code:\s*'([^']+)',\s*libelle:\s*'([^']+)'", _table_du_front()))


def test_le_front_est_lisible():
    """Cas zéro : sans source lisible, on échoue au lieu de conclure au vert."""
    assert _FRONT.exists(), f"{_FRONT} introuvable"
    assert len(_codes_du_front()) >= 3


def test_memes_codes_des_deux_cotes():
    assert _codes_du_front() == list(CODES_PUBLIC_CIBLE), (
        "Le sélecteur et la règle d'accès ne proposent plus les mêmes destinataires.\n"
        f"  front  : {_codes_du_front()}\n"
        f"  serveur: {list(CODES_PUBLIC_CIBLE)}\n"
        "Un code présent d'un seul côté est soit une pastille qui ne cible rien, "
        "soit une règle que personne ne peut choisir."
    )


@pytest.mark.parametrize("code", CODES_PUBLIC_CIBLE)
def test_chaque_code_annonce_est_reellement_honore(code):
    """La liste ne peut pas annoncer un code que la règle ignore.

    Sans ce test, `CODES_PUBLIC_CIBLE` et le front pourraient être d'accord sur
    un code que `public_cible_visible` ne reconnaît pas — deux listes cohérentes
    décrivant un comportement inexistant.
    """
    statut, roles = _TEMOIN[code]
    temoin = Utilisateur(
        nom="X",
        prenom="Y",
        email=f"{code}@test.test",
        statut=statut,
        roles_json=roles,
        actif=True,
    )
    assert public_cible_visible(f'["{code}"]', temoin) is True, (
        f"« {code} » est annoncé au catalogue mais la règle ne l'honore pour personne."
    )


def test_memes_libelles_des_deux_cotes():
    """Le serveur écrit ces libellés dans la Suite qui change les Destinataires
    (`visibility/trace_droits.py`, 29/09/2026) : ils doivent être ceux que le
    conseil a cochés à l'écran, sinon la trace nomme un public qu'il n'a pas vu."""
    assert len(_libelles_du_front()) == len(_codes_du_front()), "libellé illisible au front"
    assert _libelles_du_front() == LIBELLES_PUBLIC_CIBLE


def test_un_temoin_par_code():
    """Le test ci-dessus ne vaut que si chaque code a son témoin."""
    assert set(_TEMOIN) == set(CODES_PUBLIC_CIBLE)


def test_le_code_par_defaut_n_est_pas_dans_le_catalogue():
    """`résidents` est l'ABSENCE de restriction, pas un profil.

    Le glisser dans la table en ferait une pastille de plus, à côté de celle que
    le sélecteur rend déjà à part — deux façons de dire « tout le monde ».
    """
    assert "résidents" not in CODES_PUBLIC_CIBLE
    assert "résidents" not in _codes_du_front()
    #  Et il reste bien reconnu par la règle, lui.
    quiconque = Utilisateur(
        nom="X",
        prenom="Y",
        email="tous@test.test",
        statut=StatutUtilisateur.locataire,
        roles_json="résident",
        actif=True,
    )
    assert public_cible_visible('["résidents"]', quiconque) is True
