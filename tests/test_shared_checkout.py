from datetime import datetime, timedelta
from decimal import Decimal
import unittest
from unittest.mock import patch

from test_public import AppConfig
from deployer import create_app, pricing
from deployer.extensions import db
from deployer.models import App

CLUSTER = "b7f112b1-26f1-46d8-a0dd-cc151c6d208f"


class SharedConfig(AppConfig):
    SECRET_KEY = "synthetic-checkout-secret"
    SHARED_MYSQL_ENABLED = True
    SHARED_MYSQL_CLUSTER_ID = CLUSTER


class PricingTest(unittest.TestCase):
    def test_tariff_covers_documented_two_to_three_week_annual_budget(self):
        # Forecast, not historical profit: 57 main + six tests, six normal
        # days, 28/29 registration adopters and three early test sites.
        D = Decimal
        now = pricing.today()
        for adopters in (28, 29):
            for lead in range(14, 22):
                start = now + timedelta(days=lead)
                registration = pricing.quote(
                    start + timedelta(days=5), start, shared=True
                )
                gross = (
                    D(57 - adopters) * 21
                    + D(adopters) * registration.total_cents / 100
                    + 36
                )
                operating = (
                    D("853.80")
                    + D("181.80")
                    + D(12) / 28 * (63 * 6 + (adopters + 3) * lead)
                )
                surplus = gross * D(".971") - D(".30") * 57 - operating
                self.assertGreaterEqual(surplus, 80, (adopters, lead, surplus))

    def test_base_remains_fifteen_dollars_for_every_registration_window(self):
        now = pricing.today()
        for lead in range(22):
            start = now + timedelta(days=lead)
            for add_test in (False, True):
                result = pricing.quote(
                    start + timedelta(days=5), start, add_test, shared=True
                )
                self.assertEqual(result.fixed_cents, 1500, (lead, add_test))

    def test_legacy_and_shared_classic_have_identical_price(self):
        now = pricing.today()
        deletion = now + timedelta(days=5)
        self.assertEqual(pricing.quote(deletion).total_cents, 2100)
        self.assertEqual(pricing.quote(deletion, shared=True).total_cents, 2100)

    def test_full_size_registration_prices_and_optional_test(self):
        now = pricing.today()
        for lead, expected in [(1, 2175), (14, 3150), (21, 3675)]:
            start = now + timedelta(days=lead)
            result = pricing.quote(start + timedelta(days=5), start, shared=True)
            self.assertEqual(result.total_cents, expected)
            test = pricing.quote(start + timedelta(days=5), start, True, shared=True)
            self.assertEqual(test.total_cents, expected + 600)

    def test_same_day_start_has_no_registration_surcharge(self):
        now = pricing.today()
        self.assertEqual(
            pricing.quote(now + timedelta(days=5), now, shared=True).total_cents, 2100
        )

    def test_invalid_and_unavailable_registration_windows(self):
        now = pricing.today()
        for start, end, shared in [
            (now - timedelta(days=1), now + timedelta(days=5), True),
            (now + timedelta(days=6), now + timedelta(days=5), True),
            (now + timedelta(days=22), now + timedelta(days=27), True),
            (now + timedelta(days=1), now + timedelta(days=5), False),
        ]:
            with self.assertRaises(ValueError):
                pricing.quote(end, start, shared=shared)


