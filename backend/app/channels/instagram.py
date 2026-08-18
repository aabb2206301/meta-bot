"""
Instagram channel adapter (Meta Messaging API for Instagram) — webhook
receive + send().

>>> PHASE 5 TARGET — implement per PROJECT_PLAN.md section 6 <<<

Same shape as channels/whatsapp.py — reuse the same signature-verification
helper and background-task pattern if you factor one out; don't duplicate
the HMAC check logic across all three channel files.

TODO:
- APIRouter with GET (verification) + POST (message receive) routes at
  /webhooks/instagram, same handshake pattern as WhatsApp.
- Parse Instagram's payload shape (different from WhatsApp's — messaging
  events under `entry[].messaging[]`, sender.id is the customer's IG-scoped
  ID) into (instagram_handle or IG-scoped id, message text, external id).
- async def send(recipient_id: str, text: str) -> None:
    POST to the Instagram Send API using settings.instagram_page_access_token.
- Register this router in main.py (Phase 6).
"""
from fastapi import APIRouter

router = APIRouter(prefix="/webhooks/instagram", tags=["instagram"])


async def send(recipient_id: str, text: str) -> None:
    raise NotImplementedError("Phase 5: implement Instagram send()")
