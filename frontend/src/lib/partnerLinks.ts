/**
 * Broker / prop-firm partner links shown on the Connections page.
 *
 * Placeholder `url`s point at each partner's plain homepage until real
 * referral/affiliate links are wired in below — never broken, never
 * misleadingly claiming a relationship that doesn't exist yet. Flip
 * `isAffiliate` to `true` for an entry once its `url` is a real referral
 * link; only then does the UI show "using this link supports TradeLogger"
 * copy, so nothing dishonest is ever shown in the meantime.
 */
export interface PartnerLink {
  id: string
  name: string
  blurb: string
  url: string
  isAffiliate: boolean
}

export const PARTNER_LINKS: PartnerLink[] = [
  {
    id: '5ers',
    name: 'The 5%ers',
    blurb: 'Get a funded account through a prop-firm challenge.',
    url: 'https://the5ers.com/', // TODO: swap for the real referral link once approved
    isAffiliate: false,
  },
  {
    id: 'capital',
    name: 'Capital.com',
    blurb: 'Open a live or demo trading account.',
    url: 'https://capital.com/', // TODO: swap for the real referral link once approved
    isAffiliate: false,
  },
]
