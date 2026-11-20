from django.contrib.auth.password_validation import validate_password
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from apps.core.serializers import TenantContextMixin, TenantRelatedField
from apps.tenancy.models import Branch

from .models import Role, User
from .perms import ALL, PERMISSIONS


class LoginSerializer(TokenObtainPairSerializer):
    default_error_messages = {"no_active_account": "Login yoki parol noto'g'ri"}

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["tenant_id"] = user.tenant_id
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        tenant = self.user.tenant
        if tenant is None or not tenant.is_active:
            raise serializers.ValidationError({"detail": "Biznes hisobi faol emas"})
        return data


class RoleBriefSerializer(serializers.ModelSerializer):
    class Meta:
        model = Role
        fields = ["id", "name"]


class TenantBriefSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()


class MeSerializer(serializers.ModelSerializer):
    roles = RoleBriefSerializer(many=True, read_only=True)
    permissions = serializers.SerializerMethodField()
    tenant = serializers.SerializerMethodField()
    branch_ids = serializers.SerializerMethodField()
    max_discount_percent = serializers.DecimalField(max_digits=5, decimal_places=2, read_only=True)
    has_pin = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "first_name",
            "last_name",
            "phone",
            "language",
            "theme",
            "roles",
            "permissions",
            "tenant",
            "branch_ids",
            "max_discount_percent",
            "has_pin",
        ]
        read_only_fields = ["id", "username", "roles"]

    def get_permissions(self, obj: User) -> list[str]:
        return sorted(PERMISSIONS) if obj.is_owner else sorted(obj.perm_codes)

    @extend_schema_field(TenantBriefSerializer(allow_null=True))
    def get_tenant(self, obj: User) -> dict | None:
        if obj.tenant is None:
            return None
        return {"id": obj.tenant_id, "name": obj.tenant.name}

    @extend_schema_field(serializers.ListField(child=serializers.IntegerField(), allow_null=True))
    def get_branch_ids(self, obj: User) -> list[int] | None:
        return obj.allowed_branch_ids()

    def get_has_pin(self, obj: User) -> bool:
        return bool(obj.pin_hash)


class PinLoginSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()
    pin = serializers.RegexField(r"^\d{4,6}$")


class RoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Role
        fields = ["id", "name", "permissions", "max_discount_percent", "is_system", "created_at"]
        read_only_fields = ["id", "is_system", "created_at"]

    def validate_permissions(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError("Ro'yxat bo'lishi kerak")
        unknown = set(value) - set(PERMISSIONS)
        if ALL in unknown:
            raise serializers.ValidationError("'*' ruxsatini faqat tizim roli oladi")
        if unknown:
            raise serializers.ValidationError(f"Noma'lum ruxsatlar: {', '.join(sorted(unknown))}")
        return sorted(set(value))

    def validate_max_discount_percent(self, value):
        if not 0 <= value <= 100:
            raise serializers.ValidationError("0 dan 100 gacha")
        return value

    def validate(self, attrs):
        if self.instance is not None and self.instance.is_system:
            raise serializers.ValidationError("Tizim rolini o'zgartirib bo'lmaydi")
        return attrs


class UserSerializer(TenantContextMixin, serializers.ModelSerializer):
    roles = TenantRelatedField(queryset=Role.objects.all(), many=True)
    branches = TenantRelatedField(queryset=Branch.objects.all(), many=True, required=False)
    password = serializers.CharField(write_only=True, required=False, min_length=8)

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "first_name",
            "last_name",
            "phone",
            "is_active",
            "roles",
            "branches",
            "password",
            "last_login",
            "date_joined",
        ]
        read_only_fields = ["id", "last_login", "date_joined"]

    def validate_password(self, value):
        validate_password(value)
        return value

    def validate(self, attrs):
        if self.instance is None and not attrs.get("password"):
            raise serializers.ValidationError({"password": "Parol majburiy"})
        request_user = self.user
        if self.instance is not None and self.instance.pk == request_user.pk:
            if "roles" in attrs or attrs.get("is_active") is False:
                raise serializers.ValidationError(
                    "O'z rolingiz yoki holatingizni o'zgartira olmaysiz"
                )
        # Egasi bo'lmagan foydalanuvchi "Egasi" rolini bera olmaydi
        roles = attrs.get("roles") or []
        if not request_user.is_owner and any(ALL in (r.permissions or []) for r in roles):
            raise serializers.ValidationError({"roles": "Egasi rolini faqat egasi bera oladi"})
        return attrs

    def create(self, validated_data):
        roles = validated_data.pop("roles", [])
        branches = validated_data.pop("branches", [])
        password = validated_data.pop("password")
        user = User(**validated_data, tenant=self.tenant)
        user.set_password(password)
        user.save()
        user.roles.set(roles)
        user.branches.set(branches)
        return user

    def update(self, instance, validated_data):
        validated_data.pop("password", None)  # parol alohida endpoint orqali
        roles = validated_data.pop("roles", None)
        branches = validated_data.pop("branches", None)
        for key, value in validated_data.items():
            setattr(instance, key, value)
        instance.save()
        if roles is not None:
            instance.roles.set(roles)
        if branches is not None:
            instance.branches.set(branches)
        instance.invalidate_perm_cache()
        return instance


class SetPasswordSerializer(serializers.Serializer):
    password = serializers.CharField(min_length=8, write_only=True)

    def validate_password(self, value):
        validate_password(value)
        return value


class SetPinSerializer(serializers.Serializer):
    pin = serializers.RegexField(r"^\d{4,6}$", allow_blank=True)


# ── OpenAPI sxemasi uchun (frontend tiplari shu yerdan generatsiya qilinadi) ──
class LoginRequestSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)


class AccessSerializer(serializers.Serializer):
    access = serializers.CharField()


class AuthResponseSerializer(AccessSerializer):
    user = MeSerializer()


class PinUserSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    username = serializers.CharField()
    full_name = serializers.CharField()


class PermissionItemSerializer(serializers.Serializer):
    code = serializers.CharField()
    label = serializers.CharField()
