# Business plan: the road toward $1M with Autopilot

> Honest disclaimer up front: **no software guarantees income.** This plan
> models realistic, widely-used monetization paths for automated short-form
> content and a SaaS built on top of this repository. Treat every number as
> an assumption to validate, not a promise. Check the MoneyPrinterTurbo
> license and each platform's ToS before commercial use.

## The product

**MoneyPrinter Autopilot** — "Your faceless video channels, on autopilot."

Define a channel once (niche, voice, cadence). The system invents fresh
topics daily, scripts them with an LLM, assembles stock-footage videos with
voiceover and subtitles, and publishes them to TikTok/Instagram — fully
hands-off. The Autopilot API in this repo (`docs/autopilot.md`) is the
working core of that product.

## Two stacked revenue engines

### Engine 1 — Operate channels (immediate, low ceiling)

Run a portfolio of faceless channels yourself with Autopilot.

| Revenue source              | Mechanics                                  |
| --------------------------- | ------------------------------------------ |
| Creator funds / ad revenue  | TikTok Creativity Program, YT Shorts ads   |
| Affiliate links in bio      | Niche-matched products (Amazon, SaaS refs) |
| Digital products            | Niche e-book / template sold via link      |
| Channel flipping            | Grown accounts sell for $0.5–3 per follower in some niches |

Model (per channel, conservative): 2 posts/day → ~60 posts/month. At a
median 3–8k views/post once a channel finds footing, that's 200–500k
views/month. Creator-fund RPM for compliant original content runs
$0.20–$1.00 → **$40–$500/month/channel**, with affiliate income typically
matching or exceeding that in commercial niches. A 10-channel portfolio is
realistically **$1–10k/month** — good cash flow, but channel income alone
does not reach $1M fast. Its real job is to be the **proof and the
marketing fuel** for Engine 2.

### Engine 2 — Sell the autopilot as SaaS (the $1M path)

People pay for outcomes they believe in. "I grew these channels on full
autopilot — here's the tool" is one of the strongest possible SaaS pitches,
and the content the tool produces is itself the ad (every video can carry a
subtle watermark/CTA).

Pricing:

| Plan     | Price/mo | Limits                                   |
| -------- | -------- | ---------------------------------------- |
| Starter  | $19      | 1 channel, 30 videos/mo, watermark       |
| Creator  | $49      | 5 channels, 150 videos/mo, no watermark  |
| Agency   | $149     | 25 channels, white-label, API access     |

Path to $1M cumulative revenue (blended ARPU ≈ $45, ~5% monthly churn):

| Milestone        | Paying users | MRR      | Cumulative time (aggressive but seen in this niche) |
| ---------------- | ------------ | -------- | ---------------------------------------------------- |
| Launch + PH      | 100          | $4.5k    | Month 1–2                                            |
| Content flywheel | 400          | $18k     | Month 6                                               |
| Affiliates + ads | 1,000        | $45k     | Month 12                                              |
| Steady state     | 1,900        | $85k     | Month 18 → **$1M cumulative ~month 22–26**            |

The marketing campaign to drive this funnel is in
`docs/marketing-campaign.md`; ready-to-paste listing copy is in
`docs/store-listing.md`.

## Why this can work (and what kills it)

**Tailwinds:** short-form video demand keeps growing; "faceless channel"
is a proven, heavily-searched intent ("faceless youtube automation" etc.);
the open-source core gives a free tier with zero COGS for self-hosters and
a credibility moat.

**Risks & mitigations:**

1. **Platform policy** — TikTok/YT derank spammy AI content. → Quality
   guardrails (topic dedup is already built in), enforce post-rate limits,
   push users toward original-value niches.
2. **API costs** — LLM + stock-footage costs scale with usage. → Usage
   caps per plan; users bring their own API keys on lower tiers (already
   how this repo works).
3. **Competition** — many "AI video" tools. → Differentiator is *autopilot*
   (scheduling + auto-publish + topic engine), not the editor. Few
   competitors close the full loop.
4. **Churn** — users leave if channels don't grow. → Onboard with proven
   niche templates; surface channel analytics; community of operators.

## Execution checklist (human-required steps)

The code in this repo is ready; these steps require accounts, payment
details and legal decisions only the owner can make:

- [ ] Company/tax setup for SaaS billing (e.g. Stripe + Merchant of Record
      like Paddle/LemonSqueezy for global VAT).
- [ ] Hosted infrastructure (a $40–80/mo GPU-less VPS handles early scale;
      generation is CPU-bound via MoviePy).
- [x] Billing layer — **built in**: the `/billing` API creates Stripe
      Checkout sessions, issues license keys via webhook on successful
      payment and enforces per-plan channel limits. Just paste your Stripe
      keys and price IDs into the `[stripe]` section of `config.toml`.
- [ ] Upload-Post (or direct platform API) production credentials.
- [ ] Product Hunt / marketplace accounts (copy is ready in
      `docs/store-listing.md`).
- [ ] Review MoneyPrinterTurbo's license terms for commercial hosting, and
      platform ToS for automated publishing.
