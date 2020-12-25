from datetime import datetime, timedelta
import os

from flask import render_template, redirect, jsonify, request, flash

from config.repo_options import options
from deployer import app
from deployer.models import *
from deployer.tasks import *
from deployer.forms import TournamentForm, ConfirmTournamentForm, ExtendTournamentForm
from deployer.clients import stripe


@app.route('/', methods=['GET'])
def index():
    tournaments = Tournament.query.filter_by(active=True).all()
    return render_template('index.html', tournaments=tournaments)


@app.route('/tournaments/new', methods=['GET', 'POST'])
def new_tournament():
    form = TournamentForm()
    if form.validate_on_submit():
        repo_data = options[form.repo_options.data]
        tournament = Tournament(form.name.data,
                                repo_data['clone_url'],
                                repo_data['branch'],
                                form.deletion_date.data,
                                form.email.data)

        db.session.add(tournament)
        db.session.commit()

        tournament.set_status('Confirming payment')
        return redirect('/tournaments/%s/confirm' % tournament.id)

    return render_template('new.html',
                           title='Create a Tournament',
                           form=form)

@app.route('/tournaments/<tournament_id>/confirm', methods=['POST', 'GET'])
def confirm_tournament(tournament_id):
    tournament = Tournament.query.get(tournament_id)
    if tournament is None: return 404
    elif tournament.confirmed: return ("Tournament already paid for and finalized", 422)

    days_active = (tournament.deletion_date - datetime.now().date()).days + 1
    base_cost = stripe.DAILY_COST * days_active
    test_cost = stripe.DAILY_COST_TEST_TOURNAMENT * days_active
    form = ConfirmTournamentForm()

    if request.method == "POST" and form.validate_on_submit():
        cost = base_cost + test_cost if form.add_test.data else base_cost
        if stripe.charge(tournament.email, form.stripe_token.data, cost):
            tournament.set_status('Initializing')
            tournament.confirmed = True
            db.session.add(tournament)
            db.session.commit()
            deploy_tournament.delay(tournament.id, form.password.data)

            if form.add_test.data:
                deploy_test.delay(tournament.name,
                                  tournament.clone_url,
                                  tournament.branch,
                                  tournament.email)
            return redirect('/tournaments/%s' % tournament.name)
        else:
            flash(
                """An error occurred while processing payment info.
                   Contact Ben via the link in the footer if the problem
                   persists.""",
                "danger"
            )

    form.stripe_token.data = None
    return render_template('confirm.html',
                            title='Confirm Details',
                            tournament=tournament,
                            form=form,
                            stripe_key=stripe.get_publishable_key(),
                            base_cost=base_cost,
                            test_cost=test_cost)

@app.route('/tournaments/<tournament_id>/extend', methods=['POST', 'GET'])
def extend_tournament(tournament_id):
    tournament = Tournament.query.get(tournament_id)
    if tournament is None: return 404
    elif not tournament.active: return ("Cannot extend an inactive tournament!", 422)
    elif tournament.is_test: return ("Cannot extend a test tournament!", 422)

    form = ExtendTournamentForm()

    if request.method == "POST" and form.validate_on_submit():
        cost = form.days.data * stripe.DAILY_COST
        if stripe.charge(tournament.email, form.stripe_token.data, cost):
            tournament.deletion_date += timedelta(days=form.days.data)
            tournament.warning_email_sent = False
            db.session.add(tournament)
            db.session.commit()
            flash("Tournament extended successfully!", "success")
        else:
            flash(
                """An error occurred while processing payment info.
                   Contact Ben via the link in the footer if the problem
                   persists.""",
                "danger"
            )

    form.stripe_token.data = None
    return render_template('extend.html',
                            title='Extend Tournament',
                            tournament=tournament,
                            form=form,
                            stripe_key=stripe.get_publishable_key(),
                            daily_cost=stripe.DAILY_COST)

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


if __name__ == '__main__':
    app.run()
