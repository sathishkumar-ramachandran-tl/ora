# Sindhai - Product Specifications

**Tagline:** The Operating System for High-Velocity Ambition.
**Vision:** To replace the fragmented productivity stack (Jira + Notion + Miro) with a single, neural interface that *thinks* with you.

## 1. Target Audience (Personas)
*   **The Founder:** Needs to balance high-level fundraising strategy with low-level product iterations.
*   **The PhD Researcher:** Manages vast amounts of unstructured data, grants, and publication deadlines.
*   **The Product Executive:** Juggles stakeholder management, roadmapping, and team execution.
*   **The Elite Student:** Optimizes learning intervals for maximum retention and GPA.

## 2. Core Modules & Use Cases

### A. The Incubator (Idea Board)
*   **Use Case:** "I have a random thought about a feature while walking."
*   **Feature:** Quick capture sticky notes. One-click "Promote" transforms a sticky note into a full-blown Strategic Initiative (Company/Domain) with its own dashboard.

### B. The Spatial Canvas (Milanote-style)
*   **Use Case:** "I need to visualize the relationship between our marketing channels and sales funnel."
*   **Feature:** Infinite whiteboard attached to every Project. Drag-and-drop notes, images, links, and task groups.

### C. The Neural Graph
*   **Use Case:** "What is the completion status of my entire life's work?"
*   **Feature:** D3.js Force Directed Graph. Node size represents progress. Glowing nodes indicate completion.

### D. The AI Strategist (Agentic Workflow)
*   **Use Case:** "I want to launch a mobile app but don't know where to start."
*   **Feature:** 
    1. User inputs: "Launch MVP for Pet Sitting App."
    2. AI decomposes this into "Market Research", "Prototype", "Beta Test".
    3. AI generates 20 specific Jira-style tickets with hour estimates.

### E. Secure Vault
*   **Use Case:** "I need to store my Pitch Deck next to my Tasks."
*   **Feature:** Encrypted document storage linked to the Knowledge Graph.

## 3. API Design (Draft for Microservices)

### Core Resources

**GET /api/v1/workspaces/{id}/summary**
*   Returns the Executive Dashboard data (KPIs, Daily Essentials).

**POST /api/v1/incubator/promote**
*   **Body:** `{ noteId: string, targetType: 'company' | 'project' }`
*   **Action:** Atomic transaction. Creates Company, moves content to Mission, Deletes Note.

**GET /api/v1/graph/nodes**
*   **Response:** JSON adjacency list for D3 rendering.
*   **Optimization:** Cached via Redis, invalidated on Task Update.

**POST /api/v1/agents/generate-plan**
*   **Body:** `{ goal: string, persona: string }`
*   **Response:** `{ tasks: Task[], riskAnalysis: string[] }`
*   **Mechanism:** Async Job ID returned immediately. Client polls via WebSocket.

## 4. Database Schema (Postgres)

*   `users`: Identity.
*   `workspaces`: Multi-tenant container.
*   `companies`: Strategic domains (Initiatives).
*   `projects`: Deliverables.
*   `tasks`: Atomic units.
*   `notes`: Unstructured thoughts (Type: 'general' | 'idea').
*   `activity_logs`: Audit trail for analytics.

## 5. Security Requirements
1.  **Encryption at Rest:** All DB volumes encrypted.
2.  **Encryption in Transit:** TLS 1.3 for all API connections.
3.  **Role-Based Access Control (RBAC):** Middleware checks `permissions` column in `custom_roles` table before executing write operations.