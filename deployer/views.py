import os

from flask import render_template, redirect, jsonify, request, flash

from config.repo_options import options
from deployer import hooks
from deployer.models import *
from deployer.tasks import *
from deployer.forms import TournamentForm
from deployer.clients import stripe


@app.route('/', methods=['GET'])
def index():
    return render_template('index.html')


@app.route('/tournaments/new', methods=['GET', 'POST'])
def new_tournament():
    form = TournamentForm()
    if form.validate_on_submit():
        if stripe.charge(request.form['stripeEmail'], request.form['stripeToken']):
            repo_data = options[form.repo_options.data]
            tournament = Tournament(form.name.data,
                                    repo_data['clone_url'],
                                    repo_data['branch'])

            db.session.add(tournament)
            db.session.commit()

            tournament.set_status('Initializing')
            deploy_tournament.delay(tournament.id,
                                    form.password.data,
                                    form.email.data)

            if form.add_test.data:
                deploy_test.delay(tournament.name,
                                tournament.clone_url,
                                tournament.branch)
            return redirect('/tournaments/%s' % tournament.name)
        else:
            flash("""
                  Error processing payment. Contact Ben (email in footer) if
                  the problem persists
                  """)

    return render_template('new.html',
                           stripe_cost=stripe.COST_IN_CENTS,
                           stripe_key=stripe.get_publishable_key(),
                           title='Create a Tournament',
                           form=form)


@app.route('/tournaments/<name>', methods=['GET'])
def show_tournament(name):
    tournament = Tournament.query.filter_by(name=name).order_by(Tournament.id.desc()).first()
    if not tournament:
        return ('', 404)

    return render_template('show.html', tournament=tournament)


@app.route('/tournaments/<name>/status', methods=['GET'])
def tournament_status(name):
    tournament = Tournament.query.filter_by(name=name).order_by(Tournament.id.desc()).first()
    if not tournament:
        return ('', 404)

    return jsonify(status=tournament.status)


@hooks.hook('push')
def update(payload, delivery):
    """
    Called via github for all push events.
    This is used to automate (some of) the deployments.
    """
    if payload['ref'] == 'refs/heads/master':
        update_repo.delay()
        return ('', 201)
    else:
        return ('', 204)

if __name__ == '__main__':
    app.run()
