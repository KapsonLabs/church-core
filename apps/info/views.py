from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from apps.accounts.permissions import HasTenantPermission

from .serializers import (
    CategorySerializer,
    TagSerializer,
    FAQSerializer,
    SOPSerializer,
    PolicyExplanationSerializer,
    TrainingArticleSerializer,
)


class InfoTenantAPIView(APIView):
    permission_classes = [IsAuthenticated, HasTenantPermission]
    required_permissions = {"GET": "info.read", "POST": "info.manage", "PUT": "info.manage", "PATCH": "info.manage", "DELETE": "info.manage"}
from .services import (
    CategoryService,
    TagService,
    FAQService,
    SOPService,
    PolicyExplanationService,
    TrainingArticleService,
)


# -----------------------------------------------------------------------------
# Category Views
# -----------------------------------------------------------------------------

class CategoryListCreateView(InfoTenantAPIView):
    """List all categories or create a new category."""
    permission_classes = InfoTenantAPIView.permission_classes

    def get(self, request):
        """List all categories."""
        params = request.query_params.dict()
        queryset = CategoryService.get_category_list_queryset(params)
        serializer = CategorySerializer(queryset, many=True)
        return Response({"data": serializer.data, "status": 200}, status=status.HTTP_200_OK)

    def post(self, request):
        """Create a new category."""
        serializer = CategorySerializer(data=request.data)
        if serializer.is_valid():
            category = CategoryService.create_category(serializer.validated_data)
            serializer = CategorySerializer(category)
            return Response({"data": serializer.data, "status": 201}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CategoryDetailView(InfoTenantAPIView):
    """Retrieve or update a category."""
    permission_classes = InfoTenantAPIView.permission_classes

    def get(self, request, id):
        """Retrieve a category."""
        category = CategoryService.get_category_by_id(id, request.query_params.get('organization_id'))
        serializer = CategorySerializer(category)
        return Response({"data": serializer.data, "status": 200}, status=status.HTTP_200_OK)

    def put(self, request, id):
        """Update a category."""
        category = CategoryService.get_category_by_id(id, request.query_params.get('organization_id'))
        serializer = CategorySerializer(category, data=request.data)
        if serializer.is_valid():
            category = CategoryService.update_category(category, serializer.validated_data)
            serializer = CategorySerializer(category)
            return Response({"data": serializer.data, "status": 200}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# -----------------------------------------------------------------------------
# Tag Views
# -----------------------------------------------------------------------------

class TagListCreateView(InfoTenantAPIView):
    """List all tags or create a new tag."""
    permission_classes = InfoTenantAPIView.permission_classes

    def get(self, request):
        """List all tags."""
        params = request.query_params.dict()
        queryset = TagService.get_tag_list_queryset(params)
        serializer = TagSerializer(queryset, many=True)
        return Response({"data": serializer.data, "status": 200}, status=status.HTTP_200_OK)

    def post(self, request):
        """Create a new tag."""
        serializer = TagSerializer(data=request.data)
        if serializer.is_valid():
            tag = TagService.create_tag(serializer.validated_data)
            serializer = TagSerializer(tag)
            return Response({"data": serializer.data, "status": 201}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class TagDetailView(InfoTenantAPIView):
    """Retrieve or update a tag."""
    permission_classes = InfoTenantAPIView.permission_classes

    def get(self, request, id):
        """Retrieve a tag."""
        tag = TagService.get_tag_by_id(id, request.query_params.get('organization_id'))
        serializer = TagSerializer(tag)
        return Response({"data": serializer.data, "status": 200}, status=status.HTTP_200_OK)

    def put(self, request, id):
        """Update a tag."""
        tag = TagService.get_tag_by_id(id, request.query_params.get('organization_id'))
        serializer = TagSerializer(tag, data=request.data)
        if serializer.is_valid():
            tag = TagService.update_tag(tag, serializer.validated_data)
            serializer = TagSerializer(tag)
            return Response({"data": serializer.data, "status": 200}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# -----------------------------------------------------------------------------
# FAQ Views
# -----------------------------------------------------------------------------

class FAQListCreateView(InfoTenantAPIView):
    """List all FAQs or create a new FAQ."""
    permission_classes = InfoTenantAPIView.permission_classes

    def get(self, request):
        """List all FAQs."""
        params = request.query_params.dict()
        queryset = FAQService.get_faq_list_queryset(params)
        serializer = FAQSerializer(queryset, many=True, context={'request': request})
        return Response({"data": serializer.data, "status": 200}, status=status.HTTP_200_OK)

    def post(self, request):
        """Create a new FAQ."""
        serializer = FAQSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            faq = FAQService.create_faq(serializer.validated_data, request.user)
            serializer = FAQSerializer(faq, context={'request': request})
            return Response({"data": serializer.data, "status": 201}, status=status.HTTP_201_CREATED)
        return Response({"data": serializer.errors, "status": 400}, status=status.HTTP_400_BAD_REQUEST)


class FAQDetailView(InfoTenantAPIView):
    """Retrieve or update a FAQ."""
    permission_classes = InfoTenantAPIView.permission_classes

    def get(self, request, id):
        """Retrieve a FAQ and increment view count."""
        faq = FAQService.get_faq_by_id(id, request.query_params.get('organization_id'))
        FAQService.increment_view_count(faq)
        serializer = FAQSerializer(faq, context={'request': request})
        return Response({"data": serializer.data, "status": 200}, status=status.HTTP_200_OK)

    def put(self, request, id):
        """Update a FAQ."""
        faq = FAQService.get_faq_by_id(id, request.query_params.get('organization_id'))
        serializer = FAQSerializer(faq, data=request.data, context={'request': request})
        if serializer.is_valid():
            faq = FAQService.update_faq(faq, serializer.validated_data, request.user)
            serializer = FAQSerializer(faq, context={'request': request})
            return Response({"data": serializer.data, "status": 200}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class FAQHelpfulView(InfoTenantAPIView):
    """Mark a FAQ as helpful or not helpful."""
    permission_classes = InfoTenantAPIView.permission_classes

    def post(self, request, id):
        """Mark a FAQ as helpful or not helpful."""
        faq = FAQService.get_faq_by_id(id, request.query_params.get('organization_id'))
        is_helpful = request.data.get('is_helpful', True)
        result = FAQService.mark_helpful(faq, is_helpful)
        return Response({"data": result, "status": 200}, status=status.HTTP_200_OK)


# -----------------------------------------------------------------------------
# SOP Views
# -----------------------------------------------------------------------------

class SOPListCreateView(InfoTenantAPIView):
    """List all SOPs or create a new SOP."""
    permission_classes = InfoTenantAPIView.permission_classes

    def get(self, request):
        """List all SOPs."""
        params = request.query_params.dict()
        queryset = SOPService.get_sop_list_queryset(params)
        serializer = SOPSerializer(queryset, many=True, context={'request': request})
        return Response({"data": serializer.data, "status": 200}, status=status.HTTP_200_OK)

    def post(self, request):
        """Create a new SOP."""
        serializer = SOPSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            sop = SOPService.create_sop(serializer.validated_data, request.user)
            serializer = SOPSerializer(sop, context={'request': request})
            return Response({"data": serializer.data, "status": 201}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class SOPDetailView(InfoTenantAPIView):
    """Retrieve or update a SOP."""
    permission_classes = InfoTenantAPIView.permission_classes

    def get(self, request, id):
        """Retrieve a SOP and increment view count."""
        sop = SOPService.get_sop_by_id(id, request.query_params.get('organization_id'))
        SOPService.increment_view_count(sop)
        serializer = SOPSerializer(sop, context={'request': request})
        return Response({"data": serializer.data, "status": 200}, status=status.HTTP_200_OK)

    def put(self, request, id):
        """Update a SOP."""
        sop = SOPService.get_sop_by_id(id, request.query_params.get('organization_id'))
        serializer = SOPSerializer(sop, data=request.data, context={'request': request})
        if serializer.is_valid():
            sop = SOPService.update_sop(sop, serializer.validated_data, request.user)
            serializer = SOPSerializer(sop, context={'request': request})
            return Response({"data": serializer.data, "status": 200}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class SOPApproveView(InfoTenantAPIView):
    """Approve a SOP."""
    permission_classes = InfoTenantAPIView.permission_classes

    def post(self, request, id):
        """Approve a SOP."""
        sop = SOPService.get_sop_by_id(id, request.query_params.get('organization_id'))
        sop = SOPService.approve_sop(sop, request.user)
        serializer = SOPSerializer(sop, context={'request': request})
        return Response({"data": serializer.data, "status": 200}, status=status.HTTP_200_OK)


# -----------------------------------------------------------------------------
# Policy Explanation Views
# -----------------------------------------------------------------------------

class PolicyExplanationListCreateView(InfoTenantAPIView):
    """List all policy explanations or create a new one."""
    permission_classes = InfoTenantAPIView.permission_classes

    def get(self, request):
        """List all policy explanations."""
        params = request.query_params.dict()
        queryset = PolicyExplanationService.get_policy_explanation_list_queryset(params)
        serializer = PolicyExplanationSerializer(queryset, many=True, context={'request': request})
        return Response({"data": serializer.data, "status": 200}, status=status.HTTP_200_OK)

    def post(self, request):
        """Create a new policy explanation."""
        serializer = PolicyExplanationSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            policy = PolicyExplanationService.create_policy_explanation(serializer.validated_data, request.user)
            serializer = PolicyExplanationSerializer(policy, context={'request': request})
            return Response({"data": serializer.data, "status": 201}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class PolicyExplanationDetailView(InfoTenantAPIView):
    """Retrieve or update a policy explanation."""
    permission_classes = InfoTenantAPIView.permission_classes

    def get(self, request, id):
        """Retrieve a policy explanation and increment view count."""
        policy = PolicyExplanationService.get_policy_explanation_by_id(id, request.query_params.get('organization_id'))
        PolicyExplanationService.increment_view_count(policy)
        serializer = PolicyExplanationSerializer(policy, context={'request': request})
        return Response({"data": serializer.data, "status": 200}, status=status.HTTP_200_OK)

    def put(self, request, id):
        """Update a policy explanation."""
        policy = PolicyExplanationService.get_policy_explanation_by_id(id, request.query_params.get('organization_id'))
        serializer = PolicyExplanationSerializer(policy, data=request.data, context={'request': request})
        if serializer.is_valid():
            policy = PolicyExplanationService.update_policy_explanation(policy, serializer.validated_data, request.user)
            serializer = PolicyExplanationSerializer(policy, context={'request': request})
            return Response({"data": serializer.data, "status": 200}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# -----------------------------------------------------------------------------
# Training Article Views
# -----------------------------------------------------------------------------

class TrainingArticleListCreateView(InfoTenantAPIView):
    """List all training articles or create a new one."""
    permission_classes = InfoTenantAPIView.permission_classes

    def get(self, request):
        """List all training articles."""
        params = request.query_params.dict()
        queryset = TrainingArticleService.get_training_article_list_queryset(params)
        serializer = TrainingArticleSerializer(queryset, many=True, context={'request': request})
        return Response({"data": serializer.data, "status": 200}, status=status.HTTP_200_OK)

    def post(self, request):
        """Create a new training article."""
        serializer = TrainingArticleSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            article = TrainingArticleService.create_training_article(serializer.validated_data, request.user)
            serializer = TrainingArticleSerializer(article, context={'request': request})
            return Response({"data": serializer.data, "status": 201}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class TrainingArticleDetailView(InfoTenantAPIView):
    """Retrieve or update a training article."""
    permission_classes = InfoTenantAPIView.permission_classes

    def get(self, request, id):
        """Retrieve a training article and increment view count."""
        article = TrainingArticleService.get_training_article_by_id(id, request.query_params.get('organization_id'))
        TrainingArticleService.increment_view_count(article)
        serializer = TrainingArticleSerializer(article, context={'request': request})
        return Response({"data": serializer.data, "status": 200}, status=status.HTTP_200_OK)

    def put(self, request, id):
        """Update a training article."""
        article = TrainingArticleService.get_training_article_by_id(id, request.query_params.get('organization_id'))
        serializer = TrainingArticleSerializer(article, data=request.data, context={'request': request})
        if serializer.is_valid():
            article = TrainingArticleService.update_training_article(article, serializer.validated_data, request.user)
            serializer = TrainingArticleSerializer(article, context={'request': request})
            return Response({"data": serializer.data, "status": 200}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
