import { describeAccount } from '../accountLabel'
import { colors } from '../theme'
import { Pill } from './ui'

/** Small tag identifying which linked account a row belongs to — see accountLabel.ts. */
export function AccountTag({ accountId }: { accountId: string }) {
  return <Pill text={describeAccount(accountId).label} color={colors.textSecondary} />
}
