import os
import logging

import stripe

__publishable_key = os.environ['STRIPE_PUBLISHABLE_KEY']
__secret_key = os.environ['STRIPE_SECRET_KEY']

stripe.api_key = __secret_key

FIXED_COST                 = 1500
DAILY_COST_TEST_TOURNAMENT = 100
DAILY_COST                 = 100

logger = logging.getLogger(__name__)

def get_publishable_key():
    return __publishable_key

def charge(email, stripe_token, amount):
    try:
        customer = stripe.Customer.create(
            email=email,
            source=stripe_token
        )

        stripe.Charge.create(
            customer=customer.id,
            amount=amount,
            currency='usd',
            description='MIT-Tab Server',
            receipt_email=email
        )
        return True
    except stripe.error.StripeError as e:
        logger.error(f"Error charging {email}: {e}", exc_info=True)
        return False
