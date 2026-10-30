"""
Académie du club — serveur de formation.
Lancement local : python app.py   (puis ouvrir http://localhost:5000)
Variables d'environnement (facultatives) :
  ADMIN_CODE       code d'accès du responsable (par défaut : changez-moi)
  SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, NOTIF_TO
                   pour recevoir un e-mail à chaque évaluation
"""
import csv, io, json, os, smtplib, sqlite3, logging
from datetime import datetime
from email.message import EmailMessage
from flask import Flask, jsonify, request, Response, render_template, g, send_from_directory, send_file
from werkzeug.security import generate_password_hash, check_password_hash

BASE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE, "data", "academie.db")
ANNEE_NOTE_MIN = 10.0
ADMIN_CODE = os.environ.get("ADMIN_CODE", "changez-moi")
WHATSAPP_URL = os.environ.get("WHATSAPP_URL", "https://chat.whatsapp.com/KiJqW3xVPU4FGlX5WXoSbt")

app = Flask(__name__)

@app.context_processor
def contexte_global():
    return {"WHATSAPP_URL": WHATSAPP_URL, "CLUB": "Club STIM", "LYCEE": "Lycée Mixte 1 de Yamoussoukro"}
log = logging.getLogger("academie")

# ---------------- contenu ----------------
with open(os.path.join(BASE, "content.json"), encoding="utf-8") as f:
    DOMAINES = json.load(f)
DOM = {d["id"]: d for d in DOMAINES}
MODULES = {m["id"]: dict(m, domaine=d["id"]) for d in DOMAINES for m in d["modules"]}
BASE_IDS = [m["id"] for m in DOM["bases"]["modules"]]

# ---------------- base de données ----------------
def db():
    if "db" not in g:
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def fermer(_):
    d = g.pop("db", None)
    if d: d.close()

def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    c = sqlite3.connect(DB_PATH)
    c.executescript("""
      CREATE TABLE IF NOT EXISTS membres(
        id INTEGER PRIMARY KEY AUTOINCREMENT, nom TEXT UNIQUE NOT NULL,
        pin_hash TEXT NOT NULL, domaines TEXT NOT NULL DEFAULT '[]', cree TEXT NOT NULL);
      CREATE TABLE IF NOT EXISTS tentatives(
        id INTEGER PRIMARY KEY AUTOINCREMENT, membre_id INTEGER NOT NULL,
        module_id TEXT NOT NULL, domaine TEXT NOT NULL, note REAL NOT NULL,
        bonnes INTEGER NOT NULL, total INTEGER NOT NULL, date TEXT NOT NULL);
      CREATE INDEX IF NOT EXISTS idx_t_membre ON tentatives(membre_id);
    """)
    c.commit(); c.close()

init_db()

# ---------------- logique métier ----------------
def meilleurs(membre_id):
    """Meilleure note par module pour un membre, et nombre de tentatives."""
    rows = db().execute("SELECT module_id, MAX(note) AS best, COUNT(*) AS n FROM tentatives WHERE membre_id=? GROUP BY module_id", (membre_id,)).fetchall()
    return {r["module_id"]: {"meilleur": r["best"], "tentatives": r["n"]} for r in rows}

def moyenne(domaine_id, res):
    ids = [m["id"] for m in DOM[domaine_id]["modules"]]
    notes = [res[i]["meilleur"] for i in ids if i in res]
    return round(sum(notes) / len(notes), 2) if notes else None

def resume(membre):
    res = meilleurs(membre["id"])
    moyennes = {d["id"]: moyenne(d["id"], res) for d in DOMAINES}
    bases_complet = all(i in res for i in BASE_IDS)
    bases_ok = bases_complet and moyennes["bases"] is not None and moyennes["bases"] >= ANNEE_NOTE_MIN
    choisis = json.loads(membre["domaines"])

    def accessible(dom_id):
        if dom_id == "bases": return True
        if not bases_complet: return False          # socle obligatoire d'abord
        if DOM[dom_id].get("gate"): return bases_ok  # informatique : moyenne >= 10 aux bases
        return True

    # placement : domaine spécialisé choisi, accessible, avec la meilleure moyenne
    candidats = [d for d in choisis if d != "bases" and accessible(d) and moyennes.get(d) is not None]
    placement = max(candidats, key=lambda d: moyennes[d]) if candidats else None
    alertes = [d for d in choisis if DOM.get(d, {}).get("gate") and not bases_ok]
    total = len(MODULES); faits = len(res)
    return {
        "nom": membre["nom"], "domaines": choisis, "moyennes": moyennes,
        "bases_complet": bases_complet, "bases_ok": bases_ok,
        "accessibles": {d["id"]: accessible(d["id"]) for d in DOMAINES},
        "placement": placement, "alertes": alertes,
        "modules_faits": faits, "modules_total": total,
        "resultats": res,
    }

