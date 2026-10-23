"""Le bridge doit accepter ce que l'API lui envoie — et le repli doit exister.

## L'incident (#1057, 19/09/2026)

Un ticket partagé sur le groupe WhatsApp n'est jamais arrivé. Deux tentatives,
deux `413 Payload Too Large`, et rien à l'écran.

La chaîne, en trois maillons dont aucun n'était fautif seul :

| Maillon | Ce qu'il faisait |
|---|---|
| `routers/uploads.py` | stocke la photo en JPEG 1600 px — **152 à 188 ko** en pratique |
| `utils/whatsapp*.py` | l'envoie **en base64 dans le corps JSON** — ×4/3, soit ≈ 200 ko |
| `whatsapp-bridge/index.js` | `express.json()` **sans option** — plafond par défaut : **100 kio** |

Le bridge refusait donc le corps **avant de le lire**. Tout partage portant une
photo était perdu, sur tous les objets du site, depuis toujours.

## Ce que ces tests verrouillent

Les deux nombres existaient déjà — la taille d'une photo et le plafond du corps.
**Personne ne les confrontait.** C'est exactement le défaut à empêcher de
revenir : un test qui compare deux valeurs écrites dans deux langages et deux
fichiers, ce qu'aucun compilateur ne fera.

⚠️ **Le cas zéro compte autant que le reste** : si `express.json()` repassait
sans option, le plafond redeviendrait 100 kio **sans qu'aucune valeur ne change
de signe**. Un test qui ne lirait que des nombres ne le verrait pas —
`test_le_bridge_declare_explicitement_un_plafond` lit la forme de l'appel.
"""

import base64
import io
import re
from pathlib import Path

import httpx
import pytest

from app.utils import whatsapp as wa
from app.utils.images import reduire_sous_budget

RACINE = Path(__file__).resolve().parents[2]
COMPOSE = (RACINE / "docker-compose.yml").read_text(encoding="utf-8")
BRIDGE = (RACINE / "whatsapp-bridge" / "index.js").read_text(encoding="utf-8")
CONFIG = (RACINE / "api" / "app" / "config.py").read_text(encoding="utf-8")

#: Place à laisser au texte du message et à l'enveloppe JSON, en octets.
MARGE_TEXTE = 32 * 1024
from tests.aides_adresse import poser_adresse_du_site


def _budget_compose() -> int:
    m = re.search(
        r'x-budget-photo-whatsapp:\s*&budget_photo_whatsapp\s*"WA_PHOTO_BUDGET_KO=(\d+)"',
        COMPOSE,
    )
    assert m, (
        "Le budget d'une photo WhatsApp doit être déclaré UNE fois, par l'ancre "
        "`x-budget-photo-whatsapp` de docker-compose.yml."
    )
    return int(m.group(1))


def test_le_budget_est_declare_une_fois_et_lu_par_les_deux_services():
    """Une ancre, deux lecteurs — pas deux nombres libres de diverger."""
    budget = _budget_compose()
    references = COMPOSE.count("- *budget_photo_whatsapp")
    assert references == 2, (
        f"L'ancre du budget est référencée {references} fois : elle doit l'être par "
        "l'API (qui réduit la photo) ET par le bridge (qui en dérive son plafond)."
    )
    assert budget > 0


def test_le_repli_hors_conteneur_porte_la_meme_valeur():
    """Le défaut Python ne doit pas contredire la valeur qui fait foi.

    Deux écritures subsistent — l'ancre de compose et le défaut de `Settings` —
    parce qu'un développeur lance l'API hors conteneur. Elles sont tolérées
    **parce que ce test refuse qu'elles divergent** : c'est le motif déjà employé
    pour `icones-svg.json`, recopié dans deux images et verrouillé octet pour
    octet.
    """
    m = re.search(r"wa_photo_budget_ko:\s*int\s*=\s*(\d+)", CONFIG)
    assert m, "`Settings.wa_photo_budget_ko` doit exister — l'API lit le budget."
    assert int(m.group(1)) == _budget_compose(), (
        "Le défaut de `config.py` et l'ancre de `docker-compose.yml` donnent deux "
        "budgets différents : l'API hors conteneur ne se comporterait pas comme en "
        "production."
    )


