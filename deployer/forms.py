import re

from datetime import datetime

from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SelectField, BooleanField, \
        HiddenField, DateField, IntegerField
from wtforms.validators import DataRequired, EqualTo, Email, ValidationError, Length, Optional

from deployer.clients import forum
from deployer.models import App
from deployer.config import REPO_OPTIONS

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
    if form.add_test.data and App.query.filter_by(name=field.data.lower() + '-test', active=True).count() > 0:
        raise ValidationError('An active test tournament with that name already exists')

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
    price_quote = HiddenField('Price quote')
    tournament_start_date = DateField(
        'Tournament start date (optional)', [Optional()], format='%Y-%m-%d',
    )
    name = StringField(
            'Tournament Name',
            [DataRequired(), validate_name, validate_unique_name, Length(max=19)]
            )
    forum_mode = SelectField(
        'APDA Forum',
        choices=[
            ('none', 'Not an APDA-sanctioned tournament'),
            ('existing', 'Use an existing forum topic'),
            ('new', 'Create a forum topic'),
        ],
        default='none',
    )
    forum_topic_url = StringField('Existing forum topic URL')
    forum_topic_title = StringField('New forum topic name')

    repo_options = SelectField(
            'MIT-Tab Version',
            choices=[(key, REPO_OPTIONS[key]['name']) for key in REPO_OPTIONS.keys()],
            default='default'
            )
    deletion_date = DateField(
            'Deletion Date',
            [DataRequired(), validate_date],
            format='%Y-%m-%d')
    email = StringField('Email Address', [Email()])
    add_test = BooleanField('Include Test Tournament?')
    stripe_token = HiddenField('Stripe Token')
    password = PasswordField(
            'Password',
            [
                DataRequired(),
                validate_password
            ])

    def validate(self, extra_validators=None):
        valid = super().validate(extra_validators)
        mode = self.forum_mode.data
        if mode not in ('existing', 'new'):
            return valid
        if not forum.configured():
            self.forum_mode.errors.append('APDA Forum publishing is currently unavailable.')
            return False
        if mode == 'existing':
            url = (self.forum_topic_url.data or '').strip()
            if len(url) > 512 or not forum.is_forum_url(url):
                self.forum_topic_url.errors.append('Enter a valid APDA Forum topic URL.')
                return False
        if mode == 'new':
            title = (self.forum_topic_title.data or '').strip()
            if not title or len(title) > 200:
                self.forum_topic_title.errors.append('Enter a topic name of 1 to 200 characters.')
                return False

        return valid

class ExtendTournamentForm(FlaskForm):
    stripe_token = HiddenField('Stripe Token')
    days = IntegerField('Number of Days to Add', [DataRequired(), validate_days])
