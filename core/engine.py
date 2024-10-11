import asyncio
import logging
import httpx
import brotli


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def fetch_url(method: str, url: str, semaphore_th: int = 1, headers: dict = None, proxy: str = None,
                    payload: dict = None):
    try:
        semaphore = asyncio.Semaphore(semaphore_th)
        async with semaphore:
            async with httpx.AsyncClient(headers=headers, proxies=proxy) as client:
                if method == 'POST':
                    response = await client.post(url, json=payload)
                else:
                    response = await client.get(url)

                if response.status_code == 200:
                    content_encoding = response.headers.get('Content-Encoding', '')

                    # Attempt to handle Brotli-compressed responses
                    if 'br' in content_encoding:
                        try:
                            decompressed_data = brotli.decompress(response.content)
                            return decompressed_data.decode('utf-8')
                        except brotli.error as e:
                            logging.error(f'Brotli decompression failed: {e}. Attempting to return raw response.')
                            return response.text  # Fallback to raw response
                    else:
                        return response.text
                else:
                    logging.error(f'Error fetching URL: {url}\nStatus code: {response.status_code}')
                    return

    except Exception as err:
        logging.error(f'Error fetching URL: {url}\nError msg: {err}')
        return
