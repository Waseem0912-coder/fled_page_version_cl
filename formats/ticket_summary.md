# Ticket/Issue Summary Report Format

## Metadata
- title: "Ticket & Issue Summary Report"
- max_words: 2000
- date_format: "YYYY-MM-DD"

## Section Weights
- Overview & Statistics: 0.15
- Critical Issues: 0.25
- Issue Categories: 0.20
- Resolution Status: 0.15
- Trends & Patterns: 0.15
- Action Items: 0.10

## Structure

### Overview & Statistics
High-level snapshot of ticket/issue landscape:

**Reporting Period**: [Start Date] to [End Date]

**Volume Metrics**:
| Metric | Count | Change from Previous Period |
|--------|-------|----------------------------|
| Total Tickets Opened | [#] | [+/-#] ([%]) |
| Total Tickets Closed | [#] | [+/-#] ([%]) |
| Currently Open | [#] | [+/-#] ([%]) |
| Backlog Size | [#] | [+/-#] ([%]) |

**Priority Distribution**:
| Priority | Open | Closed | Avg Resolution Time |
|----------|------|--------|---------------------|
| Critical (P1) | [#] | [#] | [X hours/days] |
| High (P2) | [#] | [#] | [X hours/days] |
| Medium (P3) | [#] | [#] | [X hours/days] |
| Low (P4) | [#] | [#] | [X hours/days] |

**SLA Performance**:
- Tickets resolved within SLA: [#] ([%])
- Tickets breached SLA: [#] ([%])
- Average time to first response: [X hours]
- Average resolution time: [X hours/days]

**Source Breakdown**:
- Customer reported: [#] ([%])
- Internal discovery: [#] ([%])
- Automated monitoring: [#] ([%])
- Escalations: [#] ([%])

### Critical Issues
Detailed analysis of high-priority issues requiring immediate attention:

**Currently Open Critical Issues**:

For each critical issue:
---
**[TICKET-ID]: [Issue Title]**
- **Status**: Open / In Progress / Pending / Blocked
- **Priority**: Critical (P1) / High (P2)
- **Severity**: [Service Impact Level]
- **Reported Date**: YYYY-MM-DD
- **Reporter**: [Name/Customer/System]
- **Assigned To**: [Team/Individual]
- **Age**: [X days]

**Description**:
Detailed explanation of the issue including:
- What is happening (symptoms)
- Where it is occurring (system, component, environment)
- Who is affected (users, customers, internal teams)
- When it started (first occurrence, frequency)

**Business Impact**:
- Users/customers affected: [Number or scope]
- Revenue impact: [If quantifiable]
- Operational impact: [Description]
- Reputational risk: [Assessment]

**Technical Details**:
- Error messages or codes observed
- Affected systems/services
- Related configuration or changes
- Reproduction steps if known

**Current Status & Actions**:
- Investigation findings to date
- Workarounds in place (if any)
- Next steps planned
- Estimated resolution date

**Dependencies/Blockers**:
- What is preventing resolution
- External dependencies
- Resource constraints
---

### Issue Categories
Breakdown of issues by type and area:

**By Issue Type**:
| Type | Open | Closed | % of Total | Trend |
|------|------|--------|------------|-------|
| Bug/Defect | [#] | [#] | [%] | [Up/Down/Stable] |
| Feature Request | [#] | [#] | [%] | [Up/Down/Stable] |
| Performance | [#] | [#] | [%] | [Up/Down/Stable] |
| Security | [#] | [#] | [%] | [Up/Down/Stable] |
| Documentation | [#] | [#] | [%] | [Up/Down/Stable] |
| Configuration | [#] | [#] | [%] | [Up/Down/Stable] |
| Integration | [#] | [#] | [%] | [Up/Down/Stable] |
| User Error | [#] | [#] | [%] | [Up/Down/Stable] |

**By Component/System**:
| Component | Open Issues | Critical | High | Medium | Low |
|-----------|-------------|----------|------|--------|-----|
| [Component A] | [#] | [#] | [#] | [#] | [#] |
| [Component B] | [#] | [#] | [#] | [#] | [#] |

**By Team/Owner**:
| Team | Assigned | Resolved This Period | Avg Resolution Time | SLA Compliance |
|------|----------|---------------------|---------------------|----------------|
| [Team A] | [#] | [#] | [X days] | [%] |
| [Team B] | [#] | [#] | [X days] | [%] |

**Recurring Issues**:
Issues that have occurred multiple times:
- [Issue pattern]: [# occurrences], Root cause: [Known/Unknown], Fix status: [Planned/In Progress/None]

### Resolution Status
Tracking of issue progression and closure:

**Recently Resolved** (this reporting period):

| Ticket ID | Title | Priority | Resolution | Time to Resolve | Resolved By |
|-----------|-------|----------|------------|-----------------|-------------|
| [ID] | [Title] | [P1-P4] | [Fix type] | [X days] | [Team/Person] |

**Resolution Types**:
- Fixed/Patched: [#] ([%])
- Workaround Provided: [#] ([%])
- Configuration Change: [#] ([%])
- User Education: [#] ([%])
- Cannot Reproduce: [#] ([%])
- Duplicate: [#] ([%])
- Won't Fix: [#] ([%])
- External Dependency: [#] ([%])

**Aging Analysis** (currently open tickets):
| Age Bracket | Count | P1 | P2 | P3 | P4 |
|-------------|-------|----|----|----|----|
| 0-7 days | [#] | [#] | [#] | [#] | [#] |
| 8-14 days | [#] | [#] | [#] | [#] | [#] |
| 15-30 days | [#] | [#] | [#] | [#] | [#] |
| 31-60 days | [#] | [#] | [#] | [#] | [#] |
| 60+ days | [#] | [#] | [#] | [#] | [#] |

**Stale Tickets** (no activity > 14 days):
- List of tickets requiring follow-up
- Reason for stagnation
- Recommended action

### Trends & Patterns
Analysis of issue patterns over time:

**Volume Trends**:
- Week-over-week change: [+/-#] ([%])
- Month-over-month change: [+/-#] ([%])
- Seasonal patterns observed: [Description]
- Anomalies noted: [Description]

**Quality Indicators**:
- Defect escape rate: [%] (issues found post-release)
- Regression rate: [%] (previously fixed issues recurring)
- First-contact resolution rate: [%]

**Root Cause Analysis Summary**:
Top contributing factors for issues this period:
1. [Root cause category]: [#] issues ([%])
   - Examples: [Brief descriptions]
   - Systemic fix status: [In progress/Planned/None]
2. [Root cause category]: [#] issues ([%])
3. [Root cause category]: [#] issues ([%])

**Correlation Findings**:
- Issues correlated with recent deployments: [List]
- Issues correlated with infrastructure changes: [List]
- Issues correlated with external factors: [List]

**Predictive Indicators**:
- Areas likely to generate issues based on patterns
- Recommended proactive measures

### Action Items
Concrete next steps derived from this analysis:

**Immediate Actions** (next 48-72 hours):
| Action | Owner | Due Date | Related Tickets |
|--------|-------|----------|-----------------|
| [Description] | [Name] | YYYY-MM-DD | [IDs] |

**Short-term Actions** (next 1-2 weeks):
| Action | Owner | Due Date | Expected Impact |
|--------|-------|----------|-----------------|
| [Description] | [Name] | YYYY-MM-DD | [Impact] |

**Process Improvements**:
- Recommended changes to prevent recurring issues
- Tooling or automation opportunities
- Training or documentation needs

**Escalations Required**:
- Issues requiring management attention
- Resource requests
- Policy or process decisions needed

**Follow-up Reviews Scheduled**:
- Next status review: [Date]
- Deep-dive sessions planned: [Topics and dates]
- Stakeholder communications: [Audience and timing]
