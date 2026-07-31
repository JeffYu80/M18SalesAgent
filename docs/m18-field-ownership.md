# M18 Field Ownership

## Purpose

This document defines where different categories of fields should live in the
architecture.

## Field Categories

### 1. User Business Fields

Examples:

- `cusCode`
- `proCode`
- `unitCode`
- `qty`
- `up`
- contact `email`
- contact `phone`

Owner:

- Agent captures them
- Skill defines whether they are valid or required
- Service maps them into downstream operations

### 2. Business Rule Fields

Examples:

- whether `cusCode` is enough for draft create
- whether `flowTypeId` is required for standard save
- which fields are required for quotation lines

Owner:

- Skill layer

### 3. Resolved Internal Fields

Examples:

- `cusId`
- `proId`
- global `unit.id` (resolved from `unitCode`)
- sales-line `unitId` (`price.id`, resolved from product + unit + date)

Owner:

- Resolver layer; callers must not construct sales-line `unitId` from a
  global unit or product ID
- Service layer uses them after resolution

### 4. M18 Payload Fields

Examples:

- `mainqu.values[]`
- `qut.values[]`
- `remqu.values[]`

Owner:

- Service assembles payload shape
- API wrapper submits payload

### 5. Transport Fields

Examples:

- `authorization`
- `client_id`
- request `params`
- HTTP method
- endpoint path

Owner:

- API client

## Summary Rule

Use this short rule when deciding where a field belongs:

- if the user says it, Agent receives it
- if the business requires it, Skill defines it
- if M18 needs an internal ID, Resolver resolves it
- if it becomes part of a document body, Service assembles it
- if it is part of HTTP transport, API client owns it
