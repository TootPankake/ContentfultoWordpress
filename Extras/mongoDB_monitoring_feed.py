from pymongo import MongoClient
from pymongo.server_api import ServerApi
from pymongo.mongo_client import MongoClient
from config import URI
import certifi

clientDB = MongoClient(URI, server_api=ServerApi('1'), tlsCAFile=certifi.where())
db = clientDB['brimming-test']
collection = db['users']

# Open a change stream on the given collection
with collection.watch() as stream:
    print("Monitoring changes. Press Ctrl+C to stop.")
    try:
        for change in stream:
            operation_type = change['operationType']
            print(f"\nOperation Type: {operation_type}")
            
            if operation_type == "insert":
                # Output the full document for an insert operation
                document_id = change["documentKey"]["_id"]
                full_document = change.get("fullDocument")
                status = full_document.get("subscription", {}).get("status")
                plan = full_document.get("subscription", {}).get("plan")
                renewal = full_document.get("subscription", {}).get("autoRenew")
                endDate = full_document.get("subscription", {}).get("endDate")
                #print(full_document) # for the entire thing
                #print("Inserted document:", document_id,"\nstatus->", status, "\nplan->", plan, "\nrenewal->", renewal, "\nendDate->", endDate)
                
                collection.update_one(
                        {"_id": document_id},
                        {"$set": {"merchant": "manual-prolific", "subscription.status": "active"}} ### MODIFY THIS set function to add or remove new section
                )

            elif operation_type == "update":
                # Output only the updated fields for an update operation
                update_description = change["updateDescription"]["updatedFields"]
                print("Updated fields:", update_description)
                
            elif operation_type == "delete":
                # Output the _id of the deleted document
                document_id = change["documentKey"]["_id"]
                print("Deleted document _id:", document_id)
            
            elif operation_type == "replace":
                # Output the entire new document for a replace operation
                full_document = change.get("fullDocument")
                print("Replaced document:", full_document)

    except Exception as e:
        print("Error:", e)