def notifier(membre, module, note, bonnes, total):
    host = os.environ.get("SMTP_HOST"); dest = os.environ.get("NOTIF_TO")
    if not host or not dest: return
    try:
        msg = EmailMessage()
        msg["Subject"] = f"[Académie] {membre['nom']} — {note:.1f}/20 — {module['titre']}"
        msg["From"] = os.environ.get("SMTP_USER", dest); msg["To"] = dest
        msg.set_content(f"{membre['nom']} vient de terminer « {module['titre']} »\n"
                        f"Score : {note:.1f}/20 ({bonnes}/{total} bonnes réponses)\n"
                        f"Date : {datetime.now():%d/%m/%Y %H:%M}")
        with smtplib.SMTP(host, int(os.environ.get("SMTP_PORT", 587)), timeout=10) as s:
            s.starttls()
            if os.environ.get("SMTP_USER"):
                s.login(os.environ["SMTP_USER"], os.environ.get("SMTP_PASSWORD", ""))
            s.send_message(msg)
    except Exception as e:
        log.warning("Notification e-mail non envoyée : %s", e)

def authentifier(data):
    nom = (data.get("nom") or "").strip()
    pin = str(data.get("pin") or "")
    m = db().execute("SELECT * FROM membres WHERE nom=?", (nom,)).fetchone()
    if not m or not check_password_hash(m["pin_hash"], pin):
        return None
    return m

def verifier_admin():
    return request.headers.get("X-Admin-Code") == ADMIN_CODE

# ---------------- pages ----------------
@app.route("/")
def accueil():
    return render_template("home.html")

@app.route("/formation")
def formation():
    return render_template("index.html")

@app.route("/bureau")
def bureau():
    with open(os.path.join(BASE, "bureau.json"), encoding="utf-8") as f:
        data = json.load(f)
    groupes = {}
    for m in data["membres"]:
        groupes.setdefault(m["groupe"], []).append(m)
    return render_template("bureau.html", data=data, groupes=groupes)

@app.route("/telecharger")
def telecharger():
    return render_template("telecharger.html")

@app.route("/guide.pdf")
def guide_pdf():
    return send_from_directory(os.path.join(BASE, "static", "guide"), "Guide_Bases_Numerique_Club_STIM.pdf",
                               as_attachment=True, download_name="Guide_Bases_Numerique_Club_STIM.pdf")

@app.route("/admin")
def admin_page():
    return render_template("admin.html")

# ---------------- API membres ----------------
@app.get("/api/contenu")
def api_contenu():
    # aucune bonne réponse n'est envoyée au navigateur : la correction est faite par le serveur
    out = []
    for d in DOMAINES:
        out.append({
            "id": d["id"], "nom": d["nom"], "ico": d["ico"], "c": d["c"], "desc": d["desc"],
            "gate": d.get("gate", False), "obligatoire": d.get("obligatoire", False),
            "modules": [{"id": m["id"], "titre": m["titre"], "duree": m["duree"], "lecon": m["lecon"],
                         "exemple": m["exemple"], "ressources": m["ressources"],
                         "questions": [{"q": q["q"], "o": q["o"]} for q in m["quiz"]]}
                        for m in d["modules"]]})
    return jsonify(out)

@app.post("/api/inscription")
def api_inscription():
    data = request.get_json(force=True)
    nom = (data.get("nom") or "").strip()
    pin = str(data.get("pin") or "")
    domaines = [d for d in (data.get("domaines") or []) if d in DOM]
    if len(nom) < 2: return jsonify(erreur="Entre ton prénom et ton nom."), 400
    if len(pin) < 4: return jsonify(erreur="Le code personnel doit faire au moins 4 caractères."), 400
    if "bases" not in domaines: domaines.insert(0, "bases")
    existant = db().execute("SELECT * FROM membres WHERE nom=?", (nom,)).fetchone()
    if existant:
        if not check_password_hash(existant["pin_hash"], pin):
            return jsonify(erreur="Ce nom existe déjà avec un autre code personnel."), 403
        db().execute("UPDATE membres SET domaines=? WHERE id=?", (json.dumps(domaines), existant["id"]))
        db().commit()
        return jsonify(resume(db().execute("SELECT * FROM membres WHERE id=?", (existant["id"],)).fetchone()))
    db().execute("INSERT INTO membres(nom,pin_hash,domaines,cree) VALUES(?,?,?,?)",
                 (nom, generate_password_hash(pin), json.dumps(domaines), datetime.now().isoformat(timespec="seconds")))
    db().commit()
    return jsonify(resume(db().execute("SELECT * FROM membres WHERE nom=?", (nom,)).fetchone()))

@app.post("/api/connexion")
def api_connexion():
    m = authentifier(request.get_json(force=True))
    if not m: return jsonify(erreur="Nom ou code personnel incorrect."), 401
    return jsonify(resume(m))

