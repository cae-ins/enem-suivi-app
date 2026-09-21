"""Point d'entrée : python main.py"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))


def verifier_dependances():
    manquants = []
    for nom in ("pandas", "openpyxl", "matplotlib"):
        try:
            __import__(nom)
        except ImportError:
            manquants.append(nom)
    if manquants:
        message = ("Bibliothèques manquantes : " + ", ".join(manquants) +
                   "\n\nOuvrez l'invite de commandes dans le dossier de l'application et tapez :\n"
                   "    python -m pip install -r requirements.txt")
        try:
            import tkinter.messagebox as mb
            mb.showerror("Installation incomplète", message)
        except Exception:
            print(message)
        sys.exit(1)


if __name__ == "__main__":
    verifier_dependances()
    try:
        from app.application import Application
        Application().mainloop()
    except Exception:
        import traceback
        from datetime import datetime
        trace = traceback.format_exc()
        journal = Path(__file__).resolve().parent / "donnees_app" / "erreurs.log"
        journal.parent.mkdir(parents=True, exist_ok=True)
        with journal.open("a", encoding="utf-8") as f:
            f.write(f"\n--- {datetime.now():%Y-%m-%d %H:%M:%S} ---\n{trace}")
        try:
            import tkinter as tk
            import tkinter.messagebox as mb
            r = tk.Tk()
            r.withdraw()
            mb.showerror("Erreur au démarrage", f"{trace[-1500:]}\n\nDétail enregistré dans :\n{journal}")
        except Exception:
            print(trace)
        sys.exit(1)
