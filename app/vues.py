"""Écrans de l'application."""

from __future__ import annotations

import datetime as dt
import gc
import json
import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import pandas as pd

from enem_core import RACINE_PROJET
from enem_core import references as R
from enem_core.execution import lancer
from enem_core.exports import exporter_excel, lire_excel_toutes_feuilles
from enem_core.parametres import Colonne, DateP, Dossier, Fichier, Tableau, Texte, TrimestreP, Versions, valider
from enem_core.trimestre import Trimestre

from . import theme as T
from .widgets import ChampDate, Defilant, Formulaire, Graphique, Grille


def _date_fr(texte) -> str:
    try:
        return dt.datetime.strptime(str(texte)[:19], "%Y-%m-%d %H:%M:%S").strftime("%d/%m/%Y %H:%M")
    except ValueError:
        return str(texte or "")


def statut_module(app, module, derniers: dict | None = None) -> tuple[str, str, dict | None]:
    """(libellé, couleur, dernière exécution). ``derniers`` évite une requête par module."""
    der = derniers.get(module.id) if derniers is not None else app.stockage.derniere_execution(module.id)
    if not module.frequence_jours:
        return ("À la demande", T.GRIS, der)
    if der is None:
        return ("Jamais lancé", T.ORANGE, None)
    jours = (dt.datetime.now() - dt.datetime.strptime(der["debut"], "%Y-%m-%d %H:%M:%S")).days
    if jours >= 1.5 * module.frequence_jours:
        return (f"En retard ({jours} j)", T.ROUGE, der)
    if jours >= module.frequence_jours:
        return ("À lancer", T.ORANGE, der)
    return ("À jour", T.VERT, der)


class Vue(ttk.Frame):
    titre = ""

    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app

    def en_tete(self, titre, sous_titre=""):
        cadre = ttk.Frame(self)
        cadre.pack(fill="x", padx=18, pady=(14, 6))
        ttk.Label(cadre, text=titre, style="Titre.TLabel").pack(anchor="w")
        if sous_titre:
            ttk.Label(cadre, text=sous_titre, style="Aide.TLabel", font=(T.POLICE, 10)).pack(anchor="w")
        return cadre

    def actualiser(self):
        pass


