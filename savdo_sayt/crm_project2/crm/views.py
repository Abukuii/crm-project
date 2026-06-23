from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User, Group
from django.contrib import messages
from django.db.models import Sum, Q
from django.utils import timezone
from datetime import timedelta
from django.core.paginator import Paginator
import requests
import json

from .models import Mahsulot, Kirim, Mijoz, Savdo, SavdoItem, TolovTarixi, Xarajat, Eslatma, DollarKurs, UserProfile
from .decorators import admin_required, menejer_yoki_admin, is_admin


@login_required
def dashboard(request):
    bugun = timezone.now().date()
    oy_boshi = bugun.replace(day=1)

    if request.method == 'POST' and request.POST.get('action') == 'dollar_kursi_saqlash':
        dollar_kursi = request.POST.get('dollar_kursi', '').strip()
        if dollar_kursi:
            DollarKurs.saqlash(dollar_kursi)
            messages.success(request, f"Dollar kursi {dollar_kursi} so'm qilib saqlandi!")
        return redirect('dashboard')

    jami_mahsulotlar = Mahsulot.objects.count()
    jami_savdolar = Savdo.objects.filter(sana=bugun).count()
    bugungi_daromad = Savdo.objects.filter(sana=bugun).aggregate(s=Sum('jami_summa'))['s'] or 0
    oylik_daromad = Savdo.objects.filter(sana__gte=oy_boshi).aggregate(s=Sum('jami_summa'))['s'] or 0
    jami_qarzdorlar = Mijoz.objects.filter(savdolar__to_langan=False).distinct().count()
    bugungi_xarajat = Xarajat.objects.filter(sana=bugun).aggregate(s=Sum('summa'))['s'] or 0
    oylik_xarajat = Xarajat.objects.filter(sana__gte=oy_boshi).aggregate(s=Sum('summa'))['s'] or 0
    sof_foyda = int(oylik_daromad) - int(oylik_xarajat)
    kam_qolganlar = Mahsulot.objects.filter(qoldi__lte=10).count()

    hafta_boshi = bugun - timedelta(days=6)
    haftalik_qs = (
        Savdo.objects
        .filter(sana__gte=hafta_boshi)
        .values('sana')
        .annotate(summa=Sum('jami_summa'))
        .order_by('sana')
    )
    kunlar = {entry['sana']: float(entry['summa']) for entry in haftalik_qs}
    haftalik_data = []
    for i in range(6, -1, -1):
        kun = bugun - timedelta(days=i)
        haftalik_data.append({'kun': kun.strftime('%d/%m'), 'summa': kunlar.get(kun, 0)})

    oxirgi_savdolar = Savdo.objects.select_related('mijoz').order_by('-yaratilgan')[:5]

    # DB dan kurs
    kurs_obj = DollarKurs.objects.first()
    saqlangan_kurs = str(kurs_obj.kurs) if kurs_obj else ''
    saqlangan_sana = kurs_obj.yangilangan.strftime('%Y-%m-%d') if kurs_obj else ''

    context = {
        'jami_mahsulotlar': jami_mahsulotlar,
        'jami_savdolar': jami_savdolar,
        'bugungi_daromad': bugungi_daromad,
        'oylik_daromad': oylik_daromad,
        'jami_qarzdorlar': jami_qarzdorlar,
        'kam_qolganlar': kam_qolganlar,
        'haftalik_data': json.dumps(haftalik_data),
        'oxirgi_savdolar': oxirgi_savdolar,
        'saqlangan_kurs': saqlangan_kurs,
        'saqlangan_sana': saqlangan_sana,
        'bugungi_xarajat': bugungi_xarajat,
        'oylik_xarajat': oylik_xarajat,
        'sof_foyda': sof_foyda,
    }
    return render(request, 'crm/dashboard.html', context)


