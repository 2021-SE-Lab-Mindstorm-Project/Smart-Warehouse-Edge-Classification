# Smart-Warehouse-Classification-Edge
## Overall Description
The edge server for classification system has two components, messaging system, and database.

### Messaging System
Messaging system gets the messages using Django REST framework.
Messages from the others are considered as a data that can be stores in this edge server.
Here are the lists of the messages that edge server receives.

* Check capacity request (Classification Machine) -> Classification progressed (Cloud)
* Order processed acknowledgement (Repository Edge)
* Store sensory data (Classification Machine) -> Store sensory data (Cloud, every 15s)
  * `/sensory/` with `post` method
  * You can change the settings in `CRONJOBS` of `edge_classification/edge_classification/settings.py`.


### Database
Database is based on the SQLite 3, with django. Here are the databases of the cloud server.
### Inventory
|Fields|Type|Choices|
|-------|-----|-----|
|item_type|Int|Red(1), White(2), Yellow(3)|
|value|Int||
|updated|Datetime||

### Sensory
|Fields|Type|Choices|
|-------|-----|-----|
|sensorID|Char||
|value|Float||
|datetime|Datetime||

## Run the cloud server
### Prerequisite
* Python 3.7
* Linux-based system
### Running Manual
1. Clone this repository `git clone https://github.com/2021-SE-Lab-Mindstorm-Project/Smart-Warehouse-Edge-Classification`
2. Move to `Smart-Warehouse-Edge-Classification`
3. Make `secrets.json` with `{"django_secret_key": "YOUR_KEY"}`
4. Configure `settings.json` with appropriate values.
5. Make python venv and install requirements with `requirements.txt`
6. Move to `edge_classification` folder.
7. `python manage.py migrate`
8. `python manage.py crontab add`
9. `python manage.py runserver 0:80`
