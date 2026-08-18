"""
Facebook Messenger channel adapter (Meta) — webhook receive + send().

>>> PHASE 5 TARGET — implement per PROJECT_PLAN.md section 6 <<<

Same shape as channels/whatsapp.py and channels/instagram.py.

TODO:
- APIRouter with GET (verification) + POST (message receive) routes at
  /webhooks/facebook, same handshake pattern.
- Parse Messenger's payload shape (`entry[].messaging[]`, sender.id is
  the customer's PSID — stored as customers.facebook_psid) into
  (facebook_psid, message text, external id).
- async def send(psid: str, text: str) -> None:
    POST to the Messenger Send API using settings.facebook_page_access_token.
- Register this router in main.py (Phase 6).
"""
from fastapi import APIRouter

router = APIRouter(prefix="/webhooks/facebook", tags=["facebook"])


async def send(psid: str, text: str) -> None:
    raise NotImplementedError("Phase 5: implement Facebook send()")
