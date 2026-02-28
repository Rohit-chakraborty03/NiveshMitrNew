import firebase_admin
from firebase_admin import credentials, firestore

# Point this to the JSON file you just downloaded
cred = credentials.Certificate("serviceAccountKey.json")

# Initialize the Firebase Admin app
firebase_admin.initialize_app(cred)

# Create the database client so our routes can use it
db = firestore.client()