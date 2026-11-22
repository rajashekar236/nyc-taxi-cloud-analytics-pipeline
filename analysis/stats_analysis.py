"""Step 4 - Statistical analysis: what drives card tipping in NYC taxis?

Questions
  H1  Do riders tip a different share of the fare on weekends vs weekdays?
  H2  Do airport trips tip differently from non-airport trips?
  M1  Holding distance, time of day, day type and borough constant, which
      factors move tip %? (OLS regression with robust standard errors)

Why card trips only: the TLC records tips only for card payments, so cash
trips always show $0 tip. Including them would make the results wrong.

With millions of rows almost any difference is "statistically significant",
so every test also reports an effect size. That says whether the difference is
big enough to matter to the business.

Output: reports/stats_results.md and charts in reports/.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from scipy import stats

SAMPLE_SQL = """
SELECT
  f.tip_pct,
  f.trip_distance,
  f.trip_minutes,
  f.pickup_hour,
  d.is_weekend,
  (pz.is_airport OR dz.is_airport) AS is_airport,
  pz.borough AS pickup_borough
FROM `${project}.${dataset}.fact_trips` f
JOIN `${project}.${dataset}.dim_date` d  ON d.date_key  = f.pickup_date_key
JOIN `${project}.${dataset}.dim_zone` pz ON pz.zone_key = f.pickup_zone_key
JOIN `${project}.${dataset}.dim_zone` dz ON dz.zone_key = f.dropoff_zone_key
WHERE f.payment_type_key = 1
  AND f.fare_amount >= 3
  AND f.tip_pct BETWEEN 0 AND 1
  -- Deterministic sample: the same trips are picked on every run.
  AND MOD(ABS(FARM_FINGERPRINT(f.trip_id)), 100) < @sample_pct
"""


def cohens_d(a: pd.Series, b: pd.Series) -> float:
    pooled = np.sqrt(((len(a) - 1) * a.var() + (len(b) - 1) * b.var()) / (len(a) + len(b) - 2))
    return float((a.mean() - b.mean()) / pooled) if pooled else 0.0


def size_label(d: float) -> str:
    d = abs(d)
    return "negligible" if d < 0.2 else "small" if d < 0.5 else "medium" if d < 0.8 else "large"


def compare_groups(df: pd.DataFrame, flag: str, yes: str, no: str) -> dict:
    a = df.loc[df[flag], "tip_pct"]
    b = df.loc[~df[flag], "tip_pct"]
    t = stats.ttest_ind(a, b, equal_var=False)                     # Welch's t-test
    u = stats.mannwhitneyu(a, b, alternative="two-sided")          # no normality assumption
    d = cohens_d(a, b)
    return {"yes": yes, "no": no, "n_yes": len(a), "n_no": len(b),
            "mean_yes": a.mean(), "mean_no": b.mean(),
            "diff_pts": (a.mean() - b.mean()) * 100,
            "t_p": t.pvalue, "u_p": u.pvalue, "d": d, "size": size_label(d)}


def hour_bucket(h: int) -> str:
    if 6 <= h < 10:
        return "morning_rush"
    if 10 <= h < 16:
        return "midday"
    if 16 <= h < 20:
        return "evening_rush"
    if 20 <= h < 24:
        return "night"
    return "late_night"


def regression(df: pd.DataFrame):
    data = df.assign(
        hour_bucket=df.pickup_hour.astype(int).map(hour_bucket),
        is_weekend=df.is_weekend.astype(int),
        is_airport=df.is_airport.astype(int),
        tip_pct_pts=df.tip_pct * 100,
    )
    formula = ("tip_pct_pts ~ trip_distance + trip_minutes + is_weekend + is_airport"
               " + C(hour_bucket, Treatment('midday'))"
               " + C(pickup_borough, Treatment('Manhattan'))")
    return smf.ols(formula, data=data).fit(cov_type="HC3")


def fmt_p(p: float) -> str:
    return "< 0.001" if p < 0.001 else f"{p:.3f}"


def charts(df: pd.DataFrame, out: Path) -> None:
    by_hour = df.groupby(["pickup_hour", "is_weekend"]).tip_pct.mean().unstack() * 100
    fig, ax = plt.subplots(figsize=(8, 4))
    by_hour.rename(columns={False: "Weekday", True: "Weekend"}).plot(ax=ax, marker="o")
    ax.set(title="Average card tip % by pickup hour", xlabel="Hour of day", ylabel="Tip % of fare")
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(out / "tip_pct_by_hour.png", dpi=150)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 4))
    bins = np.linspace(0, 50, 51)
    ax.hist(df.loc[~df.is_weekend, "tip_pct"] * 100, bins=bins, alpha=0.6, density=True, label="Weekday")
    ax.hist(df.loc[df.is_weekend, "tip_pct"] * 100, bins=bins, alpha=0.6, density=True, label="Weekend")
    ax.set(title="Distribution of card tip %", xlabel="Tip % of fare", ylabel="Share of trips")
    ax.legend()
    fig.tight_layout()
    fig.savefig(out / "tip_pct_distribution.png", dpi=150)
    plt.close(fig)


def run_analysis(df: pd.DataFrame, out: Path) -> str:
    out.mkdir(parents=True, exist_ok=True)
    df = df.dropna(subset=["tip_pct", "trip_distance", "trip_minutes", "pickup_hour",
                           "is_weekend", "is_airport", "pickup_borough"]).copy()
    df["is_weekend"] = df.is_weekend.astype(bool)
    df["is_airport"] = df.is_airport.astype(bool)

    h1 = compare_groups(df, "is_weekend", "Weekend", "Weekday")
    h2 = compare_groups(df, "is_airport", "Airport", "Non-airport")
    model = regression(df)
    charts(df, out)

    def test_block(title: str, r: dict) -> str:
        return (
            f"### {title}\n\n"
            f"| Group | Trips | Mean tip % |\n|---|---|---|\n"
            f"| {r['yes']} | {r['n_yes']:,} | {r['mean_yes']*100:.2f}% |\n"
            f"| {r['no']} | {r['n_no']:,} | {r['mean_no']*100:.2f}% |\n\n"
            f"- Difference: **{r['diff_pts']:+.2f} percentage points**\n"
            f"- Welch's t-test p = {fmt_p(r['t_p'])}; Mann-Whitney U p = {fmt_p(r['u_p'])}\n"
            f"- Effect size (Cohen's d) = {r['d']:.3f} → **{r['size']}**\n"
        )

    coefs = pd.DataFrame({"coef_pts": model.params, "p": model.pvalues,
                          "ci_low": model.conf_int()[0], "ci_high": model.conf_int()[1]})
    coef_rows = "\n".join(
        f"| {name} | {r.coef_pts:+.3f} | [{r.ci_low:+.3f}, {r.ci_high:+.3f}] | {fmt_p(r.p)} |"
        for name, r in coefs.iterrows()
    )

    report = f"""# Statistical analysis: what drives card tipping?

