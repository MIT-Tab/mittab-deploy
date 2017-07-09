from flask import render_template
from flask_mail import Message

from deployer.app import mail

def _send_email(subject, recipient, text_body, html_body):
    msg = Message(subject, sender='benmuschol@gmail.com', recipients=[recipient])
    msg.body = text_body
    msg.html = html_body
    return mail.send(msg)

def send_confirmation_email(recipient, tournament_name, password):
    txt = render_template('mail/confirmation.txt',
                          tournament_name=tournament_name,
                          password=password)
    html = render_template('mail/confirmation.html',
                           tournament_name=tournament_name,
                           password=password)
    subject = 'Your MIT-Tab Tournament Has Been Created!'
    return _send_email(subject, recipient, txt, html)

def send_tournament_notification(tournament_name):
    """
    Notify myself when tournaments are created so I'm not clueless
    """
    txt = 'Tournament: %s' % tournament_name
    html = '<p>Tournament: %s</p>' % tournament_name
    subject = 'A tournament has been created'
    return _send_email(subject, 'muschol.b@husky.neu.edu', txt, html)
