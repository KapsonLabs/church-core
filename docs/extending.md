# Extending the boilerplate

## Add a tenant-owned app

1. Add an `organization` foreign key to each tenant-owned root model. Add a branch foreign key only when branch scope is meaningful.
2. Define global resource/action permissions in an idempotent management command, following `seed_permissions`.
3. Put `IsAuthenticated` and `HasTenantPermission` on API views and map each HTTP method to a codename.
4. Resolve the same explicit `organization_id` in the permission class and queryset. Never rely on a client-supplied object ID without tenant filtering.
5. Mount routes below `/api/v1/<app>/` and keep response errors under `errors`.
6. Add tests showing users can operate inside their tenant and receive `403` or `404` for another tenant's identifiers.

Example:

```python
class ProjectListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated, HasTenantPermission]
    required_permissions = {"GET": "projects.read", "POST": "projects.manage"}

    def get_queryset(self):
        return Project.objects.filter(
            organization_id=self.request.query_params.get("organization_id")
        )
```

Celery tasks should accept tenant and object identifiers, reload objects from tenant-scoped querysets, and remain safe to retry. WebSocket consumers must authenticate the user and apply the same organization membership check before joining a group.
