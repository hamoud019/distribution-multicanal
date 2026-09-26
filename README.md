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

## Decision matrices

The scores, cost lines and risk register behind the deliverables are CSV files in [`analysis/`](analysis). To recompute them after changing a figure:

```
python analysis/scoring.py
python analysis/costing.py
python analysis/risks.py
python -m unittest discover analysis
```
