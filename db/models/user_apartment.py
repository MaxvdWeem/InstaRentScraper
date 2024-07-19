import asyncio
import json
import logging
from datetime import datetime

from pydantic import BaseModel

from db.db_connection import lifespan
from db.models.filter import FilterSchema, FilterStore
from db.models.user import UserStore
from tool.send_mail import send_email, send_email_with_credentials
from tool.send_whatsapp import send_whatsapp
from tool.utils import generate_rental_listings_message

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class UserApartmentSchema(BaseModel):
    user_id: str
    apartment_id: int
    created_at: datetime
    updated_at: datetime


class UserApartmentStore:

    @staticmethod
    async def create_task(user_id: str, filtered_apartments: dict):
        async with lifespan() as client:

            user_apartments = await client.table('user_apartments').select("apartment_id").eq("user_id",
                                                                                              user_id).execute()

            valid_ids = {item['apartment_id'] for item in user_apartments.data}
            updated_array = []
            filtered_array = []

            for item in filtered_apartments[user_id]:
                if item['id'] not in valid_ids:
                    filtered_array.append(item)
                    updated_array.append({"user_id": user_id, "apartment_id": item['id']})

            if filtered_array or updated_array:
                can_send = None
                if filtered_array:
                    user = await UserStore.get_user_by_id(user_id=user_id)
                    list_message, static_message, phone_number = generate_rental_listings_message(user, filtered_array)
                    try:
                        # formatted_data = json.dumps(filtered_array, indent=4)
                        # status = await send_email("Instarent nieuwe huurwoning", static_message, user['email'])
                        status = await send_email_with_credentials(static_message, user['email'], user['first_name'])
                        can_send = status
                        if user['whatsapp']:
                            print(list_message)
                            for i in list_message:
                                logger.info(i)
                                await send_whatsapp(i, phone_number)
                            logger.info("------SEND WHATSAPP MESSAGE-------")
                    except Exception as e:
                        logger.error(e)
                if can_send and updated_array:
                    await client.table("user_apartments").insert(updated_array).execute()

    @staticmethod
    async def get_tasks():
        async with lifespan() as client:
            tasks = await client.table("user_apartments").select("*").execute()
            return tasks.data
