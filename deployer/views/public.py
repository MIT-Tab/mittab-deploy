from datetime import datetime, timedelta

from flask import render_template, redirect, jsonify, request, flash

from config.repo_options import options
from deployer import app as flask_app
from deployer.models import *
from deployer.tasks import *
from deployer.forms import TournamentForm, ConfirmTournamentForm, ExtendTournamentForm
from deployer.clients import stripe


@flask_app.route('/', methods=['GET'])
def index():
    apps = App.query.filter_by(active=True).all()
    return render_template('index.html', tournaments=apps)


@flask_app.route('/tournaments/new', methods=['GET', 'POST'])
def new_tournament():
    form = TournamentForm()
    if form.validate_on_submit():
        repo_data = options[form.repo_options.data]
        app = App(form.name.data,
                  repo_data['repo_slug'],
                  repo_data['branch'],
                  form.deletion_date.data,
                  form.email.data)

        db.session.add(app)
        db.session.commit()

        app.set_status('Confirming payment')
        return redirect('/tournaments/%s/confirm' % app.id)

    return render_template('new.html',
                           title='Create a Tournament',
                           form=form)

@flask_app.route('/tournaments/<app_id>/confirm', methods=['POST', 'GET'])
def confirm_tournament(app_id):
    app = App.query.get(app_id)
    if app is None: return 404
    elif app.confirmed: return ("Tournament already paid for and finalized", 422)

    days_active = (app.deletion_date - datetime.now().date()).days + 1
    fixed_cost = stripe.FIXED_COST
    base_cost = stripe.DAILY_COST * days_active
    test_cost = stripe.DAILY_COST_TEST_TOURNAMENT * days_active
    form = ConfirmTournamentForm()

    if request.method == "POST" and form.validate_on_submit():
        cost = fixed_cost + base_cost + test_cost if form.add_test.data else base_cost + fixed_cost
        if stripe.charge(app.email, form.stripe_token.data, cost):
            app.set_status('Initializing')
            app.active = True
            app.confirmed = True
            db.session.add(app)
            db.session.commit()
            deploy_tournament.delay(app.id, form.password.data)

            if form.add_test.data:
                test_app = App(
                    f"{app.name}-test",
                    app.repo_slug,
                    app.branch,
                    app.deletion_date,
                    app.email,
                )
                db.session.add(test_app)
                db.session.commit()
                deploy_tournament.delay(test_app.id, 'password')
            return redirect('/tournaments/%s' % app.name)
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
                            tournament=app,
                            form=form,
                            stripe_key=stripe.get_publishable_key(),
                            fixed_cost=stripe.FIXED_COST,
                            base_cost=base_cost,
                            test_cost=test_cost)

@flask_app.route('/tournaments/<tournament_id>/extend', methods=['POST', 'GET'])
def extend_tournament(tournament_id):
    app = App.query.get(tournament_id)
    if app is None: return 404
    elif not app.active: return ("Cannot extend an inactive tournament!", 422)
    elif app.is_test: return ("Cannot extend a test tournament!", 422)

    form = ExtendTournamentForm()

    if request.method == "POST" and form.validate_on_submit():
        cost = form.days.data * stripe.DAILY_COST
        if stripe.charge(app.email, form.stripe_token.data, cost):
            app.deletion_date += timedelta(days=form.days.data)
            app.warning_email_sent = False
            db.session.add(app)
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
                            tournament=app,
                            form=form,
                            stripe_key=stripe.get_publishable_key(),
                            daily_cost=stripe.DAILY_COST)

@flask_app.route('/tournaments/<name>', methods=['GET'])
def show_tournament(name):
    app = App.query.filter_by(name=name).order_by(App.id.desc()).first()
    if not app:
        return ('', 404)

    return render_template('show.html', tournament=app)


@flask_app.route('/tournaments/<name>/status', methods=['GET'])
def tournament_status(name):
    app = App.query.filter_by(name=name).order_by(App.id.desc()).first()
    if not app:
        return ('', 404)

    return jsonify(status=app.status)
