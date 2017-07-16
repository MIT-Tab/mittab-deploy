import re

from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField
from wtforms.validators import DataRequired, EqualTo, Email, ValidationError

from deployer.models import Droplet

def validate_name(form, field):
    pattern = re.compile('^[\w\d\-]+$')
    if not pattern.match(field.data):
        raise ValidationError('Name contains invalid characters')

def validate_unique_name(form, field):
    if Droplet.query.filter_by(name=field.data.lower()).count() > 0:
        raise ValidationError('A tournament with that name already exists')

class TournamentForm(FlaskForm):
    name = StringField('Tournament Name', [DataRequired(), validate_name, validate_unique_name])
    email = StringField('Email Address', [Email()])
    password = PasswordField('Password', [
        DataRequired(),
        EqualTo('confirm', message='Passwords must match')
    ])
    confirm = PasswordField('Confirm Password')
