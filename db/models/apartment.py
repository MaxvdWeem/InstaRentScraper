import json
import logging

from aioredis import Redis
from pydantic import BaseModel, ValidationError
from db.db_connection import lifespan
from db.models.filter import FilterStore, FilterSchema
from tool.utils import compare_dicts_by_key_fast
from settings.config import REDIS_HOST, REDIS_PORT, REDIS_DB, REDIS_PASSWORD

rb = Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ApartmentSchema(BaseModel):
    url: str | None = None
    rent_price: int | float | None = None
    selling_price: int | float | None = None
    square_meters: float | int | None = None
    bedrooms: int | None = None
    location: str | None = None
    address: str | None = None
    furnished: bool | None = None
    image_url: str | None = None


class ApartmentStore:

    @staticmethod
    async def create_or_update_apartment(data: list[dict], site_name: str):
        validated_data = []
        for item in data:
            try:
                # Validate data using Pydantic schema
                validated_data.append(ApartmentSchema(**item).dict())
            except ValidationError as ve:
                logger.error(f"Data validation error: {ve}")
                continue

        async with lifespan() as client:
            keys_to_check_for_update = ['rent_price', 'selling_price', 'image_url'] if any("selling_price" in d for d in data) else [
                'rent_price', 'image_url']
            try:
                logger.info(rb)
                pong = await rb.ping()
                logger.info(pong)
                existing_table_json = await rb.get("list_apartment_" + site_name)
                if existing_table_json:
                    existing_table = json.loads(existing_table_json)
                else:
                    result = await client.table("apartments").select("*").execute()
                    existing_table = result.data
                    await rb.set("list_apartment_" + site_name, json.dumps(existing_table, default=str),
                                 ex=60 * 60 * 24)

                unique_data, to_update_array = compare_dicts_by_key_fast(validated_data, existing_table, 'url',
                                                                         keys_to_check_for_update)

                if unique_data:
                    await client.table("apartments").insert(unique_data).execute()

                if to_update_array:
                    urls_to_update = [d['url'] for d in to_update_array]
                    await client.table("apartments").delete().in_("url", urls_to_update).execute()
                    await client.table("apartments").insert(to_update_array).execute()

                if unique_data or to_update_array:
                    await rb.delete("list_apartment_" + site_name)
                    logger.info("Database updated, cache cleared")

            except Exception as e:
                logger.error(f"An error occurred DB: {e}")

    @staticmethod
    async def get_filtered_apartment(data: FilterSchema):
        data = data.dict()
        async with lifespan() as client:

            query = client.table('apartments').select('*')
            # Apply data based on the provided dictionary
            if data['min_price']:
                query = query.or_(
                    f"selling_price.gte.{data['min_price']},rent_price.gte.{data['min_price']}"
                )
            if data['max_price']:
                query = query.or_(
                    f"selling_price.lte.{data['max_price']},rent_price.lte.{data['max_price']}"
                )

            if data['min_square_meters']:
                query = query.gte('square_meters', round(data['min_square_meters']))

            if data['furnished']:
                query = query.eq('furnished', data['furnished'])

            if data['location']:
                query = query.ilike('location', f"%{data['location']}%")

            if data['address']:
                query = query.ilike('address', f"%{data['address']}%")

            # Execute the query and handle the response
            apartment = await query.execute()

            return apartment.data
