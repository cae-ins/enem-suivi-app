"""Profil de l'application : paramètres généraux et dernières valeurs de chaque module.

Le profil est un fichier JSON (``config/profil.json`` par défaut) : il peut être
copié et transmis à un collègue qui reprend le suivi.
"""

from __future__ import annotations

import copy
import datetime as dt
import getpass
import json
import os
from pathlib import Path

from . import RACINE_PROJET

FICHIER_PROFIL = Path(os.environ.get("ENEM_PROFIL") or RACINE_PROJET / "config" / "profil.json")

GLOBAUX_DEFAUT = {
    "utilisateur": "",
    "trimestre": "T3_2026",
    "lundi_semaine1": "29/06/2026",
    "dossier_sortie": str(RACINE_PROJET / "Resultats"),
    "semaine_ref": str(RACINE_PROJET / "reference" / "Semaine_ref.xlsx"),
    "information_agent": str(RACINE_PROJET / "reference" / "information_agent.xlsx"),
    "fichier_gantt": str(RACINE_PROJET / "reference" / "Fichier_Gant.xlsx"),
    "base_donnees": str(RACINE_PROJET / "donnees_app" / "suivi_enem.sqlite"),
    "dossier_codes_origine": str(RACINE_PROJET.parent),
    "versions_menage": [""],
    "versions_denombrement": [""],
    "cohortes": [],
}


class Profil:
    def __init__(self, chemin: str | Path = FICHIER_PROFIL):
        self.chemin = Path(chemin)
        self.globaux = copy.deepcopy(GLOBAUX_DEFAUT)
        self.modules: dict[str, dict] = {}
        self.charger()
        if not self.globaux.get("utilisateur"):
            try:
                self.globaux["utilisateur"] = getpass.getuser()
            except Exception:
                self.globaux["utilisateur"] = "utilisateur"

    def charger(self):
        if self.chemin.exists():
            try:
                data = json.loads(self.chemin.read_text(encoding="utf-8"))
                self.globaux.update(data.get("globaux", {}))
                self.modules = data.get("modules", {})
            except Exception:
                pass

    def sauver(self):
        self.chemin.parent.mkdir(parents=True, exist_ok=True)
        data = {"enregistre_le": dt.datetime.now().isoformat(timespec="seconds"),
                "globaux": self.globaux, "modules": self.modules}
        self.chemin.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    def valeurs_module(self, module) -> dict:
        """Valeurs pour le formulaire : dernières valeurs > paramètre global > défaut."""
        memo = self.modules.get(module.id, {})
        res = {}
        for p in module.parametres:
            if p.cle in memo:
                res[p.cle] = memo[p.cle]
            elif p.globale and self.globaux.get(p.globale) not in (None, "", [], [""]):
                res[p.cle] = copy.deepcopy(self.globaux[p.globale])
            else:
                res[p.cle] = copy.deepcopy(p.defaut)
        return res

    def memoriser(self, module_id: str, valeurs: dict):
        self.modules[module_id] = json.loads(json.dumps(valeurs, default=str))
        self.sauver()

    def oublier(self, module_id: str):
        self.modules.pop(module_id, None)
        self.sauver()
