---
name: M18Customer
description: >
  M18 customer lookup skill for customer master and customer-contact queries.
  Use for customer search, customer load, customer code resolution, and
  customer-contact extraction or lookup support for quotation and sales flows.
---

# M18 Customer Skill

This skill defines the domain rules for customer master lookup in M18.
It focuses on customer search, customer loading, and customer-contact access.

## Official Object Definition

- Menu code: `cus`
- Primary business purpose: customer master lookup

## Supported Actions

- `customer.search`
- `customer.load`
- `customer.resolve_code`
- `customer.contacts`

## Business Field Contract

### Customer Search

Accepted business fields:

- `beId`
- `quickSearchStr`
- `startRow`
- `endRow`

Expected outputs:

- `id`
- `code`
- `desc` or `desc__lang`
- `lastModifyDate`

### Customer Load

Accepted business fields:

- `customerId`

Expected outputs:

- customer header data
- account/profile child tables when present
- contact child tables when present

### Customer Contact Query

Accepted business fields:

- `customerId`
- optional contact filters such as:
  - `name`
  - `email`
  - `phone`
  - `department`

Expected outputs:

- contact rows extracted from the customer response or related data source

## Contact Handling Rule

Because customer-contact storage can vary across M18 deployments, the service
must support both:

- reading contact rows from the customer payload
- applying field-based filtering on extracted contact rows

If no contact child table is exposed by the current payload, the business
result should clearly state that no contact data was found.

## Cooperation Contract

The customer skill owns:

- business field names for customer and contact lookup
- result expectations
- fallback behavior when contact data is unavailable

The service layer owns:

- actual customer lookup execution
- contact row extraction
- field filtering

The API layer owns:

- search and read execution against M18