# ---------------------------------------------------------------------------
class TableauDeBord(Vue):
    def __init__(self, parent, app):
        super().__init__(parent, app)
        self.en_tete("Tableau de bord", "Où en sont les points de suivi de la collecte ?")
        self.kpi = ttk.Frame(self)
        self.kpi.pack(fill="x", padx=18, pady=4)
        self.zone = Defilant(self)
        self.zone.pack(fill="both", expand=True, padx=12, pady=6)
        self.actualiser()

    def _tuile(self, parent, titre, valeur, couleur):
        c = tk.Frame(parent, bg=T.BLANC, highlightbackground=couleur, highlightthickness=2, padx=14, pady=8)
        tk.Label(c, text=titre, bg=T.BLANC, fg=T.GRIS, font=(T.POLICE, 9)).pack(anchor="w")
        tk.Label(c, text=valeur, bg=T.BLANC, fg=couleur, font=(T.POLICE, 18, "bold")).pack(anchor="w")
        return c

    def actualiser(self):
        if getattr(self, "_version", None) == self.app.stockage.version:
            return                       # rien n'a changé : affichage conservé
        self._version = self.app.stockage.version
        derniers = self.app.stockage.derniers_lancements()
        alertes_module = self.app.stockage.alertes_par_module()
        for w in self.kpi.winfo_children():
            w.destroy()
        g = self.app.profil.globaux
        try:
            lundi = dt.datetime.strptime(g.get("lundi_semaine1", ""), "%d/%m/%Y").date()
            sem = (dt.date.today() - lundi).days // 7 + 1
            sem_txt = f"Semaine {sem}" if 1 <= sem <= 13 else f"Hors période ({sem})"
        except ValueError:
            sem_txt = "Non définie"
        nb_alertes = self.app.stockage.nb_alertes_ouvertes_total()
        hist = self.app.stockage.historique(limite=1000)
        semaine = hist[pd.to_datetime(hist["debut"]) >= pd.Timestamp.now() - pd.Timedelta(days=7)] if len(hist) else hist
        a_lancer = sum(1 for m in self.app.modules if statut_module(self.app, m, derniers)[1] in (T.ORANGE, T.ROUGE))
        for i, (t, v, c) in enumerate([("Trimestre en cours", g.get("trimestre", "?"), T.VERT),
                                       ("Semaine de référence", sem_txt, T.VERT),
                                       ("Points de suivi à lancer", str(a_lancer), T.ORANGE if a_lancer else T.VERT),
                                       ("Alertes ouvertes", str(nb_alertes), T.ROUGE if nb_alertes else T.VERT),
                                       ("Exécutions (7 derniers jours)", str(len(semaine)), T.VERT)]):
            self._tuile(self.kpi, t, v, c).grid(row=0, column=i, sticky="nsew", padx=5)
            self.kpi.columnconfigure(i, weight=1)
        z = self.zone.interieur
        for w in z.winfo_children():
            w.destroy()
        for k in range(3):
            z.columnconfigure(k, weight=1, uniform="c")
        for i, m in enumerate(self.app.modules):
            lib, coul, der = statut_module(self.app, m, derniers)
            carte = tk.Frame(z, bg=T.BLANC, highlightbackground=T.GRIS_CLAIR, highlightthickness=1)
            carte.grid(row=i // 3, column=i % 3, sticky="nsew", padx=6, pady=6)
            tk.Frame(carte, bg=m.couleur, height=6).pack(fill="x")
            corps = tk.Frame(carte, bg=T.BLANC, padx=12, pady=8)
            corps.pack(fill="both", expand=True)
            tk.Label(corps, text=m.nom, bg=T.BLANC, fg=T.TEXTE, font=(T.POLICE, 11, "bold"), wraplength=330,
                     justify="left").pack(anchor="w")
            tk.Label(corps, text=f"{m.equipe}  •  {m.frequence_libelle}", bg=T.BLANC, fg=T.GRIS,
                     font=(T.POLICE, 9)).pack(anchor="w", pady=(2, 6))
            ligne = tk.Frame(corps, bg=T.BLANC)
            ligne.pack(fill="x")
            tk.Label(ligne, text=f" {lib} ", bg=coul, fg=T.BLANC, font=(T.POLICE, 9, "bold")).pack(side="left")
            n = int(alertes_module.get(m.id, 0))
            if n:
                tk.Label(ligne, text=f" ⚠ {n} alerte(s) ", bg=T.ROUGE_CLAIR, fg=T.ROUGE,
                         font=(T.POLICE, 9)).pack(side="left", padx=6)
            txt = f"Dernier lancement : {_date_fr(der['debut'])}" if der else "Aucun lancement enregistré"
            tk.Label(corps, text=txt, bg=T.BLANC, fg=T.GRIS, font=(T.POLICE, 8)).pack(anchor="w", pady=(6, 4))
            if der and der.get("message"):
                tk.Label(corps, text=str(der["message"])[:110], bg=T.BLANC, fg=T.TEXTE, font=(T.POLICE, 8),
                         wraplength=330, justify="left").pack(anchor="w")
            bas = tk.Frame(corps, bg=T.BLANC)
            bas.pack(fill="x", pady=(8, 0))
            T.Bouton(bas, "Ouvrir", lambda mod=m: self.app.ouvrir_module(mod), padx=10, pady=3).pack(side="left")
            if der:
                T.Bouton(bas, "Résultats", lambda d=der, mod=m: self.app.resultats_execution(d, mod),
                         style="neutre", padx=8, pady=3).pack(side="left", padx=4)


# ---------------------------------------------------------------------------
class Catalogue(Vue):
    def __init__(self, parent, app):
        super().__init__(parent, app)
        self.en_tete("Catalogue des codes", "Tous les codes de suivi, leur rôle, leurs entrées et sorties, "
                                             "et l'emplacement du code d'origine.")
        barre = ttk.Frame(self)
        barre.pack(fill="x", padx=18)
        ttk.Label(barre, text="🔍 Rechercher (nom, variable, mot-clé) :").pack(side="left")
        self.q = tk.StringVar()
        e = ttk.Entry(barre, textvariable=self.q, width=40)
        e.pack(side="left", padx=6)
        e.bind("<KeyRelease>", lambda ev: self.remplir())
        self.equipe = ttk.Combobox(barre, state="readonly", width=26,
                                   values=["Toutes les équipes"] + sorted({m.equipe for m in app.modules}))
        self.equipe.set("Toutes les équipes")
        self.equipe.pack(side="left", padx=6)
        self.equipe.bind("<<ComboboxSelected>>", lambda e: self.remplir())
        pan = ttk.PanedWindow(self, orient="vertical")
        pan.pack(fill="both", expand=True, padx=18, pady=8)
        haut = ttk.Frame(pan)
        cols = ("Module", "Équipe", "Fréquence", "Entrées", "Sorties")
        self.arbre = ttk.Treeview(haut, columns=cols, show="headings")
        for c, w in zip(cols, (300, 170, 150, 380, 380)):
            self.arbre.heading(c, text=c)
            self.arbre.column(c, width=w)
        self.arbre.pack(fill="both", expand=True)
        self.arbre.bind("<<TreeviewSelect>>", lambda e: self.details())
        self.arbre.bind("<Double-1>", lambda e: self._ouvrir())
        pan.add(haut, weight=3)
        self.detail = tk.Frame(pan, bg=T.BLANC, padx=14, pady=10)
        pan.add(self.detail, weight=2)
        self.remplir()

    def _modules(self):
        q = self.q.get().lower().strip()
        eq = self.equipe.get()
        for m in self.app.modules:
            texte = " ".join([m.nom, m.description, m.entrees, m.sorties, m.mots_cles, " ".join(m.code_origine),
                              " ".join(p.libelle + " " + p.cle for p in m.parametres)]).lower()
            if (not q or q in texte) and (eq == "Toutes les équipes" or eq == m.equipe):
                yield m

    def remplir(self):
        self.arbre.delete(*self.arbre.get_children())
        for m in self._modules():
            self.arbre.insert("", "end", iid=m.id, values=(m.nom, m.equipe, m.frequence_libelle, m.entrees, m.sorties))

    def _module(self):
        sel = self.arbre.selection()
        return next((m for m in self.app.modules if sel and m.id == sel[0]), None)

    def _ouvrir(self):
        m = self._module()
        if m:
            self.app.ouvrir_module(m)

    def details(self):
        m = self._module()
        for w in self.detail.winfo_children():
            w.destroy()
        if not m:
            return
        tk.Frame(self.detail, bg=m.couleur, height=5).pack(fill="x")
        tk.Label(self.detail, text=m.nom, bg=T.BLANC, fg=T.VERT, font=(T.POLICE, 13, "bold")).pack(anchor="w", pady=4)
        tk.Label(self.detail, text=m.description, bg=T.BLANC, wraplength=1000, justify="left").pack(anchor="w")
        for lib, val in (("Entrées", m.entrees), ("Sorties", m.sorties),
                         ("Paramètres", ", ".join(p.libelle for p in m.parametres))):
            tk.Label(self.detail, text=f"{lib} : {val}", bg=T.BLANC, fg=T.GRIS, wraplength=1000,
                     justify="left").pack(anchor="w", pady=1)
        bas = tk.Frame(self.detail, bg=T.BLANC)
        bas.pack(anchor="w", pady=8)
        T.Bouton(bas, "Ouvrir le module", lambda: self.app.ouvrir_module(m)).pack(side="left")
        racine = Path(self.app.profil.globaux.get("dossier_codes_origine") or RACINE_PROJET.parent)
        for c in m.code_origine:
            chemin = racine / c
            T.Bouton(bas, f"Code d'origine : {Path(c).name}", lambda p=chemin: self._voir(p), style="neutre",
                     padx=8).pack(side="left", padx=4)
        src = Path(__import__(type(m).__module__, fromlist=["x"]).__file__)
        T.Bouton(bas, "Code Python", lambda: self._voir(src), style="secondaire", padx=8).pack(side="left", padx=4)

    def _voir(self, chemin: Path):
        if not chemin.exists():
            messagebox.showwarning("Code", f"Fichier introuvable :\n{chemin}\n\nVérifiez le « Dossier des codes "
                                           "d'origine » dans les Paramètres généraux.")
            return
        f = tk.Toplevel(self)
        f.title(chemin.name)
        f.geometry("1000x700")
        txt = tk.Text(f, wrap="none", font=("Consolas", 10), bg="#FBFBF8")
        sb = ttk.Scrollbar(f, command=txt.yview)
        txt.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        txt.pack(fill="both", expand=True)
        txt.insert("1.0", chemin.read_text(encoding="utf-8", errors="replace"))
        txt.configure(state="disabled")
        b = ttk.Frame(f)
        b.pack(fill="x")
        T.Bouton(b, "Ouvrir avec l'éditeur par défaut", lambda: T.ouvrir(chemin), style="neutre").pack(side="right", padx=6, pady=4)


# ---------------------------------------------------------------------------
class VueModule(Vue):
    def __init__(self, parent, app, module):
        super().__init__(parent, app)
        self.module = module
        self.file = queue.Queue()
        self.arret = threading.Event()
        self.thread = None
        self.resultat = None
        clair = T.eclaircir(module.couleur, 0.88)
        bandeau = tk.Frame(self, bg=module.couleur, padx=18, pady=10)
        bandeau.pack(fill="x")
        tk.Label(bandeau, text=module.nom, bg=module.couleur, fg=T.BLANC, font=(T.POLICE, 16, "bold")).pack(anchor="w")
        tk.Label(bandeau, text=module.description, bg=module.couleur, fg=T.BLANC, wraplength=1100,
                 justify="left").pack(anchor="w")
        self.info = tk.Label(bandeau, bg=module.couleur, fg=clair, font=(T.POLICE, 9))
        self.info.pack(anchor="w", pady=(4, 0))
        corps = ttk.PanedWindow(self, orient="horizontal")
        corps.pack(fill="both", expand=True, padx=8, pady=8)
        gauche = tk.Frame(corps, bg=clair, padx=4, pady=4)
        corps.add(gauche, weight=3)
        self.defil = Defilant(gauche)
        self.defil.pack(fill="both", expand=True)
        valeurs = app.profil.valeurs_module(module)
        self.formulaire = Formulaire(self.defil.interieur, module.parametres, valeurs)
        self.formulaire.pack(fill="x")
        # --- boutons SOUS le paramétrage (toujours visibles)
        actions = tk.Frame(gauche, bg=clair, pady=4)
        actions.pack(fill="x")
        actions2 = tk.Frame(gauche, bg=clair, pady=2)
        actions2.pack(fill="x")
        self.b_lancer = T.Bouton(actions, "▶  Lancer", self.lancer)
        self.b_lancer.pack(side="left", padx=3)
        self.b_arret = T.Bouton(actions, "■  Arrêter", self.arreter, style="danger")
        self.b_arret.pack(side="left", padx=3)
        self.b_arret.activer(False)
        self.b_voir = T.Bouton(actions2, "👁  Visualiser les résultats", self.visualiser, style="secondaire")
        self.b_voir.pack(side="left", padx=3)
        self.b_graph = T.Bouton(actions2, "📊  Graphiques", lambda: self.visualiser(onglet="graph"), style="secondaire")
        self.b_graph.pack(side="left", padx=3)
        self.b_dossier = T.Bouton(actions2, "📂  Dossier de sortie", self.ouvrir_dossier, style="neutre")
        self.b_dossier.pack(side="left", padx=3)
        T.Bouton(actions, "↺ Valeurs par défaut", self.reinitialiser, style="neutre").pack(side="right", padx=3)
        self.after(150, lambda: corps.sashpos(0, int(max(corps.winfo_width(), 900) * 0.64)))
        for b in (self.b_voir, self.b_graph, self.b_dossier):
            b.activer(False)
        prog = tk.Frame(gauche, bg=clair)
        prog.pack(fill="x", pady=(0, 2))
        self.barre = ttk.Progressbar(prog, maximum=100, style="Orange.Horizontal.TProgressbar")
        self.barre.pack(side="left", fill="x", expand=True, padx=3)
        self.pct = tk.Label(prog, text="0 %", bg=clair, width=6)
        self.pct.pack(side="left")
        self.etat = tk.Label(gauche, text="Prêt.", bg=clair, fg=T.TEXTE, anchor="w")
        self.etat.pack(fill="x", padx=3)
        # --- droite : journal + fichiers
        droite = ttk.Frame(corps)
        corps.add(droite, weight=2)
        ttk.Label(droite, text="Journal d'exécution", style="SousTitre.TLabel").pack(anchor="w")
        self.journal = tk.Text(droite, height=18, bg="#1F2A24", fg="#E6EDE8", font=("Consolas", 9), wrap="word",
                               insertbackground=T.BLANC)
        self.journal.pack(fill="both", expand=True)
        self.journal.tag_configure("erreur", foreground="#FF8A80")
        self.journal.tag_configure("ok", foreground="#A5D6A7")
        self.journal.tag_configure("titre", foreground=T.ORANGE)
        ttk.Label(droite, text="Fichiers produits (double-clic pour ouvrir)", style="SousTitre.TLabel").pack(anchor="w", pady=(8, 0))
        self.fichiers = tk.Listbox(droite, height=8, activestyle="none", selectbackground=T.ORANGE)
        self.fichiers.pack(fill="both", expand=False)
        self.fichiers.bind("<Double-1>", self._ouvrir_fichier)
        self._maj_info()

    def _maj_info(self):
        lib, _, der = statut_module(self.app, self.module)
        txt = f"Équipe : {self.module.equipe}   •   Fréquence : {self.module.frequence_libelle}   •   Statut : {lib}"
        if der:
            txt += f"   •   Dernier lancement : {_date_fr(der['debut'])}"
        self.info.configure(text=txt)

    def ecrire(self, texte):
        tag = "erreur" if texte.startswith("✗") else "ok" if "✓" in texte else "titre" if texte[:1] in "▶■" else None
        self.journal.insert("end", texte + "\n", tag)
        self.journal.see("end")

    def lancer(self):
        valeurs = self.formulaire.valeurs()
        _, erreurs = valider(self.module.parametres, valeurs)
        if erreurs:
            messagebox.showerror("Paramètres à corriger", "\n".join("• " + e for e in erreurs), parent=self)
            return
        self.app.profil.memoriser(self.module.id, valeurs)
        self.arret.clear()
        self.resultat = None
        # Les objets Tk ne doivent pas être détruits depuis le fil de calcul
        gc.collect()
        gc.freeze()
        self.journal.delete("1.0", "end")
        self.fichiers.delete(0, "end")
        self.b_lancer.activer(False)
        self.b_arret.activer(True)
        for b in (self.b_voir, self.b_graph, self.b_dossier):
            b.activer(False)
        self.barre["value"] = 0
        self.etat.configure(text="Traitement en cours…")
        g = dict(self.app.profil.globaux)

        def travail():
            res = lancer(self.module, valeurs, g, self.app.stockage,
                         journal=lambda t: self.file.put(("journal", t)),
                         progression=lambda p, m: self.file.put(("progression", (p, m))),
                         arret=self.arret)
            self.file.put(("fin", res))
        self.thread = threading.Thread(target=travail, daemon=True)
        self.thread.start()
        self.after(100, self._ecouter)

    def _ecouter(self):
        try:
            while True:
                genre, val = self.file.get_nowait()
                if genre == "journal":
                    self.ecrire(val)
                elif genre == "progression":
                    p, m = val
                    self.barre["value"] = p
                    self.pct.configure(text=f"{p:.0f} %")
                    if m:
                        self.etat.configure(text=m)
                elif genre == "fin":
                    self._terminer(val)
                    return
        except queue.Empty:
            pass
        self.after(100, self._ecouter)

    def _terminer(self, res):
        gc.unfreeze()
        gc.collect()
        self.resultat = res
        self.b_lancer.activer(True)
        self.b_arret.activer(False)
        for f in res.fichiers:
            self.fichiers.insert("end", Path(f).name)
        ok = res.statut == "terminé"
        self.etat.configure(text=("✓ " if ok else "✗ ") + (res.resume or res.statut),
                            fg=T.VERT_FONCE if ok else T.ROUGE)
        self.b_voir.activer(bool(res.tables))
        self.b_graph.activer(bool(res.graphiques))
        self.b_dossier.activer(bool(res.dossier) and Path(res.dossier).exists())
        self._maj_info()
        self.app.rafraichir_barre()
        if ok and res.alertes:
            self.ecrire(f"⚠ {len(res.alertes)} alerte(s) enregistrée(s) (écran Alertes)")
        if res.statut == "paramètres invalides":
            messagebox.showerror("Paramètres", res.resume, parent=self)

    def arreter(self):
        if self.thread and self.thread.is_alive():
            self.arret.set()
            self.etat.configure(text="Arrêt demandé… (le traitement s'interrompt à la prochaine étape)")

    def visualiser(self, onglet="donnees"):
        if self.resultat:
            FenetreResultats(self, self.module, self.resultat.tables, self.resultat.surlignage,
                             self.resultat.graphiques, self.resultat.fichiers, onglet)

    def ouvrir_dossier(self):
        if self.resultat and self.resultat.dossier:
            T.ouvrir(self.resultat.dossier)

    def _ouvrir_fichier(self, _):
        sel = self.fichiers.curselection()
        if sel and self.resultat:
            T.ouvrir(self.resultat.fichiers[sel[0]])

    def reinitialiser(self):
        if messagebox.askyesno("Réinitialiser", "Remettre les paramètres de ce module aux valeurs par défaut "
                                                "(et aux paramètres généraux) ?", parent=self):
            self.app.profil.oublier(self.module.id)
            self.formulaire.definir(self.app.profil.valeurs_module(self.module))

    def charger_parametres(self, valeurs: dict):
        self.formulaire.definir(valeurs)


# ---------------------------------------------------------------------------
class FenetreResultats(tk.Toplevel):
    """Fenêtre des résultats. Les tableaux sont construits à la demande (onglet ouvert),
    ce qui évite de figer l'application quand un module produit de gros fichiers."""

    def __init__(self, parent, module, tables: dict, surlignage: dict, graphiques: list, fichiers: list,
                 onglet="donnees"):
        super().__init__(parent)
        self.title(f"Résultats – {module.nom if module else ''}")
        self.geometry("1250x780")
        self.configure(bg=T.FOND)
        self.tables = tables
        self.surlignage = surlignage or {}
        self._grilles: dict[str, Grille] = {}
        self._onglets: dict[str, tuple] = {}
        tk.Frame(self, bg=module.couleur if module else T.VERT, height=6).pack(fill="x")
        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=6, pady=6)
        if tables:
            donnees = ttk.Frame(nb)
            nb.add(donnees, text="  Tableaux  ")
            self.sous = ttk.Notebook(donnees)
            self.sous.pack(fill="both", expand=True)
            for nom, df in tables.items():
                f = ttk.Frame(self.sous, padding=4)
                self.sous.add(f, text=f" {nom[:28]} ({len(df)}) ")
                ttk.Label(f, text="Chargement…", style="Aide.TLabel").pack(anchor="center", pady=20)
                self._onglets[str(f)] = (f, nom)
            self.sous.bind("<<NotebookTabChanged>>", self._changer_onglet)
            self.after(50, self._changer_onglet)
        if graphiques:
            g = ttk.Frame(nb, padding=4)
            nb.add(g, text="  Graphiques  ")
            haut = ttk.Frame(g)
            haut.pack(fill="x")
            ttk.Label(haut, text="Graphique :").pack(side="left")
            self.choix = ttk.Combobox(haut, state="readonly", width=70, values=[s["titre"] for s in graphiques])
            self.choix.pack(side="left", padx=6)
            zone = Defilant(g)
            zone.pack(fill="both", expand=True)
            self.graph = Graphique(zone.interieur)
            self.graph.pack(fill="both", expand=True)
            self.specs = graphiques
            self.choix.bind("<<ComboboxSelected>>", lambda e: self._tracer())
            self.choix.current(0)
            self.after(60, self._tracer)
            if onglet == "graph":
                nb.select(g)
        if fichiers:
            fr = Defilant(ttk.Frame(nb))
            cadre = fr.master
            nb.add(cadre, text="  Fichiers  ")
            fr.pack(fill="both", expand=True)
            for f in fichiers:
                ligne = tk.Frame(fr.interieur, bg=T.FOND)
                ligne.pack(fill="x", pady=1, padx=6)
                tk.Label(ligne, text=Path(f).name, width=70, anchor="w", bg=T.FOND).pack(side="left")
                T.Bouton(ligne, "Ouvrir", lambda p=f: T.ouvrir(p), style="neutre", padx=8, pady=1).pack(side="left")
                if f.endswith(".xlsx"):
                    T.Bouton(ligne, "Afficher ici", lambda p=f: self._afficher_fichier(module, p),
                             style="secondaire", padx=8, pady=1).pack(side="left", padx=4)

    def _changer_onglet(self, _=None):
        courant = self.sous.select()
        if not courant or courant in self._grilles:
            return
        cadre, nom = self._onglets.get(courant, (None, None))
        if cadre is None:
            return
        for w in cadre.winfo_children():
            w.destroy()
        grille = Grille(cadre, titre=nom)
        grille.pack(fill="both", expand=True)
        self._grilles[courant] = grille
        self.update_idletasks()
        grille.charger(self.tables[nom], self.surlignage.get(nom))

    def _afficher_fichier(self, module, chemin):
        self.configure(cursor="watch")
        self.update_idletasks()
        try:
            FenetreResultats(self, module, lire_excel_toutes_feuilles(chemin), {}, [], [chemin])
        finally:
            self.configure(cursor="")

    def _tracer(self):
        spec = self.specs[self.choix.current()]
        df = self.tables.get(spec["table"])
        if df is None:
            df = next((v for k, v in self.tables.items() if k.endswith(spec["table"])), pd.DataFrame())
        self.graph.tracer(spec, df)


