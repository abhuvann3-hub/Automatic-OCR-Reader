import os
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
from extract_invoice_assets import run_ocr

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", os.urandom(24))

UPLOAD_FOLDER = "uploads"
OUTPUT_FOLDER = "output"
DATABASE = "users.db"

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

ALLOWED_EXTENSIONS = {"pdf"}


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


# -------------------- DATABASE --------------------

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT    UNIQUE NOT NULL,
            password TEXT    NOT NULL
        )
    """)
    conn.commit()
    conn.close()


init_db()


# -------------------- REGISTER --------------------

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        if not username or not password:
            flash("Please fill in all fields.", "error")
            return redirect(url_for("register"))

        if len(password) < 6:
            flash("Password must be at least 6 characters.", "error")
            return redirect(url_for("register"))

        hashed = generate_password_hash(password)
        try:
            conn = get_db()
            conn.execute(
                "INSERT INTO users (username, password) VALUES (?, ?)",
                (username, hashed)
            )
            conn.commit()
            flash("Registration successful! Please log in.", "success")
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            flash("Username already exists.", "error")
        finally:
            conn.close()

    return render_template("register.html")


# -------------------- LOGIN --------------------

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        conn = get_db()
        user = conn.execute(
            "SELECT * FROM users WHERE username = ?", (username,)
        ).fetchone()
        conn.close()

        if user and check_password_hash(user["password"], password):
            session["user"] = username
            flash("Welcome back!", "success")
            return redirect(url_for("index"))
        else:
            flash("Invalid username or password.", "error")

    return render_template("login.html")


# -------------------- LOGOUT --------------------

@app.route("/logout")
def logout():
    session.pop("user", None)
    flash("Logged out successfully.", "success")
    return redirect(url_for("login"))


# -------------------- HOME (UPLOAD + OCR) --------------------

@app.route("/", methods=["GET", "POST"])
def index():
    if "user" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":
        if "file" not in request.files:
            flash("No file selected.", "error")
            return redirect(request.url)

        file = request.files["file"]

        if file.filename == "":
            flash("No file selected.", "error")
            return redirect(request.url)

        if not allowed_file(file.filename):
            flash("Only PDF files are allowed.", "error")
            return redirect(request.url)

        filename = file.filename.replace(" ", "_")
        filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        file.save(filepath)

        try:
            run_ocr(filename)
            flash("File processed successfully! Check the output folder.", "success")
        except Exception as e:
            flash(f"Error processing file: {str(e)}", "error")

        return redirect(url_for("index"))

    return render_template("index.html")


# -------------------- RUN --------------------

if __name__ == "__main__":
    debug_mode = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    app.run(debug=debug_mode)