@menejer_yoki_admin
def savdo(request):
    saqlangan_kurs = DollarKurs.olish()  # sessiya o'rniga DB dan
    mahsulotlar = Mahsulot.objects.filter(qoldi__gt=0)
    for m in mahsulotlar:
        if m.valyuta == 'usd' and saqlangan_kurs:
            m.narxi_somda = int(float(m.narxi) * float(saqlangan_kurs))
        else:
            m.narxi_somda = int(m.narxi)
    mijozlar = Mijoz.objects.all()

    if request.method == 'POST':
        tolov_turi = request.POST.get('tolov_turi', 'naqd')
        mijoz_id = request.POST.get('mijoz_id')
        mijoz_ism = request.POST.get('mijoz_ism', '')
        mijoz_tel = request.POST.get('mijoz_tel', '')
        bosh_tolov_str = request.POST.get('bosh_tolov', '').strip()

        mijoz = None
        if tolov_turi == 'nasiya':
            if mijoz_id:
                mijoz = get_object_or_404(Mijoz, pk=mijoz_id)
            elif mijoz_ism and mijoz_tel:
                mijoz = Mijoz.objects.create(ism_familiya=mijoz_ism, telefon=mijoz_tel)

        mahsulot_ids = request.POST.getlist('mahsulot_id')
        sonlar = request.POST.getlist('son')
        kelishilgan_narxlar = request.POST.getlist('kelishilgan_narx')
        jami = 0
        itemlar = []

        for i, (mid, son) in enumerate(zip(mahsulot_ids, sonlar)):
            if mid and son:
                try:
                    mahsulot = Mahsulot.objects.get(pk=mid)
                    son_int = int(son)

                    # Dollar mahsulot uchun joriy kurs bilan so'mga o'girish
                    if mahsulot.valyuta == 'usd' and saqlangan_kurs:
                        mahsulot_narxi_somda = int(float(mahsulot.narxi) * float(saqlangan_kurs))
                    else:
                        mahsulot_narxi_somda = int(mahsulot.narxi)

                    kelishilgan = None
                    if i < len(kelishilgan_narxlar) and kelishilgan_narxlar[i]:
                        try:
                            k_narx = int(kelishilgan_narxlar[i])
                            if 0 < k_narx <= mahsulot_narxi_somda:
                                kelishilgan = k_narx
                        except ValueError:
                            pass

                    if son_int > 0 and mahsulot.qoldi >= son_int:
                        itemlar.append((mahsulot, son_int, kelishilgan, mahsulot_narxi_somda))
                        joriy = kelishilgan if kelishilgan else mahsulot_narxi_somda
                        jami += joriy * son_int
                except (Mahsulot.DoesNotExist, ValueError):
                    pass

        if not itemlar:
            messages.error(request, "Hech qanday mahsulot tanlanmadi!")
            return redirect('savdo')

        # Bosh tolov hisoblash
        bosh_tolov = 0
        if tolov_turi == 'nasiya' and bosh_tolov_str:
            try:
                bosh_tolov = int(bosh_tolov_str)
                if bosh_tolov < 0:
                    bosh_tolov = 0
                if bosh_tolov > jami:
                    bosh_tolov = jami
            except ValueError:
                bosh_tolov = 0

        # To'liq to'langan deb hisoblash: naqd/plastik yoki bosh_tolov >= jami
        toliq_tolangan = (tolov_turi != 'nasiya') or (bosh_tolov >= jami)

        savdo_obj = Savdo.objects.create(
            mijoz=mijoz,
            tolov_turi=tolov_turi,
            bosh_tolov=bosh_tolov,
            to_langan=toliq_tolangan,
            jami_summa=jami
        )

        telegram_itemlar = []
        for mahsulot, son_int, kelishilgan, narxi_somda in itemlar:
            SavdoItem.objects.create(
                savdo=savdo_obj,
                mahsulot=mahsulot,
                soni=son_int,
                narxi=narxi_somda,  # ← so'mda, joriy kurs bilan
                kelishilgan_narx=kelishilgan
            )
            mahsulot.qoldi -= son_int
            mahsulot.save()
            joriy_narx = kelishilgan if kelishilgan else narxi_somda
            telegram_itemlar.append({
                'nomi': mahsulot.nomi,
                'soni': son_int,
                'jami': joriy_narx * son_int,
            })

        _telegram_notify({
            'sana': savdo_obj.sana.strftime('%d.%m.%Y'),
            'sotuvchi': request.user.get_full_name() or request.user.username,
            'tolov_turi': tolov_turi,
            'jami_summa': int(jami),
            'bosh_tolov': bosh_tolov,
            'qolgan_qarz': int(jami) - bosh_tolov if tolov_turi == 'nasiya' else 0,
            'itemlar': telegram_itemlar,
            'mijoz_ism': mijoz.ism_familiya if mijoz else '',
            'mijoz_tel': mijoz.telefon if mijoz else '',
        })

        messages.success(request, f"Savdo #{savdo_obj.pk} muvaffaqiyatli amalga oshirildi!")
        return redirect('savdo')

    context = {'mahsulotlar': mahsulotlar, 'mijozlar': mijozlar, 'saqlangan_kurs': saqlangan_kurs}
    return render(request, 'crm/savdo.html', context)


