from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User, Group
from django.contrib import messages
from django.db.models import Sum
from django.utils import timezone
from datetime import timedelta
from django.core.paginator import Paginator
from django.core.exceptions import PermissionDenied
import requests
from django.conf import settings
import json
import os
import sys

from .models import Mahsulot, Kirim, Mijoz, Savdo, SavdoItem
from .decorators import admin_required, menejer_yoki_admin, is_admin


@login_required
def dashboard(request):
    bugun = timezone.now().date()
    oy_boshi = bugun.replace(day=1)

    jami_mahsulotlar = Mahsulot.objects.count()
    jami_savdolar = Savdo.objects.filter(sana=bugun).count()
    bugungi_daromad = Savdo.objects.filter(sana=bugun).aggregate(s=Sum('jami_summa'))['s'] or 0
    oylik_daromad = Savdo.objects.filter(sana__gte=oy_boshi).aggregate(s=Sum('jami_summa'))['s'] or 0
    jami_qarzdorlar = Mijoz.objects.filter(savdolar__to_langan=False).distinct().count()
    kam_qolganlar = Mahsulot.objects.filter(qoldi__lte=10).count()

    haftalik_data = []
    for i in range(6, -1, -1):
        kun = bugun - timedelta(days=i)
        summa = Savdo.objects.filter(sana=kun).aggregate(s=Sum('jami_summa'))['s'] or 0
        haftalik_data.append({'kun': kun.strftime('%d/%m'), 'summa': float(summa)})

    oxirgi_savdolar = Savdo.objects.select_related('mijoz').order_by('-yaratilgan')[:5]

    context = {
        'jami_mahsulotlar': jami_mahsulotlar,
        'jami_savdolar': jami_savdolar,
        'bugungi_daromad': bugungi_daromad,
        'oylik_daromad': oylik_daromad,
        'jami_qarzdorlar': jami_qarzdorlar,
        'kam_qolganlar': kam_qolganlar,
        'haftalik_data': json.dumps(haftalik_data),
        'oxirgi_savdolar': oxirgi_savdolar,
    }
    return render(request, 'crm/dashboard.html', context)


