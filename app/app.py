from os.path import join, dirname

from flask import Flask
from flask import request, render_template
from flask_sqlalchemy import SQLAlchemy

from config.base import BaseConfig

app = Flask(__name__)
app.config.from_object(BaseConfig)
db = SQLAlchemy(app)

from app.models import *
from app.tasks import *


@app.route("/")
def hello():
    tournaments = Tournament.query.all()
    return "Tournaments: %s" % ', '.join([ t.name for t in tournaments ])

if __name__ == '__main__':
    app.run()
