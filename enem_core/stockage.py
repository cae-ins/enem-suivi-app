"""Base SQLite de l'application : historique des exécutions, fichiers, indicateurs, alertes."""

from __future__ import annotations

import datetime as dt
import json
import sqlite3
import threading
from pathlib import Path

import pandas as pd

_SCHEMA = """
CREATE TABLE IF NOT EXISTS executions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    module TEXT NOT NULL,
    trimestre TEXT,
    debut TEXT NOT NULL,
    fin TEXT,
    statut TEXT,
    duree_s REAL,
    utilisateur TEXT,
    parametres TEXT,
    dossier_sortie TEXT,
    message TEXT
);
CREATE TABLE IF NOT EXISTS fichiers_sortie (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    execution_id INTEGER REFERENCES executions(id),
    chemin TEXT
);
CREATE TABLE IF NOT EXISTS indicateurs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    execution_id INTEGER REFERENCES executions(id),
    module TEXT,
    trimestre TEXT,
    date_ref TEXT,
    niveau TEXT,
    cle TEXT,
    indicateur TEXT,
    valeur REAL
);
CREATE TABLE IF NOT EXISTS alertes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    execution_id INTEGER REFERENCES executions(id),
    module TEXT,
    trimestre TEXT,
    date_creation TEXT,
    gravite TEXT,
    entite TEXT,
    message TEXT,
    traitee INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS ix_exec_module ON executions(module);
CREATE INDEX IF NOT EXISTS ix_ind_module ON indicateurs(module, indicateur);
"""


