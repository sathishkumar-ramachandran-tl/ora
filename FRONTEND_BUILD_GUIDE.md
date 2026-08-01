# Enterprise Frontend Build Guide (Sindhai Cortex)

This guide provides a complete architectural blueprint to rebuild the Sindhai Cortex frontend from scratch or refactor the current one. It focuses on the **Enterprise** requirement: separating Personal and Company contexts.

## 1. Tech Stack & Setup

**Core:** React 18+, TypeScript, Vite
**Styling:** Tailwind CSS, Lucide React (Icons)
**State/Routing:** React Router DOM (v6), Context API (or Zustand)
**Network:** Axios (with Interceptors)

### Initialization
```bash
npm create vite@latest frontend -- --template react-ts
cd frontend
npm install react-router-dom axios date-fns clsx tailwind-merge lucide-react
npm install -D tailwindcss postcss autoprefixer
npx tailwindcss init -p
```

## 2. Directory Structure (Feature-Based)

Structure your application to separate concerns strictly.

```
src/
├── api/                # API definitions
│   ├── client.ts       # Axios instance & Interceptors
│   ├── auth.ts         # Login/OTP/Profile endpoints
│   ├── workspace.ts    # Workspace CRUD
│   └── org.ts          # Organization/Admin endpoints
├── components/         # Shared UI Components
│   ├── common/         # Buttons, Modals, Inputs
│   └── layout/         # Sidebars, Headers
├── contexts/           # Global State
│   └── AuthContext.tsx # User session & Workspace state
├── layouts/            # The Core Structural Layouts
│   ├── AuthLayout.tsx  # Login/Signup wrapper
│   ├── PersonalLayout.tsx # For Students/Freelancers
│   └── CompanyLayout.tsx  # For Admin/Enterprise Users
├── pages/              # View Logic
│   ├── auth/           # LoginScreen, Onboarding
│   ├── personal/       # StudyBoard, PersonalProjects
│   ├── enterprise/     # AdminConsole, OrgDashboard
│   └── shared/         # Views shared by both (e.g., Settings)
├── types/              # TypeScript Definitions
│   └── index.ts        # User, Workspace, Organization interfaces
├── config.ts           # Env handling
├── App.tsx             # Main Router logic
└── main.tsx            # Entry point
```

## 3. Core Architecture Implementation

### A. Configuration (`src/config.ts`)
Handles the Dev vs Prod API connection issues.
```typescript
const isDev = import.meta.env.DEV;
// In Dev: Use empty string to leverage Vite Proxy
// In Prod: Use the explicit URL or '/' if served from same domain
export const API_BASE_URL = isDev ? '' : (import.meta.env.VITE_API_BASE_URL || '');
```

### B. API Client (`src/api/client.ts`)
Centralized request handling.
```typescript
import axios from 'axios';
import { API_BASE_URL } from '../config';

export const apiClient = axios.create({
  baseURL: `${API_BASE_URL}/api/v1`, // Standardize on v1
});

apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('sindhai_auth_token');
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});
```

### C. The Layout Strategy (Crucial)

This is where the application splits into two distinct products based on the user's context.

**1. Personal Layout (`src/layouts/PersonalLayout.tsx`)**
*   **Sidebar Menu**: "My Learning", "My Projects", "Vault".
*   **Header**: Personal Profile, Focus Timer.
*   **Target Audience**: Students, Researchers.

**2. Company Layout (`src/layouts/CompanyLayout.tsx`)**
*   **Sidebar Menu**: "Admin Console", "Team Projects", "LMS (Training)", "Analytics".
*   **Header**: Organization Switcher, Role Badge.
*   **Target Audience**: Admins, Employees.

### D. The Router (`src/App.tsx`)

```tsx
function App() {
  const { user, workspace } = useAuth(); // Custom hook

  if (!user) return <AuthRoutes />;

  // Context Switcher Logic
  if (workspace?.context === 'company') {
    return (
      <CompanyLayout>
        <Routes>
           <Route path="/admin" element={<AdminConsole />} />
           <Route path="/projects" element={<TeamProjects />} />
           <Route path="/" element={<Navigate to="/projects" />} />
        </Routes>
      </CompanyLayout>
    );
  }

  // Default to Personal
  return (
    <PersonalLayout>
      <Routes>
         <Route path="/study" element={<StudyBoard />} />
         <Route path="/projects" element={<PersonalProjects />} />
         <Route path="/" element={<Navigate to="/study" />} />
      </Routes>
    </PersonalLayout>
  );
}
```

## 4. Key Feature Implementation Details

### 1. Admin Console (`src/pages/enterprise/AdminConsole.tsx`)
*   **Purpose**: Manage Users & RBAC.
*   **Data Source**: `GET /api/v2/orgs/{orgId}/members`.
*   **Components**: Data Table (List of users), "Invite Member" Modal.

### 2. Workspace Data Loading
*   Do not load everything at once.
*   Use `useEffect` inside the specific pages (e.g., `ProjectsPage`) to fetch data relevant to that page.
*   **Old approach**: Loaded entire DB state in App.tsx. **New approach**: Fetch-on-render.

## 5. Development Workflow (Fixing the API Issue)

1.  **Vite Config (`vite.config.ts`)**:
    ```typescript
    export default defineConfig({
      server: {
        proxy: {
          '/api': {
             target: 'http://localhost:5000',
             changeOrigin: true,
             secure: false 
          }
        }
      }
    })
    ```
2.  **API Calls**:
    *   Frontend request: `apiClient.get('/auth/me')`
    *   Resolves to: `http://localhost:5173/api/v1/auth/me`
    *   Proxied to: `http://localhost:5000/api/v1/auth/me`

## 6. Migration Checklist (If rebuilding)

1.  [ ] Setup new `frontend` folder with Vite.
2.  [ ] Copy `types.ts` to `src/types/index.ts`.
3.  [ ] Implement `api/client.ts` first.
4.  [ ] Create `pages/auth/LoginScreen.tsx` and test login.
5.  [ ] Create `layouts/PersonalLayout.tsx` (shell only).
6.  [ ] Move `AgileBoard`, `Dashboard` logic into specific pages.
7.  [ ] Implement `AdminConsole` using the new Org endpoints.
