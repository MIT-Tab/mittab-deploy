import os

from flask import render_template

from deployer import app
from deployer.models import Tournament


@app.route('/admin/tournaments', methods=['GET'])
def admin_index():
    tournaments = Tournament.query.all()
    return render_template('admin/index.html', tournaments=tournaments)

@app.route('/admin/tournaments/:id', methods=['DELETE'])
def delete_tournament(tournament_id):


if __name__ == '__main__':
    app.run()
