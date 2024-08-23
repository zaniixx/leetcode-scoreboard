import sqlite3

# Connect to the database
conn = sqlite3.connect('./leaderboard.db')
c = conn.cursor()

# Query the database to fetch all records
c.execute("SELECT * FROM submissions")
rows = c.fetchall()

# Print the records
for row in rows:
    print(row)

# Close the connection
conn.close()
