import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore
import datetime

# 1. Initialize the connection (You get this JSON key from Firebase Settings > Service Accounts)
cred = credentials.Certificate("gdg-web-scraping-data-firebase-adminsdk-fbsvc-3b2210d133.json")
firebase_admin.initialize_app(cred)
db = firestore.client()

def upload_scraped_policy(scraped_data):
    # Add the timestamp right before uploading
    scraped_data['last_updated'] = firestore.SERVER_TIMESTAMP
    
    doc_id = scraped_data['document_id']
    doc_ref = db.collection('policies').document(doc_id)
    
    # Merge=True ensures we update existing docs or create new ones
    doc_ref.set(scraped_data, merge=True)
    print(f"Successfully uploaded/updated: {doc_id}")
