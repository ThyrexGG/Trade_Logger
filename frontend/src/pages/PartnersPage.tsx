import { useEffect, useState } from 'react'
import { PageContainer } from '../components/shell/PageContainer'
import { PARTNER_LINKS } from '../lib/partnerLinks'
import { claimReferral, listMyReferralClaims, type ReferralClaim } from '../api/referrals'
import { useToast } from '../lib/toast'

const CLAIM_STATUS_LABEL: Record<ReferralClaim['status'], string> = {
  pending: 'Claim submitted — pending review',
  verified: 'Verified — reward banked ✓',
  rejected: "Couldn't verify this one",
}

/**
 * Partners (`/operations/partners`). Used to live as a small card tucked
 * inside the bottom of Connections, where it was easy to miss entirely — it
 * gets its own page instead so someone can actually find it.
 *
 * "Claim your bonus" self-reports a signup (see api/referrals.py for why
 * this can't be verified automatically) — the reward itself is a banked
 * promise (a free month of Pro once that tier exists, plus early access to
 * new features), not something granted immediately.
 */
export function PartnersPage() {
  const toast = useToast()
  const [claims, setClaims] = useState<Record<string, ReferralClaim>>({})
  const [claiming, setClaiming] = useState<string | null>(null)

  useEffect(() => {
    const c = new AbortController()
    listMyReferralClaims(c.signal)
      .then((res) => {
        const byPartner: Record<string, ReferralClaim> = {}
        for (const claim of res.claims) byPartner[claim.partner_id] = claim
        setClaims(byPartner)
      })
      .catch(() => {
        /* claim status is a nice-to-have here, not load-bearing — fail quiet */
      })
    return () => c.abort()
  }, [])

  const doClaim = async (partnerId: string) => {
    setClaiming(partnerId)
    try {
      const { claim } = await claimReferral(partnerId)
      setClaims((prev) => ({ ...prev, [partnerId]: claim }))
      toast.success("Claim submitted — we'll verify it against the partner's dashboard.")
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Could not submit the claim.')
    } finally {
      setClaiming(null)
    }
  }

  return (
    <PageContainer
      title="Partners"
      description="Don't have a broker or funded account yet? These are the ones we've actually used and vouch for."
    >
      <div className="space-y-4">
        {PARTNER_LINKS.length === 0 ? (
          <div className="rounded-lg border border-border bg-surface p-4 text-sm text-muted">
            No partner links yet — check back soon.
          </div>
        ) : (
          <div className="rounded-lg border border-border bg-surface p-4">
            <ul className="divide-y divide-border-subtle">
              {PARTNER_LINKS.map((p) => {
                const claim = claims[p.id]
                return (
                  <li key={p.id} className="space-y-1.5 py-3 first:pt-0 last:pb-0">
                    <div className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
                      <a
                        href={p.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-sm font-medium text-accent hover:underline"
                      >
                        {p.name} →
                      </a>
                      {p.code ? (
                        <span className="rounded border border-border-subtle bg-surface-elevated px-1.5 py-0.5 font-mono text-[10px] text-secondary">
                          code {p.code}
                        </span>
                      ) : null}
                    </div>
                    <p className="text-[11px] text-muted">{p.blurb}</p>
                    {p.isAffiliate ? (
                      claim ? (
                        <p className="text-[11px] text-muted">{CLAIM_STATUS_LABEL[claim.status]}</p>
                      ) : (
                        <button
                          type="button"
                          disabled={claiming === p.id}
                          onClick={() => void doClaim(p.id)}
                          className="rounded border border-border px-2 py-0.5 text-[11px] text-primary hover:bg-surface-hover disabled:opacity-50"
                        >
                          {claiming === p.id ? 'Submitting…' : 'Used this link? Claim your bonus'}
                        </button>
                      )
                    ) : null}
                  </li>
                )
              })}
            </ul>
            {PARTNER_LINKS.some((p) => p.isAffiliate) ? (
              <p className="mt-3 border-t border-border-subtle pt-3 text-[10px] text-muted">
                Some links above are referral links — using them costs you nothing extra and helps keep TradeLogger
                running. Claiming a bonus banks a free month of Pro (once that tier exists) plus early access to new
                features — we verify each claim by hand against the partner's dashboard first.
              </p>
            ) : null}
          </div>
        )}
      </div>
    </PageContainer>
  )
}
