import { describeAccount } from '../../lib/accountLabel'

/** Small tag identifying which linked account a row belongs to — see lib/accountLabel.ts. The full raw
 * id is always still available via the title tooltip, for matching against the broker/terminal directly. */
export function AccountBadge({ accountId, className = '' }: { accountId: string; className?: string }) {
  const { label } = describeAccount(accountId)
  return (
    <span
      title={accountId}
      className={`inline-block whitespace-nowrap rounded bg-surface-elevated px-1.5 py-0.5 font-mono text-[10px] text-muted ${className}`}
    >
      {label}
    </span>
  )
}
