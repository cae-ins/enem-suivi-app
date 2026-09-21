# Guide du développeur

## Ajouter un nouveau point de suivi

Créer `modules/m11_mon_controle.py` :

```python
from enem_core.execution import ModuleBase
from enem_core.parametres import Entier
from enem_core.trimestre import Trimestre
from ._communs import charger_menage, num, p_fichier_menage, p_sortie, p_trimestre, p_versions_menage


class MonControle(ModuleBase):
    id = "mon_controle"                 # identifiant unique (historique, profil)
    nom = "Mon contrôle"
    nom_court = "Mon contrôle"          # libellé du menu
    description = "Ce que fait le contrôle."
    equipe = "Terrain"                  # Terrain / Téléopérateurs / Coordination …
    frequence_jours = 7                 # None = à la demande
    frequence_libelle = "Hebdomadaire"
    couleur = "#7A5C99"                 # couleur propre au module
    entrees = "ENEM_AAAATq.dta"
    sorties = "Mon_controle_<T>.xlsx"
    code_origine = ["Dossier/ancien_code.do"]   # relatif au « dossier des codes d'origine »
    mots_cles = "mots pour la recherche"
    ordre = 65                          # position dans les listes
    sous_dossier = "Terrain"            # Terrain / Teleoperateur / Coordination

    @property
    def parametres(self):
        return [p_trimestre(), p_versions_menage(), p_fichier_menage(),
                Entier("seuil", "Seuil", 10, groupe="Règle", mini=0, maxi=100),
                p_sortie()]

    def executer(self, ctx, p):
        t = Trimestre.depuis(p["trimestre"])
        ctx.progression(10, "Lecture")           # met à jour la barre ; lève l'arrêt si demandé
        men = charger_menage(ctx, p)
        res = men[num(men, "rgmen") == 1]
        ctx.exporter(f"Mon_controle_{t.code}.xlsx", {"Resultat": res}, titre="Mon contrôle")
        ctx.alerte("National", f"{len(res)} ligne(s)")          # écran Alertes
        ctx.indicateur("nb_lignes", len(res))                   # écran Évolution
        ctx.graphique("Titre", "Resultat", "HH2", "Nbre", "bar") # onglet Graphiques
        ctx.resultat.resume = f"{len(res)} ligne(s)"


MODULE = MonControle()
```

Le module apparaît automatiquement dans le menu, le tableau de bord et le catalogue.

## Types de paramètres (`enem_core/parametres.py`)

`Texte`, `TrimestreP`, `Entier`, `Reel`, `Booleen`, `Choix`, `Dossier`, `Fichier`, `DateP` (calendrier),
`Liste` (mots séparés par des espaces), `Versions` (1 à 7 dossiers de versions), `Tableau` (lignes éditables).
L'argument `globale="…"` pré-remplit la valeur depuis les Paramètres généraux.

## Fonctions utiles

- `enem_core.donnees` : `lire_dta`, `lire_versions` (append), `fusionner` (équivalent `merge … keepusing`),
  `appliquer_libelles` (codes → libellés Stata), `sauver_dta`, `manquant`.
- `enem_core.references` : `regions`, `calendrier_zd`, `equipes`.
- `enem_core.exports.exporter_excel` : classeur mis en forme (surlignage de lignes possible).

## Tests

```
python tests/generer_donnees_test.py /chemin/donnees_fictives
python tests/test_modules.py /chemin/donnees_fictives
xvfb-run python tests/test_interface.py /chemin/donnees_fictives /chemin/captures   (Linux)
```
