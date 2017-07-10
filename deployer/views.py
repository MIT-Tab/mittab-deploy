import os

from flask import render_template, redirect, jsonify

from deployer import hooks
from deployer.models import *
from deployer.tasks import *
from deployer.forms import TournamentForm


@app.route('/', methods=['GET'])
def index():
    return render_template('index.html')


@app.route('/tournaments/new', methods=['GET', 'POST'])
def new_tournament():
    form = TournamentForm()
    if form.validate_on_submit():
        tournament = Tournament(form.name.data)
        db.session.add(tournament)
        db.session.commit()

        tournament.set_status('initializing')
        deploy_tournament.delay(tournament.id, form.password.data, form.email.data)
        return redirect('/tournaments/%s' % tournament.name)

    return render_template('new.html',
                           title='Create a Tournament',
                           form=form)

@app.route('/tournaments/<name>', methods=['GET'])
def show_tournament(name):
    tournament = Tournament.query.filter_by(name=name).first()
    if not tournament:
        return ('', 404)
    return render_template('show.html', tournament=tournament)


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
