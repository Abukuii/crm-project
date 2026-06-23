# crm/serializers.py
from rest_framework import serializers
from .models import Mahsulot, Mijoz, Savdo, SavdoItem, DollarKurs


class MahsulotSerializer(serializers.ModelSerializer):
    qoldi = serializers.ReadOnlyField()
    kam_qolgan = serializers.ReadOnlyField()

    class Meta:
        model = Mahsulot
        fields = ['id', 'nomi', 'qoldi', 'narxi', 'jami_sotildi', 'kam_qolgan', 'yaratilgan']
        read_only_fields = ['yaratilgan']


class SavdoItemSerializer(serializers.ModelSerializer):
    mahsulot_nomi = serializers.CharField(source='mahsulot.nomi', read_only=True)
    jami = serializers.ReadOnlyField()
    joriy_narx = serializers.ReadOnlyField()

    class Meta:
        model = SavdoItem
        fields = ['id', 'mahsulot', 'mahsulot_nomi', 'soni', 'narxi', 'kelishilgan_narx', 'joriy_narx', 'jami']


class SavdoSerializer(serializers.ModelSerializer):
    savdo_itemlar = SavdoItemSerializer(many=True, read_only=True)
    mijoz_ism = serializers.CharField(source='mijoz.ism_familiya', read_only=True)
    qolgan_qarz = serializers.ReadOnlyField()
    tolangan_jami = serializers.ReadOnlyField(source='toʻlangan_jami')

    class Meta:
        model = Savdo
        fields = ['id', 'mijoz', 'mijoz_ism', 'sana', 'tolov_turi',
                  'jami_summa', 'bosh_tolov', 'qolgan_qarz', 'tolangan_jami',
                  'to_langan', 'izoh', 'savdo_itemlar', 'yaratilgan']
        read_only_fields = ['jami_summa', 'yaratilgan']


class SavdoCreateSerializer(serializers.ModelSerializer):
    """Yangi savdo yaratish uchun — itemlar bilan birga."""
    itemlar = serializers.ListField(
        child=serializers.DictField(), write_only=True
    )
    bosh_tolov = serializers.IntegerField(default=0, min_value=0, required=False)

    class Meta:
        model = Savdo
        fields = ['mijoz', 'sana', 'tolov_turi', 'izoh', 'bosh_tolov', 'itemlar']

    def create(self, validated_data):
        itemlar_data = validated_data.pop('itemlar', [])
        bosh_tolov = validated_data.pop('bosh_tolov', 0)

        # Avval barcha mahsulot qoldiqlarini tekshiramiz
        for item in itemlar_data:
            mahsulot = Mahsulot.objects.get(pk=item['mahsulot_id'])
            son = int(item['soni'])
            if mahsulot.qoldi < son:
                raise serializers.ValidationError(
                    f"'{mahsulot.nomi}' uchun yetarli qoldi yo'q (mavjud: {mahsulot.qoldi} ta)"
                )

        tolov_turi = validated_data.get('tolov_turi', 'naqd')

        savdo = Savdo.objects.create(
            **validated_data,
            bosh_tolov=bosh_tolov if tolov_turi == 'nasiya' else 0,
            to_langan=(tolov_turi != 'nasiya'),
            jami_summa=0
        )
        jami = 0
        for item in itemlar_data:
            mahsulot = Mahsulot.objects.get(pk=item['mahsulot_id'])
            son = int(item['soni'])
            kelishilgan = item.get('kelishilgan_narx')
            if kelishilgan:
                try:
                    kelishilgan = int(kelishilgan)
                    if mahsulot.valyuta == 'usd':
                        kurs = DollarKurs.olish()
                        narx_somda = int(float(mahsulot.narxi) * kurs) if kurs else int(mahsulot.narxi)
                    else:
                        narx_somda = int(mahsulot.narxi)
                    if kelishilgan <= 0 or kelishilgan > narx_somda:
                        kelishilgan = None
                except (ValueError, TypeError):
                    kelishilgan = None

            SavdoItem.objects.create(
                savdo=savdo, mahsulot=mahsulot,
                soni=son, narxi=mahsulot.narxi,
                kelishilgan_narx=kelishilgan
            )
            mahsulot.qoldi -= son
            mahsulot.save()
            joriy = kelishilgan if kelishilgan else int(mahsulot.narxi)
            jami += joriy * son

        savdo.jami_summa = jami
        # Agar bosh_tolov jami dan katta yoki teng bo'lsa — to'liq to'langan
        if tolov_turi == 'nasiya' and bosh_tolov >= jami:
            savdo.to_langan = True
        savdo.save()
        return savdo


class MijozSerializer(serializers.ModelSerializer):
    jami_qarz = serializers.ReadOnlyField()
    savdolar_soni = serializers.SerializerMethodField()

    class Meta:
        model = Mijoz
        fields = ['id', 'ism_familiya', 'telefon', 'manzil',
                  'jami_qarz', 'savdolar_soni', 'yaratilgan']
        read_only_fields = ['yaratilgan']

    def get_savdolar_soni(self, obj):
        return obj.savdolar.count()


class QarzdorSerializer(serializers.ModelSerializer):
    """Faqat nasiya qarzlari bor mijozlar."""
    jami_qarz = serializers.ReadOnlyField()
    nasiya_savdolar = serializers.SerializerMethodField()

    class Meta:
        model = Mijoz
        fields = ['id', 'ism_familiya', 'telefon', 'manzil', 'jami_qarz', 'nasiya_savdolar']

    def get_nasiya_savdolar(self, obj):
        savdolar = obj.savdolar.filter(to_langan=False)
        return SavdoSerializer(savdolar, many=True).data
