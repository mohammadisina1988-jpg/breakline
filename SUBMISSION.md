# Breakline

**Category** · Intelligent Contracts

Breakline turns an independently observed annual time series into exact change-point models. Consumers can change the penalty for adding a cut and compare the resulting models without rerunning the observation.

The leader and each GenLayer validator independently fetch a public commit-pinned mirror of NASA's GISTEMP data. They check that the complete 2000–2023 annual series is present and require exact agreement on all 24 normalized observations. The contract uses those values to minimize squared error for each model with one to four segments, with at least three years per segment. One publication stores all four fits and their exact rational scores.

The live StudioNet run selected four segments at zero penalty, two at the middle tested penalty, and one at the highest. The optimal two-segment fit started its second segment in 2015. GenVM lint and six direct tests passed. Read-only replay verified the deployed source, all four models, the exact selection results, and three finalized transactions.

- **Repository** · [Source, tests, and documentation](https://github.com/mohammadisina1988-jpg/breakline)
- **StudioNet Explorer** · [Deployed contract](https://explorer-studio.genlayer.com/address/0xA45Fd551fabb0f9072a4Ba95e67791E20F5eBa8e)
- **Proofs** · [Finalized receipts, models, and penalty selections](https://github.com/mohammadisina1988-jpg/breakline/blob/main/proofs/studionet.json)
