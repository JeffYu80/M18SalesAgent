---
name: M18Product
description: >
  M18 product master skill for product lookup, product load, unit/default
  extraction, and customer item code queries driven by the
  `Jeff-CustomerPartAPI` EBI report.
---

# M18 Product Skill

This skill defines the domain rules for product master lookup in M18.
It focuses on:

- product search
- product load
- default unit extraction
- external product code lookup
- customer item code query flows

## Official Object Definition

- Menu code: `pro`

## Supported Actions

- `product.search`
- `product.load`
- `product.resolve_code`
- `product.units`
- `product.customer_item_codes`

## Business Field Contract

### Product Search

Accepted business fields:

- `beId`
- `quickSearchStr`
- `startRow`
- `endRow`

### Product Load

Accepted business fields:

- `productId`

### Customer Item Code Query

Accepted business fields:

- `customerCode`
- `productCode`
- `beId`

Expected output:

- customer identity
- product identity
- normalized customer-part matches
- raw matching customer-part rows from the EBI report
- optional product-side external reference candidates as supplemental data

## Important UAT Note

The current UAT environment has a confirmed EBI report for customer-part
lookup:

- `formatId = 102`
- `code = Jeff-CustomerPartAPI`
- `desc = 客户料号列表`

Therefore `customer_item_codes` should use this EBI report as its primary
data source.

Product-side external references remain useful as supplemental data, but they
are no longer the primary customer-item lookup source.

## Verified EBI Field Mapping

The current UAT report returns these business-relevant fields:

- `CUS_A_code` -> customer code
- `CUS_A_id` -> customer ID
- `CUS_A_desc__lang` -> customer name
- `PRO_A_code` -> product code
- `PRO_A_id` -> product ID
- `PRO_A_desc__lang` -> product name
- `F_A_refCode` -> customer part code

Service output should normalize these fields for agent-facing consumption.

## MCP Tools

This skill's actions are exposed as MCP tools via `mcp_sales.py`:

| Skill Action | MCP Tool |
|---|---|
| `product.search` | `product_search` |
| `product.load` | `product_load` |
| `product.units` | `product_units` |
| `product.customer_item_codes` | `product_customer_item_codes` |
| `product.customer_part_lookup` | `customer_part_lookup` |
| `product.customer_part_list_all` | `customer_part_list_all` |
