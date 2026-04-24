from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorCollection, AsyncIOMotorDatabase
import os
from dotenv import load_dotenv
import logging

load_dotenv()

logger = logging.getLogger(__name__)


DB_NAME = "front-desk"

class MongoDb:
    _client: AsyncIOMotorClient = None
    
    @classmethod
    def connect(cls):
        if cls._client is None:
            uri = os.getenv("MONGODB")
            if not uri:
                raise ValueError("MONGODB environment variable not set")
            cls._client = AsyncIOMotorClient(
                uri,
                maxPoolSize=100,
                minPoolSize=5,
                serverSelectionTimeoutMS=5000
            )
            logger.info("MongoDB Connected")

    @classmethod
    def disconnect(cls):
        if cls._client is not None:
            cls._client.close()
            cls._client = None
            logger.info("MongoDB Disconnected")

    @classmethod 
    def get_client(cls) -> AsyncIOMotorClient:
        if cls._client is None:
            raise RuntimeError("MongoDB not connected. Call MongoDb.connect() first.")
        return cls._client
    
    @classmethod
    def get_db(cls) -> AsyncIOMotorDatabase:
        if cls._client is None:
            raise RuntimeError("MongoDB not connected. Call MongoDB.connect() first.")
        return cls._client[DB_NAME]
    
    @classmethod
    def orgs(cls) -> AsyncIOMotorCollection:
        return cls.get_db()["orgs"]
    
    @classmethod
    def conversations(cls) -> AsyncIOMotorCollection:
        return cls.get_db()["conversations"]
    
    @classmethod
    def leads(cls) -> AsyncIOMotorCollection:
        return cls.get_db()["leads"]
    
    @classmethod
    def issues(cls) -> AsyncIOMotorCollection:
        return cls.get_db()["issues"]
    
    @classmethod
    def docs(cls) -> AsyncIOMotorCollection:
        return cls.get_db()["docs"]

    @classmethod
    async def ping(cls) -> bool:
        try:
            await cls.get_client().admin.command("ping")
            return True
        except Exception as e:
            logger.error(f"MongoDB ping failed: {e}")
            return False
        

    #indexes
    @classmethod
    async def setup_indexes(cls):
        await cls.orgs().create_index("org_id", unique = True)

        await cls.conversations().create_index("org_id")
        await cls.conversations().create_index(
            [("org_id", 1), ("thread_id", 1)], unique = True
        )

        await cls.leads().create_index("org_id")
        await cls.leads().create_index(
            [("org_id", 1), ("thread_id", 1)]
        )
        await cls.leads().create_index(
            [("org_id", 1), ("status", 1)]
        )

        await cls.issues().create_index("org_id")
        await cls.issues().create_index(
            [("org_id", 1), ("status", 1)]
        )

        await cls.docs().create_index("doc_id", unique=True)
        await cls.docs().create_index("org_id")
        await cls.docs().create_index([("org_id", 1), ("status", 1)])

        logger.info("MongoDB indexes created")


    