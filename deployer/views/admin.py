import os

from flask import render_template, redirect, flash

from deployer import app
from deployer.models import Tournament


@app.route('/admin/tournaments', methods=['GET'])
def admin_index():
    tournaments = Tournament.query.order_by(Tournament.created_at.desc())
    return render_template('admin/index.html', tournaments=tournaments)

@app.route('/admin/tournaments/<tournament_id>/delete', methods=['POST'])
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


if __name__ == '__main__':
    app.run()