# ---------------------------------------------------------------------------
class Historique(Vue):
    COLS = ("id", "debut", "module", "trimestre", "statut", "duree_s", "utilisateur", "message")

    def __init__(self, parent, app):
        super().__init__(parent, app)
        self.en_tete("Historique des exécutions", "Toutes les exécutions, avec les paramètres utilisés.")
        barre = ttk.Frame(self)
        barre.pack(fill="x", padx=18)
        self.filtre = ttk.Combobox(barre, state="readonly", width=45,
                                   values=["Tous les modules"] + [m.nom for m in app.modules])
        self.filtre.set("Tous les modules")
        self.filtre.pack(side="left")
        self.filtre.bind("<<ComboboxSelected>>", lambda e: self.actualiser(force=True))
        for txt, cmd, st in (("Voir les résultats", self.resultats, "secondaire"),
                             ("Ouvrir le dossier", self.dossier, "neutre"),
                             ("Voir les paramètres", self.parametres, "neutre"),
                             ("Relancer avec ces paramètres", self.relancer, "principal")):
            T.Bouton(barre, txt, cmd, style=st, padx=8, pady=2).pack(side="left", padx=4)
        self.arbre = ttk.Treeview(self, columns=self.COLS, show="headings")
        for c, t, w in zip(self.COLS, ("N°", "Date", "Module", "Trimestre", "Statut", "Durée (s)", "Utilisateur",
                                        "Résumé"), (50, 140, 280, 90, 90, 80, 110, 500)):
            self.arbre.heading(c, text=t)
            self.arbre.column(c, width=w)
        self.arbre.tag_configure("erreur", background=T.ROUGE_CLAIR)
        self.arbre.tag_configure("arrêté", background=T.ORANGE_CLAIR)
        self.arbre.pack(fill="both", expand=True, padx=18, pady=8)
        self._version = None
        self.arbre.bind("<Double-1>", lambda e: self.resultats())
        self.df = pd.DataFrame()
        self.actualiser()

    def actualiser(self, force=False):
        if not force and getattr(self, "_version", None) == self.app.stockage.version:
            return
        self._version = self.app.stockage.version
        mid = next((m.id for m in self.app.modules if m.nom == self.filtre.get()), None)
        self.df = self.app.stockage.historique(mid)
        noms = {m.id: m.nom for m in self.app.modules}
        self.arbre.delete(*self.arbre.get_children())
        for _, r in self.df.iterrows():
            self.arbre.insert("", "end", iid=str(r["id"]), tags=(r["statut"],), values=(
                r["id"], _date_fr(r["debut"]), noms.get(r["module"], r["module"]), r["trimestre"], r["statut"],
                f"{r['duree_s']:.1f}" if pd.notna(r["duree_s"]) else "", r["utilisateur"], r["message"]))

    def _ligne(self):
        sel = self.arbre.selection()
        if not sel:
            messagebox.showinfo("Historique", "Sélectionnez une exécution.")
            return None
        return self.df[self.df["id"] == int(sel[0])].iloc[0].to_dict()

    def resultats(self):
        r = self._ligne()
        if r:
            self.app.resultats_execution(r, self.app.module_par_id(r["module"]))

    def dossier(self):
        r = self._ligne()
        if r and r.get("dossier_sortie") and Path(r["dossier_sortie"]).exists():
            T.ouvrir(r["dossier_sortie"])

    def parametres(self):
        r = self._ligne()
        if r:
            f = tk.Toplevel(self)
            f.title(f"Paramètres de l'exécution n°{r['id']}")
            t = tk.Text(f, width=100, height=30, font=("Consolas", 9))
            t.pack(fill="both", expand=True)
            t.insert("1.0", json.dumps(json.loads(r["parametres"] or "{}"), ensure_ascii=False, indent=2))

    def relancer(self):
        r = self._ligne()
        if r:
            m = self.app.module_par_id(r["module"])
            if m:
                vue = self.app.ouvrir_module(m)
                vue.charger_parametres(json.loads(r["parametres"] or "{}"))