@menejer_yoki_admin
def barcha_mahsulotlar(request):
    mahsulotlar = Mahsulot.objects.all()
    search = request.GET.get('q', '')
    if search:
        mahsulotlar = mahsulotlar.filter(nomi__icontains=search)

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'qoshish':
            nomi = request.POST.get('nomi', '').strip()
            qoldi = int(request.POST.get('qoldi') or 0)
            valyuta = request.POST.get('valyuta', 'uzs')
            narx_turi = request.POST.get('narx_turi', 'aniq')
            asl_narx = request.POST.get('asl_narx', '').strip()
            foiz = float(request.POST.get('foiz') or 0)
            saqlangan_kurs = DollarKurs.olish()

            if not nomi:
                messages.error(request, "Mahsulot nomi kiritilishi shart!")
                return redirect('barcha_mahsulotlar')

            if not asl_narx:
                messages.error(request, "Narx kiritilishi shart!")
                return redirect('barcha_mahsulotlar')

            asl_narx = float(asl_narx)

            # Narxni hisoblash
            narx = asl_narx
            if valyuta == 'usd':
                kurs = float(saqlangan_kurs) if saqlangan_kurs else None
                if not kurs:
                    messages.error(request, "Dollar kursi topilmadi. Avval dashboardda kursni kiriting!")
                    return redirect('barcha_mahsulotlar')
                if narx_turi == 'foizli':
                    narx = narx * (1 + foiz / 100)
                # Bazada DOLLAR saqlanadi
                mahsulot = Mahsulot.objects.create(
                    nomi=nomi, qoldi=0,
                    narxi=round(narx, 2),
                    valyuta='usd'
                )
            else:
                # So'm
                if narx_turi == 'foizli':
                    narx = narx * (1 + foiz / 100)
                mahsulot = Mahsulot.objects.create(
                    nomi=nomi, qoldi=0,
                    narxi=round(narx),
                    valyuta='uzs'
                )

            # Kirim yozuvi — asl_narx=None, chunki narx allaqachon views da hisoblab mahsulotga yozildi
            # Kirim.save() qayta hisoblamasligi uchun asl_narx bo'sh
            Kirim.objects.create(
                mahsulot=mahsulot,
                soni=qoldi if qoldi > 0 else 0,
                valyuta=valyuta,
                narx_turi=narx_turi,
                asl_narx=None,
                foiz=foiz,
                dollar_kursi=saqlangan_kurs or None,
            )
            messages.success(request, f"'{nomi}' mahsuloti qo'shildi!")
        elif action == 'tahrirlash':
            mid = request.POST.get('mahsulot_id')
            mahsulot = get_object_or_404(Mahsulot, pk=mid)
            nomi = request.POST.get('nomi', '').strip()
            valyuta = request.POST.get('valyuta', 'uzs')
            narx_turi = request.POST.get('narx_turi', 'aniq')
            asl_narx = request.POST.get('asl_narx', '').strip()
            foiz = float(request.POST.get('foiz') or 0)
            saqlangan_kurs = DollarKurs.olish()

            if nomi:
                mahsulot.nomi = nomi

            if asl_narx:
                asl_narx = float(asl_narx)
                narx = asl_narx
                if valyuta == 'usd':
                    if narx_turi == 'foizli':
                        narx = narx * (1 + foiz / 100)
                    mahsulot.narxi = round(narx, 2)
                    mahsulot.valyuta = 'usd'
                else:
                    if narx_turi == 'foizli':
                        narx = narx * (1 + foiz / 100)
                    mahsulot.narxi = round(narx)
                    mahsulot.valyuta = 'uzs'

            mahsulot.save()
            messages.success(request, "Mahsulot yangilandi!")
        elif action == 'ochirish':
            mid = request.POST.get('mahsulot_id')
            mahsulot = get_object_or_404(Mahsulot, pk=mid)
            mahsulot.delete()
            messages.success(request, "Mahsulot o'chirildi!")
        elif action == 'kirim':
            mid = request.POST.get('mahsulot_id')
            mahsulot = get_object_or_404(Mahsulot, pk=mid)
            kirim_soni = int(request.POST.get('kirim_soni') or 0)
            kelgan_narx = request.POST.get('kelgan_narx', '').strip()
            manzil = request.POST.get('manzil', '').strip()

            if kirim_soni <= 0:
                messages.error(request, "Kirim soni 0 dan katta bo'lishi kerak!")
                return redirect('barcha_mahsulotlar')

            Kirim.objects.create(
                mahsulot=mahsulot,
                soni=kirim_soni,
                asl_narx=None,
                izoh=manzil,
                valyuta=mahsulot.valyuta,
                narx_turi='aniq',
            )
            messages.success(request, f"'{mahsulot.nomi}' ga +{kirim_soni} ta kirim qo'shildi!")


    paginator = Paginator(mahsulotlar, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    # views.py - barcha_mahsulotlar oxirida context ga qo'shish
    saqlangan_kurs = DollarKurs.olish()
    # Mahsulotlar uchun so'mdagi narxni oldindan hisoblash
    for m in page_obj:
        if m.valyuta == 'usd' and saqlangan_kurs:
            m.narxi_somda = int(float(m.narxi) * float(saqlangan_kurs))
        else:
            m.narxi_somda = None

    context = {
        'mahsulotlar': page_obj,
        'search': search,
        'page_obj': page_obj,
        'saqlangan_kurs': saqlangan_kurs,
    }
    return render(request, 'crm/barcha.html', context)


@menejer_yoki_admin
def kirim_tarixi(request):
    # Tarixni tozalash (faqat admin)
    if request.method == 'POST' and request.POST.get('action') == 'kirim_tarix_tozalash':
        if request.user.is_superuser or request.user.groups.filter(name='Admin').exists():
            Kirim.objects.all().delete()
            messages.success(request, "Kirim tarixi to'liq tozalandi!")
        else:
            messages.error(request, "Sizda bu amalni bajarish huquqi yo'q!")
        return redirect('kirim_tarixi')

    kirimlar = Kirim.objects.select_related('mahsulot').order_by('-yaratilgan')

    sana_dan = request.GET.get('sana_dan', '')
    sana_gacha = request.GET.get('sana_gacha', '')
    limit = request.GET.get('limit', '10')
    limit_int = int(limit) if limit in ['5', '10', '20', '50'] else 10

    if sana_dan:
        kirimlar = kirimlar.filter(sana__gte=sana_dan)
    if sana_gacha:
        kirimlar = kirimlar.filter(sana__lte=sana_gacha)

    # Filter yo'q bo'lsa faqat oxirgi N ta
    has_filter = bool(sana_dan or sana_gacha)
    if not has_filter:
        kirimlar = kirimlar[:limit_int]

    paginator = Paginator(kirimlar, limit_int)
    page_obj = paginator.get_page(request.GET.get('page'))

    context = {
        'kirimlar': page_obj,
        'page_obj': page_obj,
        'sana_dan': sana_dan,
        'sana_gacha': sana_gacha,
        'limit': str(limit_int),
        'has_filter': has_filter,
    }
    return render(request, 'crm/kirim_tarixi.html', context)


@menejer_yoki_admin
def kamayganlar(request):
    from django.db.models import Sum as DbSum
    mahsulotlar = Mahsulot.objects.filter(qoldi__lte=20).order_by('qoldi').annotate(
        _jami_kirim=DbSum('kirimlar__soni')
    )
    # Property _jami_kirim ni annotate dan olsin deb belgilaymiz
    for m in mahsulotlar:
        m._jami_kirim = m._jami_kirim or 0
    context = {'mahsulotlar': mahsulotlar}
    return render(request, 'crm/kamayganlar.html', context)


@menejer_yoki_admin
def qarzdorlar(request):
    mijozlar = Mijoz.objects.filter(
        savdolar__to_langan=False
    ).distinct().prefetch_related(
        'savdolar__savdo_itemlar__mahsulot',
        'savdolar__tolov_tarixlari',
    )

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'toliq_tolash':
            # Butun savdoni to'liq to'langan deb belgilash
            savdo_id = request.POST.get('savdo_id')
            savdo_obj = get_object_or_404(Savdo, pk=savdo_id)
            savdo_obj.to_langan = True
            savdo_obj.save()
            messages.success(request, "Qarz to'liq to'landi!")

        elif action == 'qisman_tolash':
            # Qisman to'lov qo'shish
            savdo_id = request.POST.get('savdo_id')
            tolov_summa_str = request.POST.get('tolov_summa', '').strip()
            izoh = request.POST.get('izoh', '').strip()
            savdo_obj = get_object_or_404(Savdo, pk=savdo_id)
            try:
                tolov_summa = int(tolov_summa_str)
                if tolov_summa <= 0:
                    messages.error(request, "To'lov summasi 0 dan katta bo'lishi kerak!")
                elif tolov_summa > savdo_obj.qolgan_qarz:
                    messages.error(request, f"To'lov summasi qarzdan ko'p! Qolgan qarz: {savdo_obj.qolgan_qarz:,} so'm")
                else:
                    TolovTarixi.objects.create(
                        savdo=savdo_obj,
                        summa=tolov_summa,
                        izoh=izoh,
                    )
                    if savdo_obj.qolgan_qarz - tolov_summa <= 0:
                        messages.success(request, "Qarz to'liq to'landi! ✅")
                    else:
                        qoldi = savdo_obj.qolgan_qarz - tolov_summa
                        messages.success(request, f"To'lov qabul qilindi. Qolgan qarz: {qoldi:,} so'm")
            except ValueError:
                messages.error(request, "Noto'g'ri summa kiritildi!")

        elif action == 'ochirish':
            mijoz_id = request.POST.get('mijoz_id')
            mijoz = get_object_or_404(Mijoz, pk=mijoz_id)
            mijoz.delete()
            messages.success(request, "Mijoz o'chirildi!")

        return redirect('qarzdorlar')

    # Jami qolgan qarz (bosh_tolov va to'lov tarixi hisobga olingan holda)
    from django.db.models import OuterRef, Subquery
    jami_qarz = sum(
        s.qolgan_qarz
        for m in mijozlar
        for s in m.savdolar.all()
        if not s.to_langan
    )

    context = {'mijozlar': mijozlar, 'jami_qarz': jami_qarz}
    return render(request, 'crm/qarzdorlar.html', context)


@login_required
def profil(request):
    if request.method == 'POST':
        user = request.user
        user.first_name = request.POST.get('first_name', user.first_name)
        user.last_name = request.POST.get('last_name', user.last_name)
        user.email = request.POST.get('email', user.email)
        user.save()
        messages.success(request, "Profil yangilandi!")
        return redirect('profil')

    context = {'user': request.user}
    return render(request, 'crm/profil.html', context)


@menejer_yoki_admin
def savdo_tarixi(request):
    # Tarixni tozalash (faqat admin)
    if request.method == 'POST' and request.POST.get('action') == 'tarix_tozalash':
        if request.user.is_superuser or request.user.groups.filter(name='Admin').exists():
            Savdo.objects.all().delete()
            messages.success(request, "Savdo tarixi to'liq tozalandi!")
        else:
            messages.error(request, "Sizda bu amalni bajarish huquqi yo'q!")
        return redirect('savdo_tarixi')

    savdolar = Savdo.objects.select_related('mijoz').prefetch_related(
        'savdo_itemlar__mahsulot'
    ).order_by('-yaratilgan')

    sana_dan = request.GET.get('sana_dan', '')
    sana_gacha = request.GET.get('sana_gacha', '')
    tolov_filter = request.GET.get('tolov', '')
    limit = request.GET.get('limit', '10')
    limit_int = int(limit) if limit in ['5', '10', '20', '50'] else 10

    if sana_dan:
        savdolar = savdolar.filter(sana__gte=sana_dan)
    if sana_gacha:
        savdolar = savdolar.filter(sana__lte=sana_gacha)
    if tolov_filter:
        savdolar = savdolar.filter(tolov_turi=tolov_filter)

    jami_summa = savdolar.aggregate(s=Sum('jami_summa'))['s'] or 0

    # Filter yo'q bo'lsa faqat oxirgi N ta ko'rsatamiz
    has_filter = bool(sana_dan or sana_gacha or tolov_filter)
    if not has_filter:
        savdolar = savdolar[:limit_int]

    paginator = Paginator(savdolar, limit_int)
    page_obj = paginator.get_page(request.GET.get('page'))

    context = {
        'savdolar': page_obj,
        'page_obj': page_obj,
        'sana_dan': sana_dan,
        'sana_gacha': sana_gacha,
        'tolov_filter': tolov_filter,
        'jami_summa': jami_summa,
        'limit': str(limit_int),
        'has_filter': has_filter,
    }
    return render(request, 'crm/tarix.html', context)


@admin_required
def savdo_ochirish(request, pk):
    savdo_obj = get_object_or_404(Savdo, pk=pk)
    if request.method == 'POST':
        savdo_obj.delete()
        messages.success(request, f"Savdo #{pk} o'chirildi va mahsulot qoldig'i tiklandi!")
    return redirect('savdo_tarixi')


def _telegram_notify(data: dict):
    try:
        from pathlib import Path
        from dotenv import dotenv_values

        bot_env_path = Path(__file__).resolve().parent.parent.parent / 'telegram_bot' / '.env'
        config = dotenv_values(bot_env_path)

        token = config.get('BOT_TOKEN')
        chat_id = config.get('CHANNEL_ID')

        if not token or not chat_id:
            return

        itemlar_text = "\n".join(
            f"  • {i['nomi']} × {i['soni']} = {i['jami']:,} so'm"
            for i in data.get('itemlar', [])
        )

        mijoz_text = ""
        if data.get('mijoz_ism'):
            mijoz_text = f"👤 Mijoz: {data['mijoz_ism']}"
            if data.get('mijoz_tel'):
                mijoz_text += f" ({data['mijoz_tel']})"
            mijoz_text += "\n"

        tolov_emoji = {"naqd": "💵", "plastik": "💳", "nasiya": "⏳"}.get(data.get('tolov_turi'), "💰")

        nasiya_text = ""
        if data.get('tolov_turi') == 'nasiya':
            bosh_tolov = int(data.get('bosh_tolov', 0) or 0)
            qolgan_qarz = int(data.get('qolgan_qarz', 0) or 0)
            if bosh_tolov > 0:
                nasiya_text += f"✅ Bosh to'lov: {bosh_tolov:,} so'm\n"
            if qolgan_qarz > 0:
                nasiya_text += f"⚠️ Qolgan qarz: {qolgan_qarz:,} so'm\n"

        matn = (
            f"🛒 Yangi savdo\n"
            f"📅 {data.get('sana', '')}\n"
            f"👨‍💼 Sotuvchi: {data.get('sotuvchi', '')}\n"
            f"{mijoz_text}"
            f"{tolov_emoji} To'lov: {data.get('tolov_turi', '')}\n"
            f"📦 Mahsulotlar:\n{itemlar_text}\n"
            f"💰 Jami: {data.get('jami_summa', 0):,} so'm\n"
            f"{nasiya_text}"
        )

        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": matn},
            timeout=3
        )
    except Exception:
        pass


