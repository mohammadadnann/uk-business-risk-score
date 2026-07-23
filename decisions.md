# Project decisions

## Scope: standard limited companies only
I excluded the cohort to companies with an 8 digit numeric company number.
I deliberately did this to drop Scotland (SC), Northern Ireland (NI), LLPs
(OC, SL), Limited Partnerships (LP), and overseas entities. These entity
types follow different filing rules, so a feature like "days overdue on
accounts" would not mean the same thing across them. I kept scope
consistent by restricting to one entity type.

## Defining failure
I defined "failed" as CompanyStatus being Liquidation or one of the smaller
formal distress statuses (In Administration, Receiver Manager,
Administrative Receiver, Voluntary Arrangement). Together these give me
about 14,989 standard companies to sample from.

I deliberately excluded "Active - Proposal to Strike off" (54,048
companies) from both the failed and live groups. I found this status too
ambiguous to label safely: it can mean a company is being wound up in
distress, or that a director is closing a healthy company voluntarily.
Rather than guess, I left it out and I am noting this as a limitation.

## Cohort size
I chose 1,500 failed and 1,500 live companies, sampled from the pools
above. Both pools are large enough that this is a small, comfortable
sample, not a scarcity driven choice. My main reason for capping at 1,500
per group is the Companies House API rate limit, since I will later pull
filing history per company individually.

## Missing data findings
- I found Accounts.LastMadeUpDate missing in about 25% of rows, almost
  entirely explained by recent incorporation (2025 to 2026), meaning the
  company has not reached its first filing deadline yet.
- I found Accounts.NextDueDate missing in about 3% of rows, almost entirely
  explained by AccountCategory being "NO ACCOUNTS FILED", meaning there is
  no filing history to calculate a next due date from.

I will need explicit missingness flags when I build features, rather than
silently filling these in.

## Collecting company data from the API
I initially ran the collector at 0.6 seconds between companies. Around
company 750 of 3000 I started seeing a high rate of failures. I checked one
of the failed companies directly and found the API was returning
429 Too Many Requests.

I fixed this in two ways: I added automatic retry with backoff when a 429
is returned, respecting the Retry-After header from the API. I also slowed
the collector down, first to 1.2 seconds between companies, then to 2
seconds for the final batch of retries. Because the collector already
skips any company it has already saved, I was able to resume the run
multiple times without losing progress or duplicating work.

Final result: all 3000 companies collected, 0 failures.

## Determining the failure date
I found that a single filing type could not identify the start of
liquidation for all failed companies. Voluntary liquidation is marked by
a "600" filing (liquidation-voluntary-appointment-of-liquidator), covering
899 companies. Compulsory liquidation is marked by a "COCOMP" filing
(liquidation-compulsory-winding-up-order), covering a further 354.

For the remaining 247 companies, I investigated further rather than
excluding them immediately. About 149 were still Liquidation status but
matched neither filing type. Checking one of these directly, I found its
filing history stopped in the 1980s, using legacy pre-1987 filing codes,
meaning Companies House holds no usable digital filing history for it at
all. The remaining 98 companies were in non-liquidation distress statuses
(In Administration, Receiver Manager, Voluntary Arrangement), which use
entirely different filing codes that "600" and "COCOMP" would not be
expected to match.

I excluded these 247 companies from the labelled cohort rather than
approximate a failure date for them, since a wrong date would introduce
label noise. This leaves 1,253 failed companies with a reliable,
evidence based failure date.


## Snapshot dates for live companies
I assigned each live company a snapshot date sampled from the actual
distribution of failed companies' snapshot dates, rather than using
today's date for all of them. Using today for every live company would
have let the model learn to distinguish failed from live based on how
recent the record looked, rather than on real distress signals.

I constrained sampling so a live company could only receive a snapshot
date after its own incorporation date. 234 live companies (about 16%)
were too recently incorporated to have any valid snapshot date at all
and were excluded, since they would have had little to no filing
history behind any snapshot date regardless. This leaves 1,266 live
companies, closely balanced against the 1,253 failed companies.


## Handling missing officer appointment dates
About 10% of officer records (623 of 6,210) had no appointed_on date.
Checking examples, these were consistently long serving officers from
before Companies House digitised appointment dates, several already
resigned by the mid 1990s. I treated a missing appointed_on as
pre-snapshot by default, since these officers reliably predate every
snapshot date in the cohort.