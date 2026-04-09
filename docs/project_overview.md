# Bear In Mind — Project Context

## Documentation alignment

Canonical **user stories and acceptance criteria** for this repository: [`docs/user_stories.md`](user_stories.md). Design and delivery docs: [`docs/design/`](design/).

---

## What is Bear In Mind?

**Bear In Mind** is an **LLM-powered conversational AI system** that matches sales opportunities to internal engineering divisions at Rikkeisoft in real-time.

---

## The Problem

Rikkeisoft has multiple engineering divisions (DN1, AD, etc.) each with different expertise, technologies, and experience.

When **Sales gets a new client opportunity**, they face a critical problem:

- **Sales knows**: "Client needs D365 implementation in Japan, 3 months, $500k budget"
- **Problem**: Which division can deliver this? Who are the experts? Are they available?
- **Current solution**: Manual emails, asking around, relying on personal relationships
- **Result**: Missed opportunities, slow responses, knowledge scattered across people

---

## The Solution

Instead of filling out forms or using keyword filters, **conversational AI**:

```
Sales: "We have a D365 implementation project for a Japan-based financial services 
        company. 3-month timeline, ~$500k budget. They want Azure migration."

AI Assistant:
- Understands: What are they really asking for?
  (Tech: D365/Azure, Domain: Financial Services, Location: Japan, Timeline: 3 months)

- Reasons: Who has done something like this before?
  (Searches past case studies, employee skills, division capabilities)

- Returns: Best match with explanation
  "Perfect match: DN1 Division (95% fit)
   • Expert: Thắng LB - D365/Azure specialist
   • Case study: Fujitsu D365 migration (2022)
   • Team: 3 seniors available
   • Timezone: Japan-compatible
   Why: Same tech stack, domain experience, proven delivery"

- Auto-captures opportunity to CRM
- Notifies DN1 leader in real-time
- Learns: Did this match succeed? Use it to improve future matching
```

---

## Why LLM?

### **Problem with Traditional Keyword Matching**
```
User: "Need D365 expert for Japan project"
Keyword search: ["D365", "Japan"]
❌ Result: Employees with exact words in CV (misses variations)
❌ Result: Ignores domain expertise, timezone, team availability
❌ Result: Can't reason about fit (is this person's experience relevant?)
```

### **With Claude LLM**
```
User: "Need D365 expert for Japan project"
Claude understands:
- "D365" = Microsoft Dynamics 365 (financial integration platform)
- "Japan" = timezone constraint, potentially financial services domain
- Implied: likely 3+ months timeline, senior expertise needed

Reasoning:
- Who has done D365 before?
- Who has financial services experience?
- Who works in Japan timezone?
- Who has been successful with similar projects?
```

**Why this matters:**
- Understands context (not just keywords)
- Finds semantic matches (similar experiences, not exact matches)
- Provides reasoning (why this person/division fits)
- Improves over time (learns from successful matches)

---

## How It Works (Conceptually)

### **The Flow**

**1. Sales person chats**
- Describes opportunity in natural language
- No special format needed, just describe the client need

**2. AI understands**
- Claude reads the description
- Extracts: tech stack, domain, timeline, budget, location, seniority needed
- Understands context: is this a migration? Integration? New build?

**3. AI searches knowledge base**
- "Who has done D365 projects?"
- "Who has financial services experience?"
- "Who can work in Japan timezone?"
- "Who has seniors available?"

**4. AI ranks matches**
- Scores divisions based on tech fit, domain experience, availability
- Explains why each match is relevant

**5. AI responds**
- Shows best matches with reasoning
- Includes expert names, past case studies, team size

**6. Sales acts**
- Saves opportunity to CRM
- Shares details with matched division

**7. Division leader responds**
- Gets notification about matching opportunity
- Can accept or decline to participate

**8. System learns**
- Records: Did this match lead to a successful deal?
- Improves future matching based on outcomes

---

## The 6 user stories (aligned with `docs/user_stories.md`)

Stories are labeled **US1–US6** to match the estimate sheet. Full acceptance criteria: [`docs/user_stories.md`](user_stories.md).

| US | Theme | Owner (primary) |
|----|--------|------------------|
| **US1** | Chat + matching | Sales |
| **US2** | Notifications when an opportunity fits a unit | Delivery Leader |
| **US3** | Update unit capabilities (experts, tech, HRM, Salekit) | D.Lead |
| **US4** | Memory + **periodic reminders** to refresh unit data | D.Lead / S.Lead (via AI) |
| **US5** | Capture opportunity from chat + **confirm** + HubSpot sync | Sales |
| **US6** | Open opportunity list (**HubSpot + unofficial** chat) | Delivery / Solution Leader |

