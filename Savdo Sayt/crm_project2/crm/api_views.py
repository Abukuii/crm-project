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
from .views import _telegram_notify
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

    def perform_create(self, serializer):
        savdo = serializer.save()
        try:
            itemlar = []
            for item in savdo.savdo_itemlar.select_related('mahsulot').all():
                itemlar.append({
                    'nomi': item.mahsulot.nomi,
                    'soni': item.soni,
                    'jami': int(item.jami),
                })
            _telegram_notify({
                'sana': savdo.sana.strftime('%d.%m.%Y'),
                'sotuvchi': self.request.user.get_full_name() or self.request.user.username,
                'tolov_turi': savdo.tolov_turi,
                'jami_summa': int(savdo.jami_summa),
                'bosh_tolov': int(savdo.bosh_tolov),
                'qolgan_qarz': savdo.qolgan_qarz,
                'itemlar': itemlar,
                'mijoz_ism': savdo.mijoz.ism_familiya if savdo.mijoz else '',
                'mijoz_tel': savdo.mijoz.telefon if savdo.mijoz else '',
            })
        except Exception:
            pass

    @action(detail=True, methods=['post'])
    def tolash(self, request, pk=None):
        """
        To'liq yoki qisman to'lov.
        Body: {} — to'liq to'lash
        Body: {"summa": 300000, "izoh": "naqd"} — qisman to'lov
        """
        from .models import TolovTarixi
        savdo = self.get_object()
        if savdo.to_langan:
            return Response({'detail': "Bu savdo allaqachon to'langan."}, status=400)

        summa = request.data.get('summa')

        if summa is None:
            # To'liq to'lash
            savdo.to_langan = True
            savdo.save()
            return Response({
                'detail': "Qarz to'liq to'landi.",
                'id': savdo.pk,
                'qolgan_qarz': 0,
            })
        else:
            # Qisman to'lov
            try:
                summa = int(summa)
            except (ValueError, TypeError):
                return Response({'detail': "Noto'g'ri summa."}, status=400)

            if summa <= 0:
                return Response({'detail': "Summa 0 dan katta bo'lishi kerak."}, status=400)
            if summa > savdo.qolgan_qarz:
                return Response({
                    'detail': f"To'lov summasi qarzdan ko'p. Qolgan qarz: {savdo.qolgan_qarz:,} so'm"
                }, status=400)

            izoh = request.data.get('izoh', '')
            TolovTarixi.objects.create(savdo=savdo, summa=summa, izoh=izoh)
            savdo.refresh_from_db()
            return Response({
                'detail': "To'lov qabul qilindi.",
                'id': savdo.pk,
                'tolangan': summa,
                'qolgan_qarz': savdo.qolgan_qarz,
                'to_langan': savdo.to_langan,
            })

    @action(detail=False, methods=['get'])
    def statistika(self, request):
        bugun = timezone.now().date()
        oy_boshi = bugun.replace(day=1)
        yil_boshi = bugun.replace(month=1, day=1)

        haftalik = []
        for i in range(6, -1, -1):
            kun = bugun - timedelta(days=i)
            s = Savdo.objects.filter(sana=kun).aggregate(s=Sum('jami_summa'))['s'] or 0
            haftalik.append({'sana': kun.isoformat(), 'summa': float(s)})

        bugun_stats = Savdo.objects.filter(sana=bugun).aggregate(
            soni=Count('id'), summa=Sum('jami_summa')
        )
        oy_stats = Savdo.objects.filter(sana__gte=oy_boshi).aggregate(
            soni=Count('id'), summa=Sum('jami_summa')
        )
        yil_stats = Savdo.objects.filter(sana__gte=yil_boshi).aggregate(
            soni=Count('id'), summa=Sum('jami_summa')
        )

        return Response({
            'bugun': {
                'soni': bugun_stats['soni'] or 0,
                'summa': float(bugun_stats['summa'] or 0),
            },
            'oy': {
                'soni': oy_stats['soni'] or 0,
                'summa': float(oy_stats['summa'] or 0),
            },
            'yil': {
                'soni': yil_stats['soni'] or 0,
                'summa': float(yil_stats['summa'] or 0),
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
        ).distinct().prefetch_related('savdolar__tolov_tarixlari')
        serializer = QarzdorSerializer(mijozlar, many=True)
        umumiy_qarz = sum(m.jami_qarz for m in mijozlar)
        return Response({
            'count': mijozlar.count(),
            'umumiy_qarz': float(umumiy_qarz),
            'results': serializer.data
        })
