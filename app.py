from datetime import date
from database import get_db_connection, init_db
from flask import Flask, flash, redirect, render_template, request, url_for

app = Flask(__name__)
app.secret_key = "jobtrack-pro-secret-key"

# Ensure the database table exists when the app starts
init_db()


@app.route("/")
def dashboard():
    conn = get_db_connection()

    # 1. Get counts grouped by status
    rows = conn.execute(
        "SELECT status, COUNT(*) as count FROM applications GROUP BY status"
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
        WHERE follow_up_date IS NOT NULL
          AND TRIM(follow_up_date) != ''
          AND status NOT IN ('Rejected', 'Offer')
        ORDER BY follow_up_date ASC
        """
    ).fetchall()

    overdue_followups = []
    upcoming_followups = []

    for app_row in follow_up_rows:
        if app_row["follow_up_date"] < today_str:
            overdue_followups.append(app_row)
        else:
            upcoming_followups.append(app_row)

    # 3. Fetch 5 most recent applications
    recent_apps = conn.execute(
        "SELECT * FROM applications ORDER BY date_applied DESC, id DESC LIMIT 5"
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
def applications():
    search_query = request.args.get("search", "").strip()
    status_filter = request.args.get("status", "").strip()

    query = "SELECT * FROM applications WHERE 1=1"
    params = []

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
def add_application():
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
            company, role, job_description, job_link,
            date_applied, status, location, follow_up_date, notes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
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
        ),
    )
    conn.commit()
    conn.close()

    flash(f"Added application for {role} at {company}!", "success")
    return redirect(url_for("applications"))


@app.route("/edit/<int:app_id>", methods=["POST"])
def edit_application(app_id):
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
        WHERE id = ?
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
        ),
    )
    conn.commit()
    conn.close()

    flash(f"Updated application for {role} at {company}.", "info")
    return redirect(url_for("applications"))


@app.route("/delete/<int:app_id>", methods=["POST"])
def delete_application(app_id):
    conn = get_db_connection()
    conn.execute("DELETE FROM applications WHERE id = ?", (app_id,))
    conn.commit()
    conn.close()

    flash("Application deleted successfully.", "warning")
    return redirect(url_for("applications"))


if __name__ == "__main__":
    app.run(debug=True)