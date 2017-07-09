import os

from flask import Flask, render_template, redirect
from flask_sqlalchemy import SQLAlchemy
from flask_hookserver import Hooks
from flask_mail import Mail

from config.base import BaseConfig

app = Flask('deployer')
app.config.from_object(BaseConfig)
db = SQLAlchemy(app)

hooks = Hooks(app, url='/payload')
mail = Mail(app)

from deployer.models import *
from deployer.tasks import *
from deployer.forms import TournamentForm


@app.route('/', methods=['GET'])
def index():
    return render_template('index.html')


@app.route('/tournaments/new', methods=['GET', 'POST'])
def tournament():
    form = TournamentForm()
    if form.validate_on_submit():
        create_tournament.delay(form.name.data, form.password.data, form.email.data)
        return 'Started! In 5-10 minutes, your tournament will be available at {0}.nu-tab.com'.format(form.name.data.lower())

    return render_template('new.html',
                           title='Create a Tournament',
                           form=form)

@hooks.hook('push')
def update(payload, delivery):
    """
    Called via github for all push events. This is used to automate deployments.
    """
    if payload['ref'] == 'refs/heads/master':
        update_repo.delay()
        return ('', 201)
    else:
        return ('', 204)

if __name__ == '__main__':
    app.run()
