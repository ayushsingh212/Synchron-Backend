import os
import logging
from pymongo import MongoClient
from bson import ObjectId
from dotenv import load_dotenv
from typing import Optional, Dict, Any
# Note: You might need to install python-dotenv: pip install python-dotenv

load_dotenv()
logger = logging.getLogger(__name__)

# Configuration
MONGO_URI = os.getenv("MONGO_URL")
DB_NAME = os.getenv("MONGO_DB_NAME", "SYNCHRON")
COLLECTION_NAME = "organisationdatas"

# Initialize global variables explicitly as None
client: Optional[MongoClient] = None
# Using Any for Collection type for simplicity
config_collection: Optional[Any] = None

# -----------------------------------------------------------------------------
# DATABASE CONNECTION
# -----------------------------------------------------------------------------
try:
    if MONGO_URI:
        client = MongoClient(MONGO_URI)
        # Check connection status
        client.admin.command('ping') 
        db = client[DB_NAME]
        config_collection = db[COLLECTION_NAME]
        logger.info("Connected to MongoDB successfully")
    else:
        logger.error("MONGO_URL environment variable is not set. Database connection skipped.")
except Exception as e:
    # Use logger for consistency instead of print
    logger.error(f"Failed to connect to MongoDB at {MONGO_URI}: {e}")
    client = None
    config_collection = None # Ensure this is also set to None on failure

# -----------------------------------------------------------------------------
# DATABASE UTILITY FUNCTION (FIXED)
# -----------------------------------------------------------------------------

def get_config_by_params(course: str, year: str, semester: str, organisation_id: str = None) -> Optional[Dict[str, Any]]:
    """
    Fetches the timetable configuration document based on the Mongoose Schema hierarchy.
    """
    
    # FIX: Use explicit comparison 'is None' instead of 'not client' or 'not config_collection'
    if client is None or config_collection is None:
        logger.error("Database connection failed or not initialized. Cannot fetch config.")
        return None

    # Build Query based on your Mongoose Schema
    query = {
        "course": course.lower().strip(),
        "year": year.lower().strip(),
        "semester": semester.lower().strip()
    }

    # Add Organisation ID filter if provided
    if organisation_id:
        try:
            query["organisationId"] = ObjectId(organisation_id)
        except Exception:
            logger.error(f"Invalid Organisation ID format: {organisation_id}")
            return None

    logger.info(f"Querying MongoDB with: {query}")

    # Fetch document and exclude Mongo-specific fields (_id, __v, etc.)
    projection = {
        "_id": 0, 
        "__v": 0, 
        "createdAt": 0, 
        "updatedAt": 0
    }
    
    config_document = config_collection.find_one(query, projection=projection)
    
    if config_document is None: # FIX: Check against None explicitly
        logger.warning(f"No configuration found for {course} - {year} - {semester}")
        return None

    # Returns the fetched configuration dictionary
    return config_document