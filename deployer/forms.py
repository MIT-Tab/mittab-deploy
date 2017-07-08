import re

from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField
from wtforms.validators import DataRequired, EqualTo, Email, ValidationError

def validate_name(form, field):
    pattern = re.compile('^[\w\d\-]+$')
    if not pattern.match(field.data):
        raise ValidationError('Name contains invalid characters')

class TournamentForm(FlaskForm):
    name = StringField('Tournament Name', [DataRequired(), validate_name])
    email = StringField('Email Address', [Email()])
    password = PasswordField('Password', [
        DataRequired(),
        EqualTo('confirm', message='Passwords must match')
    ])
    confirm = PasswordField('Confirm Password')