# ---------------------------------------------------------------------------
class Alertes(Vue):
    def __init__(self, parent, app):
        super().__init__(parent, app)
        self.en_tete("Alertes", "Anomalies relevées par les derniers lancements de chaque module.")
        barre = ttk.Frame(self)
        barre.pack(fill="x", padx=18)
        self.toutes = tk.BooleanVar(value=False)
        ttk.Checkbutton(barre, text="Afficher aussi les alertes traitées ou remplacées", variable=self.toutes,
                        command=self.actualiser).pack(side="left")
        T.Bouton(barre, "Marquer la sélection comme traitée", self.traiter, style="secondaire", padx=8,
                 pady=2).pack(side="left", padx=8)
        T.Bouton(barre, "Rouvrir la sélection", lambda: self.traiter(False), style="neutre", padx=8,
                 pady=2).pack(side="left")
        self.grille = Grille(self, titre="Alertes")
        self.grille.pack(fill="both", expand=True, padx=18, pady=8)
        self.actualiser()

    def actualiser(self, force=False):
        etat = (self.app.stockage.version, self.toutes.get())
        if not force and getattr(self, "_etat", None) == etat:
            return
        self._etat = etat
        df = self.app.stockage.alertes(not self.toutes.get())
        noms = {m.id: m.nom for m in self.app.modules}
        if len(df):
            df["module"] = df["module"].map(lambda x: noms.get(x, x))
            df["etat"] = df["traitee"].map({0: "Ouverte", 1: "Traitée", 2: "Remplacée"})
            df = df[["id", "date_creation", "module", "trimestre", "gravite", "entite", "message", "etat"]]
        couleur = lambda r: {"Haute": "ROUGE", "Moyenne": "ORANGE"}.get(r.get("gravite"))
        self.grille.charger(df, couleur)

    def traiter(self, etat=True):
        ids = [int(self.grille.arbre.item(i, "values")[0]) for i in self.grille.arbre.selection()]
        if ids:
            self.app.stockage.marquer_alertes(ids, etat)
            self.actualiser(force=True)
            self.app.rafraichir_barre()


