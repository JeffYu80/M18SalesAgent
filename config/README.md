# Local Config

## Files

- `m18.uat.yaml`: UAT connection and business configuration
- `m18.prod.yaml`: production connection and business configuration (local, not tracked)
- `m18_api_token.example.yaml`: legacy shareable credentials template
- `m18_business.example.yaml`: legacy shareable business-defaults template

## Notes

- `M18Client` reads `config/m18.{M18_ENV}.yaml`; `M18_ENV` defaults to `uat`.
- If the selected environment file is missing, startup fails. It never falls back to UAT.
- `password_sha1` should already be the SHA1 value required by M18 token auth.
- `quotation_standard_unit_mode` and `sales_order_standard_unit_mode` should
  be `product_price`: standard `qut/sot.unitId` is the matching product
  `price.id`, not `proId` or global `unit.id`.
- `entity_currency_by_be_id` should list each production business entity's
  base `curId`; `default_cur_id` is used only when that entity-specific entry
  is absent.
- Set `require_entity_currency_mapping: true` in Production so a new or
  unconfigured `beId` fails instead of using `default_cur_id`.
- `exchange_rate_field` selects M18's `openRate` (default) or `closeRate` for
  newly created foreign-currency documents.
- See `docs/m18-currency-usage.md` for caller examples and the quotation-to-
  order rate-refresh rule.
