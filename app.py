from flask import Flask, render_template, request, redirect, url_for, flash, session
import os
import pandas as pd
import numpy as np

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret-change-me")

# ---------- Utility helpers ----------
def project_root() -> str:
    return os.path.dirname(os.path.abspath(__file__))

def data_dir() -> str:
    return os.path.join(project_root(), "data")

def data_path(filename: str) -> str:
    return os.path.join(data_dir(), filename)

def load_csv_safe(filename: str, dtype_map=None) -> pd.DataFrame:
    path = data_path(filename)
    try:
        if dtype_map is None:
            return pd.read_csv(path)
        return pd.read_csv(path, dtype=dtype_map)
    except FileNotFoundError:
        flash(f"Missing data file: {filename}", "error")
        return pd.DataFrame()
    except Exception as exc:
        flash(f"Error loading {filename}: {exc}", "error")
        return pd.DataFrame()

def save_csv_safe(df: pd.DataFrame, filename: str) -> bool:
    path = data_path(filename)
    try:
        df.to_csv(path, index=False)
        return True
    except Exception as exc:
        flash(f"Error saving {filename}: {exc}", "error")
        return False

def get_pincodes() -> list:
    libs = load_csv_safe("libraries.csv", dtype_map={"library_id": int, "pincode": str})
    if libs.empty:
        return []
    libs["pincode"] = libs["pincode"].astype(str)
    return sorted(libs["pincode"].dropna().unique().tolist())

def load_books_and_libs() -> pd.DataFrame:
    books = load_csv_safe("books.csv", dtype_map={"book_id": int, "library_id": int})
    libs = load_csv_safe("libraries.csv", dtype_map={"library_id": int, "pincode": str})
    if books.empty or libs.empty:
        return pd.DataFrame()
    libs["pincode"] = libs["pincode"].astype(str)
    merged = books.merge(libs, on="library_id", how="left")
    return merged

# ---------- Auth protection ----------
@app.before_request
def protect_routes():
    if request.endpoint in {"dashboard"}:
        if not session.get("username"):
            flash("Please log in to continue.", "error")
            return redirect(url_for("login"))

# ---------- Routes ----------
@app.route("/")
def home():
    return render_template("home.html", pincodes=get_pincodes())

@app.route("/search", methods=["POST"])
def search():
    title_term = (request.form.get("title") or "").strip()
    author_term = (request.form.get("author") or "").strip()
    pincode = (request.form.get("pincode") or "").strip()

    if not title_term or not pincode:
        flash("Please provide a title and pincode.", "error")
        return redirect(url_for("home"))

    df = load_books_and_libs()
    if df.empty:
        flash("No data available.", "error")
        return redirect(url_for("home"))

    df = df[df["pincode"].astype(str) == pincode]
    if df.empty:
        flash("No books found.", "warning")
        return redirect(url_for("home"))

    titles = df["title"].fillna("").to_numpy(dtype=str)
    authors = df["author"].fillna("").to_numpy(dtype=str)

    titles_lower = np.char.lower(titles)
    title_mask = np.char.find(titles_lower, title_term.lower()) != -1

    if author_term:
        authors_lower = np.char.lower(authors)
        author_mask = np.char.find(authors_lower, author_term.lower()) != -1
    else:
        author_mask = np.ones_like(title_mask, dtype=bool)

    mask = np.logical_and(title_mask, author_mask)
    filtered = df[mask]

    if filtered.empty:
        flash("No books found.", "warning")
        return redirect(url_for("home"))

    results = filtered[["title", "author", "name", "pincode", "contact"]].copy()
    results = results.drop_duplicates()

    return render_template("search_results.html", results=results.to_dict(orient="records"))

