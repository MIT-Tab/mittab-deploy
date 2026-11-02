import os
import sys
import logging

import stripe

__publishable_key = os.environ['STRIPE_PUBLISHABLE_KEY']
__secret_key = os.environ['STRIPE_SECRET_KEY']

stripe.api_key = __secret_key

FIXED_COST                 = 1500
DAILY_COST_TEST_TOURNAMENT = 100
DAILY_COST                 = 100

logger = logging.getLogger(__name__)
handler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.INFO)

def get_publishable_key():
    return __publishable_key

def charge(email, stripe_token, amount, idempotency_key=None):
    try:
        customer_options = ({'idempotency_key': idempotency_key + ':customer'}
                            if idempotency_key else {})
        customer = stripe.Customer.create(
            email=email,
            source=stripe_token,
            **customer_options
        )

        charge_options = ({'idempotency_key': idempotency_key + ':charge'}
                          if idempotency_key else {})
        payment = stripe.Charge.create(
            customer=customer.id,
            amount=amount,
            currency='usd',
            description='MIT-Tab Server',
            receipt_email=email,
            **charge_options
        )
        return payment.id
    except stripe.error.StripeError as e:
        logger.error(f"Error charging {email}: {e}", exc_info=True)
        return False