Sample: **{len(df):,} card-paid trips** (deterministic hash sample of fact_trips).
Tip % = tip ÷ fare. Cash trips are excluded because the TLC doesn't record cash tips.

{test_block("H1: Weekend vs weekday", h1)}
{test_block("H2: Airport vs non-airport", h2)}
### M1: OLS regression of tip % (percentage points)

R² = {model.rsquared:.3f}, n = {int(model.nobs):,}, heteroskedasticity-robust (HC3) standard errors.
Baselines: midday pickup, Manhattan.

| Term | Coefficient (pts) | 95% CI | p |
|---|---|---|---|
{coef_rows}

**How to read this:** each coefficient is the change in tip % (in percentage points),
holding the other variables constant. A low R² is normal here: tipping is mostly
personal, so the model explains what moves the average, not what each rider does.

![Tip % by hour](tip_pct_by_hour.png)
![Tip % distribution](tip_pct_distribution.png)
"""
    (out / "stats_results.md").write_text(report, encoding="utf-8")
    return report


def main() -> None:
    from google.cloud import bigquery
    from pipeline import bq as bqh
    from pipeline.config import settings

    parser = argparse.ArgumentParser()
    parser.add_argument("--sample-pct", type=int, default=10,
                        help="percent of card trips to analyze (1-100)")
    args = parser.parse_args()

    bq = bqh.client()
    print(f"Statistical analysis ({args.sample_pct}% sample)")
    df = bqh.to_df(bq, SAMPLE_SQL,
                   [bigquery.ScalarQueryParameter("sample_pct", "INT64", args.sample_pct)])
    run_analysis(df, settings.reports_dir)
    print(f"Done: {len(df):,} trips analyzed -> reports/stats_results.md")


if __name__ == "__main__":
    main()