class Stockage:
    def __init__(self, chemin: str | Path):
        self.chemin = Path(chemin)
        self.chemin.parent.mkdir(parents=True, exist_ok=True)
        self._verrou = threading.Lock()
        self._local = threading.local()
        self.version = 0          # incrémenté à chaque écriture (évite les rafraîchissements inutiles)
        with self._cnx() as c:
            c.executescript(_SCHEMA)

    def _cnx(self):
        """Connexion réutilisée par fil d'exécution (ouvrir une connexion à chaque
        requête ralentissait le changement d'écran)."""
        cnx = getattr(self._local, "cnx", None)
        if cnx is None:
            cnx = sqlite3.connect(self.chemin, timeout=30, check_same_thread=False)
            cnx.execute("PRAGMA journal_mode=WAL")
            self._local.cnx = cnx
        return cnx

    # --- exécutions -----------------------------------------------------
    def debut_execution(self, module: str, trimestre: str, parametres: dict, utilisateur: str) -> int:
        self.version += 1
        with self._verrou, self._cnx() as c:
            cur = c.execute(
                "INSERT INTO executions(module, trimestre, debut, statut, utilisateur, parametres) VALUES (?,?,?,?,?,?)",
                (module, trimestre, _maintenant(), "en cours", utilisateur,
                 json.dumps(parametres, ensure_ascii=False, default=str)))
            return cur.lastrowid

    def fin_execution(self, exec_id: int, statut: str, duree: float, dossier: str, message: str,
                      fichiers: list, indicateurs: list, alertes: list, module: str, trimestre: str):
        maintenant = _maintenant()
        self.version += 1
        with self._verrou, self._cnx() as c:
            c.execute("UPDATE executions SET fin=?, statut=?, duree_s=?, dossier_sortie=?, message=? WHERE id=?",
                      (maintenant, statut, duree, dossier, message, exec_id))
            c.executemany("INSERT INTO fichiers_sortie(execution_id, chemin) VALUES (?,?)",
                          [(exec_id, str(f)) for f in fichiers])
            c.executemany(
                "INSERT INTO indicateurs(execution_id, module, trimestre, date_ref, niveau, cle, indicateur, valeur) "
                "VALUES (?,?,?,?,?,?,?,?)",
                [(exec_id, module, trimestre, i.get("date_ref", maintenant[:10]), i.get("niveau", ""),
                  str(i.get("cle", "")), i["indicateur"], _flottant(i.get("valeur"))) for i in indicateurs])
            c.executemany(
                "INSERT INTO alertes(execution_id, module, trimestre, date_creation, gravite, entite, message) "
                "VALUES (?,?,?,?,?,?,?)",
                [(exec_id, module, trimestre, maintenant, a.get("gravite", "Moyenne"), str(a.get("entite", "")),
                  a.get("message", "")) for a in alertes])

    # --- lectures -------------------------------------------------------
    def requete(self, sql: str, params: tuple = ()) -> pd.DataFrame:
        with self._cnx() as c:
            return pd.read_sql_query(sql, c, params=params)

    def derniers_lancements(self) -> dict:
        """Dernière exécution terminée de chaque module, en une seule requête."""
        df = self.requete(
            "SELECT e.* FROM executions e JOIN (SELECT module, MAX(id) id FROM executions "
            "WHERE statut='terminé' GROUP BY module) d ON e.id = d.id")
        return {r["module"]: r for r in df.to_dict("records")}

    def alertes_par_module(self) -> dict:
        df = self.requete("SELECT module, COUNT(*) n FROM alertes WHERE traitee=0 GROUP BY module")
        return dict(zip(df["module"], df["n"])) if len(df) else {}

    def nb_alertes_ouvertes_total(self) -> int:
        return int(self.requete("SELECT COUNT(*) n FROM alertes WHERE traitee=0")["n"].iloc[0])

    def derniere_execution(self, module: str) -> dict | None:
        df = self.requete("SELECT * FROM executions WHERE module=? AND statut='terminé' ORDER BY id DESC LIMIT 1",
                          (module,))
        return None if df.empty else df.iloc[0].to_dict()

    def historique(self, module: str | None = None, limite: int = 500) -> pd.DataFrame:
        if module:
            return self.requete("SELECT * FROM executions WHERE module=? ORDER BY id DESC LIMIT ?", (module, limite))
        return self.requete("SELECT * FROM executions ORDER BY id DESC LIMIT ?", (limite,))

    def fichiers(self, exec_id: int) -> list[str]:
        return self.requete("SELECT chemin FROM fichiers_sortie WHERE execution_id=?", (exec_id,))["chemin"].tolist()

    def alertes(self, ouvertes_seulement: bool = True) -> pd.DataFrame:
        sql = "SELECT * FROM alertes"
        if ouvertes_seulement:
            sql += " WHERE traitee=0"
        return self.requete(sql + " ORDER BY id DESC LIMIT 5000")

    def nb_alertes_ouvertes(self, module: str) -> int:
        df = self.requete("SELECT COUNT(*) n FROM alertes WHERE module=? AND traitee=0", (module,))
        return int(df["n"].iloc[0])

    def marquer_alertes(self, ids: list[int], traitee: bool = True):
        self.version += 1
        with self._verrou, self._cnx() as c:
            c.executemany("UPDATE alertes SET traitee=? WHERE id=?", [(int(traitee), i) for i in ids])

    def clore_alertes_module(self, module: str, sauf_execution: int):
        """Les alertes d'une exécution précédente sont remplacées par celles de la nouvelle."""
        self.version += 1
        with self._verrou, self._cnx() as c:
            c.execute("UPDATE alertes SET traitee=2 WHERE module=? AND execution_id<>? AND traitee=0",
                      (module, sauf_execution))

    def serie_indicateur(self, module: str, indicateur: str) -> pd.DataFrame:
        return self.requete(
            "SELECT i.date_ref, i.trimestre, i.niveau, i.cle, i.valeur, i.execution_id FROM indicateurs i "
            "WHERE i.module=? AND i.indicateur=? ORDER BY i.date_ref, i.execution_id", (module, indicateur))

    def indicateurs_disponibles(self) -> pd.DataFrame:
        return self.requete("SELECT DISTINCT module, indicateur FROM indicateurs ORDER BY module, indicateur")


def _maintenant() -> str:
    return dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _flottant(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None