@admin_required
def foydalanuvchilar(request):
    users = User.objects.all().order_by('-date_joined').prefetch_related('groups')

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'qoshish':
            username = request.POST.get('username', '').strip()
            password = request.POST.get('password', '')
            ism = request.POST.get('first_name', '')
            familiya = request.POST.get('last_name', '')
            rol = request.POST.get('rol', 'Menejer')

            if not username or not password:
                messages.error(request, "Login va parol kiritish shart!")
            elif User.objects.filter(username=username).exists():
                messages.error(request, f"'{username}' login allaqachon mavjud!")
            else:
                user = User.objects.create_user(
                    username=username, password=password,
                    first_name=ism, last_name=familiya
                )
                guruh = Group.objects.get(name=rol)
                user.groups.add(guruh)
                messages.success(request, f"'{username}' foydalanuvchisi qo'shildi ({rol})!")

        elif action == 'rol_ozgartirish':
            uid = request.POST.get('user_id')
            user = get_object_or_404(User, pk=uid)
            if user == request.user:
                messages.error(request, "O'z rolingizni o'zgartira olmaysiz!")
            else:
                yangi_rol = request.POST.get('rol')
                user.groups.clear()
                if yangi_rol in ['Admin', 'Menejer']:
                    guruh = Group.objects.get(name=yangi_rol)
                    user.groups.add(guruh)
                messages.success(request, f"'{user.username}' roli yangilandi!")

        elif action == 'parol_ozgartirish':
            uid = request.POST.get('user_id')
            user = get_object_or_404(User, pk=uid)
            yangi_parol = request.POST.get('yangi_parol', '')
            if len(yangi_parol) < 6:
                messages.error(request, "Parol kamida 6 ta belgidan iborat bo'lishi kerak!")
            else:
                user.set_password(yangi_parol)
                user.save()
                messages.success(request, f"'{user.username}' paroli o'zgartirildi!")

        elif action == 'ochirish':
            uid = request.POST.get('user_id')
            user = get_object_or_404(User, pk=uid)
            if user == request.user:
                messages.error(request, "O'zingizni o'chira olmaysiz!")
            else:
                username = user.username
                user.delete()
                messages.success(request, f"'{username}' o'chirildi!")

        return redirect('foydalanuvchilar')

    context = {'users': users}
    return render(request, 'crm/foydalanuvchilar.html', context)

