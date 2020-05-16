import json
import os

from flask import render_template, redirect, flash, request
import flask_login
from oauthlib.oauth2 import WebApplicationClient
import requests

from deployer import app, login_manager
from deployer.models import Tournament


# Lightweight user object for admin auth since we don't need persistent users
class User(flask_login.UserMixin):
    pass

@login_manager.user_loader
def user_loader(user_id):
    if user_id not in app.config.get('GOOGLE_AUTH_ALLOWED_EMAILS'):
        return

    user = User()
    user.id = user_id

    return user

oauth_client = WebApplicationClient(app.config.get('GOOGLE_CLIENT_ID'))

def get_google_provider_cfg():
    return requests.get('https://accounts.google.com/.well-known/openid-configuration').json()

@app.route('/admin/tournaments', methods=['GET'])
@flask_login.login_required
def admin_index():
    tournaments = Tournament.query.limit(100).order_by(Tournament.created_at.desc())
    return render_template('admin/index.html', tournaments=tournaments)

@app.route('/admin/tournaments/<tournament_id>/delete', methods=['POST'])
@flask_login.login_required
def delete_tournament(tournament_id):
    tournament = Tournament.query.get(int(tournament_id))

    if not tournament.is_test:
        tournament.backup()
    tournament.deactivate()

    if tournament.is_test:
        flash("Tournament %s deleted (without backup)" % tournament.name, "success")
    else:
        flash("Tournament %s deleted (with backup)" % tournament.name, "success")
    return redirect("/admin/tournaments")

@app.route("/admin/oauth-callback")
def callback():
    code = request.args.get("code")
    google_provider_cfg = get_google_provider_cfg()
    token_endpoint = google_provider_cfg["token_endpoint"]
    token_url, headers, body = oauth_client.prepare_token_request(
        token_endpoint,
        authorization_response=request.url.replace("web:8000", "nu-tab.com"),
        redirect_url=request.base_url.replace("web:8000", "nu-tab.com"),
        code=code
    )
    token_response = requests.post(
        token_url,
        headers=headers,
        data=body,
        auth=(app.config.get('GOOGLE_CLIENT_ID'), app.config.get('GOOGLE_CLIENT_SECRET')),
    )
    oauth_client.parse_request_body_response(json.dumps(token_response.json()))
    userinfo_endpoint = google_provider_cfg["userinfo_endpoint"]
    uri, headers, body = oauth_client.add_token(userinfo_endpoint)
    userinfo_response = requests.get(uri, headers=headers, data=body)
    email = userinfo_response.json().get("email")
    if email in app.config.get('GOOGLE_AUTH_ALLOWED_EMAILS'):
        flask_login.login_user(user_loader(email))
        return redirect('/admin/tournaments')
    else:
        return 'Not an authorized account'

@app.route('/admin/login')
def login():
    google_provider_cfg = get_google_provider_cfg()
    authorization_endpoint = google_provider_cfg["authorization_endpoint"]

    if app.config.get("PRODUCTION"):
        redirect_uri = "https://nu-tab.com/admin/oauth-callback"
    else:
        redirect_uri = "http://localhost:5000/admin/oauth-callback"

    request_uri = oauth_client.prepare_request_uri(
        authorization_endpoint,
        redirect_uri=redirect_uri,
        scope=["openid", "email", "profile"],
    )
    return redirect(request_uri)

@login_manager.unauthorized_handler
def unauthorized():
    return 'Login at /admin/login'

if __name__ == '__main__':
    app.run()
