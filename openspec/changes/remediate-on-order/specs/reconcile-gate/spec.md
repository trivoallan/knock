## ADDED Requirements

### Requirement: an approved operation can be withheld for a stated reason

Under `--apply-plan`, knock SHALL withhold an approved operation it cannot honour and SHALL report
the reason with the `withheld` count: `remediation-undeclared` when the operation carries a
remediation order its import does not declare, `remediation-unstaged` when it carries an order and
the run has no `--stage-to`. A withheld operation SHALL leave its destination tag as it was, and the
plan's other operations SHALL be applied.

#### Scenario: Approved order the policy cannot honour

- **WHEN** the filtered plan approves an import carrying a remediation order and the import declares
  no `remediate:` step
- **THEN** the import is not placed, it is reported withheld with `remediation-undeclared`, and the
  plan's other operations are applied