@app.post("/api/domaines")
def api_domaines():
    data = request.get_json(force=True)
    m = authentifier(data)
    if not m: return jsonify(erreur="Nom ou code personnel incorrect."), 401
    domaines = [d for d in (data.get("domaines") or []) if d in DOM]
    if "bases" not in domaines: domaines.insert(0, "bases")
    db().execute("UPDATE membres SET domaines=? WHERE id=?", (json.dumps(domaines), m["id"])); db().commit()
    return jsonify(resume(db().execute("SELECT * FROM membres WHERE id=?", (m["id"],)).fetchone()))

@app.post("/api/modules/<module_id>/soumettre")
def api_soumettre(module_id):
    data = request.get_json(force=True)
    m = authentifier(data)
    if not m: return jsonify(erreur="Nom ou code personnel incorrect."), 401
    mod = MODULES.get(module_id)
    if not mod: return jsonify(erreur="Module inconnu."), 404
    r = resume(m)
    if not r["accessibles"].get(mod["domaine"]):
        return jsonify(erreur="Ce domaine n'est pas encore accessible. Termine d'abord les modules Bases (et une moyenne de 10/20 pour l'informatique)."), 403
    reps = data.get("reponses") or []
    if len(reps) != len(mod["quiz"]):
        return jsonify(erreur="Réponds à toutes les questions."), 400
    bonnes = sum(1 for q, rep in zip(mod["quiz"], reps) if rep == q["r"])
    total = len(mod["quiz"]); note = round(bonnes / total * 20, 1)
    db().execute("INSERT INTO tentatives(membre_id,module_id,domaine,note,bonnes,total,date) VALUES(?,?,?,?,?,?,?)",
                 (m["id"], module_id, mod["domaine"], note, bonnes, total, datetime.now().isoformat(timespec="seconds")))
    db().commit()
    notifier(m, mod, note, bonnes, total)
    corrections = [{"bonne": rep == q["r"], "reponse": q["o"][q["r"]], "explication": q["e"]}
                   for q, rep in zip(mod["quiz"], reps)]
    return jsonify(note=note, bonnes=bonnes, total=total, corrections=corrections, bilan=resume(db().execute("SELECT * FROM membres WHERE id=?", (m["id"],)).fetchone()))

@app.get("/api/classement")
def api_classement():
    """Classement visible par tous les membres : transparence des scores par domaine."""
    rows = db().execute("SELECT * FROM membres").fetchall()
    resumes = [resume(r) for r in rows]
    out = {}
    for d in DOMAINES:
        liste = [{"nom": r["nom"], "moyenne": r["moyennes"][d["id"]], "modules": sum(1 for m in d["modules"] if m["id"] in r["resultats"])}
                 for r in resumes if r["moyennes"][d["id"]] is not None]
        out[d["id"]] = {"nom": d["nom"], "ico": d["ico"], "classement": sorted(liste, key=lambda x: -x["moyenne"])}
    return jsonify(out)

# ---------------- API responsable ----------------
def exiger_admin():
    if not verifier_admin():
        return jsonify(erreur="Code responsable incorrect."), 401
    return None

@app.get("/api/admin/membres")
def admin_membres():
    if (e := exiger_admin()): return e
    rows = db().execute("SELECT * FROM membres ORDER BY nom").fetchall()
    return jsonify([resume(r) | {"cree": r["cree"]} for r in rows])

@app.get("/api/admin/tentatives")
def admin_tentatives():
    if (e := exiger_admin()): return e
    limite = min(int(request.args.get("limite", 200)), 1000)
    rows = db().execute("""SELECT t.*, m.nom FROM tentatives t JOIN membres m ON m.id=t.membre_id
                           ORDER BY t.id DESC LIMIT ?""", (limite,)).fetchall()
    return jsonify([{"nom": r["nom"], "module": MODULES[r["module_id"]]["titre"], "domaine": DOM[r["domaine"]]["nom"],
                     "note": r["note"], "bonnes": r["bonnes"], "total": r["total"], "date": r["date"]} for r in rows])

@app.get("/api/admin/export.csv")
def admin_export():
    if not verifier_admin():
        return Response("Code responsable incorrect.", status=401)
    rows = db().execute("""SELECT m.nom, t.module_id, t.domaine, t.note, t.bonnes, t.total, t.date
                           FROM tentatives t JOIN membres m ON m.id=t.membre_id ORDER BY m.nom, t.date""").fetchall()
    buf = io.StringIO(); w = csv.writer(buf, delimiter=";")
    w.writerow(["Membre", "Module", "Domaine", "Note /20", "Bonnes", "Total", "Date"])
    for r in rows:
        w.writerow([r["nom"], MODULES[r["module_id"]]["titre"], DOM[r["domaine"]]["nom"],
                    str(r["note"]).replace(".", ","), r["bonnes"], r["total"], r["date"]])
    return Response("\ufeff" + buf.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=notes_academie.csv"})

@app.get("/api/admin/sauvegarde")
def admin_sauvegarde():
    """Télécharge une copie de la base de données (à faire régulièrement)."""
    if (e := exiger_admin()): return e
    db().commit()
    return send_file(DB_PATH, as_attachment=True, download_name="academie_sauvegarde.db")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)
