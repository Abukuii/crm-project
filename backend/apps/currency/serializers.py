from rest_framework import serializers

from apps.core.money import USD

from .models import ExchangeRate


class ExchangeRateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExchangeRate
        fields = ["id", "currency", "date", "rate", "source", "created_at", "updated_at"]
        read_only_fields = fields


class ManualRateSerializer(serializers.Serializer):
    currency = serializers.ChoiceField(choices=[USD], default=USD)
    rate = serializers.DecimalField(max_digits=18, decimal_places=4, min_value=1)
    date = serializers.DateField(required=False)


class CurrentRateSerializer(serializers.Serializer):
    currency = serializers.CharField()
    rate = serializers.DecimalField(max_digits=18, decimal_places=4)
    date = serializers.DateField()
    source = serializers.CharField()
