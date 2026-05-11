# M18 Usage Examples

These examples show how to use the current architecture through the service
layer instead of calling raw M18 endpoints directly.

## Files

- `_debug_utils.py`
- `customer_lookup.py`
- `customer_contacts.py`
- `product_lookup.py`
- `customer_item_lookup.py`
- `inspect_customer_payload.py`
- `quotation_create_draft.py`
- `quotation_save.py`
- `sales_order_create_draft.py`
- `sales_order_save.py`

## Notes

- All examples assume your `M18Client` credentials are configured correctly.
- The examples are intentionally small so you can swap in real `beId`,
  `beCode`, customer codes, product codes, and unit codes.
- For new draft creation, prefer `quotation_create_draft.py`.
- For standard save with code-to-ID resolution, use `quotation_save.py`.
- For customer contact calibration, run `inspect_customer_payload.py` first.
- Use `product_lookup.py` for product master verification.
- Use `customer_item_lookup.py` for customer item code style queries.
- The sales-order examples mirror the quotation flow and are intended for the
  next integration step after quotation is stable.
