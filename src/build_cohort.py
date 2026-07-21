"""Building the failed and live company cohort from the raw Companies House
snapshot. See decisions.md for the reasoning behind each choice here.
"""

import pandas as pd

COLUMNS_NEEDED = [
    "CompanyName", "CompanyNumber", "CompanyCategory", "CompanyStatus",
    "IncorporationDate", "SICCode.SicText_1",
    "Accounts.NextDueDate", "Accounts.LastMadeUpDate", "Accounts.AccountCategory",
    "ConfStmtNextDueDate", "ConfStmtLastMadeUpDate", "Mortgages.NumMortCharges",
]

FAILED_STATUSES = [
    "Liquidation", "In Administration", "Live but Receiver Manager on at least one charge",
    "Voluntary Arrangement", "In Administration/Administrative Receiver",
    "RECEIVERSHIP", "ADMINISTRATION ORDER", "ADMINISTRATIVE RECEIVER",
    "In Administration/Receiver Manager", "RECEIVER MANAGER / ADMINISTRATIVE RECEIVER",
]


def load_snapshot(path: str) -> pd.DataFrame:
    """Read the bulk snapshot CSV as text and clean up column names."""
    df = pd.read_csv(path, dtype=str, low_memory=False)
    df.columns = [c.strip() for c in df.columns]
    return df[COLUMNS_NEEDED]


def filter_standard_companies(df: pd.DataFrame) -> pd.DataFrame:
    """Keep only standard 8 digit England and Wales limited companies."""
    is_standard = df["CompanyNumber"].str.match(r"^\d{8}$")
    return df[is_standard].copy()


def label_failure(df: pd.DataFrame) -> pd.DataFrame:
    """Mark each company as failed or live, dropping the ambiguous strike off group."""
    df = df.copy()
    df["is_failed"] = df["CompanyStatus"].isin(FAILED_STATUSES).astype(int)
    keep = df["CompanyStatus"].isin(FAILED_STATUSES + ["Active"])
    return df[keep]


def build_cohort(df: pd.DataFrame, n_per_group: int = 1500, random_state: int = 1) -> pd.DataFrame:
    """Sample a balanced cohort of failed and live companies."""
    failed = df[df["is_failed"] == 1]
    live = df[df["is_failed"] == 0]

    n_failed = min(n_per_group, len(failed))
    n_live = min(n_per_group, len(live))

    sample = pd.concat([
        failed.sample(n_failed, random_state=random_state),
        live.sample(n_live, random_state=random_state),
    ])
    return sample.reset_index(drop=True)


def run(raw_path: str, output_path: str) -> pd.DataFrame:
    """Run the full cohort build and save the result."""
    df = load_snapshot(raw_path)
    df = filter_standard_companies(df)
    df = label_failure(df)
    cohort = build_cohort(df)
    cohort.to_parquet(output_path, index=False)
    print(f"saved {len(cohort)} companies to {output_path}")
    return cohort