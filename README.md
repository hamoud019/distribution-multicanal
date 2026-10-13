# distribution-multicanal

Urbanization study for a multi-channel retailer, applied to **Le Slip Français** (public figures, synthetic data): centralizing siloed ERP, CRM, POS, e-commerce, web analytics, social media and customer support data into a datamart / lakehouse for sales performance, inventory optimization and customer segmentation.

Spec and work breakdown: issue #1.

## Deliverables

| # | Deliverable | Issue |
|---|---|---|
| 0 | [Our company: Le Slip Français](docs/deliverables/00-company-profile.md) | |
| 1 | [Choosing the architecture](docs/deliverables/01-architecture-options.md) | #2 |
| 2 | [SWOT and risk assessment](docs/deliverables/02-swot-risks.md) | #4 |
| 3 | [Full costing](docs/deliverables/03-costing.md) | #3 |
| 4 | [Transformation plan](docs/deliverables/04-transformation-plan.md) | #6 |
| 5 | [Change management plan](docs/deliverables/05-change-management.md) | #7 |
| 6 | [Data governance and GDPR](docs/deliverables/06-governance-gdpr.md) | #5 |

## Proof of concept

A local version of the chosen platform on synthetic data: the 7 sources, a raw layer, and dbt models up to the Sales Performance mart, reconciled with the ERP finance figures. One command, no cloud account (Python 3.10 to 3.13):

```
py -3.12 poc/run.py
```

Then `py -3.12 poc/run.py --dashboard` opens the Sales Performance dashboard. See [poc/README.md](poc/README.md).

## Governance rules

The glossary, planned report tables, personal-data inventory, retention periods, erasure steps and access model are CSV files in [`governance/`](governance), checked by `analysis/test_governance.py`.

## Decision matrices

The scores, cost lines, risk register, transformation plan and change management plan behind the deliverables are CSV files in [`analysis/`](analysis). To recompute them after changing a figure:

```
python analysis/scoring.py
python analysis/costing.py
python analysis/risks.py
python analysis/plan.py
python analysis/change.py
python -m unittest discover analysis
```
