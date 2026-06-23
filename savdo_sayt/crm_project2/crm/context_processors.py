from .models import UserProfile


def tun_rejimi(request):
    """
    Har bir templateda {{ tun_rejimi }} o'zgaruvchisini taqdim etadi.
    True bo'lsa tun rejimi yoqilgan, False bo'lsa o'chirilgan.
    """
    if request.user.is_authenticated:
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        return {'tun_rejimi': profile.tun_rejimi}
    return {'tun_rejimi': False}
