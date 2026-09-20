import sys
from passlib.context import CryptContext
from backend.database import mongo

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def create_admin(username, password):
    if mongo.db is None:
        print("Failed to connect to MongoDB.")
        sys.exit(1)
        
    hashed_password = pwd_context.hash(password)
    mongo.db.admins.update_one(
        {"username": username},
        {"$set": {"password": hashed_password}},
        upsert=True
    )
    print(f"Admin user '{username}' created/updated successfully.")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python3 create_admin.py <username> <password>")
        sys.exit(1)
    create_admin(sys.argv[1], sys.argv[2])