# ---------------------------------------------------------------------------
class Evolution(Vue):
    def __init__(self, parent, app):
        super().__init__(parent, app)
        self.en_tete("Évolution des indicateurs", "Suivi dans le temps des indicateurs enregistrés à chaque "
                                                   "lancement (ex. ZD réalisées par région, taux de présence).")
        barre = ttk.Frame(self)
        barre.pack(fill="x", padx=18)
        ttk.Label(barre, text="Indicateur :").pack(side="left")
        self.ind = ttk.Combobox(barre, state="readonly", width=60)
        self.ind.pack(side="left", padx=6)
        self.ind.bind("<<ComboboxSelected>>", lambda e: self.charger_cles())
        T.Bouton(barre, "Tracer", self.tracer, padx=10, pady=2).pack(side="left", padx=6)
        corps = ttk.PanedWindow(self, orient="horizontal")
        corps.pack(fill="both", expand=True, padx=18, pady=8)
        g = ttk.Frame(corps)
        corps.add(g, weight=1)
        ttk.Label(g, text="Éléments (Ctrl+clic pour plusieurs) :").pack(anchor="w")
        self.cles = tk.Listbox(g, selectmode="extended", exportselection=False, width=40,
                               selectbackground=T.ORANGE)
        self.cles.pack(fill="both", expand=True)
        d = ttk.Notebook(corps)
        corps.add(d, weight=4)
        f1 = ttk.Frame(d)
        d.add(f1, text="  Graphique  ")
        self.graph = Graphique(f1)
        self.graph.pack(fill="both", expand=True)
        f2 = ttk.Frame(d)
        d.add(f2, text="  Tableau  ")
        self.grille = Grille(f2, titre="Evolution")
        self.grille.pack(fill="both", expand=True)
        self.actualiser()

    def actualiser(self):
        if getattr(self, "_version", None) == self.app.stockage.version:
            return
        self._version = self.app.stockage.version
        dispo = self.app.stockage.indicateurs_disponibles()
        noms = {m.id: m.nom for m in self.app.modules}
        self.options = [(r.module, r.indicateur) for r in dispo.itertuples()]
        self.ind.configure(values=[f"{noms.get(m, m)} — {i}" for m, i in self.options])
        if self.options and not self.ind.get():
            prefere = next((k for k, (m, i) in enumerate(self.options)
                            if (m, i) == ("evolution_zd", "zd_realisees")), 0)
            self.ind.current(prefere)
            self.charger_cles()

    def charger_cles(self):
        if self.ind.current() < 0:
            return
        m, i = self.options[self.ind.current()]
        self.serie = self.app.stockage.serie_indicateur(m, i)
        self.serie["cle"] = self.serie["cle"].fillna("").replace("", "national")
        self.cles.delete(0, "end")
        for c in sorted(self.serie["cle"].unique()):
            self.cles.insert("end", c)
        if self.cles.size() <= 8:
            self.cles.select_set(0, "end")
        else:
            self.cles.select_set(0, 7)
        self.tracer()

    def tracer(self):
        if not hasattr(self, "serie"):
            return
        choix = [self.cles.get(i) for i in self.cles.curselection()]
        s = self.serie[self.serie["cle"].isin(choix)]
        # dernière valeur par jour et par élément
        s = s.sort_values("execution_id").groupby(["cle", "date_ref"], as_index=False).last()
        series = {c: sub.rename(columns={"date_ref": "date", "valeur": "valeur"}) for c, sub in s.groupby("cle")}
        cibles = {}
        m, i = self.options[self.ind.current()]
        if i == "zd_realisees":
            c = self.app.stockage.serie_indicateur(m, "zd_cible")
            c = c[c["cle"].isin(choix)].sort_values("execution_id").groupby(["cle", "date_ref"], as_index=False).last()
            cibles = {k: sub.rename(columns={"date_ref": "date"}) for k, sub in c.groupby("cle")}
        self.graph.tracer_series(self.ind.get(), series, cibles=cibles)
        piv = s.pivot_table(index="date_ref", columns="cle", values="valeur").reset_index()
        self.grille.charger(piv)


