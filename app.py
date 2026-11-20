from datetime import date
from functools import wraps
import sqlite3
from database import get_db_connection, init_db
from flask import Flask, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)
app.secret_key = "jobtrack-pro-secret-key"

# Ensure database tables exist when the app starts
init_db()


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to access your tracker.", "warning")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function


# --- AUTHENTICATION ROUTES ---

@app.route("/register", methods=["GET", "POST"])
def register():
    if "user_id" in session:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        confirm_password = request.form.get("confirm_password", "").strip()

        if not username or not password:
            flash("Username and password are required.", "danger")
            return redirect(url_for("register"))

        if password != confirm_password:
            flash("Passwords do not match.", "danger")
            return redirect(url_for("register"))

        password_hash = generate_password_hash(password)
        conn = get_db_connection()
        try:
            conn.execute(
                "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                (username, password_hash),
            )
            conn.commit()
        except sqlite3.IntegrityError:
            conn.close()
            flash("That username is already taken. Please choose another.", "danger")
            return redirect(url_for("register"))

        conn.close()
        flash("Account created! Please log in.", "success")
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if "user_id" in session:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        conn = get_db_connection()
        user = conn.execute(
            "SELECT * FROM users WHERE username = ?", (username,)
        ).fetchone()
        conn.close()

        if user and check_password_hash(user["password_hash"], password):
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            flash(f"Welcome back, {user['username']}!", "success")
            return redirect(url_for("dashboard"))

        flash("Invalid username or password.", "danger")
        return redirect(url_for("login"))

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("login"))


# --- MAIN APPLICATION ROUTES ---

@app.route("/")
@login_required
def dashboard():
    user_id = session["user_id"]
    conn = get_db_connection()

    # 1. Get counts grouped by status for this user
    rows = conn.execute(
        "SELECT status, COUNT(*) as count FROM applications WHERE user_id = ? GROUP BY status",
        (user_id,),
    ).fetchall()

    stats = {
        "Total": 0,
        "Applied": 0,
        "Assessment": 0,
        "Interview": 0,
        "Offer": 0,
        "Rejected": 0,
    }

    for row in rows:
        status_name = row["status"]
        count = row["count"]
        if status_name in stats:
            stats[status_name] = count
        stats["Total"] += count

    # 2. Fetch applications with a follow-up date (excluding Rejected/Offer)
    today_str = date.today().isoformat()
    follow_up_rows = conn.execute(
        """
        SELECT * FROM applications
        WHERE user_id = ?
          AND follow_up_date IS NOT NULL
          AND TRIM(follow_up_date) != ''
          AND status NOT IN ('Rejected', 'Offer')
        ORDER BY follow_up_date ASC
        """,
        (user_id,),
    ).fetchall()

    overdue_followups = []
    upcoming_followups = []

    for app_row in follow_up_rows:
        if app_row["follow_up_date"] < today_str:
            overdue_followups.append(app_row)
        else:
            upcoming_followups.append(app_row)

    # 3. Fetch 5 most recent applications for this user
    recent_apps = conn.execute(
        "SELECT * FROM applications WHERE user_id = ? ORDER BY date_applied DESC, id DESC LIMIT 5",
        (user_id,),
    ).fetchall()

    conn.close()

    return render_template(
        "dashboard.html",
        stats=stats,
        overdue_followups=overdue_followups,
        upcoming_followups=upcoming_followups,
        recent_apps=recent_apps,
        today_str=today_str,
    )


@app.route("/applications")
@login_required
def applications():
    user_id = session["user_id"]
    search_query = request.args.get("search", "").strip()
    status_filter = request.args.get("status", "").strip()

    query = "SELECT * FROM applications WHERE user_id = ?"
    params = [user_id]

    if search_query:
        query += " AND (company LIKE ? OR role LIKE ?)"
        like_term = f"%{search_query}%"
        params.extend([like_term, like_term])

    if status_filter and status_filter != "All":
        query += " AND status = ?"
        params.append(status_filter)

    query += " ORDER BY date_applied DESC, id DESC"

    conn = get_db_connection()
    apps = conn.execute(query, params).fetchall()
    conn.close()

    return render_template(
        "applications.html",
        applications=apps,
        search_query=search_query,
        status_filter=status_filter,
    )


@app.route("/add", methods=["POST"])
@login_required
def add_application():
    user_id = session["user_id"]
    company = request.form.get("company", "").strip()
    role = request.form.get("role", "").strip()
    job_description = request.form.get("job_description", "").strip()
    job_link = request.form.get("job_link", "").strip()
    date_applied = request.form.get("date_applied", "").strip()
    status = request.form.get("status", "Applied").strip()
    location = request.form.get("location", "").strip()
    follow_up_date = request.form.get("follow_up_date", "").strip()
    notes = request.form.get("notes", "").strip()

    if not company or not role or not date_applied:
        flash("Company, Role, and Date Applied are required.", "danger")
        return redirect(url_for("applications"))

    conn = get_db_connection()
    conn.execute(
        """
        INSERT INTO applications (
            user_id, company, role, job_description, job_link,
            date_applied, status, location, follow_up_date, notes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            user_id,
            company,
            role,
            job_description,
            job_link,
            date_applied,
            status,
            location,
            follow_up_date,
            notes,
        ),
    )
    conn.commit()
    conn.close()

    flash(f"Added application for {role} at {company}!", "success")
    return redirect(url_for("applications"))


@app.route("/edit/<int:app_id>", methods=["POST"])
@login_required
def edit_application(app_id):
    user_id = session["user_id"]
    company = request.form.get("company", "").strip()
    role = request.form.get("role", "").strip()
    job_description = request.form.get("job_description", "").strip()
    job_link = request.form.get("job_link", "").strip()
    date_applied = request.form.get("date_applied", "").strip()
    status = request.form.get("status", "Applied").strip()
    location = request.form.get("location", "").strip()
    follow_up_date = request.form.get("follow_up_date", "").strip()
    notes = request.form.get("notes", "").strip()

    if not company or not role or not date_applied:
        flash("Company, Role, and Date Applied are required.", "danger")
        return redirect(url_for("applications"))

    conn = get_db_connection()
    conn.execute(
        """
        UPDATE applications
        SET company = ?, role = ?, job_description = ?, job_link = ?,
            date_applied = ?, status = ?, location = ?, follow_up_date = ?, notes = ?
        WHERE id = ? AND user_id = ?
        """,
        (
            company,
            role,
            job_description,
            job_link,
            date_applied,
            status,
            location,
            follow_up_date,
            notes,
            app_id,
            user_id,
        ),
    )
    conn.commit()
    conn.close()

    flash(f"Updated application for {role} at {company}.", "info")
    return redirect(url_for("applications"))


@app.route("/delete/<int:app_id>", methods=["POST"])
@login_required
def delete_application(app_id):
    user_id = session["user_id"]
    conn = get_db_connection()
    conn.execute(
        "DELETE FROM applications WHERE id = ? AND user_id = ?", (app_id, user_id)
    )
    conn.commit()
    conn.close()

    flash("Application deleted successfully.", "warning")
    return redirect(url_for("applications"))


if __name__ == "__main__":
    app.run(debug=True)