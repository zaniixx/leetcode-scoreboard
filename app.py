from flask import Flask, render_template, request, redirect, url_for
import sqlite3
from update_DB import runDB

app = Flask(__name__)

# Database connection function
def get_db_connection():
    conn = sqlite3.connect('leaderboard.db')
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/')
def index():
    conn = get_db_connection()
    users_query = """
    SELECT username, avatar, COUNT(submissions.id) as submission_count
    FROM users
    LEFT JOIN submissions ON users.id = submissions.user_id
    GROUP BY users.username
    ORDER BY submission_count DESC
    """
    users = conn.execute(users_query).fetchall()
    conn.close()
    return render_template('index.html', users=users)

@app.route('/user/<username>')
def user_profile(username):
    conn = get_db_connection()
    
    # Get user_id for the given username
    user_query = "SELECT id, avatar FROM users WHERE username = ?"
    user = conn.execute(user_query, (username,)).fetchone()
    
    if user is None:
        conn.close()
        return "User not found", 404

    user_id = user['id']
    avatar = user['avatar']
    
    # Get submissions for the user_id
    user_submissions_query = """
    SELECT title, timestamp, lang
    FROM submissions
    WHERE user_id = ?
    """
    submissions = conn.execute(user_submissions_query, (user_id,)).fetchall()
    conn.close()
    return render_template('user_profile.html', username=username, avatar=avatar, submissions=submissions)

@app.route('/add_user', methods=['GET', 'POST'])
def add_user():
    if request.method == 'POST':
        username = request.form['username']
        if username:
            runDB(username)
            return redirect(url_for('index'))
    return render_template('add_user.html')

if __name__ == "__main__":
    app.run(debug=True)
