from pymongo import MongoClient
from config import DB_URI, DB_NAME

class Database:
    def __init__(self):
        self.client = MongoClient(DB_URI)
        self.db = self.client[DB_NAME]

    def check_duplicate(self, link):
        # Check if the link exists in the database
        return self.db.news.find_one({"link": link}) is not None

    def insert_news(self, link):
        # Insert a new news entry into the database
        self.db.news.insert_one({"link": link})

# Initialize the database
database = Database()
