from rest_framework import serializers
from .models import Comment

class CommentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Comment
        fields = [
            'id',
            'customer_id',
            'book_id',
            'order_id',
            'content',
            'rating',
            'created_at',
            'updated_at',
            'helpful_count',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'helpful_count']

class CommentCreateSerializer(serializers.ModelSerializer):
    order_id = serializers.IntegerField(required=False, allow_null=True)

    class Meta:
        model = Comment
        fields = ['customer_id', 'book_id', 'order_id', 'content', 'rating']
        validators = []
    
    def validate_rating(self, value):
        if value < 1 or value > 5:
            raise serializers.ValidationError("Rating must be between 1 and 5")
        return value
