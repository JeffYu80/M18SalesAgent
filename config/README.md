# Local Config

## Files

- `m18_api_token.yaml`: local M18 API credentials used by `M18Client`
- `m18_api_token.example.yaml`: shareable template without secrets
- `m18_business.yaml`: local business defaults used by service/examples
- `m18_business.example.yaml`: shareable example business defaults

## Notes

- Do not commit real secrets from `m18_api_token.yaml` into version control.
- `M18Client` reads `config/m18_api_token.yaml` by default.
- `password_sha1` should already be the SHA1 value required by M18 token auth.
- `quotation_standard_unit_mode` controls how standard quotation save resolves
  `qut.unitId`.
