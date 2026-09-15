# Case Study: Real IPC Price-Adjustment History vs. This Project's Model

- Anonymized case: Ugandan government road contract, Design & Build, MDB-harmonized FIDIC terms
- 37 valuation periods, 2019-05-14 to 2024-02-11
- Formula weights (as actually specified in this contract): fixed 0.20; fuel 0.10; bitumen 0.20; steel 0.05; cement 0.10; equipment 0.10; labour 0.15; metal products 0.10
- Petroleum-linked share of the *variable* (non-fixed) portion — fuel + bitumen — is **37.5%**
- This contract's own index-reference lag (valuation date minus period end) is median 49 days (range 49-49)

## Convergent validity
- local_fuel_index_level_vs_brent_level: r = 0.602 (p = 0.0001, n = 37)
- local_fuel_index_level_vs_cipi_diesel_level: r = 0.999 (p = 0.0000, n = 37)
- foreign_fuel_index_level_vs_brent_level: r = 0.956 (p = 0.0000, n = 38)
- local_bitumen_index_level_vs_brent_level: r = 0.500 (p = 0.0016, n = 37)
- local_fuel_return_vs_brent_return: r = 0.099 (p = 0.5648, n = 36)
- local_fuel_return_vs_cipi_diesel_return: r = 0.989 (p = 0.0000, n = 36)

## Structural break replication (contract's own fuel index, split at Feb 2022)
- Pre-2022-02 mean monthly return: 0.508% (n=17)
- Post-2022-02 mean monthly return: 1.336% (n=19)
- Ratio post/pre: 2.63x