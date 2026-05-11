# M18 Extension Guide

## Purpose

This guide defines how to extend the M18 integration after the first
Sales Quotation implementation.

The goal is to let new modules grow without breaking architectural
consistency.

## Extension Categories

There are three common expansion types.

### 1. New Business Object

Examples:

- Sales Order
- Purchase Order
- Delivery Note
- Customer
- Customer Contact
- Product

Typical work:

- add a new skill
- add a new domain service
- optionally add an object-specific API wrapper
- reuse or extend the shared resolver

### 2. New Action on an Existing Object

Examples for Sales Quotation:

- update line items
- add remarks
- delete lines
- support more fields
- add pre-checks

Typical work:

- update the existing skill rules
- add service methods
- add wrapper methods only if transport behavior changes

### 3. Shared Infrastructure Enhancement

Examples:

- audit logging
- caching
- permission profiles
- rate limiting
- configuration centralization
- batch execution support

Typical work:

- extend shared API utilities
- extend shared resolvers or common base services
- avoid embedding shared concerns in one business module

## Standard Extension Workflow

Whenever a new M18 function is added, follow this sequence:

1. Confirm the official M18 object definition and endpoint pattern
2. Decide whether the feature is a new object or a new action
3. Create or update the relevant skill
4. Reuse existing resolver methods where possible
5. Add new resolver methods only for new reference types
6. Add or update the domain service
7. Add or update the object-specific API wrapper if needed
8. Add tests for the new flow
9. Extend the agent only after lower layers are stable

## Resolver Growth Rules

Resolvers should expand by reference type, not by page or scenario.

Recommended shared resolver methods:

- `resolve_customer_code`
- `resolve_customer_contact`
- `resolve_vendor_code`
- `resolve_product_code`
- `resolve_unit_code`
- `resolve_staff_code`
- `resolve_currency_code`
- `resolve_warehouse_code`

Rules:

- keep lookup logic centralized
- do not duplicate the same lookup flow across services
- fail explicitly on ambiguous matches

## Service Growth Rules

Services should be organized around business actions, not HTTP endpoints.

Good examples:

- `create_quotation_draft`
- `update_quotation_lines`
- `search_customers`
- `get_customer_contacts`
- `create_sales_order_draft`
- `create_purchase_order_draft`

Avoid exposing service methods that are little more than renamed URLs.

## When To Introduce Base Classes

Avoid early abstraction when only one object exists.

Consider shared base classes after at least three business objects have been
implemented and patterns are proven stable.

Likely candidates:

- `BaseM18EntityService`
- `BaseM18DocumentAPI`
- `BaseReferenceResolver`

## Suggested Rollout Order

A practical rollout sequence is:

1. Sales Quotation
2. Customer / Customer Contact / Product / Unit resolvers
3. Sales Order
4. Purchase Order
5. Delivery / Inventory / Pricing
6. EBI
7. Approval / Audit / Batch tools

Current status:

- Sales Quotation is implemented and UAT-verified
- Customer and Customer Contact lookup are implemented and UAT-verified
- Sales Order is implemented and UAT-verified

## Common Pitfalls

- duplicating `code -> ID` logic in multiple modules
- letting the agent construct payloads directly
- mixing HTTP details into skill definitions
- putting shared concerns inside one object-specific service
- writing new modules without verifying official M18 object codes first

## Definition of Done for Any New Module

A new M18 module is considered complete when:

- the official object code and tables are documented
- the correct write path rule is defined
- the service can execute at least one real business action
- code-to-ID resolution is either reused or added centrally
- test coverage exists for success and failure cases
- the agent can present results in business language
