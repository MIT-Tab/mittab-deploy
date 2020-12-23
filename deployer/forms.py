import re

from datetime import datetime

from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SelectField, BooleanField, \
        HiddenField, DateField
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

def validate_date(form, field):
    if field.data <= datetime.now().date():
        raise ValidationError('Deletion date must be in the future')

def validate_present_and_inactive_tournament(form, field):
    tournament = Tournament.query.get(field.data)
    if tournament is None:
        raise ValidationError('Tournament not provided')
    elif tournament.active:
        raise ValidationError('Cannot confirm a tournament which is already active')


#################
# Form definition
#################


class TournamentForm(FlaskForm):
    name = StringField(
            'Tournament Name',
            [DataRequired(), validate_name, validate_unique_name]
            )
    repo_options = SelectField(
            'MIT-Tab Version',
            choices=[(key, options[key]['name']) for key in options.keys()],
            default='default'
            )
    deletion_date = DateField('Deletion Date', [validate_date], format='%m/%d/%Y')

class ConfirmTournamentForm(FlaskForm):
    add_test = BooleanField('Include Test Tournament?')
    tournament_id = HiddenField('Tournament ID')
    stripe_token = HiddenField('Stripe Token')
    email = StringField('Email Address', [Email()])
    password = PasswordField(
            'Password',
            [
                DataRequired(),
                EqualTo('confirm', message='Passwords must match'),
                validate_password
            ])
    confirm = PasswordField('Confirm Password')
