import os

import stripe

__publishable_key = os.environ['STRIPE_PUBLISHABLE_KEY']
__secret_key = os.environ['STRIPE_SECRET_KEY']

stripe.api_key = __secret_key

COST_IN_CENTS = 1500

def get_publishable_key():
    return __publishable_key

def charge(email, stripe_token):
    try:
        customer = stripe.Customer.create(
            email=email,
            source=stripe_token
        )

        stripe.Charge.create(
            customer=customer.id,
            amount=COST_IN_CENTS,
            currency='usd',
            description='MIT-Tab Server',
            receipt_email=email
        )
        return True
    except stripe.error.StripeError:
        return False
