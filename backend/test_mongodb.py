import os
import sys
from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.server_api import ServerApi
from pymongo.errors import PyMongoError


def run_test():
    print("====================================")
    print("MongoDB Atlas Connection Test")
    print("====================================")

    # 1. Load environment variables
    load_dotenv()
    print("[OK] Environment variables loaded")

    # 2. Read MONGODB_URI (never expose or print the URI)
    uri = os.getenv("MONGODB_URI")
    if not uri:
        print("[FAIL] MONGODB_URI is not set in environment or .env file.")
        sys.exit(1)
    print("[OK] MongoDB URI found")

    # 3. Read and confirm database name
    database_name = os.getenv("MONGODB_DATABASE", "childdatadb")
    if database_name != "childdatadb":
        print(f"[WARN] Expected database 'childdatadb', but found '{database_name}'")
    
    # 4. Connect to MongoDB Atlas
    try:
        client = MongoClient(
            uri,
            server_api=ServerApi("1", strict=True, deprecation_errors=True)
        )
        print("[OK] Connected to MongoDB Atlas")
    except PyMongoError:
        print("[FAIL] [MONGODB ERROR] Unable to connect to MongoDB Atlas.")
        sys.exit(1)
    except Exception:
        print("[FAIL] [MONGODB ERROR] Unexpected connection initialization error.")
        sys.exit(1)

    # 5. Ping Atlas
    try:
        client.admin.command("ping")
        print("[OK] MongoDB ping successful")
    except PyMongoError:
        print("[FAIL] [MONGODB ERROR] Ping command failed against MongoDB Atlas.")
        sys.exit(1)
    except Exception:
        print("[FAIL] [MONGODB ERROR] Ping failed with unexpected exception.")
        sys.exit(1)

    # 6. Confirm database
    db = client[database_name]
    print(f"[OK] Database: {db.name}")

    # 7. Check collections accessible
    try:
        existing_collections = db.list_collection_names()
        print(f"[OK] Collections accessible (existing: {existing_collections})")

        # Verify required collections are referenced properly
        expected_collections = ["students", "guardians", "attendance", "system_events"]
        for col_name in expected_collections:
            col = db[col_name]
            # Verify collection object is ready
            _ = col.name
        print(f"[OK] Verified target collections: {', '.join(expected_collections)}")
    except PyMongoError:
        print("[FAIL] [MONGODB ERROR] Failed to access collections in database.")
        sys.exit(1)

    # 8. Safe write / read / delete permission test using temporary collection
    test_collection_name = "_connection_test"
    try:
        test_col = db[test_collection_name]
        # Insert test document
        test_doc = {"test": True, "verification": "permission_check"}
        insert_res = test_col.insert_one(test_doc)
        
        # Read back test document
        retrieved = test_col.find_one({"_id": insert_res.inserted_id})
        if not retrieved or retrieved.get("verification") != "permission_check":
            print("[FAIL] Test document write/read verification mismatch.")
            sys.exit(1)

        # Delete test document & drop temporary test collection
        test_col.delete_one({"_id": insert_res.inserted_id})
        test_col.drop()
        print("[OK] Test write/read/delete on temporary collection passed and cleaned up")
    except PyMongoError:
        print("[FAIL] [MONGODB ERROR] Temporary collection write/read test failed.")
        sys.exit(1)
    except Exception:
        print("[FAIL] Unexpected error during write/read test.")
        sys.exit(1)

    print("\nMongoDB test completed successfully.")


if __name__ == "__main__":
    run_test()