**US4 clarification:** The execution backlog emphasizes **structured unit memory**, **incremental updates**, and **scheduled reminders** (e.g. Celery). **Outcome-based learning** (“did this match win?”) remains a **future enhancement**, not the same milestone as the reminder workflow.

---

## Key Concepts

### **Opportunity**
A client project opportunity. Example:
- Client: Fujitsu
- Description: D365 implementation with Azure migration
- Timeline: 3 months
- Budget: $500k
- Location: Japan
- Domain: Financial Services

### **Division**
A team/group at Rikkeisoft. Example:
- Name: DN1 (Digital Natives 1)
- What they do: D365, Azure, C#, Cloud migrations
- Who works there: Thắng (D365 expert), Hiếu (Android/Kotlin)
- Experience: Fujitsu D365 project (2022), etc.

### **Match**
When an opportunity fits a division. Example:
- Opportunity: "D365 in Japan"
- Division: DN1
- Match score: 95%
- Why: Same tech, domain experience, timezone, availability

### **Case Study / Past Project**
A project the company has completed. Example:
- Client: Fujitsu
- What: D365 migration to Azure
- Tech stack: D365, Azure, C#
- Domain: Financial Services
- Duration: 3 months
- Outcome: Successful
- Value: When matching new opportunities, "Fujitsu D365" project shows DN1 has experience

---

## What Makes This Different

### **Traditional CRM**
```
Sales fills form:
- Client name: ___
- Tech: ___
- Domain: ___
- Division: (dropdown list)

Problem: Sales doesn't know the right division
```

### **Filter-Based Tool**
```
Sales uses filters:
- Filter by: tech=D365 → returns all D365 experts
- Filter by: domain=finance → returns all finance people

Problem: Can't reason about fit, misses context
```

### **Bear In Mind (LLM-Powered)**
```
Sales: "Client needs D365 in Japan, similar to Fujitsu project"

AI understands:
- D365 = specific platform
- Japan = timezone + market context
- Fujitsu = reference point (what we've done before)

AI searches:
- Who worked on Fujitsu?
- Who knows Japan market?
- Who has current availability?

AI returns:
- Best match with explanation
- Reasoning why this person/division fits
```

---

## Constraints

### **Timeline**
- 10 days to build
- 2 developers
- ~4 hours per day coding
- Total: ~51 hours

### **Scope (Demo-Only)**
- Not production-grade
- Can use mock/test data
- Focus on core functionality
- Real-time is priority (visible to users)

### **Data Sources**
- Employee data: HRM/RVKN system
- Case studies: Salekit system
- Opportunities: Chat input + HubSpot
- CRM sync: HubSpot API

### **Must-Have**
- Claude API for LLM (core to solution)
- Timely leader notifications (polling API is acceptable initially; push/WebSocket optional)
- Knowledge base search (semantic matching)

### **Execution alignment** (see [`docs/user_stories.md`](user_stories.md))
- **US2** fit levels: **High / Medium**; next actions UX may still be in design.
- **US4** = **scheduled reminders** + **incremental unit memory**; **outcome-based learning** is a later enhancement, not the same milestone.

### **Nice-to-Have**
- Mobile responsiveness
- Comprehensive error handling
- Production deployment

---

## Success = What We're Optimizing For

### **User Experience**
- Sales gets answer fast (<5 seconds)
- Matching results are accurate (>80% relevant)
- Division leader sees notification immediately
- Easy to understand (no training needed)

### **Technical**
- Chat works in real-time
- Claude API calls succeed reliably
- Matching finds relevant divisions
- Data doesn't get lost

### **Demo**
- Shows clear problem → solution
- All 6 stories are working/demoed
- Judges understand business value
- Live demo doesn't crash

---

## Context: Rikkeisoft

**Challenge**: Growing company with multiple engineering divisions  
**Problem**: Each division is siloed, knowledge is scattered, opportunities get lost  
**Opportunity**: AI can connect divisions, match opportunities intelligently, improve utilization  

**Divisions** (Engineering teams):
- DN1: Digital Natives 1 (D365, Azure, cloud)
- AD: App Development (mobile, Android, Kotlin)
- Others: Infrastructure, AI, etc.

**Related Systems**:
- HRM/RVKN: Employee database
- Salekit: Case study repository
- HubSpot: CRM system

---

## Bottom Line

**Bear In Mind solves a real problem at Rikkeisoft**: Knowledge is scattered across people and systems. When sales gets an opportunity, they don't know which division to propose.

**The solution**: An AI that understands context, searches across knowledge base, and matches opportunities to the right teams intelligently.

**Why it works**: Instead of keywords or dropdowns, Claude understands the opportunity in context and finds the best fit based on skills, experience, availability, and proven track record.

---

**Version**: 1.1  
**Date**: 2026-04-09  
**Purpose**: Project understanding for Claude Code and team