# ---------------------------------------------------------------------------
class TachesGantt(Vue):
    def __init__(self, parent, app):
        super().__init__(parent, app)
        from modules.m10_gantt import COLS
        self.cols = COLS
        self.en_tete("Tâches du diagramme de Gantt", "Ajoutez, modifiez ou supprimez les tâches, puis générez le Gantt.")
        barre = ttk.Frame(self)
        barre.pack(fill="x", padx=18)
        ttk.Label(barre, text="Fichier :").pack(side="left")
        self.fichier = tk.StringVar(value=app.profil.globaux.get("fichier_gantt", ""))
        ttk.Entry(barre, textvariable=self.fichier, width=70).pack(side="left", padx=4)
        T.Bouton(barre, "Charger", self.charger, style="neutre", padx=8, pady=1).pack(side="left")
        ttk.Label(barre, text="   Trimestre :").pack(side="left")
        self.filtre = ttk.Combobox(barre, state="readonly", width=12)
        self.filtre.pack(side="left", padx=4)
        self.filtre.bind("<<ComboboxSelected>>", lambda e: self.remplir())
        self.arbre = ttk.Treeview(self, columns=("idx",) + tuple(COLS), show="headings", height=14)
        for c, t, w in zip(("idx",) + tuple(COLS), ("#", "Trimestre", "Ordre", "Tâche", "Début", "Fin"),
                           (40, 90, 60, 620, 100, 100)):
            self.arbre.heading(c, text=t)
            self.arbre.column(c, width=w)
        self.arbre.pack(fill="both", expand=True, padx=18, pady=6)
        self.arbre.bind("<<TreeviewSelect>>", lambda e: self.selection())
        form = ttk.LabelFrame(self, text="  Tâche  ", padding=8)
        form.pack(fill="x", padx=18, pady=4)
        self.v_tr, self.v_ordre, self.v_nom = tk.StringVar(), tk.StringVar(), tk.StringVar()
        ttk.Label(form, text="Trimestre").grid(row=0, column=0, sticky="w")
        ttk.Entry(form, textvariable=self.v_tr, width=10).grid(row=1, column=0, padx=4)
        ttk.Label(form, text="Ordre").grid(row=0, column=1, sticky="w")
        ttk.Entry(form, textvariable=self.v_ordre, width=6).grid(row=1, column=1, padx=4)
        ttk.Label(form, text="Intitulé de la tâche").grid(row=0, column=2, sticky="w")
        ttk.Entry(form, textvariable=self.v_nom, width=70).grid(row=1, column=2, padx=4)
        ttk.Label(form, text="Début").grid(row=0, column=3, sticky="w")
        self.d_debut = ChampDate(form)
        self.d_debut.grid(row=1, column=3, padx=4)
        ttk.Label(form, text="Fin").grid(row=0, column=4, sticky="w")
        self.d_fin = ChampDate(form)
        self.d_fin.grid(row=1, column=4, padx=4)
        bas = ttk.Frame(self)
        bas.pack(fill="x", padx=18, pady=6)
        T.Bouton(bas, "+ Ajouter", self.ajouter, style="secondaire").pack(side="left")
        T.Bouton(bas, "✎ Modifier la tâche sélectionnée", self.modifier, style="secondaire").pack(side="left", padx=4)
        T.Bouton(bas, "✕ Supprimer", self.supprimer, style="danger").pack(side="left", padx=4)
        T.Bouton(bas, "💾 Enregistrer le fichier", self.enregistrer).pack(side="left", padx=12)
        T.Bouton(bas, "Générer le Gantt →", self.generer, style="secondaire").pack(side="right")
        self.df = pd.DataFrame(columns=COLS)
        self.charger()

    def charger(self):
        from modules.m10_gantt import lire_taches
        try:
            self.df = lire_taches(self.fichier.get()).reset_index(drop=True)
        except Exception as e:
            messagebox.showerror("Gantt", str(e))
            return
        trims = sorted(self.df["Timestre_a_debute"].dropna().unique())
        self.filtre.configure(values=["Tous"] + trims)
        self.filtre.set(self.app.profil.globaux.get("trimestre") if self.app.profil.globaux.get("trimestre") in trims else "Tous")
        self.remplir()

    def remplir(self):
        self.arbre.delete(*self.arbre.get_children())
        f = self.filtre.get()
        for i, r in self.df.iterrows():
            if f not in ("", "Tous") and r["Timestre_a_debute"] != f:
                continue
            fmt = lambda d: d.strftime("%d/%m/%Y") if pd.notna(d) else ""
            self.arbre.insert("", "end", iid=str(i), values=(i, r["Timestre_a_debute"], r["Ordre_exécution"],
                                                              r["Intitule_taches"], fmt(r["Date_debut_Tache"]),
                                                              fmt(r["Date_fin_tache"])))

    def selection(self):
        sel = self.arbre.selection()
        if sel:
            r = self.df.loc[int(sel[0])]
            self.v_tr.set(r["Timestre_a_debute"])
            self.v_ordre.set(str(r["Ordre_exécution"]))
            self.v_nom.set(r["Intitule_taches"])
            self.d_debut.set(r["Date_debut_Tache"].date() if pd.notna(r["Date_debut_Tache"]) else "")
            self.d_fin.set(r["Date_fin_tache"].date() if pd.notna(r["Date_fin_tache"]) else "")

    def _saisie(self):
        d0, d1 = self.d_debut.date(), self.d_fin.date()
        try:
            ordre = int(self.v_ordre.get())
        except ValueError:
            ordre = None
        if not self.v_tr.get() or not self.v_nom.get() or ordre is None or not d0 or not d1:
            messagebox.showerror("Tâche", "Renseignez le trimestre, l'ordre (entier), l'intitulé et les deux dates.")
            return None
        if d1 < d0:
            messagebox.showerror("Tâche", "La date de fin précède la date de début.")
            return None
        return {"Timestre_a_debute": self.v_tr.get().strip(), "Ordre_exécution": ordre,
                "Intitule_taches": self.v_nom.get().strip(), "Date_debut_Tache": pd.Timestamp(d0),
                "Date_fin_tache": pd.Timestamp(d1)}

    def ajouter(self):
        s = self._saisie()
        if s:
            self.df = pd.concat([self.df, pd.DataFrame([s])], ignore_index=True)
            self.remplir()

    def modifier(self):
        sel = self.arbre.selection()
        s = self._saisie()
        if sel and s:
            for k, v in s.items():
                self.df.at[int(sel[0]), k] = v
            self.remplir()

    def supprimer(self):
        sel = self.arbre.selection()
        if sel and messagebox.askyesno("Supprimer", f"Supprimer {len(sel)} tâche(s) ?"):
            self.df = self.df.drop(index=[int(i) for i in sel]).reset_index(drop=True)
            self.remplir()

    def enregistrer(self):
        from modules.m10_gantt import ecrire_taches
        try:
            ecrire_taches(self.fichier.get(), self.df)
            self.app.profil.globaux["fichier_gantt"] = self.fichier.get()
            self.app.profil.sauver()
            messagebox.showinfo("Gantt", "Fichier des tâches enregistré.")
        except PermissionError:
            messagebox.showerror("Gantt", "Impossible d'écrire : le fichier est peut-être ouvert dans Excel.")

    def generer(self):
        m = self.app.module_par_id("gantt")
        vue = self.app.ouvrir_module(m)
        vals = {"fichier_taches": self.fichier.get()}
        if self.filtre.get() not in ("", "Tous"):
            vals["trimestre"] = self.filtre.get()
        vue.charger_parametres(vals)


