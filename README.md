# distribution-multicanal

Urbanization study for a multi-channel retailer: centralizing siloed ERP, CRM, POS, e-commerce, web analytics, social media and customer support data into a datamart / lakehouse for sales performance, inventory optimization and customer segmentation.

Spec and work breakdown: issue #1.

## Deliverables

| # | Deliverable | Issue |
|---|---|---|
| 1 | [Architecture options comparison & recommendation](docs/deliverables/01-architecture-options.md) | #2 |

## Decision matrices

The scores behind the deliverables are CSV files in [`analysis/`](analysis). To recompute the rankings after changing a score or weight:

```
python analysis/scoring.py
python -m unittest discover analysis
```
