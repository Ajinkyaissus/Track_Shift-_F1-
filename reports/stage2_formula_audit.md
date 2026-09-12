# STAGE 2 FORMULA AUDIT & MATHEMATICAL DERIVATION

### Authoritative Stage 2 Production Formula

1. **Stage 1 Baseline:** $\hat{y}_i = 0.1974 + 0.0400 \cdot \text{tyre\_age}_i$
2. **Residual (Contextual Deviation):** $r_i = y_i - \hat{y}_i$
3. **Tyre Debt Increment:** $\text{debt\_increment}_i = \max(0.0, r_i)$
4. **Cumulative Tyre Debt:** $\text{cumulative\_debt}_i = \sum_{k=1}^i \text{debt\_increment}_k$

### Resolution of Documentation Inconsistency

Because the Stage 1 M1 baseline already models expected linear tyre degradation (beta_1 * tyre_age), the residual r_i = y_i - y_hat_i directly measures deviation relative to expected degradation. Subtracting expected degradation a second time would constitute double-subtraction. Thus, debt_increment = max(0, residual) is mathematically exact.
