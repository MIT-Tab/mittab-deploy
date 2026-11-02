from datetime import datetime, timedelta

from flask import Blueprint, jsonify, render_template, redirect, request, flash

from deployer.config import REPO_OPTIONS
from deployer.extensions import db
from deployer.models import *
from deployer.tasks import *
from deployer.forms import TournamentForm, ExtendTournamentForm
from deployer.clients import stripe

bp = Blueprint('public', __name__)


@bp.route('/', methods=['GET'])
def index():
    apps = App.query.filter_by(active=True).all()
    return render_template('index.html', tournaments=apps)


@bp.route('/api/tournaments', methods=['GET'])
def tournament_directory():
    """List deployed Mit-Tab instances for Black Rod's live-results cache."""
    apps = App.query.filter_by(active=True).all()
    return jsonify({
        "tournaments": [
            {"name": app.name, "url": app.url}
            for app in apps
            if app.status == "Deployed" and not app.is_test
        ]
    })


@bp.route('/tournaments/quote', methods=['GET'])
def tournament_quote():
    from deployer.checkout import quote_route
    return quote_route()


@bp.route('/tournaments/new', methods=['GET', 'POST'])
def new_tournament():
    from deployer.checkout import new_tournament as create_tournament
    return create_tournament()


@bp.route('/tournaments/<tournament_id>/extend', methods=['POST', 'GET'])
def extend_tournament(tournament_id):
    app = App.query.get(tournament_id)
    if app is None: return 404
    elif not app.active: return ("Cannot extend an inactive tournament!", 422)
    elif app.is_test: return ("Cannot extend a test tournament!", 422)

    form = ExtendTournamentForm()
    paired_tests = (App.query.filter_by(parent_id=app.id, active=True).all()
                    if app.database_mode == 'shared' else [])
    extension_daily_cost = stripe.DAILY_COST * (1 + len(paired_tests))

    if request.method == "POST" and form.validate_on_submit():
        cost = form.days.data * extension_daily_cost
        if stripe.charge(app.email, form.stripe_token.data, cost):
            app.deletion_date += timedelta(days=form.days.data)
            app.warning_email_sent = False
            db.session.add(app)
            for test_app in paired_tests:
                test_app.deletion_date = app.deletion_date
                test_app.warning_email_sent = False
                db.session.add(test_app)
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
                            daily_cost=extension_daily_cost)

@bp.route('/tournaments/<name>', methods=['GET'])
def show_tournament(name):
    app = App.query.filter_by(name=name).order_by(App.id.desc()).first()
    if not app:
        return ('', 404)

    return render_template('show.html', tournament=app)


@bp.route('/tournaments/<name>/status', methods=['GET'])
def tournament_status(name):
    app = App.query.filter_by(name=name).order_by(App.id.desc()).first()
    if not app:
        return ('', 404)

    return {'status': app.status}
