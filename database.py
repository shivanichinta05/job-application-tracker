import sqlite3

DB_NAME = "tracker.db"


def get_db_connection():
    """Creates and returns a connection to the SQLite database."""
    conn = sqlite3.connect(DB_NAME)
    # Allows accessing columns by name (e.g., row['company']) instead of index
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Initializes the database and creates the applications table if it doesn't exist."""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company TEXT NOT NULL,
            role TEXT NOT NULL,
            job_description TEXT,
            job_link TEXT,
            date_applied TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Applied',
            location TEXT,
            follow_up_date TEXT,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()
    print("Database initialized successfully!")


if __name__ == "__main__":
    init_db()