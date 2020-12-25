from deployer import app

def cents_as_string(cents_amount):
    if cents_amount < 0:
        raise ValueError('Cannot be a negative amount!')
    elif cents_amount < 100:
        return "$0.{}".format(cents_amount)
    else:
        amount_str = str(cents_amount)
        return "${}.{}".format(amount_str[:-2], amount_str[-2:])

app.jinja_env.globals.update(cents_as_string=cents_as_string)
