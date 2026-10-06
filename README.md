# BPUT PS08 — BRSR ESG Reporting Portal

## Project Overview

A web-based ESG reporting portal for centralized collection, validation, review, approval, consolidation, and reporting of Business Responsibility and Sustainability Reporting (BRSR) data.

The project is being developed for the BPUT Hackathon PS08 problem statement and is designed around a multi-level organizational structure for group, subsidiary, business-unit, and project-level ESG reporting.

## Problem Statement

Large organizations may need to collect ESG information from multiple subsidiaries, business units, and projects while maintaining a consistent reporting framework, evidence, review controls, and consolidated reporting.

The portal provides a centralized workflow for:

- Collecting BRSR data
- Managing reporting periods and organizational boundaries
- Uploading supporting evidence
- Validating mandatory information
- Reviewing and approving submissions
- Locking approved submissions
- Consolidating project-level ESG metrics
- Generating a consolidated PDF report
- Maintaining an audit history

## Solution

```text
React + Vite + TypeScript
          |
          v
       FastAPI
          |
          v
      SQLAlchemy
          |
          v
      PostgreSQL
```

Users interact with the React frontend. The FastAPI backend handles authentication, authorization, validation, workflow operations, reporting, and database access.

## Key Features

### Authentication

- JWT-based authentication
- Password hashing
- Protected API endpoints
- Session persistence in the frontend

### Role-Based Access Control

The backend defines roles including:

- SUPER_ADMIN
- GROUP_ESG_ADMIN
- SUBSIDIARY_ESG_MANAGER
- BUSINESS_UNIT_MANAGER
- PROJECT_DATA_ENTRY
- REVIEWER
- APPROVER
- AUDITOR

Project-level access is scoped according to organizational permissions.

### Organizational Hierarchy

```text
Organization
   └── Entity
        └── Business Unit
             └── Project
```

The development seed includes MEIL and a sample project hierarchy.

### BRSR Framework

The system includes the SEBI BRSR 2021 framework:

- Section A
- Section B
- Section C
- Nine principles in Section C
- Essential and Leadership indicators
- 140 questions in the full framework

The BRSR Core framework is preserved separately.

### ESG Data Entry

Supported response types include:

- Number
- Text
- Boolean
- Select
- Table

Mandatory questions are validated before submission.

### Evidence Upload

Supporting evidence can be uploaded against submissions with file-size validation, streaming handling, safe generated storage names, and protected access.

### Submission Workflow

```text
DRAFT
  |
  v
SUBMITTED
  |
  v
UNDER_REVIEW
  |
  +----------------------+
  |                      |
  v                      v
CORRECTION_REQUIRED    APPROVED
  |                      |
  v                      v
RESUBMITTED             LOCKED
```

### ESG Consolidation

Approved and locked submissions can contribute to consolidation.

The service:

- Respects project access scope
- Selects the canonical submission for each project
- Aggregates numeric metrics
- Provides reporting-period and framework information
- Calculates a renewable-electricity consumption-weighted KPI

Calculation:

```text
Σ(electricity consumption × renewable percentage / 100)
------------------------------------------------------- × 100
             Σ(electricity consumption)
```

### ESG Consolidation Dashboard

The dashboard provides:

- Reporting period selection
- BRSR framework selection
- Projects contributing
- Metrics aggregated
- Derived KPI display
- Consolidated metrics table
- Contributing projects table
- Loading, error, and empty states

### PDF Export

The portal generates a consolidated ESG PDF containing:

- Reporting period
- Framework information
- Derived KPI
- Consolidated metrics
- KPI warnings
- Contributing projects

### Audit Logging

The system records important activity such as:

- User login
- BRSR value updates
- Evidence uploads

A read-only audit activity page provides filtering and refresh.

## Technology Stack

### Frontend

- React
- TypeScript
- Vite
- Native Fetch API
- CSS

### Backend

- Python
- FastAPI
- SQLAlchemy
- Pydantic
- JWT authentication
- bcrypt password hashing
- ReportLab

### Database

- PostgreSQL

### Development

- Git / GitHub
- Pytest
- Docker configuration

## Project Structure

```text
BPUT HACKTHON/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   ├── core/
│   │   ├── db/
│   │   └── services/
│   ├── tests/
│   ├── alembic/
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── api/
│   │   └── pages/
│   ├── package.json
│   └── vite.config.ts
└── scratch/
    └── local development / verification files
```

The `scratch/` directory contains local development artifacts and is not intended for deployment.

## Local Setup

### Prerequisites

- Python
- Node.js and npm
- PostgreSQL

### Backend

From the project root:

```powershell
$env:PYTHONPATH="."
uvicorn backend.app.main:app --reload --port 8000
```

Backend:

```text
http://127.0.0.1:8000
```

### Frontend

In another terminal:

```powershell
cd frontend
npm install
npm.cmd run dev
```

Frontend:

```text
http://localhost:5173
```

### Frontend API Configuration

```text
VITE_API_BASE_URL=http://localhost:8000/api/v1
```

Configure this in `frontend/.env`.

## Database Configuration

The backend expects database configuration through environment variables.

Example local PostgreSQL URL:

```text
postgresql+psycopg2://postgres:postgres@localhost:5432/esg_brsr
```

Do not commit real production credentials or secrets.

## Development Seed

The project includes development seed data for:

- MEIL organization
- Sample entity
- Sample business unit
- Sample project
- FY2025-26 reporting period
- BRSR framework data
- Demo administrator

Development credentials must not be used in production.

## API Overview

Main API areas include:

```text
/api/v1/auth
/api/v1/organizations
/api/v1/reporting
/api/v1/brsr
/api/v1/submissions
/api/v1/evidence
/api/v1/audit-logs
```

FastAPI OpenAPI documentation is available when the backend is running.

## Testing

Backend tests:

```powershell
$env:PYTHONPATH="."
pytest backend/tests -v
```

The currently verified suite contains 13 passing tests covering audit logging and consolidation behavior.

Frontend production build:

```powershell
cd frontend
npm run build
```

## Current MVP Status

Implemented:

- Authentication
- RBAC
- Organizational hierarchy
- BRSR framework
- ESG data entry
- Evidence upload
- Mandatory validation
- Review and approval workflow
- Submission locking
- Project-level consolidation
- Renewable-energy derived KPI
- ESG consolidation dashboard
- Consolidated PDF export
- Audit logging
- Backend tests
- Frontend production build

## Future Enhancements

Potential future enhancements, not represented as completed MVP functionality:

- AI-assisted document extraction
- OCR for scanned documents
- Automated anomaly detection
- Expanded SDG visualizations
- Advanced BRSR Core analytics
- Object storage such as S3
- XBRL/export integrations
- CI/CD improvements
- Broader automated test coverage
- Production-grade security hardening

## Security Notes

This is a hackathon/MVP implementation.

Before production use:

- Replace development secrets
- Use a strong production JWT secret
- Use production database credentials
- Configure secure CORS origins
- Enforce HTTPS
- Review file-upload security
- Review access-control policies
- Add production monitoring and logging
- Perform a formal security assessment

The project does not claim SEBI certification or regulatory certification.

## Contribution Workflow

Development should happen on feature branches rather than directly on the team's default branch.

Example:

```text
Sneha
  ^
  | Pull Request
  |
sitakanta-ps08-mvp
```

Changes should be reviewed before merging into the team's default branch.

## License

Add the team's chosen license before public production distribution.
