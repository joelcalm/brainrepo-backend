# stripe_utils.py
import os
import stripe
from fastapi import APIRouter, Request, HTTPException
from firebase_config import db
from pydantic import BaseModel


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
        session_id = session["id"] 
        
        # 2) Check if we've already processed this session_id
        session_doc_ref = db.collection("stripe_sessions").document(session_id)
        if session_doc_ref.get().exists:
            # Already processed => skip
            print(f"Session {session_id} already processed, skipping.")
            return {"status": "success - duplicate"}

        # Not processed before => proceed

        # 3) Mark this session as processed (create doc right away)
        session_doc_ref.set({"processed": True})

        # 4) Extract the customer's email & plan_id
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

                # 6) Update the user's plan and credits
                user_doc.reference.update({
                    "plan": plan_id,
                    "credits": new_credits,
                })

                print(f"Added {credits_to_add} credits to {customer_email}. Now has {new_credits} total.")

                # 7) Store the Stripe customer ID in the user doc
                #    This is crucial for letting them manage the subscription.
                stripe_customer_id = session.get("customer")  # e.g. "cus_ABC123..."
                if stripe_customer_id:
                    user_doc.reference.update({
                        "stripeCustomerId": stripe_customer_id
                    })
                    print(f"Stored stripeCustomerId={stripe_customer_id} for user {customer_email}.")

    # Return a 200 to acknowledge receipt of the event
    return {"status": "success"}


portal_router = APIRouter()

class PortalRequest(BaseModel):
    email: str

@portal_router.post("/create-portal-session")
def create_portal_session(data: PortalRequest):
    # 1) Look up the user doc by email
    users_query = (
        db.collection("users")
        .where("email", "==", data.email)
        .limit(1)
        .get()
    )
    if len(users_query) == 0:
        raise HTTPException(status_code=404, detail="User not found")

    user_doc = users_query[0].to_dict()
    stripe_customer_id = user_doc.get("stripeCustomerId")

    if not stripe_customer_id:
        # User might never have purchased a plan => no subscription to manage
        raise HTTPException(status_code=400, detail="No stripeCustomerId found. User not subscribed?")

    # 2) Create a portal session for that customer
    session = stripe.billing_portal.sessions.create(
        customer=stripe_customer_id,
        return_url="https://brainrepo.es/plan"  # the page user sees after they close the portal
    )
    return {"url": session.url}