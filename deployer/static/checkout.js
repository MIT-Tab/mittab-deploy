/* The server calculates and signs every price; no second date formula in JS. */
(() => {
    const form = document.getElementById('tournament-form');
    if (!form) return;
    const button = document.getElementById('submit_button');
    const breakdown = document.getElementById('price-breakdown');
    const error = document.getElementById('price-error');
    let quote = null;
    let sequence = 0;
    const dollars = cents => '$' + (cents / 100).toFixed(2);
    const handler = window.StripeCheckout ? window.StripeCheckout.configure({
        key: form.dataset.stripeKey,
        locale: 'auto',
        token(token) {
            form.elements.stripe_token.value = token.id;
            button.disabled = true;
            button.textContent = 'Processing payment...';
            form.submit();
        },
        closed() { if (!form.elements.stripe_token.value) button.disabled = !quote; }
    }) : null;

    async function refreshPrice() {
        const current = ++sequence;
        quote = null;
        form.elements.price_quote.value = '';
        form.elements.stripe_token.value = '';
        button.disabled = true;
        button.textContent = 'Choose dates';
        error.textContent = '';
        if (!form.elements.deletion_date.value) return;
        const params = new URLSearchParams({
            deletion_date: form.elements.deletion_date.value,
            add_test: String(form.elements.add_test.checked)
        });
        if (form.elements.tournament_start_date?.value) {
            params.set('tournament_start_date', form.elements.tournament_start_date.value);
        }
        button.textContent = 'Calculating price...';
        try {
            const response = await fetch(form.dataset.quoteUrl + '?' + params, {cache: 'no-store'});
            const data = await response.json();
            if (current !== sequence) return;
            if (!response.ok) throw new Error(data.error || 'Could not calculate the price.');
            quote = data;
            form.elements.price_quote.value = data.price_quote;
            const items = [dollars(data.fixed_cents) + ' base'];
            if (data.registration_days) items.push(data.registration_days + ' registration days × ' + dollars(data.registration_daily_cents));
            items.push(data.normal_days + ' normal days × ' + dollars(data.normal_daily_cents));
            if (data.test_days) items.push(data.test_days + ' test days × ' + dollars(data.normal_daily_cents));
            breakdown.textContent = items.join(' + ') + ' = ' + dollars(data.total_cents);
            button.textContent = 'Confirm & Pay ' + dollars(data.total_cents);
            button.disabled = false;
        } catch (problem) {
            if (current !== sequence) return;
            breakdown.textContent = 'Please check your dates.';
            error.textContent = problem.message;
            button.textContent = 'Check dates';
        }
    }
    ['deletion_date', 'tournament_start_date', 'add_test'].forEach(name => {
        form.elements[name]?.addEventListener('change', refreshPrice);
    });
    form.addEventListener('submit', event => {
        event.preventDefault();
        if (!quote || button.disabled) return;
        if (!handler) {
            error.textContent = 'Payments are temporarily unavailable. Please reload the page.';
            return;
        }
        button.disabled = true;
        handler.open({name: 'MIT-Tab', description: 'MIT-Tab server',
            email: form.elements.email.value, amount: quote.total_cents});
    });
    window.addEventListener('popstate', () => handler?.close());
    refreshPrice();
})();
