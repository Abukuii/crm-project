from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.authtoken.models import Token
from rest_framework.views import APIView
from django.db.models import Sum, Count, Q
from django.utils import timezone
from datetime import timedelta

from .models import Mahsulot, Mijoz, Savdo, SavdoItem
from .serializers import (
    MahsulotSerializer, MijozSerializer, SavdoSerializer,
    SavdoCreateSerializer, QarzdorSerializer
)


class CustomAuthToken(ObtainAuthToken):
    """POST /api/login/ — token olish."""
    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(
            data=request.data, context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']
        token, _ = Token.objects.get_or_create(user=user)
        return Response({
            'token': token.key,
            'user_id': user.pk,
            'username': user.username,
            'is_admin': user.is_superuser,
        })


class LogoutView(APIView):
    """POST /api/logout/ — tokenni o'chirish."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        request.user.auth_token.delete()
        return Response({'detail': "Muvaffaqiyatli chiqildi."})


class MahsulotViewSet(viewsets.ModelViewSet):
    queryset = Mahsulot.objects.all()
    serializer_class = MahsulotSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['nomi']
    ordering_fields = ['nomi', 'qoldi', 'narxi', 'yaratilgan']
    ordering = ['-yaratilgan']

    @action(detail=False, methods=['get'])
    def kam_qolganlar(self, request):
        """20 ta va undan kam qolgan mahsulotlar."""
        chegara = int(request.query_params.get('chegara', 20))
        # TUZATILDI: soni -> qoldi
        mahsulotlar = Mahsulot.objects.filter(qoldi__lte=chegara).order_by('qoldi')
        serializer = self.get_serializer(mahsulotlar, many=True)
        return Response({
            'count': mahsulotlar.count(),
            'chegara': chegara,
            'results': serializer.data
        })

    @action(detail=False, methods=['get'])
    def statistika(self, request):
        """Mahsulotlar bo'yicha umumiy statistika."""
        qs = Mahsulot.objects.all()
        # TUZATILDI: soni -> qoldi, sotildi -> jami_sotildi property
        jami_sotildi = SavdoItem.objects.aggregate(s=Sum('soni'))['s'] or 0
        return Response({
            'jami_turlar': qs.count(),
            'jami_qoldi': qs.aggregate(s=Sum('qoldi'))['s'] or 0,
            'jami_sotildi': jami_sotildi,
            'kam_qolganlar': qs.filter(qoldi__lte=10).count(),
            'tugaganlar': qs.filter(qoldi=0).count(),
        })


class SavdoViewSet(viewsets.ModelViewSet):
    queryset = Savdo.objects.select_related('mijoz').prefetch_related('savdo_itemlar__mahsulot')
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.OrderingFilter]
    ordering = ['-yaratilgan']

    def get_serializer_class(self):
        if self.action == 'create':
            return SavdoCreateSerializer
        return SavdoSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        sana = self.request.query_params.get('sana')
        tolov = self.request.query_params.get('tolov_turi')
        tolangan = self.request.query_params.get('to_langan')
        if sana:
            qs = qs.filter(sana=sana)
        if tolov:
            qs = qs.filter(tolov_turi=tolov)
        if tolangan is not None:
            qs = qs.filter(to_langan=(tolangan.lower() == 'true'))
        return qs

    def perform_destroy(self, instance):
        # Savdo o'chirilganda qoldiq tiklanadi (models.py delete() metodi orqali)
        instance.delete()

    @action(detail=True, methods=['post'])
    def tolash(self, request, pk=None):
        savdo = self.get_object()
        if savdo.to_langan:
            return Response({'detail': "Bu savdo allaqachon to'langan."}, status=400)
        savdo.to_langan = True
        savdo.save()
        return Response({'detail': "To'lov muvaffaqiyatli amalga oshirildi.", 'id': savdo.pk})

    @action(detail=False, methods=['get'])
    def statistika(self, request):
        bugun = timezone.now().date()
        oy_boshi = bugun.replace(day=1)
        yil_boshi = bugun.replace(month=1, day=1)

        def summa(qs):
            return qs.aggregate(s=Sum('jami_summa'))['s'] or 0

        haftalik = []
        for i in range(6, -1, -1):
            kun = bugun - timedelta(days=i)
            haftalik.append({
                'sana': kun.isoformat(),
                'summa': float(summa(Savdo.objects.filter(sana=kun)))
            })

        return Response({
            'bugun': {
                'soni': Savdo.objects.filter(sana=bugun).count(),
                'summa': float(summa(Savdo.objects.filter(sana=bugun))),
            },
            'oy': {
                'soni': Savdo.objects.filter(sana__gte=oy_boshi).count(),
                'summa': float(summa(Savdo.objects.filter(sana__gte=oy_boshi))),
            },
            'yil': {
                'soni': Savdo.objects.filter(sana__gte=yil_boshi).count(),
                'summa': float(summa(Savdo.objects.filter(sana__gte=yil_boshi))),
            },
            'haftalik': haftalik,
        })


class MijozViewSet(viewsets.ModelViewSet):
    queryset = Mijoz.objects.all()
    serializer_class = MijozSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter]
    search_fields = ['ism_familiya', 'telefon']

    @action(detail=False, methods=['get'])
    def qarzdorlar(self, request):
        mijozlar = Mijoz.objects.filter(
            savdolar__to_langan=False
        ).distinct()
        serializer = QarzdorSerializer(mijozlar, many=True)
        jami = sum(m.jami_qarz for m in mijozlar)
        return Response({
            'count': mijozlar.count(),
            'umumiy_qarz': float(jami),
            'results': serializer.data
        })
