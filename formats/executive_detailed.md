# Detailed Executive Summary Report Format

## Metadata
- title: "Executive Briefing: Situation Analysis & Action Plan"
- max_words: 3000
- date_format: "YYYY-MM-DD"

## Section Weights
- Executive Summary: 0.10
- Situation Overview: 0.15
- Root Cause Analysis: 0.25
- Impact Assessment: 0.25
- Current Situation: 0.10
- Final Action & Recommendations: 0.15

## Structure

### Executive Summary
Concise briefing for senior leadership (max 200 words):

**Subject**: [One-line description of the situation/issue/event]

**Classification**: [Incident / Project Issue / Operational Challenge / Strategic Risk / Opportunity]

**Severity Level**: [Critical / High / Medium / Low]

**Bottom Line Up Front (BLUF)**:
- What happened in 1-2 sentences
- Why it matters to the business
- What we're doing about it
- Key decision or action needed from leadership

**Key Numbers**:
| Metric | Value |
|--------|-------|
| Duration/Timeline | [X hours/days/weeks] |
| Financial Impact | [$X or range] |
| Affected Users/Customers | [#] |
| Systems/Services Impacted | [#] |

**Status**: [Resolved / Contained / In Progress / Monitoring / Escalated]

---

### Situation Overview
Comprehensive context and background:

**Event/Situation Description**:

Detailed narrative covering:
- **What occurred**: Complete description of the event, issue, or situation
- **When it started**: Exact date and time of onset or discovery (YYYY-MM-DD HH:MM timezone)
- **How it was discovered**: Detection method (monitoring, user report, audit, etc.)
- **Initial response**: First actions taken upon discovery

**Timeline of Key Events**:

| Date/Time | Event | Actor | Significance |
|-----------|-------|-------|--------------|
| YYYY-MM-DD HH:MM | [Event description] | [Person/Team/System] | [Why this matters] |
| YYYY-MM-DD HH:MM | [Event description] | [Person/Team/System] | [Why this matters] |

Include all significant events from:
- Initial occurrence or trigger
- Detection and escalation points
- Major investigation milestones
- Mitigation actions taken
- Resolution or current state

**Context & Background**:
- Relevant history (previous similar events, related changes, ongoing projects)
- Environmental factors (market conditions, regulatory context, organizational changes)
- Stakeholders involved or affected
- Prior warnings or indicators that may have been missed

**Scope Definition**:
- **Affected Systems**: List all systems, applications, services, or infrastructure components
- **Affected Geographies**: Regions, data centers, offices impacted
- **Affected Business Units**: Departments, teams, or functions impacted
- **Affected Customer Segments**: Customer types or tiers impacted
- **Data Implications**: Any data loss, exposure, corruption, or compliance concerns

---

### Root Cause Analysis
Deep investigation into why this occurred:

**Primary Root Cause**:

Detailed explanation of the fundamental cause:
- **Category**: [Technical / Process / Human Error / External / Design Flaw / Resource Gap]
- **Description**: Comprehensive explanation of what fundamentally caused this situation
- **Evidence**: Data, logs, analysis, or findings that support this determination
- **Confidence Level**: [Confirmed / Highly Likely / Probable / Under Investigation]

**Contributing Factors**:

Secondary factors that enabled or exacerbated the situation:

| Factor | Category | Contribution | Evidence |
|--------|----------|--------------|----------|
| [Factor 1] | [Category] | [How it contributed] | [Supporting data] |
| [Factor 2] | [Category] | [How it contributed] | [Supporting data] |
| [Factor 3] | [Category] | [How it contributed] | [Supporting data] |

**Causal Chain Analysis**:

Step-by-step breakdown of how the root cause led to the observed impact:

```
[Initial Condition/Trigger]
        ↓
[First Failure Point] - Why: [Explanation]
        ↓
[Cascading Effect 1] - Why: [Explanation]
        ↓
[Cascading Effect 2] - Why: [Explanation]
        ↓
[Observable Impact/Symptom]
```

**Five Whys Analysis**:
1. Why did [symptom] occur? → Because [answer 1]
2. Why did [answer 1] happen? → Because [answer 2]
3. Why did [answer 2] happen? → Because [answer 3]
4. Why did [answer 3] happen? → Because [answer 4]
5. Why did [answer 4] happen? → Because [root cause]

**What Failed**:
- **Technical Controls**: Systems, monitoring, automation that should have prevented/detected this
- **Process Controls**: Procedures, reviews, approvals that should have caught this
- **Human Factors**: Training, staffing, workload, or communication gaps
- **Organizational Factors**: Structure, incentives, or culture elements that contributed

**What Worked**:
- Controls or processes that limited the damage
- Detection mechanisms that worked correctly
- Response actions that were effective
- Team behaviors that helped contain the situation

**Knowledge Gaps**:
- Questions still unanswered
- Additional investigation needed
- External expertise required

---

### Impact Assessment
Comprehensive measurement of consequences:

**Business Impact**:

| Impact Category | Measurement | Details |
|-----------------|-------------|---------|
| **Revenue** | [$X direct loss] | Lost sales, refunds, credits issued |
| **Cost** | [$X remediation] | Labor, tools, external services, penalties |
| **Productivity** | [X person-hours] | Internal time spent on response/recovery |
| **Opportunity Cost** | [$X or qualitative] | Delayed projects, missed opportunities |

**Operational Impact**:

| Metric | Value | Normal Baseline | Variance |
|--------|-------|-----------------|----------|
| Service Availability | [%] | [%] | [-X%] |
| Transaction Volume | [#] | [#] | [-X%] |
| Processing Time | [X ms/s] | [X ms/s] | [+X%] |
| Error Rate | [%] | [%] | [+X%] |

**Customer Impact**:

- **Affected Customers**: [Number] total
  - By segment: [Enterprise: X, SMB: X, Consumer: X]
  - By severity of impact: [Severe: X, Moderate: X, Minor: X]
- **Customer Experience Effects**:
  - Service unavailability duration per customer
  - Degraded service experience description
  - Data or functionality loss
- **Customer Communications**:
  - Notifications sent: [Date, channel, audience]
  - Support tickets generated: [#]
  - Escalations received: [#]
- **Customer Sentiment**:
  - Complaints received
  - Social media mentions
  - NPS or satisfaction impact (if measurable)

**Reputational Impact**:

- Media coverage (if any)
- Social media activity and sentiment
- Partner/vendor communications
- Industry analyst awareness
- Regulatory/legal attention

**Compliance & Legal Impact**:

- Regulatory notification requirements (e.g., GDPR, HIPAA, SOX)
- Notifications filed: [Date, authority]
- Potential penalties or sanctions
- Legal exposure assessment
- Audit implications

**Long-term Impact Projection**:

| Timeframe | Expected Impact | Mitigation Status |
|-----------|-----------------|-------------------|
| Immediate (0-30 days) | [Description] | [Status] |
| Short-term (1-3 months) | [Description] | [Status] |
| Medium-term (3-12 months) | [Description] | [Status] |
| Long-term (12+ months) | [Description] | [Status] |

---

### Current Situation
Real-time status and ongoing conditions:

**Status as of [Date/Time]**:

**Overall Status**: [Resolved / Stable / Improving / Degraded / Critical]

**Current State**:
- Systems operational: [Yes/Partial/No] - Details
- Normal service levels: [Yes/Partial/No] - Details
- Backlog status: [Description of any work queue buildup]
- Monitoring status: [Enhanced/Normal] - Details on what's being watched

**Active Mitigations in Place**:
| Mitigation | Purpose | Effectiveness | Duration |
|------------|---------|---------------|----------|
| [Action 1] | [What it prevents/enables] | [High/Medium/Low] | [Permanent/Temporary until X] |
| [Action 2] | [What it prevents/enables] | [High/Medium/Low] | [Permanent/Temporary until X] |

**Workarounds Active**:
- [Workaround 1]: Who uses it, limitations, when it can be removed
- [Workaround 2]: Who uses it, limitations, when it can be removed

**Known Limitations**:
- Functionality still impaired or unavailable
- Performance constraints
- Capacity restrictions
- Geographic or segment restrictions

**Ongoing Activities**:
| Activity | Team | Status | ETA |
|----------|------|--------|-----|
| [Activity 1] | [Team] | [In Progress/Blocked/Complete] | [Date] |
| [Activity 2] | [Team] | [In Progress/Blocked/Complete] | [Date] |

**Resource Allocation**:
- Teams currently engaged: [List]
- FTEs dedicated: [#]
- External resources: [Vendors, consultants]
- Estimated effort remaining: [Person-hours/days]

**Risk of Recurrence**:
- **Probability**: [High/Medium/Low] - Rationale
- **Conditions that could trigger recurrence**: [List]
- **Early warning indicators being monitored**: [List]

**Escalation Status**:
- Current escalation level: [Normal/Elevated/Executive]
- Stakeholders briefed: [List with dates]
- Next briefing scheduled: [Date/Time]

---

### Final Action & Recommendations
Comprehensive action plan and strategic guidance:

**Immediate Actions (0-48 hours)**:

| # | Action | Owner | Due | Status | Success Criteria |
|---|--------|-------|-----|--------|------------------|
| 1 | [Action] | [Name] | [Date] | [Not Started/In Progress/Complete] | [How we know it's done] |
| 2 | [Action] | [Name] | [Date] | [Status] | [Criteria] |
| 3 | [Action] | [Name] | [Date] | [Status] | [Criteria] |

**Short-term Actions (1-4 weeks)**:

| # | Action | Owner | Due | Priority | Dependencies | Investment |
|---|--------|-------|-----|----------|--------------|------------|
| 1 | [Action] | [Name] | [Date] | [High/Med] | [List] | [$X or effort] |
| 2 | [Action] | [Name] | [Date] | [Priority] | [List] | [Investment] |

**Long-term Actions (1-6 months)**:

| # | Initiative | Owner | Timeline | Investment | Expected Outcome |
|---|------------|-------|----------|------------|------------------|
| 1 | [Initiative] | [Name] | [Q1/Q2/etc] | [$X] | [Outcome] |
| 2 | [Initiative] | [Name] | [Timeline] | [Investment] | [Outcome] |

**Preventive Measures**:

Actions to prevent recurrence:
1. **[Measure 1]**: Description, owner, timeline, investment required
2. **[Measure 2]**: Description, owner, timeline, investment required
3. **[Measure 3]**: Description, owner, timeline, investment required

**Detection Improvements**:

Actions to detect similar issues faster:
1. **[Improvement 1]**: What it will detect, implementation plan
2. **[Improvement 2]**: What it will detect, implementation plan

**Response Improvements**:

Actions to improve future incident response:
1. **[Improvement 1]**: Current gap, proposed change, benefit
2. **[Improvement 2]**: Current gap, proposed change, benefit

**Strategic Recommendations**:

Higher-level recommendations for leadership consideration:

1. **[Recommendation 1]**:
   - Rationale: Why this is important
   - Options: Alternative approaches considered
   - Recommendation: Specific suggested action
   - Investment: Resources required
   - Timeline: When this could be implemented
   - Risk of inaction: What happens if we don't do this

2. **[Recommendation 2]**:
   - [Same structure]

**Decisions Required**:

| Decision | Options | Recommendation | Decision Maker | Deadline |
|----------|---------|----------------|----------------|----------|
| [Decision 1] | [A, B, C] | [Recommended option with rationale] | [Role/Name] | [Date] |
| [Decision 2] | [Options] | [Recommendation] | [Decision Maker] | [Date] |

**Success Metrics**:

How we will measure the effectiveness of our response:
| Metric | Current Value | Target Value | Measurement Frequency |
|--------|---------------|--------------|----------------------|
| [Metric 1] | [Current] | [Target] | [Daily/Weekly/Monthly] |
| [Metric 2] | [Current] | [Target] | [Frequency] |

**Communication Plan**:

| Audience | Message | Channel | Timing | Owner |
|----------|---------|---------|--------|-------|
| Executive Leadership | [Key points] | [Email/Meeting] | [Date] | [Name] |
| Affected Customers | [Key points] | [Email/Portal] | [Date] | [Name] |
| Internal Teams | [Key points] | [Slack/Email] | [Date] | [Name] |
| External Partners | [Key points] | [Channel] | [Date] | [Name] |

**Follow-up Schedule**:

| Review Type | Date | Attendees | Purpose |
|-------------|------|-----------|---------|
| Progress Review | [Date] | [List] | Check action completion |
| Lessons Learned | [Date] | [List] | Document learnings |
| Effectiveness Review | [Date] | [List] | Validate improvements |
| Close-out Review | [Date] | [List] | Confirm resolution |

---

## Appendices

### Appendix A: Technical Details
[Reserved for detailed technical information, logs, configurations]

### Appendix B: Supporting Documentation
[References to related documents, tickets, runbooks]

### Appendix C: Glossary
[Definitions of technical terms or acronyms used]
