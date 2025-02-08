# stripe_webhook.py
import os
import stripe
from fastapi import APIRouter, Request, HTTPException
from firebase_config import db

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
endpoint_secret = os.getenv("STRIPE_WEBHOOK_SECRET")  # from your Stripe dashboard

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
        customer_email = session.get("customer_email")
        # If you stored metadata in your checkout session, you can retrieve it:
        plan_id = session.get("metadata", {}).get("plan_id")

        if customer_email:
            users_query = db.collection("users") \
                             .where("email", "==", customer_email) \
                             .limit(1) \
                             .get()
            if len(users_query) > 0:
                user_doc = users_query[0]
                user_data = user_doc.to_dict()

                # Example: "pro" plan -> add 30 credits, "legend" -> add a big number
                # Or interpret from line items, etc.
                credits_to_add = 0
                if plan_id == "pro":
                    credits_to_add = 30
                elif plan_id == "legend":
                    credits_to_add = 999  # or any logic you want

                new_credits = user_data.get("credits", 0) + credits_to_add
                user_doc.reference.update({"credits": new_credits})

    # Return a 200 to acknowledge receipt of the event
    return {"status": "success"}
