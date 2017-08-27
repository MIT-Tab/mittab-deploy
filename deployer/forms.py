import re

from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SelectField, BooleanField
from wtforms.validators import DataRequired, EqualTo, Email, ValidationError

from deployer.models import Droplet
from config.repo_options import options

# Custom validations

def validate_name(form, field):
    pattern = re.compile('^[\w\d\-]+$')
    if not pattern.match(field.data):
        raise ValidationError('Name contains invalid characters')

def validate_unique_name(form, field):
    if Droplet.query.filter_by(name=field.data.lower()).count() > 0:
        raise ValidationError('A tournament with that name already exists')

# Form definition

class TournamentForm(FlaskForm):
    name = StringField('Tournament Name', [DataRequired(), validate_name, validate_unique_name])
    email = StringField('Email Address', [Email()])
    password = PasswordField('Password', [
        DataRequired(),
        EqualTo('confirm', message='Passwords must match')
    ])
    confirm = PasswordField('Confirm Password')
    repo_options = SelectField('MIT-Tab Version',
                               choices=[ (key, options[key]['name']) for key in options.keys() ],
                               default='default')
    add_test = BooleanField('Include Test Tournament?')
