from rest_framework import serializers
from .models import CustomerBookInteraction, Recommendation


class CustomerBookInteractionSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomerBookInteraction
        fields = '__all__'


class RecommendationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Recommendation
        fields = '__all__'
