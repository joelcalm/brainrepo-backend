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

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]

        # 1) Grab the session ID and check for duplicate processing
        session_id = session["id"]
        session_doc_ref = db.collection("stripe_sessions").document(session_id)
        if session_doc_ref.get().exists:
            print(f"Session {session_id} already processed, skipping.")
            return {"status": "success - duplicate"}

        # Mark this session as processed
        session_doc_ref.set({"processed": True})

        # 2) Extract the payment link to determine the plan
        payment_link_id = session.get("payment_link")
        plan_id = None

        # Match your known Payment Link IDs
        if payment_link_id == "plink_1R0UCGGzs5DdWJoJ1WwuTkLV":
            plan_id = "pro"
        elif payment_link_id == "plink_1R0UEzGzs5DdWJoJwcyF0Tgu":
            plan_id = "legend"
        else:
            print(f"Unknown payment link {payment_link_id}. Cannot determine plan.")

        # 3) Get the customer's email (from customer_details if customer_email is null)
        customer_email = session.get("customer_email") or session.get("customer_details", {}).get("email")

        # Proceed only if both customer_email and plan_id are determined
        if customer_email and plan_id:
            users_query = db.collection("users") \
                            .where("email", "==", customer_email) \
                            .limit(1) \
                            .get()

            if len(users_query) > 0:
                user_doc = users_query[0]
                user_data = user_doc.to_dict()

                # 4) Determine credits to add based on plan
                credits_to_add = 0
                if plan_id == "pro":
                    credits_to_add = 30
                elif plan_id == "legend":
                    credits_to_add = 999

                new_credits = user_data.get("credits", 0) + credits_to_add

                # 5) Update the user's plan and credits in Firestore
                user_doc.reference.update({
                    "plan": plan_id,
                    "credits": new_credits,
                })
                print(f"Updated {customer_email}: set plan={plan_id} and added {credits_to_add} credits (new total: {new_credits}).")

                # 6) Store the Stripe customer ID for managing subscriptions
                stripe_customer_id = session.get("customer")
                if stripe_customer_id:
                    user_doc.reference.update({
                        "stripeCustomerId": stripe_customer_id
                    })
                    print(f"Stored stripeCustomerId={stripe_customer_id} for user {customer_email}.")
            else:
                print(f"No user found with email {customer_email}.")
        else:
            print("Missing customer_email or plan_id; cannot update user data.")

    # Return a 200 response to acknowledge receipt of the event
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
        raise HTTPException(status_code=400, detail="You are not subscribed to any plan.")

    # 2) Create a portal session for that customer
    session = stripe.billing_portal.Session.create(
        customer=stripe_customer_id,
        return_url="https://brainrepo.es/plan"  # the page user sees after they close the portal
    )
    return {"url": session.url}