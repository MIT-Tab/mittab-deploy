import re

from datetime import datetime

from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SelectField, BooleanField, \
        HiddenField, DateField, IntegerField
from wtforms.validators import DataRequired, EqualTo, Email, ValidationError

from deployer.models import App
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
    if App.query.filter_by(name=field.data.lower(), active=True).count() > 0:
        raise ValidationError('An active tournament with that name already exists')

def validate_date(form, field):
    if field.data <= datetime.now().date():
        raise ValidationError('Deletion date must be in the future')

def validate_days(form, field):
    if field.data < 1:
        raise ValidationError('Must be at least 1 day')

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
    deletion_date = DateField(
            'Deletion Date',
            [DataRequired(), validate_date],
            format='%m/%d/%Y')
    email = StringField('Email Address', [Email()])

class ConfirmTournamentForm(FlaskForm):
    add_test = BooleanField('Include Test Tournament?')
    stripe_token = HiddenField('Stripe Token')
    password = PasswordField(
            'Password',
            [
                DataRequired(),
                EqualTo('confirm', message='Passwords must match'),
                validate_password
            ])
    confirm = PasswordField('Confirm Password')

class ExtendTournamentForm(FlaskForm):
    stripe_token = HiddenField('Stripe Token')
    days = IntegerField('Number of Days to Add', [DataRequired(), validate_days])
