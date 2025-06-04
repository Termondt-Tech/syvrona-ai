# Map your internal plan codes to Stripe Price IDs
import os


STRIPE_PRICE_IDS = {
    "pro_monthly": os.getenv("STRIPE_PRICE_ID_PRO_MONTHLY"),
    "pro_yearly": os.getenv("STRIPE_PRICE_ID_PRO_YEARLY"),
}

PRICE_LABELS = {
    os.getenv("STRIPE_PRICE_ID_PRO_MONTHLY"): "Pro Monthly ($9.99/mo)",
    os.getenv("STRIPE_PRICE_ID_PRO_YEARLY"): "Pro Yearly ($99/year)",
    "free": "Free Plan (Limited Features)",
}
