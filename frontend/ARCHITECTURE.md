# Sindhai (fka AxonDesk) - Enterprise Architecture

## 1. Overview
Sindhai is a vertical SaaS Operating System designed for high-performance cognition and execution. It serves as a "Neural Executive" that decomposes abstract strategic goals into executable tasks using Agentic AI patterns.

**Core Philosophy:**
The system models the brain of a Chief of Staff:
1.  **Capture:** Incubator (Idea Board).
2.  **Structure:** Initiatives (Companies) & Projects.
3.  **Execute:** Tasks & Deep Work Timers.
4.  **Analyze:** Neural Graph & Dashboard.

## 2. Core Hierarchy (Data Model)
The application follows a strict constraint-management hierarchy:
1.  **Workspace (The Entity):** The root container. Secured via strict `workspaceId` scoping.
2.  **Initiative (The Domain):** A high-level domain of concern (e.g., "BioTech Startup", "PhD Research").
3.  **Project (The Deliverable):** A finite effort with a specific outcome (e.g., "Series A Pitch Deck").
4.  **Task (The Atomic Unit):** An action that takes < 4 hours.
5.  **Idea (The Seed):** Unstructured thought data stored in the `notes` table with `type='idea'`.

## 3. Current Tech Stack (Client-Side SaaS)
*   **Frontend:** React 19, TypeScript, TailwindCSS.
*   **Persistence:** PostgreSQL (NeonDB Serverless) connected directly via `@neondatabase/serverless` (WebSocket-based).
*   **AI:** Google Gemini 2.5/3.0 Models via `@google/genai`.
*   **State:** Local React State + Optimistic UI updates.

## 4. Security Audit & Critical Warnings (Public Deployment)
**⚠️ CRITICAL WARNING FOR PUBLIC DEPLOYMENT ⚠️**

The current implementation connects to the Database and AI Services *directly from the Browser Client*. This exposes API Keys and Database Credentials in the browser network tab.

**To deploy securely, you MUST implement a Middleware Layer:**

### 4.1. Required Architecture Changes
1.  **Backend Proxy:** Move all calls in `services/db.ts` and `services/geminiService.ts` to a backend API (Next.js API Routes, Express, or Cloudflare Workers).
2.  **Authentication:** Replace the simulated `LoginScreen` with a provider like Clerk, Auth0, or Supabase Auth.
3.  **Secrets Management:** `process.env.API_KEY` and DB Connection Strings must only exist in the Server Environment variables, never leaked to the client bundle.

### 4.2. Current Security Measures (Implemented)
*   **SQL Injection:** All DB queries use **Parameterized Queries** (`$1`, `$2`) to prevent SQL injection attacks.
*   **Access Control (Logic Level):** Every DB function in `services/db.ts` strictly enforces `WHERE workspace_id = $1`.
*   **XSS Protection:** React's default escaping is utilized. No `dangerouslySetInnerHTML` is used for user-generated content.

## 5. Microservices Roadmap (Target Architecture)

To scale Sindhai, the backend will be split into the following microservices:

### Service A: Identity & Access (IAM)
*   **Responsibility:** Auth, Workspace Management, Role-Based Access Control (RBAC).
*   **Tech:** Go or Node.js + Redis (Session Store).

### Service B: The Cortex (AI Agent Orchestrator)
*   **Responsibility:** Chaining Gemini Agents (Strategist -> Tactician -> Risk Officer).
*   **Tech:** Python (FastAPI) or LangChain.
*   **Features:**
    *   Async Job Queue (BullMQ) for long-running strategy generation.
    *   Vector Database (Pinecone) for RAG on Document Vault.

### Service C: The Ledger (Core Data)
*   **Responsibility:** CRUD operations for Companies, Projects, Tasks, Ideas.
*   **Tech:** Node.js (Express/NestJS) + PostgreSQL.
*   **API Pattern:** GraphQL (Federated) or REST.

### Service D: The Synapse (Real-time)
*   **Responsibility:** Live Collaboration (Spatial Canvas), Voice Assistant streaming.
*   **Tech:** WebSocket Server (Socket.io) or Elixir Phoenix.

## 6. Agentic Workflow (A2A)
We utilize a sequential agent chain:
1.  **Strategist:** Decomposes abstract goals into Milestones (Gemini Pro).
2.  **Tactician:** Converts milestones into Atomic Tasks (Gemini Flash).
3.  **Risk Officer:** Audits plans for optimism bias.

## 7. Deployment
*   **Frontend:** Vercel / Netlify / AWS S3+CloudFront.
*   **Backend:** AWS Lambda / Google Cloud Run / DigitalOcean App Platform.
*   **Database:** Neon (Serverless Postgres).