const {test} = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');

function page() {
    const inputs = {};
    for (const name of ['deletion_date', 'tournament_start_date', 'add_test', 'price_quote', 'stripe_token', 'email']) {
        inputs[name] = {value: '', checked: false, events: {}, addEventListener(event, callback) {this.events[event] = callback;}};
    }
    const form = {elements: inputs, dataset: {quoteUrl: '/tournaments/quote', stripeKey: 'pk_test'}, events: {},
        addEventListener(event, callback) {this.events[event] = callback;}, submit() {this.submitted = true;}};
    const button = {disabled: true, textContent: ''};
    const elements = {'tournament-form': form, submit_button: button,
        'price-breakdown': {textContent: ''}, 'price-error': {textContent: ''}};
    const requests = [];
    const opened = [];
    const context = {
        document: {getElementById(id) {return elements[id];}}, URLSearchParams,
        window: {StripeCheckout: {configure() {return {open(options) {opened.push(options);}, close() {}};}}, addEventListener() {}},
        fetch(url) {return new Promise(resolve => requests.push({url, resolve}));}
    };
    vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../deployer/static/checkout.js'), 'utf8'), context);
    return {inputs, form, button, requests, opened, elements};
}
const quote = (amount, token) => ({fixed_cents: 1950, registration_days: 14, registration_daily_cents: 50,
    normal_days: 6, normal_daily_cents: 100, test_days: 0, total_cents: amount, price_quote: token});

test('checkout uses the exact server quote and signed token', async () => {
    const p = page();
    p.inputs.deletion_date.value = '2026-11-21';
    const complete = p.inputs.deletion_date.events.change();
    assert.equal(p.button.disabled, true);
    p.requests[0].resolve({ok: true, async json() {return quote(3250, 'signed');}});
    await complete;
    assert.equal(p.inputs.price_quote.value, 'signed');
    assert.equal(p.button.textContent, 'Confirm & Pay $32.50');
    p.form.events.submit({preventDefault() {}});
    assert.equal(p.opened[0].amount, 3250);
});

test('an old quote response cannot overwrite the newly selected dates', async () => {
    const p = page();
    p.inputs.deletion_date.value = '2026-11-21';
    const first = p.inputs.deletion_date.events.change();
    p.inputs.deletion_date.value = '2026-11-28';
    const second = p.inputs.deletion_date.events.change();
    p.requests[1].resolve({ok: true, async json() {return quote(3950, 'new');}});
    await second;
    p.requests[0].resolve({ok: true, async json() {return quote(3250, 'old');}});
    await first;
    assert.equal(p.inputs.price_quote.value, 'new');
    assert.equal(p.button.textContent, 'Confirm & Pay $39.50');
});

test('a rejected price clears the old token and prevents checkout', async () => {
    const p = page();
    p.inputs.price_quote.value = 'old';
    p.inputs.deletion_date.value = '2026-11-21';
    const complete = p.inputs.deletion_date.events.change();
    p.requests[0].resolve({ok: false, async json() {return {error: 'Invalid dates'};}});
    await complete;
    assert.equal(p.inputs.price_quote.value, '');
    assert.equal(p.button.disabled, true);
    p.form.events.submit({preventDefault() {}});
    assert.equal(p.opened.length, 0);
});
