import os

from flask import Flask, render_template, redirect
from flask_sqlalchemy import SQLAlchemy

from config.base import BaseConfig

app = Flask('deployer')
app.config.from_object(BaseConfig)
db = SQLAlchemy(app)

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
        create_tournament.delay(form.name.data, form.password.data)
        return 'Started! In 5-10 minutes, your tournament will be available at {0}.nu-tab.com'.format(form.name.data.lower())

    return render_template('new.html',
                           title='Create a Tournament',
                           form=form)

@app.route('/update', methods=['POST'])
def update():
    data = request.get_json()
    if data['ref'] == 'refs/heads/master':
        os.system('./bin/update')
        return ('', 201)
    else:
        return ('', 204)


if __name__ == '__main__':
    app.run()
