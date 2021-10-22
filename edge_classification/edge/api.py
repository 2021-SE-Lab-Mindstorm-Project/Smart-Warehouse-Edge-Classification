from datetime import datetime

import requests
from drf_yasg.utils import swagger_auto_schema
from rest_framework import serializers, viewsets
from rest_framework.response import Response

from edge_classification.settings import settings
from . import models
from .models import Sensory, Inventory, Message


# Serializer
class SensoryListSerializer(serializers.ListSerializer):
    def create(self, validated_data):
        sensory_data_list = [Sensory(**item) for item in validated_data]
        return Sensory.objects.bulk_create(sensory_data_list)


class SensorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Sensory
        fields = '__all__'
        list_serializer_class = SensoryListSerializer


class MessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Message
        fields = '__all__'


# Sensory Data
class SensoryViewSet(viewsets.ModelViewSet):
    queryset = Sensory.objects.all()
    serializer_class = SensorySerializer
    http_method_names = ['post']

    @swagger_auto_schema(responses={400: "Bad Request"})
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data, many=isinstance(request.data, list))
        serializer.is_valid(raise_exception=True)

        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, headers=headers)


class MessageViewSet(viewsets.ModelViewSet):
    queryset = Message.objects.all()
    serializer_class = MessageSerializer
    http_method_names = ['post']

    @swagger_auto_schema(responses={400: "Bad request / Invalid Message Title / Invalid Message Sender"})
    def create(self, request, *args, **kwargs):
        super().create(request, *args, **kwargs)
        sender = request.data['sender']
        title = request.data['title']

        if sender == models.MACHINE_CLASSIFICATION:
            if title == 'Check Capacity':
                item_type = int(request['msg']['item_type'])

                target_item = Inventory.objects.filter(id=item_type)[0]
                if target_item.value == int(settings['maximum_capacity_repository']):
                    return Response(status=400)

                else:
                    target_item.value += 1
                    target_item.updated = datetime.now()
                    target_item.save()

                    process_message = {'sender': models.EDGE_CLASSIFICATION,
                                       'title': 'Classification Processed',
                                       'msg': {'item_type': item_type}}
                    requests.post(settings['cloud_address'] + '/api/message/', data=process_message)

                    return Response(status=201)

            return Response({400: "Invalid Message Title"})

        elif sender == models.EDGE_REPOSITORY:
            if title == 'Order Processed':
                item_type = request['msg']['item_type']

                # Modify Inventory DB
                target_item = Inventory.objects.filter(id=item_type)[0]
                target_item.value -= 1
                target_item.updated = datetime.now()
                target_item.save()

                return Response(status=201)

            return Response({400: "Invalid Message Title"})

        return Response({400: "Invalid Message Sender"})
