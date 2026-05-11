# M18 Integration Architecture

## Overview

The M18 integration should use a four-layer architecture:

1. Agent
2. Skill
3. Resolver / Domain Service
4. API Client

This architecture keeps user interaction, business rules, data resolution,
and technical transport clearly separated.

It also distinguishes between:

- business fields
- transport fields
- resolved internal identifiers

## Layer Responsibilities

### 1. Agent Layer

Purpose:

- interact with users
- detect intent
- collect missing business inputs
- call skill actions
- summarize outputs

The agent must not:

- construct raw M18 URLs
- translate business codes to IDs
- embed M18 table structures

### 2. Skill Layer

Purpose:

- define business rules for one M18 object or domain
- choose the correct write path
- define required fields
- define error interpretation

The skill must:

- know object identity such as `oldqu`, `mainqu`, `qut`, `remqu`
- decide between `bsFlow` and standard `save`
- expose business actions such as `quotation.search` and `quotation.save`
- define the business-facing field contract for each action

The skill must not:

- perform raw HTTP requests
- manage token state
- own generic retry logic

### 3. Resolver / Domain Service Layer

Purpose:

- bridge user business inputs to M18-ready payloads
- resolve codes into IDs when required
- orchestrate object-specific business flows

This layer contains two sub-concerns:

- reference resolution
- domain workflow composition

Reference resolution examples:

- `cusCode -> cusId`
- `proCode -> proId`
- `unitCode -> unitId`

Domain service examples:

- create quotation draft from codes
- create or update quotation with IDs
- load quotation summary
- search customer master data
- extract or query customer contacts

### 4. API Client Layer

Purpose:

- execute authenticated HTTP requests to M18
- manage tokens
- apply retries
- normalize common failures

The API client should expose reusable primitives:

- `search`
- `read`
- `save`
- `delete`
- `bsflow_save`

The API client should not own business field definitions. It should only
accept already-decided params and payloads.

Object-specific wrappers may sit on top of the shared client when a module
needs its own helper methods.

## Core Design Rule

Users speak in business codes.

The system should preserve codes as long as possible and only resolve to IDs
when a standard `save` path requires them.

This means:

- new draft creation should prefer `bsFlow`
- existing-record updates should prefer standard `save`
- code-to-ID logic must be centralized

## Where Business Fields Should Be Defined

Business fields should be defined primarily in the Skill layer and assembled
in the Resolver / Domain Service layer.

Recommended ownership:

- Agent layer:
  captures user intent and business inputs such as customer code, item code,
  quantity, contact name, phone, and email filters
- Skill layer:
  defines which business fields are valid or required for each business action
- Resolver / Domain Service layer:
  maps those business fields into lookup operations and final M18 payload
  structures
- API Client layer:
  only sends the final params and payload to M18

In short:

- business field rules live in Skill
- business field mapping lives in Service / Resolver
- transport field execution lives in API Client

## Recommended Repository Structure

```text
agents/
  m18-sales-quotation-agent/
    AGENT.md

skills/
  M18SalesQuotation/
    SKILL.md
  M18Customer/
    SKILL.md

services/
  reference_resolver.py
  quotation_service.py
  customer_service.py

scripts/
  m18_api.py
  m18_sales_quotation_api.py
  m18_customer_api.py

tests/
  test_reference_resolver.py
  test_quotation_service.py
  test_sales_quotation_api.py
  test_customer_service.py
```

## First Vertical Slice

The first implementation target is Sales Quotation:

- menu code: `oldqu`
- draft create path: `POST /erp/bsFlow/save/oldqu`
- standard save path: `PUT /root/api/save/oldqu`
- search path: `GET /search/search?stSearch=oldqu`

This slice establishes the pattern to be reused for:

- Sales Order
- Purchase Order
- Customer
- Customer Contact
- Product
- Inventory
- EBI

## Success Criteria

The architecture is considered healthy when:

- the agent can create or update quotations without knowing internal IDs
- code-to-ID logic exists in one place only
- new object support can be added by following the same pattern
- business rules are readable without reading low-level transport code
