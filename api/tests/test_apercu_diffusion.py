"""L'aperçu montre **ce qui partira**, jamais une reconstitution (#498).

## Pourquoi ce garde-fou

Demandé le 19/08/2026 : *« avant la diffusion il faudrait voir le mail (aperçu)
avant de confirmer son envoi »*, étendu à WhatsApp.

🔴 **Un aperçu qui ment est pire que pas d'aperçu.** S'il recomposait le message
de son côté, il deviendrait faux à la première évolution d'un gabarit — et
personne ne s'en apercevrait, puisque c'est justement l'aperçu qu'on regarderait
pour le vérifier. C'est le faux-vert de `standards/04` §14 : observer la chose,
pas son enregistrement.

La seule protection qui tienne est structurelle : **une seule composition**, que
l'aperçu et l'envoi appellent tous deux. Ce fichier vérifie qu'elle le reste.

⚠️ Deux des trois tests sont de l'**analyse statique** — ils lisent le code, pas
son résultat. C'est délibéré : le défaut qu'on veut empêcher est *l'apparition
d'une seconde écriture*, et aucune exécution ne la révèle tant que les deux
copies sont d'accord. C'est exactement ce qui a laissé la clé `fichiers` absente
d'un des deux envois pendant des mois (`test_email_contexte_appel.py`).

## 🔴 Toute entité qui DIFFUSE doit pouvoir montrer ce qu'elle enverra

Puis, le même jour : *« cela est à intégrer partout où l'objet diffusion par mail
est concerné »*. L'aperçu n'a pourtant été construit **que pour les tickets**. Le
31/08, une actualité est partie au conseil syndical sans que son auteur ait rien
pu voir ni annuler. Il l'a signalé comme une régression ; ce n'en était pas une —
c'était la moitié jamais construite, et *la distinction ne change rien pour qui
reçoit le mail*.

⚠️ Rien ne signalait le manque. Chaque écran savait envoyer ; aucun contrôle ne
demandait s'il savait **montrer**. D'où la table `ENTITES` : chaque entité qui
diffuse expose un aperçu, qui **délègue** aux assembleurs partagés, et prend son
contexte à la **même** fonction que l'envoi. Ces contrôles vivaient dans
`test_apercu_generalise.py`, réuni ici le 30/09/2026 : les deux fichiers
vérifiaient les mêmes règles, l'un pour les tickets, l'autre pour toutes.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path
from tests.aides_ast import corps_avec_delegations, corps_de

_APP = Path(__file__).resolve().parents[1] / "app"
_EMAIL = _APP / "utils" / "email" / "__init__.py"
_APERCU = _APP / "routers" / "tickets" / "apercu.py"
#  🔴 LA COMPOSITION A DÉMÉNAGÉ LE 31/08/2026, et ces tests l'ont refusée.
#
#  Ils lisaient `tickets/apercu.py` et y cherchaient `composer_email(` et
#  `construire_message(`. Le jour où ces deux appels sont passés dans un module
#  partagé — pour que les actualités et le calendrier aient enfin le même aperçu —
#  les tests ont échoué alors que le code venait de S'AMÉLIORER.
#
#  ⚠️ C'est le piège que ce dépôt connaît bien : *un contrôle qui ne voit pas la
#  factorisation mesure la forme, pas le fait* (self-test de `lib-volumes.sh`,
#  `check-formulaire-creation` aveugle aux formulaires extraits). La correction
#  n'est PAS d'assouplir : c'est de suivre la composition là où elle est, et
#  d'exiger EN PLUS que le routeur passe par elle.
_ASSEMBLEUR = _APP / "utils" / "apercu_diffusion.py"
_WHATSAPP = _APP / "utils" / "whatsapp.py"
#  La COMPOSITION du message vit à part depuis le 28/09/2026 (#779) : c'est là
#  que l'aperçu prend ses deux fonctions, et là qu'on vérifie qu'elles existent.
_MESSAGE = _APP / "utils" / "whatsapp_message.py"

#  Les entités qui diffusent par courriel, et où vivent leurs deux chemins.
#
#  ⚠️ Cette table est tenue à la main, et c'est assumé : le repérage automatique
#  d'« une entité qui diffuse » n'existe pas — c'est une notion métier. En
#  revanche le test échoue si l'un des fichiers cités disparaît, donc elle ne
#  peut pas pointer dans le vide sans se faire voir.
#
#  `fonction_envoi` (facultative) nomme la fonction d'envoi qui doit appeler le
#  contexte ELLE-MÊME — pas seulement quelque part dans le module.
ENTITES = {
    "ticket": {
        "apercu": "routers/tickets/apercu.py",
        "envoi": "routers/tickets/courriels.py",
        "contexte": "contexte_ticket_syndic",
        "fonction_envoi": "envoyer_email_syndic_cs",
    },
    #  L'actualité est une affaire depuis le 23/09/2026 (#1091) : son aperçu est
    #  celui des affaires, son envoi et son contexte vivent dans `actualite.py`.
    "actualite": {
        "apercu": "routers/tickets/apercu.py",
        "envoi": "routers/tickets/actualite.py",
        "contexte": "contexte_actualite",
    },
    #  Dernière des quatre à recevoir l'aperçu (01/09/2026), et la seule qui en
    #  était privée DÉLIBÉRÉMENT : tant que son serveur ne consommait qu'un canal
    #  sur trois, un aperçu y aurait montré un envoi qui n'a pas lieu — le
    #  mensonge même que #498 existe pour empêcher. Les trois canaux sont
    #  consommés depuis #480, et la condition est levée.
    "annonce_hall": {
        "apercu": "routers/annonces_hall_apercu.py",
        "envoi": "routers/annonces_hall_courriels.py",
        "contexte": "contexte_annonce_hall",
    },
}


def _source(rel: str) -> str:
    chemin = _APP / rel
    assert chemin.exists(), (
        f"{rel} est introuvable — ce test surveillait un fichier qui n'existe "
        "plus, il ne surveillait donc plus rien."
    )
    return chemin.read_text(encoding="utf-8")


def test_chaque_entite_qui_diffuse_a_son_apercu():
    """Un écran qui sait envoyer doit savoir montrer.

    C'est la règle que l'incident du 31/08/2026 a rendue nécessaire : personne
    n'avait remarqué que six entités sur sept en étaient dépourvues, parce que
    rien ne posait la question.
    """
    assert _ASSEMBLEUR.exists(), (
        "L'assembleur partagé a disparu : les aperçus recomposent alors chacun "
        "de leur côté, et divergeront de l'envoi sans que rien ne le dise."
    )
    for entite, chemins in ENTITES.items():
        source = _source(chemins["apercu"])
        assert "apercu-diffusion" in source, (
            f"L'entité « {entite} » n'expose pas d'endpoint d'aperçu : on y coche "
            "un canal et l'on découvre le résultat en le recevant."
        )


def test_aucun_apercu_ne_recompose_de_son_cote():
    """Les routeurs d'aperçu délèguent aux DEUX assembleurs, ils ne les recopient pas.

    🔴 Un aperçu qui ment est pire que pas d'aperçu (`standards/04` §14). Et c'est
    la moitié que le déménagement de la composition aurait pu faire perdre : sans
    elle, un routeur pourrait rappeler `composer_email` à sa façon, et
    l'assembleur partagé ne servirait plus qu'à ceux qui veulent bien s'en servir.
    """
    ecarts = []
    for entite, chemins in ENTITES.items():
        source = _source(chemins["apercu"])
        ecarts += [
            f"  « {entite} » n'appelle plus `{assembleur}` : il compose de son côté, "
            "et divergera des entités branchées sur l'assembleur"
            for assembleur in ("apercu_email(", "apercu_whatsapp(")
            if assembleur not in source
        ]
        ecarts += [
            f"  « {entite} » appelle `{interdit}` en direct : la composition doit "
            "rester dans `apercu_diffusion.py`, sinon il y en a de nouveau deux"
            for interdit in ("composer_email(", "construire_message(", "_contexte_rendu(")
            if interdit in source
        ]
    assert not ecarts, "Un aperçu recompose le message :\n" + "\n".join(ecarts)


def test_l_apercu_et_l_envoi_composent_l_email_au_meme_endroit():
    """`composer_email` est la seule composition, et l'aperçu passe par elle.

    L'assembleur est le maillon dont tout le reste dépend : s'il recomposait,
    toutes les entités montreraient la même chose — et la même chose fausse.
    """
    apercu = _ASSEMBLEUR.read_text(encoding="utf-8")
    for attendu in ("composer_email(", "_contexte_rendu("):
        assert attendu in apercu, (
            f"L'aperçu ne passe plus par `{attendu}` : il recompose le message de "
            "son côté, et montrera donc autre chose que ce qui partira."
        )
    #  Et il ne remet pas le gabarit lui-même : `_wrap_email` n'a rien à faire ici.
    assert "_wrap_email(" not in apercu, (
        "L'aperçu appelle `_wrap_email` directement : toute règle ajoutée dans "
        "`composer_email` lui échapperait, et les deux rendus divergeraient."
    )
    #  Le PAQUET entier : le rendu vit dans `email/rendu.py` depuis le 13/10/2026 (#1902).
    envoi = "".join(p.read_text(encoding="utf-8") for p in sorted(_EMAIL.parent.glob("*.py")))
    #  🔴 ON SUIT LA DÉLÉGATION (05/09/2026). Ce test exigeait l'appel DANS le
    #  corps de chaque fonction ; le jour où `send_email` et `send_email_group`
    #  ont été factorisées — elles étaient identiques à 68 % —, la composition
    #  est descendue d'un cran et les deux ont échoué, alors que la propriété
    #  surveillée n'avait pas bougé. `standards/04` §35 : un contrôle qui
    #  reconnaît son objet à un indice de forme devient d'autant plus aveugle
    #  que le code est bien factorisé.
    for fonction in ("send_email", "send_email_group"):
        assert "composer_email(" in corps_avec_delegations(_EMAIL, fonction), (
            f"`{fonction}` ne passe plus par `composer_email`, ni directement ni "
            "par une fonction du module : elle recomposerait le message de son "
            "côté, et l'aperçu montrerait autre chose que ce qui part."
        )
    #  Une seule définition, sinon « la seule composition » est un vœu.
    assert len(re.findall(r"^def composer_email\(", envoi, re.MULTILINE)) == 1


def test_l_apercu_et_l_envoi_prennent_le_contexte_au_MEME_endroit():
    """Le point le plus fragile, et celui qu'aucune exécution ne révèle.

    Un aperçu peut employer la bonne fonction de composition et rester faux si on
    lui donne un contexte fabriqué à la main : les variables du gabarit
    divergeraient alors en silence. C'est la même famille que la clé `fichiers`
    absente d'un des deux envois pendant des mois.
    """
    ecarts = []
    for entite, chemins in ENTITES.items():
        nom = chemins["contexte"]
        envoi = _source(chemins["envoi"])
        if f"{nom}(" not in _source(chemins["apercu"]):
            ecarts.append(
                f"  l'aperçu de « {entite} » construit son propre contexte au lieu "
                f"d'appeler `{nom}` : ses variables peuvent diverger de l'envoi"
            )
        if not re.search(rf"^def {nom}\(", envoi, re.MULTILINE):
            ecarts.append(
                f"  `{nom}` n'est pas défini dans {chemins['envoi']} : l'aperçu importe "
                "une fonction qui n'y est plus, et l'erreur ne se verrait qu'à l'exécution"
            )
        #  Et l'ENVOI l'appelle aussi : une fonction de contexte que seul
        #  l'aperçu emploierait ne prouve rien du tout.
        appels = {
            n.func.id
            for n in ast.walk(ast.parse(envoi))
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
        }
        if nom not in appels:
            ecarts.append(
                f"  l'envoi de « {entite} » n'appelle pas `{nom}` : les deux chemins "
                "ne s'en servent pas — donc rien n'est partagé"
            )
        fonction = chemins.get("fonction_envoi")
        if fonction and f"{nom}(" not in corps_de(_APP / chemins["envoi"], fonction):
            ecarts.append(
                f"  `{fonction}` n'appelle pas `{nom}` elle-même : l'envoi de "
                f"« {entite} » compose avec un autre contexte que l'aperçu"
            )
    assert not ecarts, "Aperçu et envoi ne partagent pas leur contexte :\n" + "\n".join(ecarts)


def test_l_apercu_whatsapp_ne_reecrit_pas_le_message():
    """`construire_message` est déjà pure — l'aperçu l'appelle, il ne la copie pas.

    Et il lit `message_sans_contenu` : c'est ce qui lui permet d'annoncer qu'un
    message partira **amputé** sur un périmètre restreint ou un contenu
    confidentiel. Rien à l'écran ne le disait avant, et c'est le meilleur apport
    de cet aperçu.
    """
    apercu = _ASSEMBLEUR.read_text(encoding="utf-8")
    assert "construire_message(" in apercu
    assert "message_sans_contenu(" in apercu, (
        "L'aperçu ne consulte pas `message_sans_contenu` : il montrerait le "
        "message complet alors que le groupe recevra un message amputé."
    )
    #  Les deux fonctions existent bien là où l'aperçu les prend.
    whatsapp = _MESSAGE.read_text(encoding="utf-8")
    for nom in ("construire_message", "message_sans_contenu"):
        assert re.search(rf"^def {nom}\(", whatsapp, re.MULTILINE), (
            f"`{nom}` a disparu de `whatsapp_message.py` : l'aperçu importe une fonction "
            "qui n'existe plus, et l'erreur ne se verrait qu'à l'exécution."
        )


def test_l_apercu_whatsapp_transmet_TOUT_ce_que_l_envoi_transmet():
    """Les deux appels à `construire_message` doivent porter les mêmes arguments.

    🔴 POURQUOI (01/09/2026). `apercu_whatsapp` n'avait pas de paramètre `lien`,
    donc ne le transmettait pas — alors que `_envoyer_whatsapp` le passe. Aucun
    appelant ne s'en servait, et le défaut est resté invisible jusqu'à ce que
    l'annonce de hall envoie un lien vers l'actualité d'origine (#480). L'aperçu
    aurait alors montré un message **sans le lien** que le groupe reçoit.

    ⚠️ C'est l'angle mort propre aux aperçus : on regarde l'aperçu POUR vérifier
    ce qui part. Une omission y est indétectable à l'usage — seule la comparaison
    des deux appels la révèle, et seulement en lisant le code.

    Le test compare les **mots-clés** des deux appels. Les positionnels ne sont
    pas comparés : leur ordre est déjà verrouillé par la signature, et les nommer
    ici recopierait cette signature — une seconde liste qui divergerait.
    """

    def _mots_cles(source: str, dans: str) -> set[str]:
        """Les arguments NOMMÉS de l'appel à `construire_message` dans `dans`."""
        arbre = ast.parse(source)
        for noeud in ast.walk(arbre):
            if not (isinstance(noeud, ast.FunctionDef) and noeud.name == dans):
                continue
            for appel in ast.walk(noeud):
                if (
                    isinstance(appel, ast.Call)
                    and getattr(appel.func, "id", None) == "construire_message"
                ):
                    return {kw.arg for kw in appel.keywords if kw.arg}
        raise AssertionError(
            f"aucun appel à `construire_message` dans `{dans}` — le test "
            "surveillait un appel qui n'existe plus, il ne surveillait donc rien."
        )

    cotes = _mots_cles(_ASSEMBLEUR.read_text(encoding="utf-8"), "apercu_whatsapp")
    envoi = _mots_cles(_WHATSAPP.read_text(encoding="utf-8"), "envoyer_whatsapp")

    manquants = envoi - cotes
    assert not manquants, (
        "`apercu_whatsapp` ne transmet pas à `construire_message` : "
        + ", ".join(sorted(manquants))
        + " — l'aperçu tairait ce que le message porte, et personne ne pourrait "
        "le voir : c'est l'aperçu qu'on regarde pour vérifier."
    )


def test_l_apercu_n_ecrit_rien_en_base():
    """Un aperçu qui persiste son brouillon laisserait des tickets fantômes.

    Le ticket prévisionnel est un objet en mémoire, jamais ajouté à la session.
    """
    corps = corps_de(_APERCU, "apercu_diffusion") + corps_de(_APERCU, "_ticket_previsionnel")
    for interdit in ("session.add(", "session.commit(", "session.delete("):
        assert interdit not in corps, (
            f"L'aperçu appelle `{interdit}` : il modifierait la base alors que "
            "l'utilisateur n'a encore rien confirmé."
        )
