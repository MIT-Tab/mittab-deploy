import time
import logging
import os
import sys
from datetime import datetime, timedelta

from celery.schedules import crontab
from tenacity import retry, stop_after_attempt, wait_fixed

from deployer.extensions import db, celery
from deployer.clients import email, digital_ocean
from deployer.models import App

logger = logging.getLogger(__name__)
handler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.INFO)


class ServerNotReadyError(Exception):
    pass


class SetupFailedError(Exception):
    pass


class BackupFailedError(Exception):
    pass


@celery.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    if os.environ.get('DEPLOYER_PROCESS') == 'celery':
        sender.add_periodic_task(
            crontab(hour=10, minute=30),
            delete_apps.s()
        )

@celery.task()
def deploy_tournament(app_id, password):
    app = App.query.get(app_id)
    if app.database_mode == 'shared' and (not app.active or app.status == 'Deployed'):
        return

    completed = deploy_app(app, password)
    if app.database_mode == 'shared' and completed is False:
        return
    email.send_confirmation(app, password)
    email.send_notification(app.name)


@retry(stop=stop_after_attempt(5), wait=wait_fixed(300))
def deploy_app(app, password):
    if app.database_mode == 'shared':
        return deploy_shared_app(app, password)
    try:
        app.active = True
        app.temporary_url = None
        app.set_status('Creating database')
        db = digital_ocean.create_database(app.name)

        time.sleep(5 * 60)

        app.set_status('Creating server')
        result = digital_ocean.create_app(app.name, password, db, app.repo_slug, app.branch)

        app.set_status('Waiting for server to deploy')
        app.temporary_url = digital_ocean.wait_for_app(result['app']['id'])

        app.set_status('Deployed')
    except Exception as e:
        logger.error(f"Error deploying {app.name}: {e}", exc_info=True)
        app.set_status('An error occurred. Retrying up to 5 times')
        app.deactivate()
        raise e


def deploy_shared_app(app, password):
    from deployer.clients import shared_mysql
    now = datetime.utcnow()
    # A persisted lease prevents duplicate Celery deliveries from revoking a
    # tenant user's grants while another worker is starting the same app.
    acquired = App.query.filter(
        App.id == app.id, App.active.is_(True), App.status != 'Deployed',
        db.or_(App.provisioning_until.is_(None), App.provisioning_until < now),
    ).update({'provisioning_until': now + timedelta(minutes=20)}, synchronize_session=False)
    db.session.commit()
    if not acquired:
        return False
    try:
        resource = shared_mysql.find_app(app)
        if resource is None:
            app.set_status('Creating shared database')
            database = shared_mysql.ensure_database(app)
            app.set_status('Creating server')
            resource = digital_ocean.create_app(
                app.name, password, database, app.repo_slug, app.branch,
            )['app']
        app.cloud_app_id = resource['id']
        db.session.add(app)
        db.session.commit()
        app.temporary_url = digital_ocean.wait_for_app(app.cloud_app_id, timeout=900)
        app.set_status('Deployed')
        return True
    except Exception:
        # An uncertain provider response is not permission to delete an app or
        # its data. Retries reconcile ownership and retain partial resources.
        app.set_status('An error occurred. Retrying up to 5 times')
        raise
    finally:
        app.provisioning_until = None
        db.session.add(app)
        db.session.commit()

@celery.task()
def delete_apps():
    apps = App.query.filter_by(active=True).all()
    current_date = datetime.now().date()
    logger.info("Checking {} apps for deletion".format(len(apps)))

    for app in apps:
        if app.deletion_date < current_date and app.warning_email_sent:
            try:
                app.deactivate()
                app.set_status('Deleted')
                logger.info("Successfully deleted {}".format(app.name))
            except Exception as e:
                logger.error("Error deleting {}".format(app.name), exc_info=True)
                app.set_status('Error while deleting')
        elif (app.deletion_date - current_date).days <= 3 and \
                not app.warning_email_sent:
            logger.info("Sending warning email to {}".format(app.name))
            email.send_warning(app)
            app.warning_email_sent = True
            db.session.add(app)
            db.session.commit()
