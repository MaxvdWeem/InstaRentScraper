import asyncio
import os
import re
import logging

from db.models.apartment import ApartmentStore
from settings.config import VESTEDA_CD
from core.engine import fetch_url
from bs4 import BeautifulSoup

async def main_huur(page_num=None):
    if page_num:
        url = f'https://www.pararius.nl/huurwoningen/nederland/page-{page_num}'
    else:
        url = 'https://www.pararius.nl/huurwoningen/nederland'

    headers = {
        "Accept": "*/*",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 OPR/110.0.0.0",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Accept-Language": "en-US,en;q=0.9",
        "scheme": "https",
        "path": "/huurwoningen/nederland",
        "authority": "www.pararius.nl",
        "Cache-Control": "max-age=0",
        "method": "GET",
        "referer": "https://www.pararius.nl/"
    }
    data_pararius = await fetch_url('GET', url, headers=headers)
    return data_pararius



async def scrape_data(file_name: str):
    result = []
    page_num = None

    try:
        while True:
            data_huur = await main_huur(page_num=page_num)

            soup_data = BeautifulSoup(data_huur, "html.parser")
            elements = soup_data.find_all("section", class_="listing-search-item--for-rent")

            if elements:
                for ele in elements:
                    # getting the location
                    raw_location = ele.find("div", class_="listing-search-item__sub-title'").contents[0].strip()
                    location = ' '.join(raw_location.split(' ')[2:]).split('(')[0].strip()

                    # getting the detail element
                    detail_ele = ele.find('a', class_='listing-search-item__link--title')

                    # getting the  detail URL
                    detail_url = detail_ele.get('href')
                    url = f'https://pararius.nl{detail_url}'

                    # getting the address
                    address = ' '.join(detail_ele.contents[0].strip().split(' ')[1:])

                    # getting the rent price
                    rent_price = ele.find('div', class_='listing-search-item__price').contents[0].strip().replace('\xa0', '')
                    rent_price =  re.sub(r'[^\d]', '', rent_price)
                    if rent_price.isdigit():
                        rent_price = int(rent_price)
                    else:
                        rent_price = None

                    # getting the area
                    square_meters = ele.find('li', class_='illustrated-features__item--surface-area').contents[0].strip()
                    square_meters = re.sub(r'[^\d\.]', '', square_meters)

                    # getting the number of rooms
                    bedrooms = ele.find('li', class_='illustrated-features__item--number-of-rooms').contents[0].strip()
                    bedrooms = re.sub(r'[^\d]', '', bedrooms)

                    # getting the image URL
                    image_url = ele.find('img', class_='picture__image')['src']

                    data = {
                        'url': url,
                        'rent_price': rent_price,
                        'square_meters': square_meters,
                        'bedrooms': bedrooms,
                        'location': location,
                        'address': address,
                        'image_url': image_url
                    }
                    result.append(data)

                # getting the active page
                active_page = soup_data.find('li', class_='pagination__item--active')

                # getting the next page
                next_page = active_page.find_next('li')
                if next_page:
                    next_page_link = next_page.find('a', class_='pagination__link')
                    if next_page_link:
                        page_num = int(next_page_link['data-page'])  # Update to the next page number
                        logging.info(f"Moving to page {page_num}")
                    else:
                        logging.info('No further pages available. Ending scraping.')
                        break
                else:
                    logging.info('No further pages available. Ending scraping.')
                    break
    except Exception as e:
        logging.error(f'Error scraping data from Pararius: {e}')

    if result:
        try:
            await ApartmentStore.create_or_update_apartment(result, file_name)
            pass
        except Exception as e:
            print(e)



async def main():
    script_path = os.path.abspath(__file__)
    script_name = (os.path.basename(script_path)).split('.')[0]
    while True:
        await scrape_data(file_name=script_name)
        await asyncio.sleep(VESTEDA_CD)



if __name__ == "__main__":
    asyncio.run(main())
