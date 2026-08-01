# Application Architecture 2.0 - Enterprise Grade

## 1. Overview
This document outlines the architectural upgrade to Sindhai Cortex to support "Enterprise Grade" requirements, specifically separating Personal and Company workflows into distinct, secure, and scalable domains.

## 2. Core Concepts
The application is divided into two primary contexts:

### A. Personal Context
Designed for individual users (Students, Freelancers, Researchers).
- **Study Workspace**: Focused on learning, notes, and research.
- **Project Workspace**: Focused on freelance work, personal building, and execution.

### B. Company Context (Organization)
Designed for teams and institutions.
- **Admin/Control Panel**: For managing users, billing, and global settings.
- **Study Workspace**: For training, onboarding, and LMS features.
- **Project Workspace**: For team collaboration, agile management, and delivery.

## 3. Database Schema (PostgreSQL/SQLAlchemy)

### Entities

#### `Organization` (New)
*Represents a Tenant (Company, University).*
- `id`: UUID
- `name`: String
- `domain`: String (for auto-joining)
- `owner_id`: FK(User)
- `settings`: JSONB (White-labeling, etc.)

#### `Workspace` (Enhanced)
*The container for data.*
- `id`: UUID
- `name`: String
- `mode`: Enum(`personal`, `company`)
- `type`: Enum(`study`, `project`) -- *Maps to User's request*
- `organization_id`: FK(Organization, nullable) -- *If mode=company*
- `owner_id`: FK(User)
- `settings`: JSONB

#### `Project` & `Course` (New/Renamed)
*Workspaces contain Projects (for execution) or Courses (for study).*

## 4. Backend Architecture (Flask + Blueprints)

Structure:
```
backend/
  app/
    api/
      auth.py       # Authentication & Authorization (RBAC)
      org.py        # Organization Management
      workspace.py  # Workspace CRUD
      study.py      # Learning specific logic
      projects.py   # Project management logic
    services/       # Business Logic Layer (Agentic AI hooks here)
    models.py       # Database Entities
```

## 5. Frontend Architecture (React + Vite)

Structure:
```
src/
  layouts/
    PersonalLayout  # Sidebar with "My Study", "My Projects"
    CompanyLayout   # Sidebar with "Org Admin", "Team Projects", "Training"
  views/
    admin/          # Org Control Panel
    study/          # LMS / Study View
    project/        # PM / Agile View
```

## 6. Security & Scalability
- **Authorization**: RBAC (Role Based Access Control) implemented via middleware.
- **Testing**: Pytest for backend, Vitest for frontend.
- **Documentation**: Swagger/OpenAPI for API endpoints.

## 7. Future Proofing
- **Multi-lingual**: All UI strings to be moved to `i18n` JSON files.
- **Agentic AI**: Services layer designed to accept "AI Agents" as first-class users/actors.
