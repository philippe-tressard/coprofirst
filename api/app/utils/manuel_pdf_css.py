"""Feuille de style du manuel imprimable — extraite au fil de l'eau.

Même geste que `fiche_arrivant_css.py`, et pour la même raison : `manuel_pdf.py`
a franchi les 500 lignes du plafond de modularité (rang 1 §4) en gagnant les deux
colonnes et le sommaire paginé.

La feuille de style est ce qui s'en détache le plus proprement — elle n'a aucune
logique, et elle change pour des raisons qui ne sont pas celles du document : une
retouche de charte n'est pas un changement de contenu.

⚠️ Elle reprend la feuille de l'ÉCRAN et n'en redéfinit que ce que l'impression
impose. Redessiner ici les cartes et les couleurs du manuel créerait une seconde
charte, qui dériverait à la première retouche de l'écran.
"""

from __future__ import annotations

from app.utils.manuel_pdf_pages import css_des_pages_ajoutees
from app.utils.pdf_theme import FONT_SANS, FONT_SERIF, PALETTE_CSS, regle_page


def css_du_pdf(styles_manuel: str) -> str:
    """Le CSS du PDF : celui du manuel, plus ce que l'impression exige."""
    return f"""
{PALETTE_CSS}
{styles_manuel}

{regle_page()}
/*  🔴 Une accolade orpheline suivait ici `regle_page()` (jusqu'au 23/10/2026) :
    le moteur jetait alors la règle suivante, et la page de garde gardait les
    marges et le numéro des autres pages. `test_manuel_pdf` compte les accolades.
    La page de garde n'a ni marge ni numéro : elle est une affiche. */
@page garde {{ margin: 0; @bottom-center {{ content: none; }} }}

body {{
  font-family: {FONT_SANS};
  color: var(--ink);
  background: #fff;
  font-size: 9pt;
  line-height: 1.42;
}}

/*  🔴 CE QUE L'IMPRESSION IMPOSE, et que l'écran n'a pas. La barre latérale et
    les boutons d'action sont des gestes d'écran : sur le papier, ils ne mènent
    nulle part. Le repli des blocs, lui, est levé À LA COMPOSITION (voir
    `corps_du_manuel`) — pas ici : ce qui suit habille le résultat. */
.sidebar, .hero-actions, .aide-liens {{ display: none !important; }}
.renvoi-en-ligne {{
  margin: 1.5mm 0 0;
  font-size: 7.5pt;
  font-style: italic;
  color: var(--muted);
}}
.sommaire-avis {{
  margin: 0 0 5mm;
  padding: 2.5mm 3.5mm;
  background: var(--bg);
  border-left: 3px solid var(--gold);
  color: var(--muted);
}}
/*  🔴 Le premier libellé des tableaux d'affaires ne se coupe pas, à l'écran
    (`white-space: nowrap`) : dans la largeur d'une page, il débordait SUR la
    colonne voisine — « Copro-bailleurs, Bailleurs, Locataires… » imprimé par-dessus
    son explication (signalé le 23/10/2026). */
.affaire-table {{ font-size: 8.5pt; }}
.affaire-table th, .affaire-table td {{ padding: 1.2mm 2mm; }}
.affaire-table td:first-child {{ white-space: normal; }}
/*  Un tableau à deux colonnes — un nom, son explication : le nom n'a pas besoin
    de la moitié de la largeur. */
.affaire-table td:first-child:nth-last-child(2) {{ width: 30%; }}
/*  🔴 `inline-flex` se lit, chez WeasyPrint, comme un bloc : chaque pictogramme
    au trait d'une phrase (✎ le crayon, la pastille « Occupants »…) partait seul
    sur sa ligne, et coupait la phrase en trois (vu au rendu du 23/10/2026). */
.ic, .pastille-lecture-ex {{ display: inline; }}
.ic svg, .pastille-lecture-ex svg {{ display: inline; vertical-align: -.15em; }}
.pastille-lecture-ex > * + * {{ margin-left: .25em; }}
/*  La fin du manuel invite à télécharger… ce document : sur le papier, le lien
    renvoie à lui-même. Le glyphe d'aide, lui, coûtait un tiers de page. */
.aide-pdf, .aide-glyphe {{ display: none !important; }}
.aide-fin {{ padding: 3mm 4mm; margin-bottom: 0; break-inside: avoid; }}

/*  🔴 DEUX COLONNES PAR UNE GRILLE, et non par `column-count` (23/10/2026).
    Les quatre grilles sont des listes de blocs courts : en pleine largeur A4,
    chacun tiendrait trois mots suivis de vingt centimètres de blanc (demandé le
    03/09/2026).

    Elles étaient en `column-count`, et WeasyPrint repoussait alors le conteneur
    entier à la page suivante : « Pour qui ? », « Mini sommaire par profil » et
    la grille des écrans laissaient chacun une page presque vide derrière leur
    titre (signalé le 23/10/2026). Une grille se coupe entre deux rangées.

    ⚠️ `break-inside: avoid` sur chaque carte : une carte coupée se lirait en
    deux morceaux. Il ne tient que parce que les cartes sont COURTES — les blocs
    « En savoir plus » ne sont plus imprimés (`corps_du_manuel`). Une carte plus
    haute qu'une page ne se couperait pas : elle déborderait, et son texte
    sortirait de la feuille, comme les fiches Admin et Conseil syndical
    jusqu'au 23/10/2026. */
.ecran-grid, .quick-grid, .persona-grid, .profils-grid {{
  display: grid;
  grid-template-columns: 1fr 1fr;
  column-gap: 7mm;
  row-gap: 2.5mm;
}}
.ecran-card, .quick-card, .persona-card, .profil-card {{
  break-inside: avoid;
  page-break-inside: avoid;
  border: 1px solid var(--border);
  border-left: 1mm solid var(--navy);
  border-radius: 0 2mm 2mm 0;
  padding: 2.5mm 3mm;
  background: #fff;
}}
/*  Les trois étapes du démarrage se distinguent des quinze écrans : c'est un
    parcours, pas un catalogue. Liseré doré et pastille numérotée, en écho aux
    titres de section. */
.quick-card {{ border-left-color: var(--gold); }}
.quick-step {{
  display: inline-block;
  width: 5.5mm;
  height: 5.5mm;
  line-height: 5.5mm;
  text-align: center;
  border-radius: 50%;
  background: var(--gold);
  color: #fff;
  font-weight: 700;
  font-size: 8.5pt;
  margin-bottom: 1.5mm;
}}
.persona-card {{ border-left-color: var(--green); }}
/*  Les six profils : la porte d'entrée du document — « est-ce que ça
    me concerne ? ». Ils se distinguent des écrans par leur liseré. */
.profil-card {{ border-left-color: #2563eb; }}
.profil-card strong {{ display: block; margin-bottom: .6mm; }}
.apropos {{ margin-bottom: 5mm; }}

/*  🔴 LES DEUX MAQUETTES DU MENU. Elles sont reconstruites en HTML, pas
    photographiées : une capture se périme au premier écran renommé et pixellise
    à l'impression. Celle-ci reste nette à toute taille et suit le site.

    ⚠️ `break-inside: avoid` sur chaque figure : une maquette coupée en deux
    pages ne montre plus un menu, elle montre deux moitiés de liste. */
/*  🔴 FLEX, ET NON `column-count` (04/09/2026).
    Les deux maquettes étaient décrites en colonnes typographiques, et se sont
    retrouvées l'une SOUS l'autre : `break-inside: avoid` sur des blocs plus hauts
    que la colonne disponible interdit à WeasyPrint de les répartir, il les
    empile. Le flux en colonnes est fait pour du TEXTE qui coule ; ces deux
    figures ne coulent pas, elles se comparent.

    Or la comparaison EST le propos : empilées, elles redeviennent deux listes
    sans rapport l'une avec l'autre, et le lecteur ne voit plus que c'est le
    même menu à deux endroits. Le flex les met côte à côte quoi qu'il arrive. */
.maq-duo {{
  display: flex;
  align-items: flex-start;
  gap: 6mm;
  margin: 3mm 0;
  break-inside: avoid;
  page-break-inside: avoid;
}}
.maq {{
  flex: 1 1 0;
  min-width: 0;
  break-inside: avoid;
  page-break-inside: avoid;
  margin: 0;
}}
.maq-legende {{
  font-size: 8pt;
  font-weight: 700;
  color: var(--muted);
  margin-bottom: 1.5mm;
}}
.maq-cadre {{
  border: 1px solid var(--border);
  border-radius: 2mm;
  overflow: hidden;
}}
.maq-bureau {{ border-top: 1mm solid var(--navy); }}
.maq-mobile {{ border-top: 1mm solid var(--gold); max-width: 52mm; }}
.maq-marque {{
  display: flex;
  align-items: center;
  gap: 1.5mm;
  font-weight: 700;
  font-size: 8pt;
  padding: 1.5mm 2mm;
}}
.maq-bureau .maq-marque {{ border-bottom: 1px solid var(--border); }}
.maq-barre {{
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid var(--border);
  background: var(--bg);
}}
/*  Le bouton du menu est DESSINÉ et encadré, pour ressembler à un bouton. Il
    portait le caractère ☰, qui se lit comme une décoration — et ne dit rien à
    qui n'a jamais fait le rapprochement, c'est-à-dire au lecteur de ce guide. */
.maq-burger {{
  display: inline-flex;
  align-items: center;
  justify-content: center;
  margin: 1mm 1.5mm;
  padding: .8mm;
  border: 1px solid var(--border);
  border-radius: 1.5mm;
  background: #fff;
  color: var(--navy);
}}
/*  La légende du bouton : sous la maquette qui le montre, jamais ailleurs. */
.maq-explication {{
  display: flex;
  align-items: flex-start;
  gap: 1.5mm;
  margin: 1.5mm 0 0;
  padding: 1.5mm 2mm;
  border-left: .8mm solid var(--gold);
  background: #fdf8ef;
  font-size: 7.5pt;
  color: var(--muted);
  line-height: 1.4;
  break-inside: avoid;
}}
.maq-explication-icone {{ color: var(--gold); }}
.maq-liste {{ list-style: none; margin: 0; padding: 1mm; }}
.maq-item {{
  display: flex;
  align-items: center;
  gap: 1.5mm;
  padding: .7mm 1.5mm;
  border-radius: 1.5mm;
  font-size: 7.5pt;
  color: var(--muted);
}}
/*  L'entrée active fait comprendre que la colonne EST un menu, pas une liste. */
.maq-actif {{
  background: var(--bg);
  color: var(--navy);
  font-weight: 700;
}}
.maq-note {{ font-size: 8pt; color: var(--muted); }}
.ecran-acces {{
  display: inline-block;
  font-size: 7pt;
  font-weight: 700;
  border-radius: 999px;
  padding: .4mm 1.8mm;
  border: 1px solid var(--border);
  color: var(--muted);
  background: var(--bg);
}}
.ecran-icone {{ width: 6mm; height: 6mm; color: var(--navy); }}
/*  ⚠️ PAS de `column-span: all` sur les cartes dépliées, contrairement à ma
    première idée : l'aperçu montre qu'elles tiennent dans leur colonne, et leur
    donner toute la largeur aurait coûté le blanc qu'on cherche justement à
    supprimer. La règle est partie avant d'être livrée. */
.chapter, .quick-start, .hero {{
  page-break-inside: auto;
  background: none;
  color: var(--ink);
  padding: 0;
  margin-bottom: 5mm;
}}
/*  Le manuel aère beaucoup pour l'écran ; sur le papier, chaque respiration
    coûte une fraction de page. On resserre sans coller. */
.chapter-header {{ margin-bottom: 3mm; }}
.chapter-icon {{ display: none; }}
p {{ margin-bottom: 1.6mm; }}
ul, ol {{ margin: 1.5mm 0 1.5mm 4mm; }}
li {{ margin-bottom: .8mm; }}
.divider {{ display: none; }}
.hero h1 {{ color: var(--navy); font-family: {FONT_SERIF}; }}
.hero p, .hero-note {{ color: var(--muted); }}
/*  🔴 LES SUR-TITRES SONT MASQUÉS, et c'est une correction de MON fait.
    « Bienvenue sur votre extranet de résidence », « Guide express » : à l'écran
    ce sont des accroches, posées au-dessus du vrai titre. Je les avais repeints
    en doré — ils devenaient alors les éléments les plus voyants de la page,
    alors qu'ils ne figurent pas au sommaire. Signalé à l'écran : *« bref c'est
    pas cohérent »*.

    Un document imprimé se lit par sa structure : ce qui saute aux yeux doit être
    ce que le sommaire annonce, et rien d'autre. Trois titres au sommaire, trois
    titres dans le corps. */
.hero-kicker, .quick-badge {{ display: none !important; }}
/*  Les pastilles du bandeau d'accueil sont blanches sur fond bleu à l'écran :
    sur le papier, le fond disparaît et elles deviennent invisibles. Repeintes
    plutôt que masquées — elles portent trois phrases utiles. */
.hero-cards {{ display: block; margin-top: 4mm; }}
.hero-card {{
  display: inline-block;
  margin: 0 2mm 2mm 0;
  padding: 1.5mm 3mm;
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 999px;
  color: var(--muted);
  font-size: 8.5pt;
}}
/*  🔴 LES TITRES DE SECTION SONT NUMÉROTÉS ET COLORÉS (03/09/2026).
    « Pas très joli », et c'était juste : trois titres perdus dans le gris, alors
    que le sommaire les annonce numérotés. Le compteur est le MÊME que celui du
    sommaire — un lecteur qui cherche « 2. » le retrouve tel qu'il l'a lu.

    Le numéro est en pastille dorée, le titre en marine sur un aplat très clair :
    la section s'ouvre par un bloc qu'on repère en feuilletant, ce que trois mots
    en gras ne font pas. */
body {{ counter-reset: sect; }}
h2 {{
  counter-increment: sect;
  font-family: {FONT_SERIF};
  color: var(--navy);
  font-size: 15pt;
  margin: 0 0 3mm;
  padding: 2.5mm 3mm 2.5mm 14mm;
  background: linear-gradient(90deg, var(--bg) 0%, #fff 82%);
  border-left: 1.6mm solid var(--gold);
  border-radius: 0 2mm 2mm 0;
  position: relative;
  page-break-after: avoid;
}}
h2::before {{
  content: counter(sect);
  position: absolute;
  left: 3.5mm;
  top: 50%;
  transform: translateY(-50%);
  width: 7mm;
  height: 7mm;
  line-height: 7mm;
  text-align: center;
  border-radius: 50%;
  background: var(--gold);
  color: #fff;
  font-family: {FONT_SANS};
  font-size: 10pt;
  font-weight: 700;
}}
/*  Le titre du sommaire et celui des mentions ne sont pas des sections du
    manuel : ils gardent le style, sans le numéro qui décalerait le compteur. */
.sommaire h2, .mentions h2 {{ counter-increment: none; padding-left: 3mm; }}
.sommaire h2::before, .mentions h2::before {{ content: none; }}
h3 {{
  font-family: {FONT_SERIF};
  color: var(--navy);
  font-size: 10.5pt;
  margin-bottom: 1mm;
  page-break-after: avoid;
}}
/*  Le titre d'accueil est l'INTRODUCTION du document, pas une de ses trois
    sections : il n'est donc pas numéroté au sommaire, et il se distingue des
    `h2` par sa taille plutôt que par une couleur de plus. */
/*  L'introduction : un chapeau, pas une section. Filet doré court sous le titre
    — le même geste que la page de garde, pour que les deux se répondent. */
.hero h1 {{
  font-size: 20pt;
  margin-bottom: 2mm;
  padding-bottom: 2mm;
  border-bottom: 2px solid var(--gold);
  display: inline-block;
}}
a {{ color: var(--navy); text-decoration: none; }}

{css_des_pages_ajoutees()}
"""
