import os
from flask import Flask, render_template, request, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
import sqlite3
import configparser
from datetime import datetime
import requests

app = Flask(__name__)
app.secret_key= "key"
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///app.db')
db = SQLAlchemy(app)

# Read config
config = configparser.ConfigParser()
config.read('secrets.ini')

# Configuration from the secrets file
db_path = config['database']['path']
admin_username = config['admin']['username']
admin_password = config['admin']['password']
admin_dashboard_route = config['routing']['admin_dashboard']
admin_login_route = config['routing']['admin_login']
admin_logout_route = config['routing']['admin_logout']
set_end_time_route = config['routing']['set_end_time']
set_start_time_route = config['routing']['set_start_time']
user_profile_route = config['routing']['user_profile']
add_user_route = config['routing']['add_user']

# Database connection function
def get_db_connection():
    conn = sqlite3.connect(db_path, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/')
def index():
    conn = get_db_connection()
    users_query = """
    SELECT username, avatar, COUNT(submissions.id) as submission_count
    FROM users
    LEFT JOIN submissions ON users.id = submissions.user_id
    GROUP BY users.id
    ORDER BY submission_count DESC
    """
    users = conn.execute(users_query).fetchall()
    
    # Get competition end time
    end_time_query = "SELECT end_time FROM settings LIMIT 1"
    end_time_row = conn.execute(end_time_query).fetchone()
    
    if end_time_row:
        end_time = end_time_row['end_time']
    else:
        end_time = None
    
    conn.close()
    return render_template('index.html', users=users, end_time=end_time)


@app.route(admin_login_route, methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if username == admin_username and password == admin_password:
            session['logged_in'] = True
            return redirect(admin_dashboard_route)
        return 'Invalid credentials', 403
    return render_template('admin_login.html')

@app.route(admin_logout_route)
def admin_logout():
    session.pop('logged_in', None)
    return redirect(admin_login_route)

@app.route(admin_dashboard_route)
def admin_dashboard():
    if not session.get('logged_in'):
        return redirect(admin_login_route)
    
    conn = get_db_connection()
    users_query = """
    SELECT id, username, avatar FROM users
    """
    users = conn.execute(users_query).fetchall()
    conn.close()
    
    return render_template('admin_dashboard.html', users=users)

@app.route(set_end_time_route, methods=['POST'])
def set_end_time():
    if not session.get('logged_in'):
        return redirect(admin_login_route)
    
    end_time = request.form['end_time']
    start_time = request.form['start_time']
    
    conn = get_db_connection()
    conn.execute("DELETE FROM settings")  # Clear existing settings
    conn.execute("INSERT INTO settings (end_time, start_time) VALUES (?, ?)", (end_time, start_time))
    conn.commit()
    conn.close()
    return redirect(admin_dashboard_route)

@app.template_filter('to_datetime')
def to_datetime_filter(timestamp, format='%Y-%m-%d %H:%M:%S'):
    return datetime.utcfromtimestamp(timestamp).strftime(format)

@app.route(user_profile_route, methods=['GET'])
def user_profile(username):
    conn = get_db_connection()
    
    # Get user_id for the given username
    user_query = "SELECT id, username, avatar FROM users WHERE username = ?"
    user = conn.execute(user_query, (username,)).fetchone()
    
    if user is None:
        conn.close()
        print(f"not User found: {user}")
        return "User not found", 404

    user_id = user['id']
    
    # Get submissions for the user_id
    user_submissions_query = """
    SELECT title, timestamp, lang
    FROM submissions
    WHERE user_id = ?
    """
    print(f"User found: {user}")
    submissions = conn.execute(user_submissions_query, (user_id,)).fetchall()

    formatted_submissions = []
    for submission in submissions:
        formatted_submission = {
            'title': submission['title'],
            'lang': submission['lang'],
            'timestamp': datetime.fromtimestamp(submission['timestamp']).strftime('%Y-%m-%d %H:%M:%S')
        }
        formatted_submissions.append(formatted_submission)

    conn.close()
    return render_template('user_profile.html', username=username, avatar=user['avatar'], submissions=submissions)


@app.route(add_user_route, methods=['GET', 'POST'])
def add_user():
    if request.method == 'POST':
        username = request.form['username']
        if username:
            runDB(username)
            return redirect('/')
    return render_template('add_user.html')

@app.route('/delete_user/<int:user_id>', methods=['POST'])
def delete_user(user_id):
    if not session.get('logged_in'):
        return redirect(admin_login_route)
    
    conn = get_db_connection()
    conn.execute('DELETE FROM users WHERE id = ?', (user_id,))
    conn.execute('DELETE FROM submissions WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()
    
    return redirect(admin_dashboard_route)

@app.route('/delete_all_submissions', methods=['POST'])
def delete_all_submissions():
    if not session.get('logged_in'):
        return redirect(admin_login_route)
    
    conn = get_db_connection()
    conn.execute("DELETE FROM submissions")
    conn.commit()
    conn.close()
    
    return redirect(admin_dashboard_route)


def runDB(username):
    SUBurl = f"http://localhost:3000/{username}/acSubmission"
    PROFurl = f"http://localhost:3000/{username}"
    
    new_submissions = fetch_and_store_interests(SUBurl, PROFurl, username)
    
    if new_submissions:
        print("New submissions found and added to the database:")
        for submission in new_submissions:
            print(f"Username: {submission['username']}, Title: {submission['title']}, Timestamp: {submission['timestamp']}, Language: {submission['lang']}")
    else:
        print("No new submissions found or user not found.")

@app.route('/refresh_all_users')
def refresh_all_users():
    conn = get_db_connection()
    users_query = "SELECT username FROM users"
    users = conn.execute(users_query).fetchall()
    conn.close()

    for user in users:
        username = user['username']
        SUBurl = f"http://localhost:3000/{username}/acSubmission"
        PROFurl = f"http://localhost:3000/{username}"
        
        fetch_and_store_interests(SUBurl, PROFurl, username)

    return redirect('/')


def fetch_and_store_interests(SUBurl, PROFurl, username):
    conn = get_db_connection()
    c = conn.cursor()
    
    try:
        # Check if the username exists in the users table
        c.execute("SELECT id FROM users WHERE username = ?", (username,))
        user_id_row = c.fetchone()
        
        # If the username doesn't exist, insert it
        if user_id_row is None:
            c.execute("INSERT INTO users (username) VALUES (?)", (username,))
            conn.commit()
            # Fetch the new user_id
            c.execute("SELECT id FROM users WHERE username = ?", (username,))
            user_id_row = c.fetchone()
            print(f"Added new user: {username}")

        user_id = user_id_row['id']

        # Fetch start time
        c.execute("SELECT start_time FROM settings LIMIT 1")
        start_time_row = c.fetchone()
        start_time = start_time_row['start_time'] if start_time_row else None
        if start_time:
            start_time = datetime.fromisoformat(start_time).timestamp()

        # Fetch submissions data
        response = requests.get(SUBurl)
        profile = requests.get(PROFurl)
        
        if response.status_code != 200:
            print(f"Failed to retrieve data from {SUBurl}. Status code: {response.status_code}")
            return []

        if profile.status_code != 200:
            print(f"Failed to retrieve data from {PROFurl}. Status code: {profile.status_code}")
            return []
        
        data = response.json()
        submissions = data.get("submission", [])

        data = profile.json()
        avatar = data.get("avatar", "")

        new_submissions = []

        for item in submissions:
            title = item.get('title')
            timestamp = item.get('timestamp')
            lang = item.get('lang')

            if title is None or timestamp is None or lang is None:
                continue

            # Convert submission timestamp to a datetime object
            try:
                # If timestamp is Unix time
                submission_time = float(timestamp)
            except ValueError:
                # Handle if timestamp is not in Unix time format
                continue

            # Discard submissions before the start time
            if start_time and submission_time < start_time:
                continue

            # Check if the submission already exists
            c.execute("SELECT * FROM submissions WHERE user_id=? AND title=? AND timestamp=? AND lang=?", 
                      (user_id, title, timestamp, lang))
            result = c.fetchone()

            if result is None:
                # Insert new submission
                c.execute("INSERT INTO submissions (user_id, title, timestamp, lang) VALUES (?, ?, ?, ?)", 
                          (user_id, title, timestamp, lang))
                new_submissions.append({'username': username, 'title': title, 'timestamp': timestamp, 'lang': lang})

        # Update or insert avatar
        c.execute("UPDATE users SET avatar = ? WHERE id = ?", (avatar, user_id))
        conn.commit()

    except sqlite3.OperationalError as e:
        print(f"Database error: {e}")
        new_submissions = []
    finally:
        conn.close()
    return new_submissions


if __name__ == "__main__":
    app.run(debug=True)