@menejer_yoki_admin
def xarajatlar(request):
    xarajatlar_qs = Xarajat.objects.all()

    # Filter
    sana_dan = request.GET.get('sana_dan', '')
    sana_gacha = request.GET.get('sana_gacha', '')
    kategoriya_filter = request.GET.get('kategoriya', '')
    if sana_dan:
        xarajatlar_qs = xarajatlar_qs.filter(sana__gte=sana_dan)
    if sana_gacha:
        xarajatlar_qs = xarajatlar_qs.filter(sana__lte=sana_gacha)
    if kategoriya_filter:
        xarajatlar_qs = xarajatlar_qs.filter(kategoriya=kategoriya_filter)

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'qoshish':
            nomi = request.POST.get('nomi', '').strip()
            summa = request.POST.get('summa', '').strip()
            kategoriya = request.POST.get('kategoriya', 'boshqa')
            sana = request.POST.get('sana', '')
            izoh = request.POST.get('izoh', '').strip()
            if not nomi or not summa:
                messages.error(request, "Nomi va summa kiritilishi shart!")
            else:
                Xarajat.objects.create(
                    nomi=nomi,
                    summa=float(summa),
                    kategoriya=kategoriya,
                    sana=sana or timezone.now().date(),
                    izoh=izoh,
                )
                messages.success(request, f"'{nomi}' xarajati qo'shildi!")

        elif action == 'tahrirlash':
            xid = request.POST.get('xarajat_id')
            x = get_object_or_404(Xarajat, pk=xid)
            nomi = request.POST.get('nomi', '').strip()
            summa = request.POST.get('summa', '').strip()
            if nomi:
                x.nomi = nomi
            if summa:
                x.summa = float(summa)
            x.kategoriya = request.POST.get('kategoriya', x.kategoriya)
            sana = request.POST.get('sana', '')
            if sana:
                x.sana = sana
            x.izoh = request.POST.get('izoh', '').strip()
            x.save()
            messages.success(request, "Xarajat yangilandi!")

        elif action == 'ochirish':
            xid = request.POST.get('xarajat_id')
            x = get_object_or_404(Xarajat, pk=xid)
            x.delete()
            messages.success(request, "Xarajat o'chirildi!")

        return redirect('xarajatlar')

    jami_summa = xarajatlar_qs.aggregate(s=Sum('summa'))['s'] or 0
    paginator = Paginator(xarajatlar_qs, 20)
    page_obj = paginator.get_page(request.GET.get('page'))

    context = {
        'xarajatlar': page_obj,
        'page_obj': page_obj,
        'jami_summa': jami_summa,
        'sana_dan': sana_dan,
        'sana_gacha': sana_gacha,
        'kategoriya_filter': kategoriya_filter,
        'kategoriyalar': Xarajat.KATEGORIYA,
    }
    return render(request, 'crm/xarajatlar.html', context)


