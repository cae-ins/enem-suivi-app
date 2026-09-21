"""Cadre commun d'exécution des modules : contexte, progression, arrêt, résultats."""

from __future__ import annotations

import datetime as dt
import threading
import time
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import pandas as pd

from . import exports
from .donnees import ErreurDonnees
from .parametres import Param, valider


class ArretDemande(Exception):
    """Levée lorsque l'utilisateur clique sur « Arrêter »."""


@dataclass
class Resultat:
    tables: dict = field(default_factory=dict)          # nom -> DataFrame (vue Résultats)
    fichiers: list = field(default_factory=list)        # chemins produits
    alertes: list = field(default_factory=list)         # {gravite, entite, message}
    indicateurs: list = field(default_factory=list)     # {niveau, cle, indicateur, valeur, date_ref}
    surlignage: dict = field(default_factory=dict)      # nom table -> fonction(ligne) -> couleur
    graphiques: list = field(default_factory=list)      # specs de graphiques
    resume: str = ""
    dossier: str = ""
    statut: str = "terminé"
    execution_id: int | None = None


class Contexte:
    def __init__(self, module: "ModuleBase", globaux: dict, dossier_sortie: Path,
                 journal: Callable[[str], None] | None = None,
                 progression: Callable[[float, str], None] | None = None,
                 arret: threading.Event | None = None):
        self.module = module
        self.globaux = globaux
        self.dossier = dossier_sortie
        self._journal = journal or print
        self._progression = progression or (lambda p, m: None)
        self._arret = arret or threading.Event()
        self.resultat = Resultat(dossier=str(dossier_sortie))

    # --- communication avec l'interface ---------------------------------
    def journal(self, message: str):
        self._journal(message)

    def progression(self, pourcentage: float, message: str = ""):
        self.verifier_arret()
        self._progression(max(0.0, min(100.0, pourcentage)), message)
        if message:
            self._journal(message)

    def verifier_arret(self):
        if self._arret.is_set():
            raise ArretDemande()

    # --- sorties ----------------------------------------------------------
    def chemin(self, nom_fichier: str) -> Path:
        self.dossier.mkdir(parents=True, exist_ok=True)
        return self.dossier / nom_fichier

    def exporter(self, nom_fichier: str, feuilles: dict, titre: str | None = None,
                 surlignage: dict | None = None, afficher: "bool | list" = True) -> Path:
        chemin = exports.exporter_excel(self.chemin(nom_fichier), feuilles, titre, surlignage)
        self.resultat.fichiers.append(str(chemin))
        if afficher:
            for nom, df in feuilles.items():
                if isinstance(afficher, (list, tuple, set)) and nom not in afficher:
                    continue
                cle = nom if nom not in self.resultat.tables else f"{Path(nom_fichier).stem[:18]}·{nom}"
                self.resultat.tables[cle] = df
                if surlignage and nom in surlignage:
                    self.resultat.surlignage[cle] = surlignage[nom]
        self.journal(f"  ✓ Fichier créé : {chemin.name}")
        return chemin

    def exporter_csv(self, nom_fichier: str, df: pd.DataFrame, sep: str = ";") -> Path:
        chemin = exports.exporter_csv(self.chemin(nom_fichier), df, sep)
        self.resultat.fichiers.append(str(chemin))
        self.journal(f"  ✓ Fichier créé : {chemin.name}")
        return chemin

    def fichier_produit(self, chemin: Path):
        self.resultat.fichiers.append(str(chemin))

    def alerte(self, entite: str, message: str, gravite: str = "Moyenne"):
        self.resultat.alertes.append({"entite": entite, "message": message, "gravite": gravite})

    def indicateur(self, indicateur: str, valeur, niveau: str = "national", cle: str = "", date_ref: str | None = None):
        self.resultat.indicateurs.append({"indicateur": indicateur, "valeur": valeur, "niveau": niveau,
                                          "cle": cle, "date_ref": date_ref or dt.date.today().isoformat()})

    def graphique(self, titre: str, table: str, x: str, y: list | str, type: str = "bar", **options):
        self.resultat.graphiques.append({"titre": titre, "table": table, "x": x,
                                         "y": [y] if isinstance(y, str) else list(y), "type": type, **options})


