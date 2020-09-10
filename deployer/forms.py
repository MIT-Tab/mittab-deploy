import re

from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SelectField, BooleanField, \
        HiddenField
from wtforms.validators import DataRequired, EqualTo, Email, ValidationError

from deployer.models import Droplet
from deployer.clients import stripe
from config.repo_options import options

####################
# Custom validations
####################


def validate_name(form, field):
    pattern = re.compile('^[\w\d\-]+$')
    if not pattern.match(field.data):
        raise ValidationError('Name contains invalid characters')

def validate_password(form, field):
    pattern = re.compile('[a-zA-Z0-9]+$')
    if not pattern.match(field.data):
        raise ValidationError('Password can only contain alphanumeric characters. Keep it simple and don\'t use important passwords!')


def validate_unique_name(form, field):
    if Droplet.query.filter_by(name=field.data.lower(), active=True).count() > 0:
        raise ValidationError('An active tournament with that name already exists')


def validate_discord_required(form, field):
    if form.cleaned_data['repo_options'] == 'discord' and not field.data:
        raise ValidationError('Please submit a valid Discord ID since you have selected a Discord version of MIT-Tab')


def validate_discord_id(form, field):
    pattern = re.compile('[\w\d]+#\d{4}')
    if not pattern.match(field.data):
        raise ValidationError('The Discord ID is in the wrong format.  It should take the form <username>#<discord ID>'.)


#################
# Form definition
#################


class TournamentForm(FlaskForm):
    name = StringField(
            'Tournament Name',
            [DataRequired(), validate_name, validate_unique_name]
            )
    email = StringField('Email Address', [Email()])
    password = PasswordField(
            'Password',
            [
                DataRequired(),
                EqualTo('confirm', message='Passwords must match'),
                validate_password
            ])
    confirm = PasswordField('Confirm Password')
    repo_options = SelectField(
            'MIT-Tab Version',
            choices=[(key, options[key]['name']) for key in options.keys()],
            default='default'
            )
    add_test = BooleanField('Include Test Tournament?')
    discord_admin = StringField(
        'Discord ID of superadmin',
        [
            validate_discord_required, validate_discord_id
        ]
    )
    stripe_token = HiddenField('Stripe Token')
