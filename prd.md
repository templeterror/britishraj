# WealthBridge — Product Requirements Document

**Product:** WealthBridge (working title)
**Version:** MVP 1.0
**Target customer:** Wealth management firms and family offices serving high-net-worth individuals and discreet multi-generational wealth families

## 1. Product Overview

WealthBridge is an AI-powered, multi-generational wealth management platform that helps financial advisors align parents' financial decisions with their children's long-term goals.

**Core problem.** Wealth management firms struggle to retain inherited assets because heirs often lack trust, understanding, and established relationships with their parents' financial advisors.

**Solution.** Build a shared financial knowledge graph connecting family assets, historical investment decisions, advisor meeting notes, and heirs' future goals. AI agents continuously identify misalignments and recommend interventions to wealth managers.

**Primary business objective.** Increase next-generation client retention and assets under management (AUM) retained after inheritance.

**Core value proposition.** Help wealth managers earn the next generation's trust before wealth changes hands.

## 2. User Roles and Dashboards

Access is organized by family and wealth management firm. Three roles each get an isolated, permission-based dashboard.

### A. Parent Dashboard

- **Portfolio overview.** Assets, investments, transactions, and performance.
- **Financial goals.** Define estate planning intentions and long-term family objectives.
- **Decision history.** View investment decisions and advisor meeting summaries.
- **Goal alignment.** Understand how current financial decisions support heirs' stated goals.

### B. Child / Heir Dashboard

- **Financial goals.** Write and update personal goals in their own words each quarter.
- **Inheritance readiness.** Understand financial plans and assets the parent has explicitly shared.
- **AI financial assistant.** Query authorized financial history and understand past decisions in plain English.
- **Educational insights.** Understand investment strategies and long-term wealth planning.

### C. Wealth Manager Dashboard

- **Family portfolio overview.** View managed family relationships and portfolios.
- **Knowledge graph.** Explore connections between financial decisions, assets, family members, and goals.
- **Alignment intelligence.** AI-generated alerts identifying conflicts between parent decisions and heir goals.
- **Meeting management.** Schedule meetings and track relationship-building activities.
- **Relationship health.** Track heir engagement, unresolved conflicts, and retention risk indicators.

## 3. Core Product Features

| Feature | Description | Priority |
| --- | --- | --- |
| Authentication and RBAC | Three user roles with isolated, permission-based dashboards | P0 |
| Financial data integration | Ingest synthetic Plaid financial accounts and transactions | P0 |
| Financial knowledge graph | Connect assets, decisions, goals, meeting notes, and family relationships | P0 |
| Meeting notes ingestion | Convert advisor notes into structured decisions and historical context | P0 |
| Quarterly goal check-ins | Collect heirs' evolving financial goals and update their profiles | P0 |
| Goal alignment agent | Compare parental investment decisions against heirs' goals | P0 |
| Discrepancy detection | Flag potential conflicts, with supporting evidence and explanations | P0 |
| Manager alerts | Notify advisors of discrepancies requiring attention | P0 |
| Meeting recommendations | Suggest advisor-family meetings when conflicts arise | P1 |
| Financial history chat | Read-only AI assistant answering questions using authorized records | P1 |

## 4. AI Agent Architecture

Agents provide recommendations only. They cannot execute trades, change allocations, or initiate financial transactions.

### Agent 1: Knowledge Graph Agent

**Purpose:** Build and maintain family financial context.

- Ingest financial data from Plaid Sandbox.
- Extract investment decisions and reasoning from meeting notes.
- Store relationships between assets, individuals, decisions, and financial goals in Neo4j.

### Agent 2: Goal Alignment Agent

**Purpose:** Identify discrepancies between generations.

- Compare the parent's investment strategy with the heir's stated goals.
- Incorporate relevant market information retrieved through Bright Data.
- Identify potentially conflicting financial decisions.
- Produce an alignment score, explanation, and evidence references.

### Agent 3: Relationship Management Agent

**Purpose:** Help advisors proactively build trust.

