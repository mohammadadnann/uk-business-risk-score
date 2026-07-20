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