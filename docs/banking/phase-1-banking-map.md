# Victor Banking System Map

Last reviewed: April 17, 2026

This document maps the first strong version of Victor's member banking system with a thin Discord surface, a treasury-holding Highrise bot, and a platform-ledger core that can later back Blackmarket settlement.

## System Shape

The bank should be split into three roles:

- Highrise bot: treasury rail that receives real gold and executes approved payouts.
- Bank platform: source of truth for accounts, ledger entries, taxes, escrow, and reconciliation.
- Discord bot: member-facing terminal for balance visibility, transfers, and staff review.

The platform is the bank.
Discord is only an interface.
Highrise is only the deposit and payout rail.

## Core Boundaries

Discord should handle only:

- account linking
- balance visibility
- member-to-member transfers
- Blackmarket settlement prompts and status views
- staff approval and review actions

The platform should handle:

- all balances and account state
- all tax and fee rules
- savings logic
- treasury backing rules
- escrow rules
- payout eligibility
- fraud checks
- reconciliation
- analytics and reporting

Highrise should handle:

- incoming gold to the treasury bot
- confirmed tip events
- wallet balance reads
- approved outbound payouts

## Primary Product Rules

These rules define the first safe version of the bank:

1. The Highrise bot treasury holds the real funds.
2. Member balances exist in the platform ledger, not in Discord.
3. Deposits are credited only from confirmed Highrise tip events.
4. Internal transfers happen inside the ledger and do not touch Highrise.
5. Savings is the only withdrawable member balance.
6. Checking is the default activity balance for transfers and market movement unless policy later changes.
7. Taxes and fees are collected automatically inside the bank ledger.
8. No action should mutate balances without an auditable transaction trail.
9. Treasury-backed balance must always be distinguishable from user-visible balance.
10. Blackmarket should use escrow and ledger settlement, not ad hoc manual balance edits.

## Account Model

The first clean account model is:

- Member checking
  - liquid internal balance
  - used for transfers and routine market activity
- Member savings
  - withdrawable balance
  - moved into intentionally by the member or by policy
- Treasury reserve
  - platform-side representation of the Highrise bot wallet
- Tax reserve
  - collected taxes and fees
- Blackmarket escrow
  - funds temporarily locked for open deals
- Pending deposits
  - incoming events awaiting confirmation or idempotent processing
- Pending withdrawals
  - approved or queued payouts not yet completed in Highrise
- Adjustment reserve
  - staff-controlled correction lane with strict audit requirements

Each member should have at least:

- one checking account
- one savings account
- one linked Highrise identity record

## Identity Model

The bank only works if identity linking is strong.

Required identity linkage:

- Discord user ID
- Discord guild ID
- Highrise username
- Highrise user ID
- verification status
- last verified timestamp

Important rule:

- Deposits, transfers, and Blackmarket settlement can operate on linked users.
- Withdrawals should require a verified active Highrise identity tied to the same member account.

## Ledger Model

Do not build this around a single mutable `balance` field.
Use a transaction ledger with derived balances.

The minimum financial model should support:

- transaction header
- one or more ledger entries per transaction
- account snapshots or cached balances for read speed
- immutable audit trail

Each transaction should include:

- transaction ID
- transaction type
- status
- idempotency key
- actor type
- actor ID
- source system
- created timestamp
- finalized timestamp
- reference metadata

Each ledger entry should include:

- entry ID
- transaction ID
- account ID
- member ID if applicable
- direction
- amount
- asset type
- resulting balance snapshot if cached
- note or reason code

## Balance Views

Members should never see a vague single number.

The platform should calculate or expose:

- checking balance
- savings balance
- escrowed balance
- pending incoming balance
- pending outgoing balance
- available transfer balance
- available withdrawal balance

The treasury side should calculate:

- wallet observed balance
- total user liabilities
- total savings liabilities
- reserved escrow liability
- tax reserve holdings
- available treasury buffer

## Transaction Types

The initial banking core should support these transaction families:

- Highrise deposit credit
- internal transfer
- checking to savings move
- savings to checking move
- Blackmarket escrow hold
- Blackmarket escrow release
- Blackmarket settlement
- Blackmarket refund
- tax collection
- withdrawal request creation
- withdrawal payout completion
- withdrawal payout failure rollback
- staff adjustment

The important part is that all of them use the same ledger model.

## Transaction Lifecycles

### Highrise deposit

1. Highrise bot receives tip event.
2. Event is normalized into a deposit payload.
3. Platform checks idempotency against source event data.
4. Platform credits member checking.
5. Platform offsets treasury reserve.
6. Platform stores the event as completed.

### Internal transfer

