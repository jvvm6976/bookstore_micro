from rest_framework import serializers
from .models import (
    CustomerBookInteraction, CustomerBehaviorProfile,
    Recommendation, KBEntry, ChatSession, ChatMessage,
)


class CustomerBookInteractionSerializer(serializers.ModelSerializer):
    weighted_score = serializers.ReadOnlyField()

    class Meta:
        model  = CustomerBookInteraction
        fields = '__all__'


class CustomerBehaviorProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model  = CustomerBehaviorProfile
        fields = '__all__'


class RecommendationSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Recommendation
        fields = '__all__'


class KBEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model  = KBEntry
        fields = '__all__'


class ChatMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model  = ChatMessage
        fields = '__all__'


class ChatSessionSerializer(serializers.ModelSerializer):
    messages = ChatMessageSerializer(many=True, read_only=True)

    class Meta:
        model  = ChatSession
        fields = '__all__'