@menejer_yoki_admin
def savdo(request):
    mahsulotlar = Mahsulot.objects.filter(qoldi__gt=0)
    mijozlar = Mijoz.objects.all()

    if request.method == 'POST':
        tolov_turi = request.POST.get('tolov_turi', 'naqd')
        mijoz_id = request.POST.get('mijoz_id')
        mijoz_ism = request.POST.get('mijoz_ism', '')
        mijoz_tel = request.POST.get('mijoz_tel', '')

        mijoz = None
        if tolov_turi == 'nasiya':
            if mijoz_id:
                mijoz = get_object_or_404(Mijoz, pk=mijoz_id)
            elif mijoz_ism and mijoz_tel:
                mijoz = Mijoz.objects.create(ism_familiya=mijoz_ism, telefon=mijoz_tel)

        mahsulot_ids = request.POST.getlist('mahsulot_id')
        sonlar = request.POST.getlist('son')
        jami = 0
        itemlar = []

        for mid, son in zip(mahsulot_ids, sonlar):
            if mid and son:
                try:
                    mahsulot = Mahsulot.objects.get(pk=mid)
                    son_int = int(son)
                    if son_int > 0 and mahsulot.qoldi >= son_int:
                        itemlar.append((mahsulot, son_int))
                        jami += mahsulot.narxi * son_int
                except (Mahsulot.DoesNotExist, ValueError):
                    pass

        if not itemlar:
            messages.error(request, "Hech qanday mahsulot tanlanmadi!")
            return redirect('savdo')

        savdo_obj = Savdo.objects.create(
            mijoz=mijoz,
            tolov_turi=tolov_turi,
            to_langan=(tolov_turi != 'nasiya'),
            jami_summa=jami
        )

        telegram_itemlar = []
        for mahsulot, son_int in itemlar:
            SavdoItem.objects.create(
                savdo=savdo_obj, mahsulot=mahsulot,
                soni=son_int, narxi=mahsulot.narxi
            )
            mahsulot.qoldi -= son_int
            mahsulot.save()
            telegram_itemlar.append({
                'nomi': mahsulot.nomi,
                'soni': son_int,
                'jami': int(mahsulot.narxi * son_int),
            })

        # Telegram kanalga xabar
        _telegram_notify({
            'sana': savdo_obj.sana.strftime('%d.%m.%Y'),
            'sotuvchi': request.user.get_full_name() or request.user.username,
            'tolov_turi': tolov_turi,
            'jami_summa': int(jami),
            'itemlar': telegram_itemlar,
            'mijoz_ism': mijoz.ism_familiya if mijoz else '',
            'mijoz_tel': mijoz.telefon if mijoz else '',
        })

        messages.success(request, f"Savdo #{savdo_obj.pk} muvaffaqiyatli amalga oshirildi!")
        return redirect('savdo')

    context = {'mahsulotlar': mahsulotlar, 'mijozlar': mijozlar}
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
            nomi = request.POST.get('nomi')
            qoldi = request.POST.get('qoldi', 0)
            narxi = request.POST.get('narxi', 0)
            if nomi:
                Mahsulot.objects.create(nomi=nomi, qoldi=qoldi, narxi=narxi)
                messages.success(request, f"'{nomi}' mahsuloti qo'shildi!")
        elif action == 'tahrirlash':
            mid = request.POST.get('mahsulot_id')
            mahsulot = get_object_or_404(Mahsulot, pk=mid)
            mahsulot.nomi = request.POST.get('nomi', mahsulot.nomi)
            mahsulot.narxi = request.POST.get('narxi', mahsulot.narxi)
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
            kirim_soni = int(request.POST.get('kirim_soni', 0))
            kirim_narxi = request.POST.get('kirim_narxi') or None
            izoh = request.POST.get('izoh', '')
            if kirim_soni > 0:
                Kirim.objects.create(
                    mahsulot=mahsulot,
                    soni=kirim_soni,
                    narxi=kirim_narxi,
                    izoh=izoh
                )
                messages.success(request, f"'{mahsulot.nomi}' ga +{kirim_soni} ta kirim qo'shildi!")
            else:
                messages.error(request, "Kirim soni 0 dan katta bo'lishi kerak!")
        return redirect('barcha_mahsulotlar')

    # Pagination - har sahifada 20 ta
    paginator = Paginator(mahsulotlar, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {'mahsulotlar': page_obj, 'search': search, 'page_obj': page_obj}
    return render(request, 'crm/barcha.html', context)


@menejer_yoki_admin
def kirim_tarixi(request):
    kirimlar = Kirim.objects.select_related('mahsulot').order_by('-yaratilgan')

    # Sana filtri
    sana_dan = request.GET.get('sana_dan', '')
    sana_gacha = request.GET.get('sana_gacha', '')
    if sana_dan:
        kirimlar = kirimlar.filter(sana__gte=sana_dan)
    if sana_gacha:
        kirimlar = kirimlar.filter(sana__lte=sana_gacha)

    # Pagination
    paginator = Paginator(kirimlar, 20)
    page_obj = paginator.get_page(request.GET.get('page'))

    context = {'kirimlar': page_obj, 'page_obj': page_obj, 'sana_dan': sana_dan, 'sana_gacha': sana_gacha}
    return render(request, 'crm/kirim_tarixi.html', context)


@menejer_yoki_admin
def kamayganlar(request):
    mahsulotlar = Mahsulot.objects.filter(qoldi__lte=20).order_by('qoldi')
    context = {'mahsulotlar': mahsulotlar}
    return render(request, 'crm/kamayganlar.html', context)


@menejer_yoki_admin
def qarzdorlar(request):
    # N+1 muammo tuzatildi: select_related va prefetch_related
    mijozlar = Mijoz.objects.filter(
        savdolar__to_langan=False
    ).distinct().prefetch_related(
        'savdolar__savdo_itemlar__mahsulot'
    )

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'tolash':
            savdo_id = request.POST.get('savdo_id')
            savdo_obj = get_object_or_404(Savdo, pk=savdo_id)
            savdo_obj.to_langan = True
            savdo_obj.save()
            messages.success(request, "Qarz to'landi!")
        elif action == 'ochirish':
            mijoz_id = request.POST.get('mijoz_id')
            mijoz = get_object_or_404(Mijoz, pk=mijoz_id)
            mijoz.delete()
            messages.success(request, "Mijoz o'chirildi!")
        return redirect('qarzdorlar')

    # Jami qarz summasi
    jami_qarz = sum(m.jami_qarz for m in mijozlar)

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
    savdolar = Savdo.objects.select_related('mijoz').prefetch_related(
        'savdo_itemlar__mahsulot'
    ).order_by('-yaratilgan')

    # Sana filtri
    sana_dan = request.GET.get('sana_dan', '')
    sana_gacha = request.GET.get('sana_gacha', '')
    tolov_filter = request.GET.get('tolov', '')

    if sana_dan:
        savdolar = savdolar.filter(sana__gte=sana_dan)
    if sana_gacha:
        savdolar = savdolar.filter(sana__lte=sana_gacha)
    if tolov_filter:
        savdolar = savdolar.filter(tolov_turi=tolov_filter)

    # Jami statistika (filterdan keyin)
    jami_summa = savdolar.aggregate(s=Sum('jami_summa'))['s'] or 0

    # Pagination
    paginator = Paginator(savdolar, 20)
    page_obj = paginator.get_page(request.GET.get('page'))

    context = {
        'savdolar': page_obj,
        'page_obj': page_obj,
        'sana_dan': sana_dan,
        'sana_gacha': sana_gacha,
        'tolov_filter': tolov_filter,
        'jami_summa': jami_summa,
    }
    return render(request, 'crm/tarix.html', context)


@admin_required
def savdo_ochirish(request, pk):
    """Savdoni o'chirish — faqat superuser yoki xato savdolar uchun"""
    savdo_obj = get_object_or_404(Savdo, pk=pk)
    if request.method == 'POST':
        savdo_obj.delete()  # models.py da qoldiq tiklanadi
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

        matn = (
            f"🛒 Yangi savdo\n"
            f"📅 {data.get('sana', '')}\n"
            f"👨‍💼 Sotuvchi: {data.get('sotuvchi', '')}\n"
            f"{mijoz_text}"
            f"{tolov_emoji} To'lov: {data.get('tolov_turi', '')}\n"
            f"📦 Mahsulotlar:\n{itemlar_text}\n"
            f"💰 Jami: {data.get('jami_summa', 0):,} so'm"
        )

        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": matn},
            timeout=3
        )
    except Exception:
        pass


# ── FOYDALANUVCHILAR BOSHQARUVI (faqat Admin) ──────────────────

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