- Receive discrepancies from the Goal Alignment Agent.
- Generate actionable alerts for wealth managers.
- Recommend follow-up conversations and meeting agendas.
- Track whether identified discrepancies have been addressed.

## 5. Technical Architecture

| Layer | Technology | Responsibility |
| --- | --- | --- |
| Frontend | Next.js + Tailwind CSS | Authentication UI and three dashboards |
| Authentication | Clerk | User authentication, organizations, role-based permissions |
| Backend | FastAPI | REST APIs, agent orchestration, authorization |
| Deployment | Railway | Backend hosting |
| Relational database | Supabase (PostgreSQL) | User profiles, goals, meeting notes, alerts |
| Graph database | Neo4j | Financial knowledge graph and relationships |
| Financial data | Plaid Sandbox | Synthetic accounts, balances, transactions, investments |
| Market intelligence | Bright Data | Retrieve relevant public market information |
| AI | LLM API | Knowledge extraction, reasoning, discrepancy analysis |

### Access model

Three roles (Parent, Child, Wealth Manager), organized by family and wealth management firm. Clerk manages identities and roles. FastAPI enforces record-level access. Heirs can access only explicitly authorized financial information.

### Data limitation

Plaid Sandbox provides simulated financial data, but not every requested dataset (such as comprehensive credit histories) is available through standard Plaid products. Supplement missing datasets with clearly labeled synthetic records.

## 6. Primary User Workflow

### Step 1 — Financial onboarding

Wealth manager creates a family profile, connects synthetic Plaid data, and uploads historical meeting notes. The financial knowledge graph is generated.

### Step 2 — Goal collection

Parent defines financial intentions. Child completes a quarterly financial-goal questionnaire. Goals are added to Neo4j.

### Step 3 — Intelligence analysis

The Goal Alignment Agent evaluates decisions against both generations' goals, retrieves relevant market context, and flags discrepancies supported by evidence.

### Step 4 — Advisor intervention

The wealth manager receives an alert, reviews the discrepancy and supporting reasoning, schedules a family meeting, and records the outcome.

### Step 5 — Continuous relationship building

The child updates goals quarterly. The knowledge graph refreshes. Agents reevaluate alignment. The advisor tracks relationship progress.

## 7. MVP Demonstration Scenario

**Family:** Robert (father), James (son), Sarah (wealth manager).

Robert has a roughly $25M investment portfolio, most of it in real estate securities, with about $1.5M available in cash. James writes, in his own words, that he wants to start a technology company in the next three years and will need about $5M he can actually access.

The AI identifies a potential mismatch between the portfolio's liquidity and James's stated needs. Sarah receives an alert explaining the discrepancy and recommending a family planning discussion. Sarah schedules a meeting and documents the resulting decisions.

James can subsequently query the AI: "Why did my father invest so heavily in real estate?" The assistant explains Robert's documented reasoning, referencing historical meeting notes.

**Expected outcome.** James better understands his family's financial strategy, and Sarah establishes a trusted relationship with him before inheritance.

## 8. Success Metrics

| Metric | MVP target |
| --- | --- |
| User roles | 3 functioning dashboards |
| Synthetic financial data | 100 client profiles |
| Knowledge graph | Assets, decisions, goals, and relationships connected |
| Goal alignment | Identify and explain at least 3 meaningful discrepancies |
| Advisor alerts | Automatically generate actionable conflict alerts |
| AI assistant | Answer historical financial questions with source references |
| Goal check-ins | Functional quarterly questionnaire and goal updates |

**Long-term business KPI.** Percentage of inherited AUM retained by the wealth management firm, measured after wealth transfer.

## 9. MVP Scope

### Must build

Authentication, three dashboards, synthetic financial records, Neo4j knowledge graph, goal collection, discrepancy detection, and wealth manager alerts.

### Nice to have

Meeting scheduling integrations, AI financial history chat, advanced portfolio visualizations, and automated quarterly reminders.

### Out of scope

Executing trades, automatically modifying portfolios, providing autonomous investment advice, and processing actual inheritances.
