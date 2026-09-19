# Architecture

## Core and examples

`config`, `apps.accounts`, and `apps.organization` form the reusable core. `apps.crm`, `apps.info`, and `apps.kpis` are optional examples. Core code must never import an example app; an enabled example may depend on the core.

## Tenancy model

Users are global identities identified by email. An `OrganizationMembership` grants a user access to one organization and optionally assigns one role. A `BranchMembership` narrows operational membership to a branch and is valid only while the organization membership is active. A user's record contains no organization, branch, or tenant role foreign key.

Roles belong to exactly one organization. Reusable resource/action permissions are global definitions such as `branches.read`; roles collect those definitions for a tenant. Role names and slugs are unique only inside their organization.

## Authorization flow

Every tenant API request carries an explicit `organization_id` in its URL, query string, or request body. `HasTenantPermission` resolves that organization and verifies the authenticated user's active membership, active role, and required permission. The view then scopes its queryset to the same organization before retrieving an object. Superusers are platform operators and can cross tenant boundaries.

Never fetch a tenant object globally and authorize it afterward. Filtering before lookup prevents object identifiers from becoming a cross-tenant data channel.

## Runtime

Development and production settings inherit from `config.settings.base`. PostgreSQL is the persistent store; Redis backs Channels and Celery. The core ASGI application serves HTTP without importing any example WebSocket routes.
