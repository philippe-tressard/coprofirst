"""L'accès au modèle de langage — la clé, et les trois fournisseurs.

## Ce que ce test protège

1. **La clé d'API ne sort jamais de l'API**, même pour un administrateur. C'est
   la règle posée le 03/09/2026 après que `smtp_password` eut voyagé en clair
   dans une réponse HTTP : l'écran ne l'affichait pas, mais elle était lisible
   dans l'onglet réseau du navigateur, dans un cache, dans une capture d'écran.
   *Un secret qu'un écran n'affiche pas mais que l'API transmet est un secret
   exposé : la protection est alors dans le rendu, c'est-à-dire nulle part.*

2. **Les trois fournisseurs ne divergent pas.** Azure OpenAI HÉRITE d'OpenAI —
   il n'en redéfinit que l'URL et l'en-tête d'authentification. Si quelqu'un
   recopiait le corps de requête au lieu d'en hériter, ce test le dirait.
"""

from __future__ import annotations

import pytest

from app.routers.config import MARQUEUR_SECRET, _SECRETS, _valeur_pour_admin
from app.utils.llm import (
    FOURNISSEURS,
    USAGES,
    ConfigLLM,
    ErreurLLM,
    Fournisseur,
    FournisseurAzure,
)


@pytest.fixture()
def session_llm(session):
    """Une base en mémoire portant une configuration LLM exploitable."""
    from app.models.core import ConfigSite

    for cle, valeur in {
        "llm_actif": "1",
        "llm_fournisseur": "openai",
        "llm_api_key": "sk-x",
        "llm_synthese_contrat_actif": "1",
        "llm_synthese_contrat_modele": "gpt-4o-mini",
    }.items():
        session.add(ConfigSite(cle=cle, valeur=valeur))
    session.commit()
    return session


# ── 1. Le secret ────────────────────────────────────────────────────────────


def test_la_cle_d_api_ne_sort_JAMAIS_de_l_api():
    """🔴 Le point de sécurité de ce lot."""
    assert "llm_api_key" in _SECRETS
    assert _valeur_pour_admin("llm_api_key", "sk-tres-secret") == MARQUEUR_SECRET


def test_le_marqueur_dit_qu_une_cle_EXISTE_sans_la_donner():
    """L'écran a besoin de savoir si une clé est posée — pas laquelle.

    C'est pourquoi le marqueur n'est pas une chaîne vide : sans lui, l'écran
    redemanderait la clé à chaque visite, et quelqu'un finirait par la
    ressaisir dans un champ qui l'écraserait.
    """
    assert _valeur_pour_admin("llm_api_key", "") == ""
    assert _valeur_pour_admin("llm_api_key", "sk-x") == MARQUEUR_SECRET
    assert MARQUEUR_SECRET != ""


# ── 2. Les trois fournisseurs ───────────────────────────────────────────────


def test_les_trois_standards_sont_proposés():
    assert set(FOURNISSEURS) == {"openai", "anthropic", "azure_openai"}


def test_azure_HÉRITE_du_corps_d_openai():
    """🔴 C'est l'héritage qui porte la ressemblance, pas une copie.

    Azure OpenAI est OpenAI derrière une autre porte : même corps de requête,
    même lecture de la réponse. Si quelqu'un recopiait `corps()` au lieu d'en
    hériter, les deux divergeraient au premier ajustement — et personne ne les
    compare jamais, puisque chacune est cohérente avec elle-même.
    """
    openai = FOURNISSEURS["openai"]
    azure = FOURNISSEURS["azure_openai"]
    assert isinstance(azure, FournisseurAzure)
    assert isinstance(azure, Fournisseur)
    assert type(azure).corps is type(openai).corps
    assert type(azure).lire is type(openai).lire


def test_chaque_fournisseur_a_SA_porte_et_SON_en_tête():
    urls = {c: f.url("mon-modele", "https://x", "2024-06-01") for c, f in FOURNISSEURS.items()}
    assert urls["openai"].endswith("/chat/completions")
    assert urls["anthropic"].endswith("/v1/messages")
    #  Azure met le nom du DÉPLOIEMENT dans l'URL, là où les autres le passent
    #  dans le corps — c'est toute la raison de redéfinir `url()`.
    assert "/openai/deployments/mon-modele/" in urls["azure_openai"]
    assert "api-version=2024-06-01" in urls["azure_openai"]

    entetes = {c: f.entetes("CLE") for c, f in FOURNISSEURS.items()}
    assert entetes["openai"]["Authorization"] == "Bearer CLE"
    assert entetes["anthropic"]["x-api-key"] == "CLE"
    assert entetes["azure_openai"]["api-key"] == "CLE"