@menejer_yoki_admin
def eslatmalar(request):
    eslatmalar_qs = Eslatma.objects.all()

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'qoshish':
            matn = request.POST.get('matn', '').strip()
            daraja = request.POST.get('daraja', 'oddiy')
            if not matn:
                messages.error(request, "Eslatma matni kiritilishi shart!")
            else:
                Eslatma.objects.create(matn=matn, daraja=daraja)
                messages.success(request, "Eslatma qo'shildi!")

        elif action == 'tahrirlash':
            eid = request.POST.get('eslatma_id')
            e = get_object_or_404(Eslatma, pk=eid)
            matn = request.POST.get('matn', '').strip()
            if matn:
                e.matn = matn
            e.daraja = request.POST.get('daraja', e.daraja)
            e.save()
            messages.success(request, "Eslatma yangilandi!")

        elif action == 'bajarildi':
            eid = request.POST.get('eslatma_id')
            e = get_object_or_404(Eslatma, pk=eid)
            e.bajarildi = not e.bajarildi
            e.save()

        elif action == 'ochirish':
            eid = request.POST.get('eslatma_id')
            e = get_object_or_404(Eslatma, pk=eid)
            e.delete()
            messages.success(request, "Eslatma o'chirildi!")

        return redirect('eslatmalar')

    context = {'eslatmalar': eslatmalar_qs}
    return render(request, 'crm/eslatmalar.html', context)


# ─── TUN REJIMI ───────────────────────────────────────────────────────────────
@login_required
def toggle_dark_mode(request):
    if request.method == 'POST':
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        profile.tun_rejimi = not profile.tun_rejimi
        profile.save()
    next_url = request.POST.get('next', 'dashboard')
    return redirect(next_url)
