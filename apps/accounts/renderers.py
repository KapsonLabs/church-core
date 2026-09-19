from rest_framework.renderers import JSONRenderer


class EnvelopeJSONRenderer(JSONRenderer):
    """Use one predictable top-level shape for API success and error responses."""

    def render(self, data, accepted_media_type=None, renderer_context=None):
        response = (renderer_context or {}).get("response")
        if data is not None and response is not None:
            key = "errors" if response.status_code >= 400 else "data"
            if not (isinstance(data, dict) and key in data):
                data = {key: data}
        return super().render(data, accepted_media_type, renderer_context)
