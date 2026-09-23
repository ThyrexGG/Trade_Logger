/**
 * Turns a raw `account_id` (whatever shape the sync that wrote it used) into something a person can
 * actually tell apart at a glance, now that an account is routinely one of several a user has linked
 * (Capital.com + one or more MT5 logins, plus hand-logged trades filed under a free-text label).
 *
 * `platform` is only set when the id unambiguously matches a known synced-broker convention:
 *   - MT5:         "MT5_<login>"                          (agent/mt5_push_agent.py, mt5_ingest.py)
 *   - Capital.com: a long digits-only account/deal number   (capital_sync.py — no distinguishing prefix)
 * Anything else (a manual/demo label like "OWN_MONEY", "DEMO_MAIN") is shown as typed, with no invented
 * platform claim — better an honest plain label than a guessed-wrong one.
 */
export type AccountPlatform = 'MT5' | 'Capital.com' | null

export interface AccountInfo {
  platform: AccountPlatform
  /** what to actually show, e.g. "MT5 14271408" / "Capital.com ••6500" / "OWN_MONEY" */
  label: string
}

const MT5_ID = /^MT5_(\d+)$/
const CAPITAL_ID = /^\d{5,}$/

export function describeAccount(accountId: string | null | undefined): AccountInfo {
  const id = (accountId ?? '').trim()
  const mt5 = MT5_ID.exec(id)
  if (mt5) return { platform: 'MT5', label: `MT5 ${mt5[1]}` }
  if (CAPITAL_ID.test(id)) return { platform: 'Capital.com', label: `Capital.com ••${id.slice(-4)}` }
  return { platform: null, label: id || 'Unknown account' }
}

/** Stable account ordering: Capital.com, then MT5, then anything else
 * alphabetically by label — matches the priority the rest of the app already
 * gives Capital.com (default account, default Analytics view). */
function accountSortKey(accountId: string): string {
  const { platform, label } = describeAccount(accountId)
  const rank = platform === 'Capital.com' ? 0 : platform === 'MT5' ? 1 : 2
  return `${rank}:${label}`
}

/** Splits a list of account-tagged items into one group per account, in the
 * stable order above — used wherever a mixed "all accounts" list needs to be
 * shown as separate per-account sections instead of one interleaved list. */
export function groupByAccount<T extends { account_id: string }>(items: T[]): { account: string; items: T[] }[] {
  const byAccount = new Map<string, T[]>()
  for (const item of items) {
    const list = byAccount.get(item.account_id)
    if (list) list.push(item)
    else byAccount.set(item.account_id, [item])
  }
  return [...byAccount.entries()]
    .map(([account, groupItems]) => ({ account, items: groupItems }))
    .sort((a, b) => accountSortKey(a.account).localeCompare(accountSortKey(b.account)))
}
