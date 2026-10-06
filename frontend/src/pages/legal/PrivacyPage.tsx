import { LegalPageLayout } from './LegalPageLayout'

export function PrivacyPage() {
  return (
    <LegalPageLayout title="Privacy Policy" updated="October 6, 2026">
      <p>
        This page explains what TradeLogger collects, why, and how it's protected. TradeLogger is
        a small, independently-run journal — your data is never sold, and is used only to run the
        features described below.
      </p>

      <h2 className="pt-2 text-base font-semibold text-primary">1. What we collect</h2>
      <ul className="list-disc space-y-1 pl-5">
        <li>Account info: email, display name, and a hashed (never plaintext) password.</li>
        <li>
          Trade &amp; journal data: positions, trade history, notes, tags, and screenshots you
          add or that sync from a connected broker/MT5 terminal.
        </li>
        <li>
          Broker credentials, if you connect one: encrypted at rest (Fernet/AES) and decrypted
          only in-memory, only to make the read-only sync call to your broker's API.
        </li>
        <li>
          AI Assistant / Chart Analyzer content: the text or chart image you submit for those
          features, sent to Google's Gemini API to generate the response (see §3).
        </li>
        <li>
          Basic technical metadata: your IP address (used only for login/signup rate-limiting and
          abuse prevention), and timestamps of activity.
        </li>
      </ul>

      <h2 className="pt-2 text-base font-semibold text-primary">2. What we don't collect</h2>
      <p>
        No payment or card details — TradeLogger doesn't process payments. No tracking cookies,
        ad identifiers, or third-party analytics/advertising scripts.
      </p>

      <h2 className="pt-2 text-base font-semibold text-primary">3. Who your data goes to</h2>
      <ul className="list-disc space-y-1 pl-5">
        <li><strong>Google Gemini</strong> — only the specific text/chart image you submit to the AI Assistant or Chart Analyzer, to generate that one response. Not your trade history or account details.</li>
        <li><strong>Your own broker (Capital.com) or MetaTrader terminal</strong> — your encrypted credentials are used solely to authenticate as you and read your own account history.</li>
        <li><strong>Neon, Render, Cloudflare</strong> — the database, application, and frontend hosting providers that run TradeLogger. They store/transmit data on our behalf under their own security practices; none independently use it.</li>
      </ul>
      <p>
        Inbound market/economic data providers (FRED, CFTC, Financial Modeling Prep, and similar)
        only send data to TradeLogger — they never receive any of your personal or trading data.
      </p>

      <h2 className="pt-2 text-base font-semibold text-primary">4. Security</h2>
      <p>
        Passwords are hashed with scrypt (never stored in plaintext). Broker credentials are
        encrypted at rest. Sessions use httpOnly cookies validated against a server-side token
        hash. All traffic is served over HTTPS. No system is perfectly secure, but we don't store
        more than we need, and nothing here is a substitute for you using a strong, unique
        password.
      </p>

      <h2 className="pt-2 text-base font-semibold text-primary">5. Retention &amp; deletion</h2>
      <p>
        Your data is kept while your account is active. You can request export or permanent
        deletion of your account and all associated data at any time by emailing{' '}
        <a className="underline" href="mailto:privacy@tradelogger.site">privacy@tradelogger.site</a>
        . Deletion requests are processed within 30 days.
      </p>

      <h2 className="pt-2 text-base font-semibold text-primary">6. Your rights</h2>
      <p>
        Wherever you're located, you can ask to see, export, correct, or delete your personal
        data at any time — just email us. We'll respond to every request.
      </p>

      <h2 className="pt-2 text-base font-semibold text-primary">7. Children</h2>
      <p>TradeLogger is not directed at, or intended for use by, anyone under 18.</p>

      <h2 className="pt-2 text-base font-semibold text-primary">8. Changes</h2>
      <p>If this policy changes, the "last updated" date above will change with it.</p>

      <h2 className="pt-2 text-base font-semibold text-primary">9. Contact</h2>
      <p>
        <a className="underline" href="mailto:privacy@tradelogger.site">privacy@tradelogger.site</a>
      </p>
    </LegalPageLayout>
  )
}
