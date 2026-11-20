import httpx
from celery import shared_task

from .services import fetch_cbu_rates


@shared_task(
    autoretry_for=(httpx.HTTPError,), retry_backoff=60, retry_backoff_max=1800, max_retries=6
)
def fetch_cbu_rates_task() -> int:
    return fetch_cbu_rates()