class ModuleBase:
    id: str = ""
    nom: str = ""
    nom_court: str = ""
    description: str = ""
    equipe: str = ""
    frequence_jours: int | None = 7
    frequence_libelle: str = "Hebdomadaire"
    couleur: str = "#4A675A"
    entrees: str = ""
    sorties: str = ""
    code_origine: list = []
    mots_cles: str = ""
    ordre: int = 50
    sous_dossier: str = ""   # Terrain / Teleoperateur / Coordination

    @property
    def parametres(self) -> list[Param]:
        return []

    def trimestre(self, p: dict) -> str:
        return str(p.get("trimestre", "") or "")

    def executer(self, ctx: Contexte, p: dict) -> None:  # à surcharger
        raise NotImplementedError


def dossier_execution(racine: str | Path, module: ModuleBase, trimestre: str) -> Path:
    horodatage = dt.datetime.now().strftime("%Y-%m-%d_%Hh%M")
    base = Path(racine or ".")
    if trimestre:
        base = base / trimestre
    if module.sous_dossier:
        base = base / module.sous_dossier
    chemin = base / module.id / horodatage
    i = 2
    while chemin.exists():
        chemin = base / module.id / f"{horodatage}_{i}"
        i += 1
    return chemin


def lancer(module: ModuleBase, valeurs: dict, globaux: dict, stockage=None,
           journal=None, progression=None, arret: threading.Event | None = None) -> Resultat:
    """Valide les paramètres, exécute le module, enregistre l'historique."""
    journal = journal or print
    propres, erreurs = valider(module.parametres, valeurs)
    if erreurs:
        res = Resultat(statut="paramètres invalides", resume="\n".join(erreurs))
        for e in erreurs:
            journal("✗ " + e)
        return res
    trimestre = module.trimestre(propres)
    racine = propres.get("dossier_sortie") or globaux.get("dossier_sortie") or "Resultats"
    dossier = dossier_execution(racine, module, trimestre)
    ctx = Contexte(module, globaux, dossier, journal, progression, arret)
    exec_id = None
    if stockage is not None:
        exec_id = stockage.debut_execution(module.id, trimestre, propres, globaux.get("utilisateur", ""))
    t0 = time.time()
    journal(f"▶ {module.nom} — {dt.datetime.now():%d/%m/%Y %H:%M}")
    journal(f"  Dossier de sortie : {dossier}")
    statut, message = "terminé", ""
    try:
        module.executer(ctx, propres)
        ctx._progression(100, "Terminé")
        message = ctx.resultat.resume or f"{len(ctx.resultat.fichiers)} fichier(s) produit(s)"
        journal(f"■ Terminé en {time.time() - t0:.1f} s — {message}")
    except ArretDemande:
        statut, message = "arrêté", "Traitement interrompu par l'utilisateur"
        journal("■ " + message)
    except ErreurDonnees as e:
        statut, message = "erreur", str(e)
        journal("✗ ERREUR : " + message)
    except Exception as e:  # erreur imprévue : on garde la trace complète
        statut, message = "erreur", f"{type(e).__name__} : {e}"
        journal("✗ ERREUR : " + message)
        journal(traceback.format_exc())
    res = ctx.resultat
    res.statut, res.execution_id = statut, exec_id
    if not res.resume:
        res.resume = message
    if stockage is not None and exec_id is not None:
        stockage.fin_execution(exec_id, statut, time.time() - t0, str(dossier), message,
                               res.fichiers, res.indicateurs if statut == "terminé" else [],
                               res.alertes if statut == "terminé" else [], module.id, trimestre)
        if statut == "terminé":
            stockage.clore_alertes_module(module.id, exec_id)
    return res
