# UK SME Credit Risk Intelligence Platform — Design Decisions

## Business Context & Credit Risk Challenge

Traditional company risk assessment relies heavily on statutory filings,
which may not reflect a company's latest financial position. Credit
controllers, suppliers, landlords, and procurement teams assessing a UK
company's insolvency risk often have limited access to timely predictive
signals beyond statutory filings and commercial credit reports.

According to the UK Government's Business Population Estimates 2025, the
UK has approximately 5.69 million private sector businesses, of which
5.68 million (99.85%) are SMEs. Only 8,335 businesses (0.15%) are large
enough to be classified as large businesses. Large PLCs already have
credit ratings, analyst coverage, and public financial disclosure. SMEs
generally have significantly less access to these external risk
assessment mechanisms.

According to the Government's Business Insolvency Demography 2015 to
2025, businesses with 10 to 249 employees experience higher insolvency
rates than both micro businesses and large businesses. This highlights
the importance of early-warning risk assessment within the SME segment,
where access to sophisticated risk monitoring is typically more limited.

I built this project to address that gap directly: a system that reads a
company's public filing behaviour and produces a live, explained
insolvency risk estimate for exactly the population that currently lacks
one.

Sources: [Business Population Estimates 2025](https://www.gov.uk/government/statistics/business-population-estimates-2025/business-population-estimates-for-the-uk-and-regions-2025-statistical-release),
[Business Insolvency Demography 2015 to 2025](https://www.gov.uk/government/statistics/business-insolvency-demography-2015-to-2025)

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

## Excluding fast failing companies
I found 8 failed companies with a negative company age at their snapshot
date. This happens when a company fails within 12 months of incorporation,
since the snapshot date (failure date minus 12 months) then falls before
the company existed. These companies have no genuine pre-snapshot history
to build features from, so I excluded them, leaving 2511 companies in the
features table.

## Fixing the accounts due date fallback
I found 84 companies missing days_overdue_on_accounts even though most
had genuinely filed accounts before. Looking at the raw profile data
directly, I found the cause: some records store the next due date under
an older top level next_due field instead of the newer next_accounts.due_on
field my function was reading. I added a fallback to check both, which
recovered all but 83 companies.

## Handling remaining missing values
For the 83 companies still missing a due date, and 383 missing a longest
filing gap (companies with fewer than two pre snapshot filings), I added
a missingness flag column for each rather than guessing a value, then
filled the missing values with 0. This lets the model learn from the
pattern of missingness itself rather than treating a filled in 0 as a
real measurement.


## Fixing a leakage bug in the accounts overdue feature
My original days_overdue_on_accounts feature read the company's current
live profile, which is not filtered by snapshot date the way filings and
officers are. For live companies with snapshot dates several years in the
past, this compared a historical snapshot date against a present day due
date, producing meaningless extreme values (over 11000 days in one case).
All these extreme values were live companies, which was quietly making
the feature look artificially predictive.

I rebuilt the feature as days_since_last_accounts, computed only from
filing history before the snapshot date, so it respects the leakage
boundary for every company regardless of snapshot date. This is a more
honest signal, and it changed my baseline substantially: precision at top
10% dropped from 0.98 to 0.52. This was expected once I understood the
bug, since the original figure was inflated by the leak.

Final result on the corrected features: XGBoost achieves 0.60 precision
and 0.19 recall at top 10%, against a baseline of 0.52 precision and 0.16
recall using the single strongest feature alone. The model provides a
real, modest improvement over the baseline once the leakage bug is fixed.


## Company age as the strongest feature
SHAP analysis showed company_age_years as the model's most influential
feature. Checking the underlying data, failed companies are older on
average (mean 11.6 years) than live companies (mean 8.0 years), the
opposite of what I initially expected. This makes sense given how the
failed group is defined: formal liquidation typically follows years of
accumulated debt and creditor relationships, so younger companies that
fail are more likely to be struck off quietly rather than enter formal
liquidation, and would not appear in this failed group at all.


## Out of distribution detection and withholding predictions
The model is built specifically for UK private limited SMEs within the
model's defined training population, in line with the business case
above. PLCs, banks, and other large or structurally different entities
were never the target population, so the API does not produce a risk
score for them at all.

I implemented an eligibility validation layer based on legal structure
and company characteristics before applying the risk model. A company is
excluded from scoring if it is registered as a PLC, if it is well outside
the training data's typical company age range, or if it shows unusually
high recent director turnover, since each of these indicates the company
is unlikely to resemble the population the model was trained on. Rather
than silently returning a number for any company regardless of type, if a
company matches any of these checks, the API returns no prediction and
instead returns the specific reason, and the dashboard shows a distinct
"Prediction unavailable" state. This keeps the system's output honest and
consistent with its stated scope: a score is only ever produced for the
population the model was actually built to serve.


## Calibrating the model
I checked whether the model's predicted probabilities matched real world
failure rates, using a calibration curve. The raw model was overconfident
across most of the range, for example predicting 30% risk for companies
that actually failed 45% of the time.

I calibrated the model with isotonic regression, fit on a held out slice
of training data rather than the test set, to avoid leaking test
information into the calibration step itself. This reduced the average
gap between predicted and actual failure rates from around 16 percentage
points to around 11 across five probability bands.

With around 500 companies in my test set, checking calibration at finer
resolution than five bins becomes unreliable, since some bins then contain
very few companies and the percentages become noisy. A larger cohort would
allow tighter calibration validation. I consider the current calibration
a genuine, verified improvement, not a fully solved problem.


## Reporting overall and in-distribution precision honestly
Rather than reporting only a precision figure computed after removing
out-of-distribution companies, I report both. Overall precision at top
10% is 0.72. Restricted to the 493 of 503 test companies that pass my
out-of-distribution check (age under 50, fewer than 3 recent
resignations), precision is 0.73, only marginally different because so
few test companies (10, or 2%) are actually flagged. The real value of
the out-of-distribution check is not on this test set, which was drawn
from the same population the model was trained on, but on live lookups
of companies structurally unlike anything in the training data, such as
large PLCs, which the check is specifically designed to catch.

## Validating the out of distribution detector
I built a labelled validation set of 9 real UK companies: 4 large PLCs
and banks I expected the detector to flag (Tesco, HSBC, Shell, Barclays)
and 5 ordinary small companies drawn from my own training cohort that I
expected it not to flag. Testing against the live API, the detector
correctly classified all 9 (100% accuracy).

While building this test, I found and fixed a real bug, for companies
with no recorded accounts filing (returning NaN), my code used the
pattern "value or 0" to provide a default, which silently fails because
NaN is truthy in Python. This crashed every request for companies like
Shell and Barclays that had missing accounts data. I fixed it using an
explicit pd.isna() check instead.

## Containerizing the project and finalizing scope
I packaged the API and dashboard as separate Docker containers, connected
via docker-compose, so the full system runs with a single command and no
longer depends on my local machine's Python environment (this replaced
a real, multi-hour dependency conflict I had hit locally between xgboost
and the OpenMP runtime on Apple Silicon).

I also added a small pytest suite covering the leakage filter and the
core feature functions, verifying with automated tests that no
post-snapshot information can leak into any feature, complementing the
manual verification done throughout the project.

Finally, I renamed the project to "UK SME Credit Risk Intelligence
Platform" to accurately reflect its actual scope, after confirming the
model reliably serves UK private limited SMEs and correctly declines to
score companies outside that population.