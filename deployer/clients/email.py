from flask import render_template
from flask_mail import Message

from deployer import mail


def __send_email(subject, recipient, text_body, html_body):
    msg = Message(subject, sender='benmuschol@gmail.com', recipients=[recipient])
    msg.body = text_body
    msg.html = html_body
    return mail.send(msg)


def send_confirmation(recipient, tournament, password):
    txt = render_template('mail/confirmation.txt',
                          tournament_name=tournament.name,
                          ip_address=tournament.ip_address,
                          password=password)
    html = render_template('mail/confirmation.html',
                           tournament_name=tournament.name,
                           ip_address=tournament.ip_address,
                           password=password)
    subject = 'Your MIT-Tab Tournament Has Been Created!'
    return __send_email(subject, recipient, txt, html)


def send_notification(tournament_name):
    """
    Notify myself when tournaments are created so I'm not clueless
    """
    txt = 'Tournament: {}'.format(tournament_name)
    html = '<p>Tournament: {}</p>'.format(tournament_name)
    subject = 'A tournament has been created'
    return __send_email(subject, 'muschol.b@husky.neu.edu', txt, html)
