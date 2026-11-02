# Shared MySQL for new bookings

This change shares one **separate, pre-existing tournament MySQL cluster** among
new bookings. Each main/test tournament owns a random schema and a restricted
user. It keeps the normal `professional-xs` 1 GiB web instance throughout.
It does not resize web instances, schedule an upscale, reduce controller costs,
or move an existing tournament's database.

## Existing tournaments

The migration adds nullable columns without backfilling old rows. NULL database
mode means the existing dedicated-database path. Existing instances are never
redeployed, rebound or repriced by this migration. Their extensions remain $1/day.
Cleanup uses each row's persisted mode, not the feature flag. Legacy deletion
refuses shared bindings and the configured pool ID. Shared deletion can delete
only an owned app, schema and user; it has no cluster-delete operation.

## Pricing

Prices are integer cents, calculated and signed by the server before checkout.
Calendar days use UTC; the deletion date is the last included hosting day.

| Booking | Base | Before tournament start | Start through deletion, inclusive |
| --- | ---: | ---: | ---: |
| Classic / start today | $15.00 | — | $1.00/day |
| Advance registration (1–21 days early) | $19.50 | $0.50/day | $1.00/day |

The optional test site adds $1 per normal day, with its advance hosting included
in the main registration charge. Shared main/test extensions extend both sites
and cost $2/day while the test site is active; classic legacy extensions keep
their old behavior. Saved charges include the price version and Stripe charge ID.

For six normal days, classic is $21, two weeks early is $32.50, and three weeks
early is $36 (add $6 for a test site). Deploying early under the old tariff would
have cost $35/$42. **This interim change does not meet the original $21 total
price target.** Sharing SQL alone cannot fund the extra full-size web time at
that price under the budget below. The earlier smaller-web plan's $0.25/day
registration rate is not used here. Web/controller savings remain later work.

### Reproducible budget, not historical profit

Research snapshot: November 2, 2026. Assumptions: 57 main tournaments/year, six
optional tests, six normal days each; 28 or 29 registration adopters with three
early test sites. Fixed existing controller plus Spaces budget $853.80/year;
separate tournament pool $181.80/year; web $12/28 per instance-day; payment fees
2.9% plus $0.30/main checkout. No old dedicated tournament databases remain in
this steady-state scenario. For lead time `L` and adopters `n`:

```
gross = (57-n)*21 + n*(19.50 + 0.50*L + 6) + 6*6
operating = 853.80 + 181.80 + (12/28)*(63*6 + (n+3)*L)
surplus = gross*0.971 - 57*0.30 - operating
```

| Adopters | Early days | Gross | Operating before fees | Surplus after fees |
| ---: | ---: | ---: | ---: | ---: |
| 28 | 14 | $1,555.00 | $1,383.60 | $109.21 |
| 29 | 14 | $1,566.50 | $1,389.60 | $114.37 |
| 28 | 21 | $1,653.00 | $1,476.60 | $111.36 |
| 29 | 21 | $1,668.00 | $1,485.60 | $116.93 |

The pricing regression test evaluates every integer lead time 1–21 with both
adoption counts and requires at least $100 modeled surplus. This is not a
guarantee for different normal durations, adoption, test uptake or a larger pool.
It excludes transition overlap, tax, labor, refunds, disputes, unusual transfer
and other unbudgeted costs. Ben's actual annual profit remains unreconciled.
Zero registration adoption has different economics; it is not covered by the
50% adoption guarantee.

