# stripe_webhook.py
import os
import stripe
from fastapi import APIRouter, Request, HTTPException
from firebase_config import db

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
endpoint_secret = os.getenv("STRIPE_WEBHOOK_SECRET")  # from your Stripe Dashboard

stripe_webhook_router = APIRouter()

@stripe_webhook_router.post("/stripe-webhook")
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, endpoint_secret
        )
    except ValueError:
        # Invalid payload
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError:
        # Invalid signature
        raise HTTPException(status_code=400, detail="Invalid signature")

    # Handle the event
    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        
        # 1) Grab the session ID
        session_id = session["id"]  # e.g. "cs_test_a1d5xk073JD..."

        # 2) Check if we've already processed this session_id
        session_doc_ref = db.collection("stripe_sessions").document(session_id)
        if session_doc_ref.get().exists:
            # Already processed => skip
            print(f"Session {session_id} already processed, skipping.")
            return {"status": "success - duplicate"}

        # Not processed before => proceed

        # 3) Mark this session as processed (create doc right away)
        session_doc_ref.set({"processed": True})

        # 4) Extract email & plan_id
        customer_email = session.get("customer_email")
        plan_id = session.get("metadata", {}).get("plan_id")

        if customer_email:
            users_query = db.collection("users") \
                             .where("email", "==", customer_email) \
                             .limit(1) \
                             .get()
            if len(users_query) > 0:
                user_doc = users_query[0]
                user_data = user_doc.to_dict()

                # 5) Add credits based on the plan
                credits_to_add = 0
                if plan_id == "pro":
                    credits_to_add = 30
                elif plan_id == "legend":
                    credits_to_add = 999

                new_credits = user_data.get("credits", 0) + credits_to_add
                user_doc.reference.update({"credits": new_credits})
                print(f"Added {credits_to_add} credits to {customer_email}. Now has {new_credits} total.")

                # 6) Update the user's plan
                user_doc.reference.update({"plan": plan_id})

    # Return a 200 to acknowledge receipt of the event
    return {"status": "success"}