# ---------------------------------------------------------------------------
class ParametresGeneraux(Vue):
    def __init__(self, parent, app):
        super().__init__(parent, app)
        self.en_tete("Paramètres généraux", "Valeurs communes utilisées pour pré-remplir tous les modules. "
                                             "Elles sont enregistrées dans config/profil.json.")
        self.params = [
            Texte("utilisateur", "Nom de l'utilisateur", groupe="Utilisateur"),
            TrimestreP("trimestre", "Trimestre en cours", groupe="Collecte en cours"),
            DateP("lundi_semaine1", "Lundi de la semaine de référence 1", groupe="Collecte en cours"),
            Versions("versions_menage", "Versions de la base ménage / individuelle", groupe="Bases du trimestre",
                     obligatoire=False, fichier_attendu="ENEM_AAAATq.dta, membres.dta"),
            Versions("versions_denombrement", "Versions de la base de dénombrement", groupe="Bases du trimestre",
                     obligatoire=False, fichier_attendu="menage.dta, batiment.dta, ilot.dta"),
            Tableau("cohortes", "Cohortes de réinterrogation du trimestre", groupe="Bases du trimestre",
                    obligatoire=False,
                    colonnes=[Colonne("libelle", "Trimestre d'origine (ex. T2-2025)", "texte", 16),
                              Colonne("rgmen", "Valeur rgmen / Cohorte_vrai", "entier", 8),
                              Colonne("dossier", "Dossier des bases de ce trimestre", "dossier", 40)]),
            Dossier("dossier_sortie", "Dossier racine des résultats", groupe="Dossiers", doit_exister=False),
            Fichier("semaine_ref", "Fichier Semaine_ref.xlsx", groupe="Fichiers de référence",
                    types=[("Excel", "*.xlsx")]),
            Fichier("information_agent", "Fichier information_agent.xlsx", groupe="Fichiers de référence",
                    types=[("Excel", "*.xlsx")]),
            Fichier("fichier_gantt", "Fichier des tâches du Gantt", groupe="Fichiers de référence",
                    types=[("Excel", "*.xlsx")]),
            Dossier("dossier_codes_origine", "Dossier des codes d'origine (Stata / Python)", groupe="Dossiers",
                    obligatoire=False, doit_exister=False,
                    aide="Dossier contenant Code_gant, Code_status_emploi, … (consultation depuis le catalogue)."),
            Fichier("base_donnees", "Base de données de l'application (SQLite)", groupe="Dossiers",
                    sauvegarde=True, types=[("SQLite", "*.sqlite")],
                    aide="Pour partager l'historique entre collègues, placez-la dans un dossier commun. "
                         "Redémarrer l'application après modification."),
        ]
        defil = Defilant(self)
        defil.pack(fill="both", expand=True, padx=12)
        self.form = Formulaire(defil.interieur, self.params, app.profil.globaux)
        self.form.pack(fill="x")
        bas = ttk.Frame(self)
        bas.pack(fill="x", padx=18, pady=(8, 2))
        bas2 = ttk.Frame(self)
        bas2.pack(fill="x", padx=18, pady=(2, 8))
        T.Bouton(bas, "💾 Enregistrer", self.enregistrer).pack(side="left")
        T.Bouton(bas, "Lundi semaine 1 depuis Semaine_ref.xlsx (Automate_envoie)", self.lundi,
                 style="secondaire").pack(side="left", padx=6)
        T.Bouton(bas, "Appliquer ces valeurs à tous les modules", self.appliquer,
                 style="neutre").pack(side="left", padx=6)
        T.Bouton(bas2, "Exporter le profil (pour un collègue)…", self.exporter, style="neutre").pack(side="left")
        T.Bouton(bas2, "Importer un profil…", self.importer, style="neutre").pack(side="left", padx=6)

    def enregistrer(self, silencieux=False):
        vals, err = valider([p for p in self.params], self.form.valeurs())
        err = [e for e in err if "obligatoire" not in e]
        if err:
            messagebox.showerror("Paramètres", "\n".join(err))
            return False
        brut = self.form.valeurs()
        brut["cohortes"] = vals["cohortes"]
        self.app.profil.globaux.update(brut)
        self.app.profil.sauver()
        self.app.rafraichir_barre()
        if not silencieux:
            messagebox.showinfo("Paramètres", "Paramètres généraux enregistrés.")
        return True

    def lundi(self):
        try:
            tr = Trimestre.depuis(self.form.valeur("trimestre"))
        except ValueError as e:
            messagebox.showerror("Trimestre", str(e))
            return
        d = R.premier_lundi(self.form.valeur("semaine_ref"), tr.code)
        if d:
            self.form.definir({"lundi_semaine1": d})
        else:
            messagebox.showwarning("Semaine 1", f"{tr.code} absent de la feuille Automate_envoie.")

    def appliquer(self):
        if not self.enregistrer(silencieux=True):
            return
        if messagebox.askyesno("Appliquer", "Les paramètres des modules liés aux paramètres généraux (trimestre, "
                                            "bases, cohortes, fichiers, dossier de sortie) vont être remplacés. "
                                            "Continuer ?"):
            for m in self.app.modules:
                memo = self.app.profil.modules.get(m.id)
                if memo:
                    for p in m.parametres:
                        if p.globale:
                            memo.pop(p.cle, None)
            self.app.profil.sauver()
            self.app.fermer_vues_modules()
            messagebox.showinfo("Appliquer", "C'est fait : les modules utiliseront ces valeurs.")

    def exporter(self):
        f = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("Profil", "*.json")],
                                         initialfile="profil_ENEM.json")
        if f:
            self.enregistrer(silencieux=True)
            Path(f).write_text(self.app.profil.chemin.read_text(encoding="utf-8"), encoding="utf-8")

    def importer(self):
        f = filedialog.askopenfilename(filetypes=[("Profil", "*.json")])
        if f and messagebox.askyesno("Importer", "Remplacer le profil actuel par ce fichier ?"):
            self.app.profil.chemin.write_text(Path(f).read_text(encoding="utf-8"), encoding="utf-8")
            self.app.profil.charger()
            self.form.definir(self.app.profil.globaux)
            self.app.fermer_vues_modules()
            self.app.rafraichir_barre()


