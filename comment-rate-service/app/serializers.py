from rest_framework import serializers
from .models import Review, ReviewReply

class ReviewReplySerializer(serializers.ModelSerializer):
    class Meta:
        model = ReviewReply
        fields = '__all__'
        read_only_fields = ['review']

class ReviewSerializer(serializers.ModelSerializer):
    replies = ReviewReplySerializer(many=True, read_only=True)

    class Meta:
        model = Review
        fields = ['id', 'user_id', 'product_id', 'order_id', 'rating', 'comment', 'status', 'created_at', 'updated_at', 'replies']
        read_only_fields = ['status', 'user_id']