Rate references: [App Platform pricing](https://docs.digitalocean.com/products/app-platform/details/pricing/),
[managed database pricing](https://www.digitalocean.com/pricing/managed-databases),
[generic domestic-card fees](https://stripe.com/pricing). These are modeling
inputs from the research snapshot, not an invoice reconciliation.

## Isolation and admission

DigitalOcean-created users can start with broad privileges. Before binding a
user to an app, provisioning removes role memberships/default roles and grants,
then grants only the specific schema's required DDL/DML privileges (including
schema-only LOCK TABLES for importing older tournament dumps). It requires
TLS, enforces a connection limit and audits SHOW GRANTS. No tenant receives
`doadmin`, global SELECT, CREATE USER, global locks or grant delegation. Tenant
names contain no SQL grant wildcard characters. Administrator TLS verifies both
the provider CA and hostname; credentials are never stored in controller rows.

Default admission is eight **sites** (a paired test consumes another slot),
eight SQL connections/site, plus ten admin connections. Admission checks the
actual server limit, existing schemas and paid pending records under a MySQL
advisory lock. It fails before payment if full/unreachable. Each new shared web
app has two workers and three admitted connections/worker, leaving two SQL
connections for backup/restore. This bounds HTTP concurrency; it does not prove
that a 1 GiB pool can sustain eight busy tournaments. Do not raise limits without
measuring actual concurrent tournament workloads.

Paid ownership records commit before queueing. Signed quote nonces and Stripe
idempotency keys protect checkout replay. A 20-minute persisted lease serializes
provisioning and cleanup. Retries reconcile app identity and exact database/user
bindings; failed startup preserves data and app resources. Backup/restore uses
schema-scoped InnoDB snapshots via the companion MIT-Tab change.

## Rollout and recovery

1. Merge/deploy the companion MIT-Tab restricted-user backup PR first. Only the
   default source branch is offered in shared mode until other branches adopt it.
2. Back up the controller DB and run `uv run --env-file .env flask db upgrade`.
   Deploy this release to both web and Celery processes with the flag **off**.
3. Create a separate MySQL 8 tournament pool, separate from the controller and
   live dedicated clusters. Configure its trusted sources for the deployer and
   tournament apps. The deployer needs API database/user/app operations and SQL
   `doadmin` access; tenant apps must use restricted bindings. Back up this pool.
4. Set `SHARED_MYSQL_CLUSTER_ID` to its UUID; leave `SHARED_MYSQL_ENABLED=false`
   until the canary below passes. Defaults: `SHARED_MYSQL_MAX_TENANTS=8`,
   `SHARED_MYSQL_MAX_CONNECTIONS=8`.
5. Enable shared mode consistently on web/workers. Only **new** bookings share SQL.
   Keep the pool ID configured even when disabling new shared bookings.

A production DigitalOcean canary is **still required**. Local tests do not
exercise the managed service's exact admin restrictions, firewall integration,
App Platform variable binding, startup timing or pool capacity. Before paid use:
create two synthetic tenants on the proposed pool; deploy both through this
controller; verify migrations, initialization, login, registration, tab/round
operations, backups, valid restore and failed-restore recovery; assert each app
reports its own CURRENT_USER()/DATABASE(), cannot read the peer/controller and
cannot acquire global locks. Load both concurrently with the real app settings
and backup activity; measure memory, latency, SQL connections and errors. Test
deleting one through the controller while the other remains usable. Confirm the
pool and unrelated existing dedicated app IDs are unchanged. Check quote and
Stripe test-mode amounts and replay. Disable shared mode if any gate fails.
No paid resource or live tournament was changed for local verification.

Disable the flag to stop new shared bookings; existing shared provisioning and
cleanup continue from recorded ownership. Do not roll workers back to code that
predates shared cleanup while shared records exist. Migration downgrade refuses
while any shared row remains (including inactive history). An uncertain deployment
must be inspected/retried, never “fixed” by deleting the pool. Use the existing
`flask redeploy-tournament <app-id>` command to enqueue a failed paid deployment
without another charge; wait for its lease to expire after a killed worker.
If payment succeeded but queueing failed, records remain available for that
command. Reconcile Stripe before manually replaying a failed DB commit: this
change is not a transactional payment/queue outbox.

## Local verification

Use only a disposable MySQL 8 server whose test administrator may create/drop
users and schemas. The explicit port opt-in prevents accidental integration runs.
DigitalOcean and Stripe HTTP operations are mocked; SQL grants/DDL are real.

```bash
TEST_MYSQL_PORT=33319 uv run --frozen python -m unittest discover -s tests -v
node --test tests/checkout.test.js
```

Coverage includes migration of seeded old rows, legacy pricing/deletion guards,
restricted SQL tenant isolation, grant/role removal, capacity reservations,
partial failure/retry, lease races, signed checkout, replay and stale browser
quotes. The companion PR additionally migrates/initializes two real Django
schemas, submits registrations and tests dump/restore/rollback with both MySQL
and MariaDB command-line clients. Neither suite substitutes for the provider
canary or a production-capacity test.
