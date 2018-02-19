import os

import paypalrestsdk


__account = os.environ['PAYPAL_ACCOUNT']
__client_id = os.environ['PAYPAL_CLIENT_ID']
__secret = os.environ['PAYPAL_SECRET']


COST = 10.50

paypalrestsdk.configure({
    "mode": os.environ['PAYPAL_MODE'],
    "client_id": __client_id,
    "client_secret": __secret
})


class PaymentNotSentError(Exception):
    def __init__(self, recipient, *args):
        message = "Error sending invoice to {}".format(recipient)
        super(PaymentNotSentError, self).__init__(message, args)


def send_invoice(recipient):
    success = False
    try:
        invoice = paypalrestsdk.Invoice({
            'merchant_info': {
                'email': __account
            },
            'billing_info': [{
                'email': recipient
            }],
            'items': [{
                'name': 'MIT Tab Server',
                'quantity': 1,
                'unit_price': {
                    'currency': 'USD',
                    'value': COST
                }
            }]
        })
        success = invoice.create() and invoice.send()
    finally:
        if success is not True:
            raise PaymentNotSentError(recipient)