def test_le_bridge_declare_explicitement_un_plafond():
    """Cas zéro : `express.json()` nu ramènerait le plafond à 100 kio en silence."""
    assert re.search(r"express\.json\(\{\s*limit:", BRIDGE), (
        "`express.json()` doit recevoir une option `limit`. Sans elle, le plafond "
        "redevient celui par défaut d'express — 100 kio — et tout message portant "
        "une photo est refusé par 413 (#1057)."
    )
    assert re.search(r"PHOTO_BUDGET_KO\s*=\s*parseInt\(process\.env\.WA_PHOTO_BUDGET_KO", BRIDGE), (
        "Le bridge doit lire le budget de l'environnement, pas le réécrire."
    )


def test_le_plafond_du_bridge_depasse_ce_que_l_api_peut_envoyer():
    """L'invariant : plafond du corps ≥ photo en base64 + texte.

    C'est la confrontation qui manquait. Les deux nombres vivaient dans deux
    langages, personne ne les comparait, et l'écart valait un message perdu.
    """
    budget_octets = _budget_compose() * 1024

    m_defaut = re.search(
        r'PHOTO_BUDGET_KO\s*=\s*parseInt\(process\.env\.WA_PHOTO_BUDGET_KO\s*\|\|\s*"(\d+)"',
        BRIDGE,
    )
    assert m_defaut, "Le repli du bridge doit être lisible."
    assert int(m_defaut.group(1)) == _budget_compose(), (
        "Le repli du bridge et l'ancre de compose donnent deux budgets différents."
    )

    m_facteur = re.search(r"BODY_LIMIT_KO\s*=\s*PHOTO_BUDGET_KO\s*\*\s*(\d+)", BRIDGE)
    assert m_facteur, "Le plafond du corps doit être DÉRIVÉ du budget, pas écrit à part."

    plafond_octets = budget_octets * int(m_facteur.group(1))
    base64_octets = -(-budget_octets * 4 // 3)  # arrondi supérieur
    assert plafond_octets >= base64_octets + MARGE_TEXTE, (
        f"Plafond du corps {plafond_octets} o < photo en base64 {base64_octets} o "
        f"+ marge texte {MARGE_TEXTE} o : le bridge refusera des messages que l'API "
        "juge pourtant envoyables."
    )


# ── Le repli : un corps refusé ne doit pas perdre le message ────────────────


def _reponse(code: int) -> httpx.Response:
    return httpx.Response(code, request=httpx.Request("POST", "http://bridge/send"), json={})


class _ClientEnregistreur:
    """Client httpx factice qui note chaque corps posté et rend les codes fournis."""

    corps: list[dict] = []
    codes: list[int] = []

    def __init__(self, **_):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def post(self, url, json=None, headers=None):
        #  Une COPIE : `envoyer_whatsapp` retire la photo du dictionnaire pour
        #  la reemission, et enregistrer la reference ferait voir le meme corps
        #  deux fois — un test qui ne prouverait plus rien.
        _ClientEnregistreur.corps.append(dict(json))
        reponse = _reponse(_ClientEnregistreur.codes.pop(0))
        reponse.raise_for_status()
        return reponse


@pytest.fixture
def bridge_factice(monkeypatch):
    _ClientEnregistreur.corps = []
    _ClientEnregistreur.codes = []
    monkeypatch.setattr(wa.httpx, "Client", _ClientEnregistreur)
    monkeypatch.setattr(wa, "image_pour_bridge", lambda _url: "UEhPVE8=")
    return _ClientEnregistreur


CONFIG_WA = {
    "whatsapp_enabled": "1",
    "whatsapp_api_url": "http://whatsapp-bridge:8090",
    "whatsapp_group_jid": "123@g.us",
}


def test_un_corps_refuse_reemet_le_message_sans_la_photo(bridge_factice, monkeypatch):
    """413 : le texte seul passe, et il dit où voir la photo.

    Le repli existait déjà — mais pour la photo ILLISIBLE sur le disque. Quand
    c'est le bridge qui refuse le corps, il ne s'appliquait pas, et le message
    entier était perdu alors que le texte serait passé.
    """
    bridge_factice.codes = [413, 200]
    poser_adresse_du_site(monkeypatch, "https://exemple.fr")

    wa.envoyer_whatsapp(
        "Porte des boîtes aux lettres",
        "Elle ne ferme plus.",
        False,
        None,
        "/uploads/fichiers/photo.jpg",
        CONFIG_WA,
    )

    assert len(bridge_factice.corps) == 2, "Le message doit être réémis une fois, pas zéro."
    premier, second = bridge_factice.corps
    assert "imageBase64" in premier
    assert "imageBase64" not in second, "La réémission doit se faire SANS la photo."
    assert "exemple.fr" in second["text"], (
        "Le message de repli doit dire où voir la photo, plutôt que de laisser "
        "croire qu'il n'y en a pas."
    )


def test_une_seule_reemission(bridge_factice):
    """Un corps refusé deux fois ne se rejoue pas indéfiniment."""
    bridge_factice.codes = [413, 413]

    with pytest.raises(httpx.HTTPStatusError):
        wa.envoyer_whatsapp(
            "Titre",
            "Contenu",
            False,
            None,
            "/uploads/fichiers/photo.jpg",
            CONFIG_WA,
        )
    assert len(bridge_factice.corps) == 2


def test_un_refus_qui_n_est_pas_413_ne_reemet_rien(bridge_factice):
    """Une clé d'API refusée (401) n'a rien à voir avec le poids : ne pas rejouer."""
    bridge_factice.codes = [401]

    with pytest.raises(httpx.HTTPStatusError):
        wa.envoyer_whatsapp(
            "Titre",
            "Contenu",
            False,
            None,
            "/uploads/fichiers/photo.jpg",
            CONFIG_WA,
        )
    assert len(bridge_factice.corps) == 1


# ── La réduction : le cas courant ne doit rien recompresser ─────────────────


def _jpeg(dimension: int, bruit: bool) -> bytes:
    """Fabrique un JPEG — bruité, il résiste à la compression et pèse lourd."""
    from PIL import Image

    img = Image.new("RGB", (dimension, dimension), (200, 120, 60))
    if bruit:
        import random

        rnd = random.Random(1)
        pixels = img.load()
        for x in range(dimension):
            for y in range(dimension):
                pixels[x, y] = (rnd.randrange(256), rnd.randrange(256), rnd.randrange(256))
    sortie = io.BytesIO()
    img.save(sortie, format="JPEG", quality=95)
    return sortie.getvalue()


def test_une_photo_qui_tient_deja_n_est_pas_recompressee():
    """Sinon chaque diffusion dégraderait une photo qui allait très bien."""
    petite = _jpeg(64, bruit=False)
    assert reduire_sous_budget(petite, 400 * 1024) is petite


def test_une_photo_trop_lourde_est_ramenee_sous_le_budget():
    grosse = _jpeg(1600, bruit=True)
    budget = 100 * 1024
    assert len(grosse) > budget, "Le cas de départ doit bien dépasser le budget."
    reduite = reduire_sous_budget(grosse, budget)
    assert len(reduite) <= budget
    #  Et elle reste une image lisible, pas des octets tronqués.
    from PIL import Image

    Image.open(io.BytesIO(reduite)).verify()


def test_des_octets_illisibles_ne_font_pas_echouer_la_reduction():
    """Le cas dégradé : on rend ce qu'on a, l'envoi décidera."""
    ordures = base64.b64decode("bm90LWFuLWltYWdl")
    assert reduire_sous_budget(ordures, 1) == ordures
