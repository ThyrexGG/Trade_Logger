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
  /** Optional discount/coupon code to show alongside the link. */
  code?: string
}

export const PARTNER_LINKS: PartnerLink[] = [
  {
    id: '5ers',
    name: 'The 5%ers',
    blurb: 'Get a funded account through a prop-firm challenge.',
    url: 'https://www.the5ers.com/?afmc=1fqo',
    isAffiliate: true,
    code: 'WJC5V5',
  },
  // Capital.com: left out on purpose until the affiliate application
  // (capital.com/en-int/partnerships/affiliate-programme) is approved --
  // no point showing a plain, non-affiliate link. Re-add here once there's
  // a real referral link, same shape as the 5ers entry above:
  // { id: 'capital', name: 'Capital.com', blurb: 'Open a live or demo trading account.',
  //   url: '<real referral link>', isAffiliate: true },
]