def test_la_consigne_voyage_dans_les_trois_formes():
    """Chez Claude la consigne est un champ `system` à part ; ailleurs c'est un
    message de rôle `system`. La divergence est réelle — et c'est la SEULE qui
    justifie de redéfinir `corps()`."""
    for code, f in FOURNISSEURS.items():
        corps = f.corps("m", "CONSIGNE", "MESSAGE", 100)
        assert "CONSIGNE" in str(corps), code
        assert "MESSAGE" in str(corps), code
        assert corps["max_tokens"] == 100, code


# ── 3. On échoue AVANT la requête, avec un message lisible ──────────────────


def _config(**kw) -> ConfigLLM:
    base = dict(
        actif=True,
        fournisseur=FOURNISSEURS["openai"],
        cle="sk-x",
        base_url="https://api.openai.com/v1",
        version_api="2024-06-01",
        delai_s=30,
        envoi_document=True,
        usage=USAGES["synthese_contrat"],
        actif_usage=True,
        modele="gpt-4o-mini",
        prompt="CONSIGNE",
        max_jetons=800,
    )
    base.update(kw)
    return ConfigLLM(**base)


@pytest.mark.parametrize(
    "champ, valeur, extrait",
    [
        ("actif", False, "désactivé"),
        ("cle", "", "clé"),
        ("modele", "", "modèle"),
    ],
)
def test_une_configuration_incomplète_échoue_AVANT_le_réseau(champ, valeur, extrait):
    """Un 401 met plusieurs secondes et rend un message du fournisseur, pas du
    produit. On le dit nous-mêmes, tout de suite."""
    with pytest.raises(ErreurLLM) as e:
        _config(**{champ: valeur}).verifier()
    assert extrait in str(e.value).lower()


def test_azure_EXIGE_son_point_d_accès():
    """Azure n'a pas d'adresse publique : chaque client a la sienne. Sans elle,
    l'appel partirait vers une chaîne vide."""
    with pytest.raises(ErreurLLM) as e:
        _config(fournisseur=FOURNISSEURS["azure_openai"], base_url="", modele="depl").verifier()
    assert "point d" in str(e.value).lower()
    #  Les deux autres s'en passent : ils ont une adresse par défaut.
    _config().verifier()


# ── 4. Le catalogue de modèles — demandé au fournisseur, jamais recopié ─────
#
#  🔴 11/09/2026, « on peut choisir un modèle plus intelligent ? ». Le champ
#  était libre, adossé à trois exemples écrits en dur et au commentaire « le
#  catalogue bouge vite » — l'aveu du défaut. Ces tests verrouillent que la
#  liste vient du SERVICE, et que son absence reste une absence, jamais une
#  erreur ni une liste vide présentée comme un choix.


def test_openai_ecarte_ce_qui_ne_repond_pas_a_une_conversation():
    """La liste d'OpenAI mêle transcription, images et plongements : les
    proposer ferait choisir un modèle qui répond 404 à la première synthèse."""
    lus = FOURNISSEURS["openai"].lire_modeles(
        {
            "data": [
                {"id": "gpt-4o", "created": 20},
                {"id": "whisper-1", "created": 30},
                {"id": "text-embedding-3-large", "created": 31},
                {"id": "dall-e-3", "created": 32},
                {"id": "gpt-4o-audio-preview", "created": 33},
                {"id": "gpt-4o-mini", "created": 10},
            ]
        }
    )
    assert [m["id"] for m in lus] == ["gpt-4o", "gpt-4o-mini"]


def test_les_modeles_arrivent_du_plus_recent_au_plus_ancien():
    """Un tri par date est un FAIT. Désigner un « meilleur » modèle depuis le
    produit serait une appréciation, qui se périmerait."""
    lus = FOURNISSEURS["openai"].lire_modeles(
        {"data": [{"id": "gpt-4.1", "created": 5}, {"id": "gpt-5", "created": 99}]}
    )
    assert [m["id"] for m in lus] == ["gpt-5", "gpt-4.1"]


def test_anthropic_rend_le_nom_commercial_que_le_gestionnaire_lit():
    lus = FOURNISSEURS["anthropic"].lire_modeles(
        {"data": [{"id": "claude-sonnet-4-5-20250929", "display_name": "Claude Sonnet 4.5"}]}
    )
    assert lus == [{"id": "claude-sonnet-4-5-20250929", "libelle": "Claude Sonnet 4.5"}]


def test_azure_n_a_PAS_de_liste_et_le_dit():
    """⚠️ `None` n'est pas une panne : sur Azure on choisit un DÉPLOIEMENT, que
    seule l'API de gestion connaît. L'écran garde la saisie libre."""
    assert (
        FOURNISSEURS["azure_openai"].url_modeles("https://x.openai.azure.com", "2024-06-01") is None
    )
    assert FOURNISSEURS["openai"].url_modeles("https://api.openai.com/v1", "") is not None


