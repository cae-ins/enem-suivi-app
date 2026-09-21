# Suivi de la collecte ENEM – ANSTAT

Application Tkinter qui regroupe, en Python, les codes de suivi de la collecte de l'Enquête Nationale sur l'Emploi auprès des Ménages (ENEM).

## Installation (une seule fois par poste)

1. Python 3.11 ou plus récent doit être installé (cocher « Add Python to PATH » à l'installation).
2. Double-cliquer sur **INSTALLER.bat** (installe pandas, openpyxl, matplotlib et, si possible, pyreadstat).
3. Double-cliquer sur **LANCER_APPLICATION.bat** (ou taper `python main.py` dans ce dossier).

## Premier lancement

1. Ouvrir **Paramètres généraux** :
   - trimestre en cours (ex. `T3_2026`) et lundi de la semaine de référence 1 (bouton calendrier, ou bouton « depuis Semaine_ref.xlsx ») ;
   - dossiers des versions des bases ménage et dénombrement (bouton « Détecter les versions dans un dossier… ») ;
   - cohortes de réinterrogation : trimestre d'origine, valeur de `rgmen` et dossier des bases de ce trimestre ;
   - dossier racine des résultats.
2. Cliquer sur **Enregistrer**, puis sur « Appliquer ces valeurs à tous les modules ».
3. Ouvrir un module, vérifier les paramètres, cliquer sur **Lancer**.

## Modules

| Module | Code d'origine | Fréquence |
|---|---|---|
| Préparation des bases (append des versions) | Code_evolution_ZD.do | avant les contrôles |
| Présence des agents (paradata) | suivi_presence_agents_v2.py | hebdomadaire |
| Temps d'administration et performance | Main_performance.do, Transformation_HH13.do, Indicateur_performance_AG_claude3_Elodie.do, Modification_Elodie.do | toutes les 2 semaines |
| Vérification du numéro de porte | Verif_numero_porte.do | hebdomadaire |
| Cohérence inter-passages (sexe / emploi) | Correction_between_sexe.do, Correction_between_Emploi.do | hebdomadaire |
| Nombre de ménages par ZD | Nbre_MEN_ZD_T3_2026.do | toutes les 2 semaines |
| Contrôles de base | Code_suivi_collecte.do (sections 5 à 9) | hebdomadaire |
| Évolution des ZD (régions en retard) | Code_evolution_ZD.do (terminé) | hebdomadaire |
| Codification emploi (CITP / activités / produits) | Code_suivi_collecte.do (section 10) | fin de mois |
| Simulation indicateur – 1. Pondération simulée | simulation_pmencor_ind_T3_2026.do | à mi-parcours |
| Simulation indicateur – 2. Tableaux du bulletin | 1_Tabulation_DG_Bulletin_version_amélioré_sim.do, 1_1_Var_objectives_lower.do, 1_2_Indicateur_Bulletin_To_Run.do, Revision_CISE_12112024.do, programme_master_simple(.ANNUEL).do, programme_repartition_horiz_FINAL_total.do / _CORRIGE_ANNUEL.do | chaque trimestre |
| Diagramme de Gantt | generer_gantt.py | à la demande |

Les règles de calcul appliquées sont celles du document `00_Documentation/Observations_Unification_codes_ENEM_v1.2.docx`.

## Organisation du dossier

```
ENEM_Suivi/
├── main.py                  point d'entrée
├── INSTALLER.bat / LANCER_APPLICATION.bat
├── enem_core/               bibliothèque commune (trimestres, lecture .dta multi-versions, exports, historique)
├── modules/                 un fichier par point de suivi (ajout automatique dans l'application)
├── app/                     interface (écrans, grille type Excel, graphiques, calendrier)
├── reference/               Semaine_ref.xlsx, information_agent.xlsx, Fichier_Gant.xlsx,
│                            Tableaux_Indicateurs_ENEM_template_DG.xlsx (maquette du bulletin)
├── assets/                  logo ANSTAT
├── config/profil.json       paramètres enregistrés (créé au premier enregistrement)
├── donnees_app/             base SQLite de l'historique, journal des erreurs
├── docs/                    guide du développeur
└── tests/                   jeu de données fictif et tests automatiques
```

## Nouveautés de la version 1.0.3

Migration complète du bloc **« Simulation indicateur »** (dossier `Simulation_Indicateur`), en deux modules
qui s'enchaînent.

**1. Pondération simulée** (`simulation_pmencor_ind_T3_2026.do`) : la pondération du trimestre de référence
(même rang, année précédente : T3-2025 pour T3-2026) est ajustée par une **loi Gamma estimée par la méthode
des moments** — forme = moyenne² / variance, échelle = variance / moyenne, graine 12345 — exactement comme le
do-file. La base ménage est fusionnée avec `membres.dta` (1:m, on garde les appariés), les noms de variables
sont normalisés (minuscules, `__` → `_`), la pondération simulée est tirée, les variables du bulletin sont
construites et l'ensemble est enregistré sous `Base_Travail_BT_vf_<AA>T<q>.dta`. Les autres lois
(bootstrap, log-normale, moyenne de strate) et le calage restent disponibles en option, mais la valeur par
défaut reproduit le do-file.

**2. Tableaux du bulletin** (`1_Tabulation_DG_Bulletin_version_amélioré_sim.do`) : les variables objectives
(`1_1`), les indicateurs du bulletin (`1_2`) et la CISE 18 révisée (`Revision_CISE_12112024.do`) sont
reconstruits en Python, puis les **39 tableaux** du bulletin sont calculés par les deux moteurs de tabulation
portés à l'identique (`export_indicateur_simple` et `export_repartition_horiz`, avec leurs variantes
annuelles, la variante annuelle horizontale reprenant les corrections de décalage de lignes). Les résultats
sont écrits dans la maquette `Tableaux_Indicateurs_ENEM_template_DG.xlsx`, recopiée en
`Tableaux_Indicateurs_ENEM_DG.xlsx`, aux onglets et cellules exacts du do-file (PAT B6, Repartition_PAT
B6/AL6, Taux_emploi B6, Sous_utilisation_MO B7/K7/T7/AC7 et AL7/AU7/BD7/BM7, chomage_Annuel B7…P7,
CISE_risque B6/BD6, CISE_risque_10 B6/CW6, Branche_activite B6/AU6, NEETs B6, etc.). Un récapitulatif Excel
indique, tableau par tableau, ce qui a été produit et ce qui ne l'a pas été (variable absente, onglet absent,
aucune observation après filtrage).

