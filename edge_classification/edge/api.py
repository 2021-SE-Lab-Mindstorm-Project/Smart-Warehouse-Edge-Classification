import json
from datetime import datetime

import requests
from drf_yasg.utils import swagger_auto_schema
from rest_framework import serializers, viewsets
from rest_framework.response import Response

from edge_classification.settings import settings
from . import models, rl
from .models import Sensory, Inventory, Message, Status

if int(settings['anomaly_aware']) == 1:
    rl_model = rl.DQN(6, path='../../a_rl_c.pth')
else:
    rl_model = rl.DQN(4, path='../../rl_c.pth')
anomaly = [False, False]

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


def find_good_dest(item_type):
    state = [item_type]
    available = [True] * 4
    for i in range(3):
        stored_items = Inventory.objects.filter(stored=i)
        if len(stored_items) == 0:
            state.append(-1)
        else:
            state.append(stored_items[0].item_type)

        if len(stored_items) == settings["maximum_capacity_repository"]:
            available[i] = False

    if settings['anomaly_aware']:
        state.extend(anomaly)

    return rl_model.select_tactic(state, available)


class MessageViewSet(viewsets.ModelViewSet):
    queryset = Message.objects.all()
    serializer_class = MessageSerializer
    http_method_names = ['post']

    @swagger_auto_schema(
        responses={400: "Bad request", 204: "Invalid Message Title / Invalid Message Sender / Not allowed"})
    def create(self, request, *args, **kwargs):
        super().create(request, *args, **kwargs)
        sender = int(request.data['sender'])
        title = request.data['title']

        if sender == models.MACHINE_CLASSIFICATION:
            if title == 'Running Check':
                if len(Status.objects.all()) == 0:
                    return Response("Not allowed", status=204)

                current_status = Status.objects.all()[0]

                if current_status.status:
                    return Response(status=201)

                return Response("Not allowed", status=204)

            if title == 'Check Capacity':
                item_type = int(request.data['msg'])

                stored = find_good_dest(item_type)

                if stored is None:
                    return Response("Not allowed", status=204)

                new_item = Inventory(item_type=item_type, stored=stored)
                new_item.save()

                process_message = {'sender': models.EDGE_CLASSIFICATION,
                                   'title': 'Classification Processed',
                                   'msg': json.dumps({'item_type': item_type, 'stored': stored})}
                requests.post(settings['cloud_address'] + '/api/message/', data=process_message)
                requests.post(settings['edge_repository_address'] + '/api/message/', data=process_message)

                return Response(stored, status=201)

            return Response("Invalid Message Title", status=204)

        elif sender == models.EDGE_REPOSITORY:
            if title == 'Order Processed':
                item_type = int(request.data['msg'])

                # Modify Inventory DB
                target_item = Inventory.objects.filter(item_type=item_type)[0]
                target_item.value -= 1
                target_item.updated = datetime.now()
                target_item.save()

                return Response(status=201)

            elif title == 'Anomaly Occurred':
                repo = int(request.data['msg'])
                anomaly[repo] = True

                return Response(status=201)

            elif title == 'Anomaly Solved':
                repo = int(request.data['msg'])
                anomaly[repo] = False

                return Response(status=201)

            return Response("Invalid Message Title", status=204)

        elif sender == models.CLOUD:
            if title == 'Start':
                Inventory.objects.all().delete()
                if len(Status.objects.all()) == 0:
                    current_state = Status()
                else:
                    current_state = Status.objects.all()[0]

                current_state.status = True
                current_state.save()
                return Response(status=201)

            if title == 'Stop':
                if len(Status.objects.all()) == 0:
                    current_state = Status()
                else:
                    current_state = Status.objects.all()[0]

                current_state.status = False
                current_state.save()
                return Response(status=201)

        return Response("Invalid Message Sender", status=204)