class SharedCheckoutTest(unittest.TestCase):
    def setUp(self):
        self.app = create_app(SharedConfig)
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()
        self.client = self.app.test_client()
        self.start = pricing.today() + timedelta(days=14)
        self.end = self.start + timedelta(days=5)

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.context.pop()

    def booking(self, add_test=True):
        result = self.client.get(
            "/tournaments/quote",
            query_string={
                "deletion_date": self.end.isoformat(),
                "tournament_start_date": self.start.isoformat(),
                "add_test": str(add_test).lower(),
            },
        )
        self.assertEqual(result.status_code, 200)
        data = {
            "name": "new-open",
            "password": "Simple12",
            "email": "tab@example.com",
            "repo_options": "default",
            "deletion_date": self.end.isoformat(),
            "tournament_start_date": self.start.isoformat(),
            "stripe_token": "tok_synthetic",
            "price_quote": result.get_json()["price_quote"],
        }
        if add_test:
            data["add_test"] = "y"
        return data

    @patch("deployer.checkout.deploy_tournament.delay")
    @patch("deployer.checkout.stripe.charge", return_value="ch_synthetic")
    @patch("deployer.checkout.shared_mysql.booking_capacity")
    def test_checkout_records_restricted_ownership_and_price_before_queueing(
        self, capacity, charge, queue
    ):
        data = self.booking()
        response = self.client.post("/tournaments/new", data=data)
        self.assertEqual(response.status_code, 302)
        main = App.query.filter_by(name="new-open").one()
        test = App.query.filter_by(parent_id=main.id).one()
        self.assertEqual(main.database_mode, "shared")
        self.assertEqual(main.shared_cluster_id, CLUSTER)
        self.assertRegex(main.shared_tenant, r"^nt[0-9a-f]{24}$")
        self.assertNotEqual(main.shared_tenant, test.shared_tenant)
        self.assertTrue(test.active)
        self.assertEqual(main.amount_paid_cents, 3750)
        self.assertEqual(main.stripe_charge_id, "ch_synthetic")
        self.assertEqual(main.pricing_version, pricing.SHARED)
        self.assertEqual(queue.call_count, 2)
        capacity.assert_called_once_with(2)
        self.assertEqual(charge.call_args.kwargs["idempotency_key"], main.checkout_key)

    @patch("deployer.checkout.deploy_tournament.delay")
    @patch("deployer.checkout.stripe.charge", return_value="ch_synthetic")
    @patch("deployer.checkout.shared_mysql.booking_capacity")
    def test_replayed_checkout_does_not_charge_or_deploy_twice(
        self, _capacity, charge, queue
    ):
        data = self.booking()
        self.client.post("/tournaments/new", data=data)
        again = self.client.post("/tournaments/new", data=data)
        self.assertEqual(again.status_code, 302)
        self.assertEqual(App.query.count(), 2)
        self.assertEqual(charge.call_count, 1)
        self.assertEqual(queue.call_count, 2)

    @patch("deployer.checkout.stripe.charge")
    def test_tampered_dates_never_charge(self, charge):
        data = self.booking()
        data["deletion_date"] = (self.end + timedelta(days=1)).isoformat()
        self.client.post("/tournaments/new", data=data)
        charge.assert_not_called()
        self.assertEqual(App.query.count(), 0)

    @patch("deployer.checkout.stripe.charge")
    def test_disabled_shared_mode_rejects_previously_quoted_registration(self, charge):
        data = self.booking()
        self.app.config["SHARED_MYSQL_ENABLED"] = False
        self.client.post("/tournaments/new", data=data)
        charge.assert_not_called()

    @patch("deployer.checkout.stripe.charge")
    @patch(
        "deployer.checkout.shared_mysql.booking_capacity",
        side_effect=ValueError("at capacity"),
    )
    def test_capacity_is_checked_before_payment(self, _capacity, charge):
        self.client.post("/tournaments/new", data=self.booking())
        charge.assert_not_called()

    @patch("deployer.checkout.stripe.charge")
    def test_unsigned_price_is_rejected(self, charge):
        data = self.booking()
        data["price_quote"] = "not-a-valid-quote"
        self.client.post("/tournaments/new", data=data)
        charge.assert_not_called()

    @patch("deployer.checkout.stripe.charge")
    def test_unverified_source_branch_is_rejected_before_payment(self, charge):
        data = self.booking()
        data["repo_options"] = "discord"
        self.client.post("/tournaments/new", data=data)
        charge.assert_not_called()

    @patch("deployer.checkout.stripe.charge")
    def test_existing_live_test_name_cannot_be_reused_by_new_checkout(self, charge):
        existing = App(
            "new-open-test", "MIT-Tab/mit-tab", "master", self.end, "other@example.com"
        )
        existing.active = True
        db.session.add(existing)
        db.session.commit()
        self.client.post("/tournaments/new", data=self.booking())
        charge.assert_not_called()
        self.assertEqual(App.query.count(), 1)

    @patch("deployer.clients.stripe.charge", return_value="ch_extension")
    def test_shared_extension_charges_and_extends_both_active_sites(self, charge):
        main = App("paired", "MIT-Tab/mit-tab", "master", self.end, "tab@example.com")
        main.active = True
        main.database_mode = "shared"
        db.session.add(main)
        db.session.flush()
        test = App("paired-test", main.repo_slug, main.branch, self.end, main.email)
        test.active = True
        test.database_mode = "shared"
        test.parent_id = main.id
        db.session.add(test)
        db.session.commit()
        response = self.client.post(
            "/tournaments/%s/extend" % main.id,
            data={"days": "2", "stripe_token": "tok_synthetic"},
        )
        self.assertEqual(response.status_code, 200)
        charge.assert_called_once_with(main.email, "tok_synthetic", 400)
        self.assertEqual(main.deletion_date, self.end + timedelta(days=2))
        self.assertEqual(test.deletion_date, main.deletion_date)

    @patch("deployer.clients.stripe.charge", return_value="ch_extension")
    def test_existing_extension_price_and_database_ownership_are_unchanged(
        self, charge
    ):
        legacy = App(
            "existing", "MIT-Tab/mit-tab", "master", self.end, "tab@example.com"
        )
        legacy.active = True
        db.session.add(legacy)
        db.session.commit()
        response = self.client.post(
            "/tournaments/%s/extend" % legacy.id,
            data={"days": "2", "stripe_token": "tok_synthetic"},
        )
        self.assertEqual(response.status_code, 200)
        charge.assert_called_once_with("tab@example.com", "tok_synthetic", 200)
        self.assertIsNone(legacy.database_mode)
        self.assertIsNone(legacy.shared_cluster_id)
        self.assertEqual(legacy.deletion_date, self.end + timedelta(days=2))

    @patch("deployer.clients.shared_mysql.delete_tournament")
    @patch("deployer.models.delete_app")
    def test_cleanup_dispatch_uses_persisted_mode_not_feature_flag(
        self, legacy_delete, shared_delete
    ):
        legacy = App("legacy", "MIT-Tab/mit-tab", "master", self.end, "tab@example.com")
        pooled = App("pooled", "MIT-Tab/mit-tab", "master", self.end, "tab@example.com")
        pooled.database_mode = "shared"
        db.session.add_all([legacy, pooled])
        db.session.commit()
        self.app.config["SHARED_MYSQL_ENABLED"] = False
        legacy.deactivate()
        pooled.deactivate()
        legacy_delete.assert_called_once_with("legacy")
        shared_delete.assert_called_once_with(pooled)

    @patch("deployer.clients.shared_mysql.delete_tournament")
    def test_cleanup_cannot_race_an_active_provisioning_lease(self, delete):
        pooled = App("pooled", "MIT-Tab/mit-tab", "master", self.end, "tab@example.com")
        pooled.database_mode = "shared"
        pooled.active = True
        pooled.provisioning_until = datetime.utcnow() + timedelta(minutes=15)
        db.session.add(pooled)
        db.session.commit()
        with self.assertRaisesRegex(RuntimeError, "already in progress"):
            pooled.deactivate()
        delete.assert_not_called()
        self.assertTrue(pooled.active)

    @patch(
        "deployer.clients.shared_mysql.delete_tournament",
        side_effect=RuntimeError("uncertain cloud response"),
    )
    def test_failed_cleanup_preserves_active_record_and_releases_lease(self, _delete):
        pooled = App("pooled", "MIT-Tab/mit-tab", "master", self.end, "tab@example.com")
        pooled.database_mode = "shared"
        pooled.active = True
        db.session.add(pooled)
        db.session.commit()
        with self.assertRaisesRegex(RuntimeError, "uncertain cloud response"):
            pooled.deactivate()
        self.assertTrue(pooled.active)
        self.assertIsNone(pooled.provisioning_until)
