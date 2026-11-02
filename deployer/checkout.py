"""Signed, server-calculated prices and persisted ownership for new bookings."""

from datetime import datetime
from contextlib import ExitStack
import uuid

from flask import current_app, jsonify, flash, redirect, render_template, request
from itsdangerous import URLSafeTimedSerializer, BadSignature
from sqlalchemy.exc import IntegrityError

from deployer import pricing
from deployer.clients import shared_mysql, stripe
from deployer.config import REPO_OPTIONS
from deployer.extensions import db
from deployer.forms import TournamentForm
from deployer.models import App
from deployer.tasks import deploy_tournament


def serializer():
    return URLSafeTimedSerializer(current_app.secret_key, salt="tournament-price-v1")


def quote_inputs(deletion, start, add_test):
    return {
        "deletion_date": deletion.isoformat(),
        "tournament_start_date": start.isoformat() if start else None,
        "add_test": bool(add_test),
        "shared": shared_mysql.enabled(),
        "on_date": pricing.today().isoformat(),
    }


def quote_route():
    try:
        deletion = datetime.strptime(
            request.args.get("deletion_date", ""), "%Y-%m-%d"
        ).date()
        raw_start = request.args.get("tournament_start_date")
        start = datetime.strptime(raw_start, "%Y-%m-%d").date() if raw_start else None
        add_test = request.args.get("add_test") == "true"
        result = pricing.quote(deletion, start, add_test, shared=shared_mysql.enabled())
        payload = quote_inputs(deletion, start, add_test)
        payload.update(quote=result.as_dict(), key=uuid.uuid4().hex)
        response = result.as_dict()
        response["price_quote"] = serializer().dumps(payload)
        return jsonify(response)
    except ValueError as exc:
        return jsonify(error=str(exc)), 422


def render_page(form):
    return render_template(
        "new.html",
        title="Create a Tournament",
        form=form,
        stripe_key=stripe.get_publishable_key(),
        shared_enabled=shared_mysql.enabled(),
    )


def new_tournament():
    form = TournamentForm()
    if shared_mysql.enabled():
        # Alternate source branches must adopt the restricted-user backup
        # contract before they can be offered on a shared cluster.
        form.repo_options.choices = [("default", REPO_OPTIONS["default"]["name"])]
    payload = None
    if request.method == "POST":
        try:
            payload = serializer().loads(form.price_quote.data or "", max_age=1800)
            existing = App.query.filter_by(checkout_key=payload["key"]).first()
            if existing:
                if (
                    existing.name != (form.name.data or "").lower()
                    or existing.email != form.email.data
                ):
                    raise ValueError("Checkout belongs to a different tournament")
                return redirect("/tournaments/%s" % existing.name)
        except (BadSignature, KeyError, TypeError, ValueError):
            flash("Please refresh the price before submitting payment.", "danger")
            payload = None

    if not form.validate_on_submit() or payload is None:
        return render_page(form)
    try:
        result = pricing.quote(
            form.deletion_date.data,
            form.tournament_start_date.data,
            form.add_test.data,
            shared=shared_mysql.enabled(),
        )
        expected = quote_inputs(
            form.deletion_date.data, form.tournament_start_date.data, form.add_test.data
        )
        if (
            any(payload.get(k) != v for k, v in expected.items())
            or payload["quote"] != result.as_dict()
        ):
            raise ValueError("The price changed; refresh the quote before paying")
    except (ValueError, RuntimeError) as exc:
        flash(str(exc), "danger")
        return render_page(form)
    with ExitStack() as admission:
        if shared_mysql.enabled():
            try:
                admission.enter_context(
                    shared_mysql.booking_capacity(2 if form.add_test.data else 1)
                )
            except Exception:
                current_app.logger.exception(
                    "Shared hosting capacity check failed before payment"
                )
                flash(
                    "Hosting is temporarily unavailable. Please try again later; no payment was taken.",
                    "danger",
                )
                return render_page(form)
        return complete_booking(form, payload, result)


def complete_booking(form, payload, result):
    repo = REPO_OPTIONS[form.repo_options.data]
    app = App(
        form.name.data,
        repo["repo_slug"],
        repo["branch"],
        form.deletion_date.data,
        form.email.data,
    )
    app.active = True
    app.confirmed = True
    app.pricing_version = result.version
    app.tournament_start_date = form.tournament_start_date.data
    app.checkout_key = payload["key"]
    app.amount_paid_cents = result.total_cents
    if shared_mysql.enabled():
        app.database_mode = "shared"
        app.shared_cluster_id = shared_mysql.cluster_id()
        app.shared_tenant = shared_mysql.new_tenant()

    payment = stripe.charge(
        app.email,
        form.stripe_token.data,
        result.total_cents,
        idempotency_key=app.checkout_key,
    )
    if not payment:
        flash(
            "Payment could not be processed. Please contact support if you were charged.",
            "danger",
        )
        return render_page(form)

    app.stripe_charge_id = payment if isinstance(payment, str) else None
    db.session.add(app)
    try:
        db.session.flush()
    except IntegrityError:
        db.session.rollback()
        existing = App.query.filter_by(checkout_key=payload["key"]).first()
        if existing is None:
            raise
        return redirect("/tournaments/%s" % existing.name)

    test_app = None
    if form.add_test.data:
        test_app = App(
            app.name + "-test", app.repo_slug, app.branch, app.deletion_date, app.email
        )
        test_app.active = True
        test_app.parent_id = app.id
        test_app.database_mode = app.database_mode
        test_app.shared_cluster_id = app.shared_cluster_id
        test_app.shared_tenant = (
            shared_mysql.new_tenant() if app.database_mode == "shared" else None
        )
        test_app.pricing_version = app.pricing_version
        test_app.tournament_start_date = app.tournament_start_date
        db.session.add(test_app)
    db.session.commit()
    # Commit both ownership records before any worker can see either task.
    deploy_tournament.delay(app.id, form.password.data)
    if test_app:
        deploy_tournament.delay(test_app.id, form.password.data)
    return redirect("/tournaments/%s" % app.name)