@app.route("/all_books")
def all_books():
    df = load_books_and_libs()
    if df.empty:
        flash("No data available.", "error")
        return redirect(url_for("home"))

    df_grouped = (
        df.assign(location=lambda d: d["name"].astype(str) + " (" + d["pincode"].astype(str) + ")")
    )
    grouped = df_grouped.groupby(["title", "author"], as_index=False).agg({"location": lambda s: sorted(set(s))})

    sizes = df_grouped.groupby(["title", "author"]).size().to_numpy()
    _ = np.bincount(sizes)

    titles = []
    for _, row in grouped.iterrows():
        titles.append({
            "title": row["title"],
            "author": row["author"],
            "locations": ", ".join(row["location"]) if isinstance(row["location"], list) else str(row["location"])
        })

    return render_template("all_books.html", titles=titles)

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("librarian_login.html")

    username = (request.form.get("username") or "").strip()
    password = (request.form.get("password") or "").strip()
    if not username or not password:
        flash("Please enter username and password.", "error")
        return redirect(url_for("login"))

    df = load_csv_safe("librarians.csv")
    if df.empty:
        flash("No librarian data available.", "error")
        return redirect(url_for("login"))

    match = df[df["username"].astype(str) == username]
    if match.empty:
        flash("Invalid credentials.", "error")
        return redirect(url_for("login"))

    stored_pw = str(match.iloc[0]["password"])
    lib_id = int(match.iloc[0]["library_id"]) if not pd.isna(match.iloc[0]["library_id"]) else None

    if stored_pw != password:
        flash("Invalid credentials.", "error")
        return redirect(url_for("login"))

    session["username"] = username
    session["library_id"] = lib_id
    flash("Logged in.", "success")
    return redirect(url_for("dashboard", library_id=lib_id))

@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out.", "success")
    return redirect(url_for("home"))

@app.route("/dashboard/<int:library_id>", methods=["GET", "POST"])
def dashboard(library_id: int):
    session_lib = session.get("library_id")
    if session_lib is None or int(session_lib) != int(library_id):
        flash("Unauthorized access to library dashboard.", "error")
        return redirect(url_for("home"))

    books_df = load_csv_safe("books.csv", dtype_map={"book_id": int, "library_id": int})
    if request.method == "POST":
        action = request.form.get("action")
        if books_df.empty:
            books_df = pd.DataFrame(columns=["book_id", "title", "author", "library_id"])

        if action == "add":
            title = (request.form.get("title") or "").strip()
            author = (request.form.get("author") or "").strip()
            if not title or not author:
                flash("Title and author are required.", "error")
                return redirect(url_for("dashboard", library_id=library_id))

            new_id = int(books_df["book_id"].max()) + 1 if not books_df.empty else 1
            new_row = {"book_id": new_id, "title": title, "author": author, "library_id": int(library_id)}
            books_df = pd.concat([books_df, pd.DataFrame([new_row])], ignore_index=True)
            if save_csv_safe(books_df, "books.csv"):
                flash("Book added.", "success")
            return redirect(url_for("dashboard", library_id=library_id))

        if action == "edit":
            try:
                book_id = int(request.form.get("book_id"))
            except Exception:
                flash("Invalid book id.", "error")
                return redirect(url_for("dashboard", library_id=library_id))
            title = (request.form.get("title") or "").strip()
            author = (request.form.get("author") or "").strip()
            if not title or not author:
                flash("Title and author are required.", "error")
                return redirect(url_for("dashboard", library_id=library_id))
            mask = books_df["book_id"] == book_id
            if not mask.any():
                flash("Book not found.", "error")
                return redirect(url_for("dashboard", library_id=library_id))
            books_df.loc[mask, ["title", "author"]] = [title, author]
            if save_csv_safe(books_df, "books.csv"):
                flash("Book updated.", "success")
            return redirect(url_for("dashboard", library_id=library_id))

        if action == "delete":
            try:
                book_id = int(request.form.get("book_id"))
            except Exception:
                flash("Invalid book id.", "error")
                return redirect(url_for("dashboard", library_id=library_id))
            before = len(books_df)
            books_df = books_df[books_df["book_id"] != book_id]
            if len(books_df) == before:
                flash("Book not found.", "error")
            else:
                if save_csv_safe(books_df, "books.csv"):
                    flash("Book deleted.", "success")
            return redirect(url_for("dashboard", library_id=library_id))

    my_books_df = books_df[books_df["library_id"] == int(library_id)] if not books_df.empty else pd.DataFrame(columns=["book_id","title","author","library_id"])
    my_books = my_books_df.sort_values("book_id").to_dict(orient="records")

    shared = load_books_and_libs()
    shared_view = [] if shared.empty else shared[["title", "author", "name", "pincode"]].copy().sort_values(["title", "name"]).to_dict(orient="records")

    return render_template(
        "librarian_dashboard.html",
        library_id=library_id,
        my_books=my_books,
        shared_view=shared_view,
    )

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0")