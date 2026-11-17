from datetime import UTC, datetime
from time import time_ns

from pymongo import ASCENDING, DESCENDING

from flora.products import Product


RECENT_LIMIT = 8
RECENT_TTL = 24 * 60 * 60


class Products:
    def __init__(self, collection):
        self.collection = collection

    def list(self):
        documents = self.collection.find().sort(
            [("created_at", DESCENDING), ("_id", ASCENDING)]
        )
        return [Product.from_document(document) for document in documents]

    def save(self, product_id, fields):
        result = self.collection.update_one(
            {"_id": product_id},
            {"$setOnInsert": {**fields, "created_at": datetime.now(UTC)}},
            upsert=True,
        )
        return result.upserted_id is not None


class RecentProducts:
    def __init__(self, redis, visitor_id):
        self.redis = redis
        self.key = f"florastore:recent:{visitor_id}"

    def record(self, product_id):
        with self.redis.pipeline(transaction=True) as pipe:
            pipe.zadd(self.key, {product_id: time_ns() // 1_000})
            pipe.zremrangebyrank(self.key, 0, -RECENT_LIMIT - 1)
            pipe.expire(self.key, RECENT_TTL)
            pipe.execute()

    def list(self):
        return self.redis.zrevrange(self.key, 0, RECENT_LIMIT - 1)
