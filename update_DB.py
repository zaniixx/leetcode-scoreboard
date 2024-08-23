import requests
import sqlite3

# Database connection function
def get_db_connection():
    conn = sqlite3.connect('leaderboard.db', timeout=10)
    conn.row_factory = sqlite3.Row
    return conn

def fetch_and_store_interests(SUBurl, PROFurl, username):
    conn = get_db_connection()
    c = conn.cursor()
    
    try:
        # Check if the username exists in the users table
        c.execute("SELECT id FROM users WHERE username = ?", (username,))
        user_id_row = c.fetchone()
        
        # If the username doesn't exist, insert it
        if user_id_row is None:
            # Fetch profile data to get avatar URL
            profile = requests.get(PROFurl)
            if profile.status_code == 200:
                profile_data = profile.json()
                avatar_url = profile_data.get("avatar", None)
            else:
                avatar_url = None
            
            c.execute("INSERT INTO users (username, avatar) VALUES (?, ?)", (username, avatar_url))
            conn.commit()
            # Fetch the new user_id
            c.execute("SELECT id FROM users WHERE username = ?", (username,))
            user_id_row = c.fetchone()
            print(f"Added new user: {username}")  # Debugging line

        user_id = user_id_row['id']

        # Fetch submissions data
        response = requests.get(SUBurl)
        
        if response.status_code != 200:
            print(f"Failed to retrieve data from {SUBurl}. Status code: {response.status_code}")
            return []

        data = response.json()
        submissions = data.get("submission", [])

        new_submissions = []

        for item in submissions:
            title = item.get('title')
            timestamp = item.get('timestamp')
            lang = item.get('lang')

            if title is None or timestamp is None or lang is None:
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

        # Commit the new submissions
        conn.commit()

    except sqlite3.OperationalError as e:
        print(f"Database error: {e}")
        new_submissions = []
    finally:
        conn.close()
    return new_submissions

# Example usage
def runDB(username):
    SUBurl = f"http://localhost:3000/{username}/acSubmission"  # Replace with the actual JSON file URL
    PROFurl = f"http://localhost:3000/{username}"  # Replace with the actual profile URL
    
    new_submissions = fetch_and_store_interests(SUBurl, PROFurl, username)
    
    if new_submissions:
        print("New submissions found and added to the database:")
        for submission in new_submissions:
            print(f"Username: {submission['username']}, Title: {submission['title']}, Timestamp: {submission['timestamp']}, Language: {submission['lang']}")
    else:
        print("No new submissions found or user not found.")

if __name__ == "__main__":
    username = input("Enter username: ")
    runDB(username)
