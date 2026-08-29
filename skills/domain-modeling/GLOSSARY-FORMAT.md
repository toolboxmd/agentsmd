# GLOSSARY.md Format

## Structure

```md
# {Domain Name} Glossary

**Order**:
A request by a Customer for one or more Products.
_Avoid_: Purchase, transaction

**Invoice**:
A request for payment sent to a Customer after delivery.
_Avoid_: Bill, payment request

**Customer**:
A person or organization that places Orders.
_Avoid_: Client, buyer, account
```

## Rules

- **Pick one term.** List competing names under `_Avoid_`.
- **Keep definitions tight.** Use one or two sentences that define what the
  concept is.
- **Keep the glossary domain-specific.** Exclude general programming concepts,
  implementation details, plans, and routine decisions.
- **Group terms only when useful.** A cohesive glossary may remain flat.

## Single and multiple domains

Most repositories use one root `GLOSSARY.md`.

When multiple distinct domains need separate language, create a root
`GLOSSARY-MAP.md`:

```md
# Glossary Map

## Domains

- [Ordering](./src/ordering/GLOSSARY.md): receives and tracks Customer Orders
- [Billing](./src/billing/GLOSSARY.md): issues Invoices and records Payments
- [Fulfillment](./src/fulfillment/GLOSSARY.md): picks and ships Orders

## Relationships

- **Ordering to Fulfillment**: an accepted Order starts fulfillment
- **Fulfillment to Billing**: a dispatched shipment authorizes invoicing
```

If the relevant domain is unclear, ask before writing.

## Legacy fallback

Legacy `CONTEXT.md` and `CONTEXT-MAP.md` files may be read only when their
new-name replacements are absent. They are migration inputs, not write
targets. Write all resolved language to `GLOSSARY.md` or
`GLOSSARY-MAP.md`.