1. Member initiates transfer in Discord.
2. Platform verifies sender and available transfer balance.
3. Platform debits sender checking.
4. Platform credits recipient checking.
5. Platform records immutable transaction and emits a summary back to Discord.

### Savings withdrawal

1. Member requests withdrawal from savings.
2. Platform verifies linked Highrise identity and available withdrawable balance.
3. Platform moves funds into pending withdrawals.
4. Staff or policy engine approves if needed.
5. Highrise bot attempts payout.
6. On success, pending withdrawal clears and treasury reserve is reduced.
7. On failure, funds return to savings or remain pending depending on failure mode.

### Blackmarket settlement

1. Buyer commits funds.
2. Platform locks funds into Blackmarket escrow.
3. Trade completes or staff confirms completion.
4. Platform calculates tax.
5. Platform credits seller net proceeds.
6. Platform credits tax reserve.
7. Platform clears escrow.

## Tax Model

Taxes should be platform-native, not manually collected.

The first version should support:

- transfer tax policy
- market settlement tax policy
- withdrawal fee policy if desired later

Recommended first rule:

- do not tax ordinary member transfers at launch unless there is a clear policy reason
- do tax Blackmarket settlement inside the bank

Tax handling should:

- calculate from a stable policy config
- round consistently
- move tax into `tax_reserve`
- keep gross and net amounts visible in the transaction record

## Treasury Backing Rules

This is the safety core of the system.

The bank must distinguish:

- user balances owed
- treasury funds actually held
- locked reserves
- tax-owned funds

The system should regularly compare:

- Highrise wallet observed gold
- total checking liabilities
- total savings liabilities
- total escrow liabilities
- total pending withdrawal liabilities
- total tax reserve

The bank must be able to answer:

- Are all user balances fully backed?
- Are withdrawals safe to approve?
- Is escrow overcommitted?
- Has the treasury drifted from the ledger?

## Reconciliation Model

Reconciliation should be built early, not after launch.

The first version should include:

- periodic wallet snapshot from Highrise bot
- comparison against ledger liabilities
- discrepancy report
- alert state for treasury mismatch

Reconciliation states:

- healthy
- warning
- critical

If the treasury is under-backed:

- new withdrawals should pause
- staff should receive a clear alert
- Blackmarket settlement should still be controllable by policy

## Discord Surface

Discord should stay intentionally small.

Member-facing actions:

- view balances
- transfer to another linked member
- view recent transaction summaries

Staff-facing actions:

- review withdrawal queue
- review treasury health
- review disputed or failed market settlements
- approve or reverse staff-controlled actions

Discord should not become the full banking system UI.

## Blackmarket Integration Path

Blackmarket should connect to the bank only after the bank core is stable.

The future integration should look like this:

- listing exists in Blackmarket
- buyer confirms purchase path
- bank locks buyer funds in escrow
- staff or seller marks fulfillment
- bank settles seller proceeds minus tax
- Blackmarket reads settlement state from the bank

Important boundary:

- Blackmarket should never directly edit balances
- it should request bank actions and receive bank outcomes

## Minimal Data Model

The first platform schema should cover these concepts:

- `linked_accounts`
  - discord user and guild mapping to Highrise identity
- `bank_accounts`
  - per-member checking and savings plus system accounts
- `transactions`
  - transaction headers and lifecycle state
- `ledger_entries`
  - detailed debits and credits
- `withdrawal_requests`
  - member withdrawal intent and payout execution state
- `treasury_snapshots`
  - observed Highrise wallet snapshots
- `market_escrows`
  - escrow records tied to Blackmarket deals
- `risk_events`
  - reconciliation failures, suspicious patterns, or manual review flags

## Invariants

These should stay true at all times:

- no negative account balances unless a specific account type explicitly allows it
- every balance-changing action is tied to a transaction record
- every external event uses an idempotency key
- every withdrawal is backed by sufficient treasury funds at approval time
- every escrow hold is either settled or released
- every staff adjustment includes actor ID and reason
- Blackmarket balance actions must route through the bank platform

## Build Order

Phase 1:

- identity linking review
- bank account model
- ledger and transaction engine
- treasury snapshot model
- thin Discord balance and transfer surface

Phase 2:

- savings movement rules
- withdrawal request lifecycle
- payout worker handoff to Highrise bot
- reconciliation reporting

Phase 3:

- Blackmarket escrow integration
- tax reserve automation
- dispute and refund tooling

## Recommended First Deliverable

The first thing to actually build is not a long command set.

It should be:

- linked member account records
- checking and savings accounts
- transaction and ledger tables
- one clean internal transfer flow
- one clean balance summary view

Once that is stable, the rest of the system can hang off it cleanly.
