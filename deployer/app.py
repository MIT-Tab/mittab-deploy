from os.path import join, dirname

from flask import Flask, render_template
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


@app.route('/tournaments/new', methods=['GET'])
def hello():
    return render_template('new.html',
                           title='Create a Tournament',
                           form=TournamentForm())


@app.route('/tournaments', methods=['POST'])
def create_tournament():
    print("GOT A RESPONSE")


if __name__ == '__main__':
    app.run()