class APropos(Vue):
    def __init__(self, parent, app):
        super().__init__(parent, app)
        self.en_tete("Aide", "Utilisation de l'application")
        from enem_core import VERSION
        from modules import ERREURS_CHARGEMENT
        t = tk.Text(self, wrap="word", bg=T.BLANC, font=(T.POLICE, 10), padx=16, pady=12, relief="flat")
        t.pack(fill="both", expand=True, padx=18, pady=8)
        texte = f"""Application de suivi de la collecte ENEM – version {VERSION}

1. Paramètres généraux : indiquez le trimestre en cours, le lundi de la semaine de référence 1, les dossiers des versions des bases, les cohortes de réinterrogation et le dossier des résultats. Cliquez sur « Enregistrer ».

2. Tableau de bord : chaque carte indique si le point de suivi est à jour, à lancer ou en retard selon sa fréquence.

3. Module : vérifiez les paramètres (ils sont pré-remplis), puis cliquez sur « Lancer ». La barre de progression et le journal suivent le traitement ; « Arrêter » l'interrompt. À la fin, « Visualiser les résultats » ouvre les tableaux (tri, filtres par colonne au clic droit, recherche, export) et les graphiques.

4. Chaque exécution écrit dans un sous-dossier daté : <dossier des résultats>/<trimestre>/<équipe>/<module>/<date>. Rien n'est jamais écrit dans les bases brutes.

5. Historique : retrouver une exécution, ses paramètres, ses fichiers ; « Relancer avec ces paramètres ».

6. Alertes : liste des anomalies des derniers lancements (les alertes d'un lancement précédent du même module sont « remplacées »).

7. Évolution : courbes des indicateurs enregistrés à chaque lancement (ex. ZD réalisées par région).

8. Ajouter un nouveau contrôle : créer un fichier dans le dossier « modules » sur le modèle des modules existants ; il apparaît automatiquement.

Dossier de l'application : {RACINE_PROJET}
Profil : {app.profil.chemin}
Base de données : {app.stockage.chemin}
"""
        if ERREURS_CHARGEMENT:
            texte += "\nModules non chargés (erreurs) :\n" + "\n".join(f"- {k} :\n{v}" for k, v in ERREURS_CHARGEMENT.items())
        t.insert("1.0", texte)
        t.configure(state="disabled")