def test_l_adresse_de_liste_suit_celle_du_fournisseur():
    """Un point d'accès compatible OpenAI relayé par une autre adresse doit voir
    sa liste demandée à CETTE adresse, pas à api.openai.com."""
    assert (
        FOURNISSEURS["openai"].url_modeles("https://relais.exemple.test/v1/", "")
        == "https://relais.exemple.test/v1/models"
    )
    assert (
        FOURNISSEURS["anthropic"].url_modeles("https://api.anthropic.com", "")
        == "https://api.anthropic.com/v1/models"
    )


#  ── Le cas zéro : une liste vide N'EST PAS une liste ───────────────────────


class _ReponseFactice:
    def __init__(self, code, charge=None):
        self.status_code = code
        self._charge = charge or {}

    def json(self):
        return self._charge


def _brancher_httpx(monkeypatch, reponse):
    """Remplace le client HTTP par un faux qui rend `reponse`."""
    import httpx

    class _Client:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def get(self, *a, **k):
            if isinstance(reponse, Exception):
                raise reponse
            return reponse

    monkeypatch.setattr(httpx, "AsyncClient", _Client)


@pytest.mark.parametrize(
    "reponse, extrait",
    [
        (_ReponseFactice(200, {"data": []}), "Aucun modèle"),
        (_ReponseFactice(200, {"data": [{"id": "whisper-1", "created": 1}]}), "Aucun modèle"),
        (_ReponseFactice(401), "permission"),
        (_ReponseFactice(500), "500"),
    ],
)
def test_une_liste_indisponible_reste_une_ABSENCE_jamais_un_choix_vide(
    monkeypatch, reponse, extrait, session_llm
):
    """🔴 `standards/04` §2 — le cas zéro. Rendre `listable: true` avec zéro
    modèle ferait choisir dans un menu sans entrée ; rendre une erreur ferait
    croire l'assistant en panne alors qu'il synthétise très bien. Une clé
    restreinte à `/chat/completions` est le cas le plus fréquent."""
    import asyncio

    from app.utils.llm import modeles_disponibles

    _brancher_httpx(monkeypatch, reponse)
    r = asyncio.run(modeles_disponibles(session_llm))
    assert r["listable"] is False
    assert r["modeles"] == []
    assert extrait in r["motif"]


def test_une_vraie_liste_est_rendue_listable(monkeypatch, session_llm):
    import asyncio

    from app.utils.llm import modeles_disponibles

    _brancher_httpx(monkeypatch, _ReponseFactice(200, {"data": [{"id": "gpt-4o", "created": 9}]}))
    r = asyncio.run(modeles_disponibles(session_llm))
    assert r["listable"] is True
    assert r["modeles"] == [{"id": "gpt-4o", "libelle": "gpt-4o"}]


# ── 5. Un paramètre refusé se corrige, il ne fait pas échouer le geste ──────
#
#  🔴 11/09/2026, premier essai d'un modèle récent : « Unsupported parameter:
#  'max_tokens' is not supported with this model. Use 'max_completion_tokens'
#  instead. » L'écran affichait « Le fournisseur a répondu 400 » — un message
#  sur lequel personne ne peut agir.
#
#  La correction ÉCOUTE le service : il nomme lui-même le réglage fautif. Tenir
#  la liste des modèles qui veulent l'un ou l'autre nom aurait été un catalogue
#  de plus, périmé au prochain modèle — celui qu'on venait de supprimer.


_REFUS_MAX_TOKENS = {
    "error": {
        "message": "Unsupported parameter: 'max_tokens' …",
        "param": "max_tokens",
        "code": "unsupported_parameter",
    }
}


def test_un_plafond_de_jetons_renomme_garde_sa_VALEUR():
    """Retirer le paramètre sans reporter la valeur ferait sauter le plafond de
    coût — le garde-fou disparaîtrait au moment même où il sert."""
    f = FOURNISSEURS["openai"]
    param, code = f.lire_erreur(_REFUS_MAX_TOKENS)
    suite = f.adapter({"model": "gpt-5.6-terra", "max_tokens": 3000}, param, code)
    assert suite == {"model": "gpt-5.6-terra", "max_completion_tokens": 3000}


def test_un_parametre_sans_equivalent_est_RETIRE():
    """Une température refusée : le modèle prend la sienne. Une synthèse moins
    pilotée vaut mieux que pas de synthèse."""
    f = FOURNISSEURS["openai"]
    suite = f.adapter({"model": "m", "temperature": 0.2}, "temperature", "unsupported_value")
    assert suite == {"model": "m"}