Points d'attention :

- La sémantique Stata des valeurs manquantes est respectée : dans une comparaison, un manquant vaut plus
  l'infini (`age >= 16` est vrai si l'âge est manquant), alors que `inlist()` et `inrange()` l'excluent. Les
  résultats sont donc identiques à ceux de Stata, y compris pour les observations incomplètes.
- Les colonnes de la maquette sont remplies dans l'ordre des valeurs de `trimestre` (et de `annee`), sans
  laisser de trou : pour un alignement correct, empilez les bases de travail de **tous** les trimestres qui
  figurent dans l'en-tête des onglets.
- La variable `branche1` n'est pas construite par les do-files fournis : les tableaux qui l'utilisent sont
  signalés comme non produits tant qu'elle est absente de la base.

## Nouveautés de la version 1.0.2

- Cohérence sexe / emploi : note d'information en surbrillance au-dessus des cohortes, bouton « Parcourir… »
  pour chaque dossier de 1er passage et place réservée au bouton de suppression de ligne ; les graphiques
  portent l'étiquette de chaque écart (ex. « Féminin → Masculin ») et sa valeur au-dessus de la barre.
- Évolution des ZD : les onglets et feuilles portent le nom du trimestre de la cohorte (ex. « T3-2026 (en cours)
  (rgmen 1) ») au lieu de « Cohorte_1 ».
- Nouveau module « Simulation pondération » : simulation de la pondération du trimestre en cours à partir d'un
  trimestre déjà pondéré, application à la base en cours, rapport de comparaison des distributions et indicateurs
  de contrôle pondérés. Les tabulations officielles du bulletin restent à migrer.

## Nouveautés de la version 1.0.1

- Affichage des résultats paginé et construit onglet par onglet : plus de blocage sur les gros tableaux
  (Contrôles de base, Codification emploi). Un bouton « Afficher plus de lignes » complète l'affichage ;
  l'export et le fichier Excel contiennent toujours la totalité des lignes.
- Évolution des ZD : les cohortes sont extraites de la base du trimestre en cours par un `keep` sur `rgmen`
  (la base empilée contient déjà toutes les cohortes). Les sous-bases sont enregistrées dans un dossier de
  travail. Le dossier d'une cohorte n'est à renseigner que si elle se trouve dans une base séparée ; s'il ne
  contient pas la base attendue, il est ignoré avec un message.
- Changement d'écran nettement plus rapide (connexion à la base de données réutilisée, requêtes groupées,
  écrans rafraîchis seulement quand quelque chose a changé).

## Règles importantes

- Les bases brutes ne sont **jamais modifiées** : les recodages et corrections sont écrits dans des fichiers dérivés.
- Chaque exécution écrit dans un dossier daté : `<résultats>/<trimestre>/<équipe>/<module>/<AAAA-MM-JJ_HHhMM>`.
- Les trimestres et cohortes sont **saisis par l'utilisateur** (la règle de rotation ne sert qu'à pré-remplir).
- Pour transmettre le projet à un collègue : copier le dossier, puis « Exporter le profil » / « Importer un profil ».

## Tester sans les vraies données

```
python tests/generer_donnees_test.py            (crée tests/donnees_fictives, données inventées)
python tests/test_modules.py tests/donnees_fictives
```
