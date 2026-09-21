"""Catalogue des modules de suivi.

Pour ajouter un nouveau contrôle : créer un fichier ``modules/mon_controle.py``
qui définit une classe héritant de ``ModuleBase`` et une variable ``MODULE``.
Il apparaîtra automatiquement dans l'application.
"""

from __future__ import annotations

import importlib
import pkgutil
import traceback

from enem_core.execution import ModuleBase

ERREURS_CHARGEMENT: dict[str, str] = {}


def charger_modules() -> list[ModuleBase]:
    modules = []
    for info in pkgutil.iter_modules(__path__):
        if info.name.startswith("_"):
            continue
        try:
            m = importlib.import_module(f"{__name__}.{info.name}")
            if isinstance(getattr(m, "MODULE", None), ModuleBase):
                modules.append(m.MODULE)
        except Exception:
            ERREURS_CHARGEMENT[info.name] = traceback.format_exc()
    return sorted(modules, key=lambda x: (x.ordre, x.nom))
