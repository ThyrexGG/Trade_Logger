import { LegalPageLayout } from './LegalPageLayout'

export function TermsPage() {
  return (
    <LegalPageLayout title="Terms of Service" updated="October 6, 2026">
      <p>
        TradeLogger is a personal trading journal and research terminal. It helps you record,
        review, and analyze your own trades. Please read these terms before creating an account.
      </p>

      <h2 className="pt-2 text-base font-semibold text-primary">1. Not financial advice</h2>
      <p>
        Nothing in TradeLogger — including the AI Chart Analyzer, Killzone Scanner, Macro
        Intelligence, Challenge Tracker, or AI Assistant — is financial, investment, or trading
        advice. These are journaling and research aids that summarize data and your own history.
        Ratings, scores, and signals they produce are informational only, may be wrong, and are
        not a recommendation to open, close, or avoid any position. You are solely responsible
        for your own trading decisions and their outcomes.
      </p>

      <h2 className="pt-2 text-base font-semibold text-primary">2. No order execution</h2>
      <p>
        TradeLogger only reads data — from your broker account (Capital.com) or your own
        MetaTrader 5 terminal — to build your journal and analytics. It has no capability to
        place, modify, or close a trade on your behalf, anywhere, under any account.
      </p>

      <h2 className="pt-2 text-base font-semibold text-primary">3. Your account</h2>
      <p>
        You must be at least 18 years old to create an account. You're responsible for keeping
        your password and any connected broker credentials confidential, and for all activity
        under your account. Don't create multiple accounts to bypass usage limits, attempt to
        access another user's data, or use the service in a way that disrupts it for others.
      </p>

      <h2 className="pt-2 text-base font-semibold text-primary">4. Broker &amp; market data</h2>
      <p>
        If you connect a broker account or sync a MetaTrader terminal, you authorize TradeLogger
        to read (never trade) your account history for the sole purpose of building your journal.
        Broker credentials you provide are encrypted at rest and are never shared with any party
        other than the broker's own API, to authenticate as you. Market and economic data shown
        in the app comes from third-party sources (e.g. FRED, CFTC, Financial Modeling Prep) and
        is provided "as is," with no guarantee of accuracy or timeliness.
      </p>

      <h2 className="pt-2 text-base font-semibold text-primary">5. Service availability</h2>
      <p>
        TradeLogger runs on free- or low-tier infrastructure and is provided on a best-effort
        basis, with no uptime guarantee. Features may change, be added, or be removed at any
        time. We'll do our best to give notice before anything that affects your data.
      </p>

      <h2 className="pt-2 text-base font-semibold text-primary">6. Limitation of liability</h2>
      <p>
        TradeLogger is provided "as is," without warranties of any kind. To the fullest extent
        permitted by law, the operator of TradeLogger is not liable for any trading losses,
        missed opportunities, or damages arising from your use of the service, including from
        inaccurate data, downtime, or a bug. Trading leveraged instruments carries substantial
        risk of loss and is not suitable for everyone.
      </p>

      <h2 className="pt-2 text-base font-semibold text-primary">7. Ending your account</h2>
      <p>
        You can request deletion of your account and data at any time (see the Privacy Policy
        for how). We may suspend or disable an account that abuses the service or its invite
        system.
      </p>

      <h2 className="pt-2 text-base font-semibold text-primary">8. Changes</h2>
      <p>
        These terms may be updated as the product changes. Continuing to use TradeLogger after a
        change means you accept the update.
      </p>

      <h2 className="pt-2 text-base font-semibold text-primary">9. Contact</h2>
      <p>
        Questions about these terms: <a className="underline" href="mailto:legal@tradelogger.site">legal@tradelogger.site</a>.
      </p>
    </LegalPageLayout>
  )
}
