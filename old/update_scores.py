import requests
from bs4 import BeautifulSoup
from datetime import datetime
from app import db
from models import Participant

def fetch_leetcode_data(username):
    url = f"https://leetcode.com/{username}/"
    response = requests.get(url)
    
    if response.status_code != 200:
        return None
    
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # Example: Extracting the number of problems solved (You will need to adjust this based on the actual HTML structure)
    problems_solved = soup.find("div", class_="some-class-for-problems-solved").text.strip()
    
    return {
        'problems_solved': int(problems_solved)
    }

def update_participant_scores():
    participants = Participant.query.all()
    
    for participant in participants:
        data = fetch_leetcode_data(participant.username)
        
        if data:
            participant.problems_solved = data['problems_solved']
            participant.last_updated = datetime.utcnow()
            db.session.commit()

if __name__ == "__main__":
    update_participant_scores()
