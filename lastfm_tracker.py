import sqlite3

LASTFM_API_KEY = "" # Removed

conn = sqlite3.connect('lastfm.db')
cursor = conn.cursor()

cursor.execute('''
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT NOT NULL
)
''')
conn.commit()

# Set lastfm username
def set_lastfm(user_id, username):
    # Check if user exists. If so, update username. If not, insert new user.
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    if cursor.fetchone():
        cursor.execute("UPDATE users SET username = ? WHERE user_id = ?", (username, user_id))
    else:
        cursor.execute("INSERT INTO users (user_id, username) VALUES (?, ?)", (user_id, username))
    conn.commit()

    return f"Last.fm username set to: {username}"

def get_lastfm(user_id):
    cursor.execute("SELECT username FROM users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    if result:
        return result[0]
    else:
        return "Last.fm username not set."
    

