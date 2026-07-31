# M18 Implementation TODO

## Current Status

Completed:

- sales quotation requirements
- architecture definition
- extension guide
- sales quotation skill
- customer skill
- quotation API wrapper
- customer API wrapper
- reference resolver
- quotation service
- customer service
- unit test scaffolding
- usage examples
- UAT authentication verification
- UAT customer lookup verification
- UAT customer contact discovery (`data.cust`)
- UAT quotation bsFlow verification
- UAT quotation standard save verification
- UAT sales order bsFlow verification
- UAT sales order standard save verification
- UAT customer-part EBI verification (`Jeff-CustomerPartAPI`, format `102`)

### Environment Calibration — Completed 2026-05-09

- ✅ Superseded: the earlier `qut.unitId = proId` conclusion was incorrect. Standard sales lines require the product `price.id`.
- ✅ `unit_master` strategy (resolving PCS from unit table) **does NOT work** — returns `core_201` "unit already used"
- ✅ Superseded: `sot.unitId` also requires the product `price.id`.
- ✅ `staffCode` is now **required** — user must specify staffCode; system resolves via `stSearch=staff`

### Priority 2: Real Integration Verification

- verified: `examples/customer_lookup.py`
- verified: customer payload inspection and contact extraction
- verified: `examples/customer_item_lookup.py`
- verified: `examples/quotation_create_draft.py`
- verified: `examples/quotation_save.py`
- verified: `examples/sales_order_create_draft.py`
- verified: `examples/sales_order_save.py`

### Priority 3: Code Hardening

- add explicit config loader abstraction
- normalize all business exceptions into one shared format
- keep customer-part query output normalized while preserving raw EBI rows for debugging
- add audit logging
- narrow contact table candidates now that `data.cust` is confirmed

### Priority 4: Expand Coverage

- product lookup service: completed
- add Vendor lookup service
- add Purchase Order object
- add approval-safe write restrictions

## Implementation Notes

- Unit resolution corrected: `qut/sot.unitId` is the product `price.id`; global `unit.id` is only used to select that product price row. `staffId` is optional in bsFlow drafts.
- `product_price` is the only supported standard sales-unit mode; legacy
  `unit_master` and `pro_id` calibration notes are superseded.
- `unit_master` strategy (resolving PCS from unit table) does NOT work in this UAT environment — use `pro_id` only
- do not move business field rules into API client
- do not duplicate resolver logic in new services
- treat `qut.unitId` in standard quotation save as an environment-specific rule, not a universal M18 assumption
- treat `sot.unitId` in standard sales order save the same way — verified matching behavior