def test_le_message_d_erreur_n_est_JAMAIS_recopie():
    """⚠️ Il peut citer la requête, donc le contrat qu'on vient d'envoyer. Seuls
    `param` et `code` — structurés, courts, sans contenu — sont lus."""
    param, code = FOURNISSEURS["openai"].lire_erreur(_REFUS_MAX_TOKENS)
    assert param == "max_tokens"
    assert code == "unsupported_parameter"


@pytest.mark.parametrize(
    "corps, param, code",
    [
        #  Un code qu'on ne sait pas traiter : on ne touche à rien.
        ({"max_tokens": 10}, "max_tokens", "rate_limit_exceeded"),
        #  Un paramètre absent du corps : rien à corriger, et surtout pas à
        #  inventer — l'appel échouerait deux fois au lieu d'une.
        ({"model": "m"}, "top_p", "unsupported_parameter"),
        #  Anthropic ne rend pas de `param` : son format d'erreur diffère, et
        #  `max_tokens` y est OBLIGATOIRE. Ne rien adapter est la bonne réponse.
        ({"max_tokens": 10}, "", "unsupported_parameter"),
    ],
)
def test_on_n_adapte_PAS_ce_qu_on_ne_comprend_pas(corps, param, code):
    assert FOURNISSEURS["openai"].adapter(corps, param, code) is None


def test_anthropic_ne_nomme_aucun_parametre_donc_n_adapte_rien():
    """Son erreur est `{"type":"error","error":{"type":…,"message":…}}` — pas de
    `param`. Un message qui ne nomme aucun paramètre FACULTATIF n'adapte rien ;
    ceux qui en nomment un sont éprouvés dans `test_effort_raisonnement.py`."""
    charge = {"type": "error", "error": {"type": "invalid_request_error", "message": "…"}}
    param, code = FOURNISSEURS["anthropic"].lire_erreur(charge)
    assert param == ""
    assert FOURNISSEURS["anthropic"].adapter({"max_tokens": 10}, param, code) is None


# ── 6. Un refus SANS paramètre nommé, qu'on sait quand même expliquer ───────
#
#  🔴 11/09/2026, troisième 400 d'affilée sur le même essai. Les deux premiers
#  se sont corrigés seuls (max_tokens renommé, temperature retirée) ; celui-ci
#  portait `param: null` et `code: null` :
#
#     « Could not finish the message because max_tokens or model output limit
#       was reached. Please try again with higher max_tokens. »
#
#  Un modèle qui RAISONNE avant de répondre consomme le plafond sans écrire un
#  mot. L'écran affichait « Le fournisseur a répondu 400 » : rien sur quoi agir,
#  alors que la configuration était bonne et qu'un seul champ était en cause.


_PLAFOND_ATTEINT = {
    "error": {
        "message": (
            "Could not finish the message because max_tokens or model output "
            "limit was reached. Please try again with higher max_tokens."
        ),
        "param": None,
        "code": None,
    }
}


def test_un_plafond_epuise_dit_QUEL_CHAMP_augmenter():
    explication = FOURNISSEURS["openai"].diagnostiquer(_PLAFOND_ATTEINT)
    assert explication is not None
    assert "Longueur maximale de la réponse" in explication


def test_le_message_du_fournisseur_n_est_PAS_recopie_dans_l_explication():
    """⚠️ Il est lu pour être CLASSÉ. Ce qui sort est notre phrase : la sienne
    peut citer la requête, donc le contrat qu'on vient d'envoyer."""
    explication = FOURNISSEURS["openai"].diagnostiquer(_PLAFOND_ATTEINT)
    assert "Could not finish" not in explication
    assert "model output limit" not in explication


@pytest.mark.parametrize(
    "charge",
    [
        {},
        {"error": {}},
        {"error": {"message": "Something else entirely"}},
    ],
)
def test_on_n_explique_PAS_ce_qu_on_ne_reconnait_pas(charge):
    """Sinon le diagnostic deviendrait un message passe-partout, qui enverrait
    régler le mauvais champ."""
    assert FOURNISSEURS["openai"].diagnostiquer(charge) is None


def test_le_test_de_connexion_emploie_le_plafond_CONFIGURE():
    """🔴 Il imposait 16 jetons : assez pour un mot, trop peu pour un modèle qui
    raisonne. Il déclarait alors en panne une configuration bonne — un test qui
    n'éprouve pas la configuration réelle n'éprouve rien."""
    import inspect

    from app.utils import llm

    source = inspect.getsource(llm.tester)
    assert "max_jetons=16" not in source
    assert "max_jetons=" not in source
