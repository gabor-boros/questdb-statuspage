![geoffroy-hauwen-i3tiM7n9_CE-unsplash](./post/img/geoffroy-hauwen-i3tiM7n9_CE-unsplash.png)

_Photo by Geoffroy Hauwen from Unsplash.com_

# Monitoring the uptime of an application with Python, Nuxt.js and QuestDB

Highly available services that serve millions of requests rely on the visibility of the system status for customers and internal teams.
This tutorial shows how a lightweight and performant time-series database coupled with queued status checks and a simple UI are key ingredients for robust application monitoring.

## Why build a status page for an application?

Even if we design the most reliable systems, incidents will occur for hard-to-predict reasons.
It's critical to provide as much information as possible to users, customers, and service teams.
The most convenient way to display this is through a status page.

Although the page's responsibility is to provide information, it can reduce the support team's load and eliminate duplicate support tickets.
Status pages are a crucial part of incident management, and usually, other teams enjoy benefits like client and service owners when they need to refer to SLAs.
In this tutorial, I'll show you how to build a simple yet powerful status page that scores well on performance and design.

## What we will build

### Overview

As mentioned above, we will build a simple status page made of two parts: the backend monitors our service, and a frontend shows our services' status on an hourly scale.

![end-result](./post/img/end-result.png)

You will need some experience in Python, JavaScript, and basic SQL knowledge. To build our service, we will use FastAPI, an ultra-fast Python web framework, Celery for scheduling monitoring tasks, QuestDB, the fastest open-source time-series database, to store monitoring results, and NuxtJs to display them.

There's a lot to learn, so let's jump right in!

### Prerequisites

You will need to have the following installed on your machine:

* Python 3.8
* NodeJS 14+
* Docker
* Docker Compose

## Setting up the environment

### Create a new project

First things first, we create a directory, called `status-page`, this is our project root. 
We also need to create another directory called `app` which will contain the backend code. 
After following these steps, you should have a project structure like this.

```
status-page (project root)
└── app (backend service directory)
```

### Installing QuestDB & Redis

Now, we will install QuestDB and Redis. QuestDB is used to store the HTTP status and the service state of our application over time, and Redis is used as a message broker between the backend application and the workers who will do the scheduled monitoring.

To install these services, we will use Docker and Docker Compose. We are going to create a `docker-compose.yml` file within the project root with the following content:

```yaml
version: '3'

volumes:
  questdb_data: {}

services:
  redis:
    image: 'redis:latest'
    ports:
      - '6379:6379'

  questdb:
    image: 'questdb/questdb:latest'
    volumes:
      # Map QuestDB's data directory to the host
      - 'questdb_data:/root/.questdb/db'
    ports:
      - '9000:9000'
      - '8812:8812'
```

Voila! When we run `docker-compose up`, QuestDB and Redis start, and we can access QuestDB's interactive console on [http://127.0.0.1:9000](http://127.0.0.1:9000).

### Install backend dependencies

Now, we have the project structure, and we can run the required services, so we need to set up our backend service to collect data about the website or service we would like to monitor. We will use poetry to manage Python dependencies during this tutorial, so let's start by installing that.

```shell
$ pip install poetry
```

To define the project requirements, create a `pyproject.toml` file with the following content:

```toml
[tool.poetry]
name = "status-page"
version = "0.1.0"
description = "QuestDB tutorial for creating a simple status page."
authors = ["Your name <your.email@example.com>"]
license = "MIT"

[tool.poetry.dependencies]
python = "3.8"

[build-system]
requires = ["poetry-core>=1.0.0"]
build-backend = "poetry.core.masonry.api"
```

Install the project dependencies by executing the following:

```shell
poetry add python fastapi pydantic uvicorn requests \
 psycopg2-binary "databases[postgresql]" "celery[redis]"
```
As you may assume by checking the requirements, we will use QuestDB's Postgres interface to connect. 
When `poetry` finishes its job, it will add the dependencies to `pyproject.toml` and we can now start to implement the backend service.

## Create a simple API

The time has come, let's create the backend service, but step-by-step.
Within the `app` directory, create an `__init__.py` and `main.py`. The first one is responsible for making the `app` directory to a package, while the latter will define the APIs our service exposes. Open `main.py` for edit and add the following:

```python
# main.py

from fastapi import FastAPI

app = FastAPI(
    title="Status Page",
    description="This service gives back the status of the configured URL.",
    version="0.1.0",
)
```

Congratulations! You just created the backend service. You can go and try it out by executing

```shell
$ poetry run uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
...
INFO:     Application startup complete.
```

Although the service does nothing yet, it works and listens for any code change. Add a new endpoint and watch it reload:

```python
# main.py

# ...

@app.get(path="/signals", tags=["Monitoring"])
async def get_signals():
  return {}
```

We have now created an API endpoint that will serve the system status data of the monitored URL. 
If you open [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc), you can see the generated documentation for the endpoint, or you can check it working at [http://127.0.0.1:8000/signals](http://127.0.0.1:8000/signals), though it won't return any data yet.

It is time to have fun, we are going to integrate QuestDB with our shiny new backend service.

## Integrate QuestDB with FastAPI

Integrating QuestDB with FastAPI is easier than you think. Thanks to QuestDB's [Postgres compatibility](https://questdb.io/docs/develop/connect), you can use any standard or popular third-party libraries of any programming language which implements Postgres wire protocol.

### Set up the table

The very first step is to create the table in QuestDB. As said before, our approach is simple, so that the table is simple, too. QuestDB is running from our docker compose script so, we open the interactive console at [http://127.0.0.1:9000](http://127.0.0.1:9000) and create a new table by running the following query:

```sql
CREATE TABLE
    signals(url STRING, http_status INT, received TIMESTAMP, available BOOLEAN)
    timestamp(received);
```

The query executes, and after refreshing the table list on the left, you can see the table we created.

![Interactive Console](./post/img/interactive-console.png)

<!-- Note this is also possible via CURL, might be worth mentioning

curl -G \
  --data-urlencode "query=CREATE TABLE \
  signals(url STRING, http_status INT, received TIMESTAMP, available BOOLEAN) \
  timestamp(received);" \
  http://localhost:9000/exec

 -->

### Connect QuestDB and FastAPI

As we have the table in the database, it is time to connect to QuestDB and query some data to return through the API. To connect, we will use the Postgres interface of QuestDB and SQLAlchemy to connect to it.

To be able to reuse the engine later on, create a new file in the `app` package which is responsible for defining how to connect and name it `db.py`:

```python
# db.py

from sqlalchemy import create_engine

engine = create_engine(
    "postgresql://admin:quest@127.0.0.1:8812/qdb", # Use a the default credentials
    pool_size=5, # Set pool size greater than 1 to not block async requests
    pool_pre_ping=True # Set pre-ping to ensure a connection is opened when sending a query
)
```

To set up a schema that represents the table in the database, create a `models.py` containing the schema definition:

```python
# models.py

from datetime import datetime
from pydantic import BaseModel, Schema


class Signal(BaseModel):
    url: str = Schema(..., description="The monitored URL")
    http_status: int = Schema(..., description="HTTP status code returned by upstream")
    available: bool = Schema(..., description="Represents the service availability")
    received: datetime = Schema(..., description="Timestamp when the signal received")

```

Let's stop here for a moment and talk through what we did in the last steps:

* set up the API which will serve the requests coming from the frontend
* created a table in QuestDB for our status records and provided connection credentials for Postgres wire 
* implemented the schema which is used to serialize the results returned by the database

The next step is to initiate a connection and return the results from the database.
First, import the `engine` and `Signal` schema and then extend the function which serves the `/signals` endpoint:

```python
# main.py

# Other imports ...
from app.db import engine
from app.models import Signal

from typing import List
from pydantic import BaseModel

class SignalResponse(BaseModel):
    url: str
    records: List[Signal]
```

After adding the `defaultdict` import, the implementation of the `/signals` endpoint should look like this:

```python
# main.py

# Other imports ...
from collections import defaultdict

# ...

@app.get(path="/signals", response_model=List[SignalResponse], tags=["Monitoring"])
async def get_signals(limit: int = 60):
    
    # A simple query to return every record belongs to the website we will monitor
    query = f"""
    SELECT * FROM signals
    WHERE url = 'https://questdb.io' ORDER BY received DESC LIMIT {limit};
    """

    signals = defaultdict(list)

    with engine.connect() as conn: # connect to the database
        for result in conn.execute(query): # execute the SELECT query
            signal = Signal(**dict(result)) # parse the results results returned by QuestDB
            signals[signal.url].append(signal) # add every result per URL

    # Return the response which is validated against the `response_model` schema
    return [
        SignalResponse(url=url, records=list(reversed(records)))
        for url, records in signals.items()
    ]
```

Let's recap on our code above, starting from the top:

* we added `defaultdict` import (we'll explain that later)
* extended the function decorator to use `response_model=List[SignalResponse]`, the response model we defined already 
* changed the function signature to include a `limit` parameter and set its default value to `60` since we will monitor HTTP status every minute 
* select the records from the database and prepare a dictionary for the parsed `Signal`s.

You may ask why to group the returned records per URL. Although we will monitor only one URL for the sake of simplicity, I challenge you to change the implementation later and explore QuestDB to handle the monitoring of multiple URLs.

In the following lines, we are connecting to the database, executing the query, and populates the dictionary, which we will use in the last four lines to construct the `SignalResponse`. 
Our version of `main.py` at this point looks like the following:

```python
# main.py

from collections import defaultdict
from typing import List

from fastapi import FastAPI
from pydantic import BaseModel

from app.db import engine
from app.models import Signal


# Add a response model to indicate the structure of the signals API response.
class SignalResponse(BaseModel):
    url: str
    records: List[Signal]

      
app = FastAPI(
    title="Status Page",
    description="This service gives back the status of the configured URL.",
    version="0.1.0",
)

@app.get(path="/signals", response_model=List[SignalResponse], tags=["Monitoring"])
async def get_signals(limit: int = 60):
    
    # A simple query to return every record belongs to the website we will monitor
    query = f"""
    SELECT * FROM signals
    WHERE url = 'https://questdb.io' ORDER BY received DESC LIMIT {limit};
    """

    signals = defaultdict(list)

    with engine.connect() as conn: # connect to the database
        for result in conn.execute(query): # execute the SELECT query
            signal = Signal(**dict(result)) # parse the results results returned by QuestDB
            signals[signal.url].append(signal) # add every result per URL

    # Return the response which is validated against the `response_model` schema
    return [
        SignalResponse(url=url, records=list(reversed(records)))
        for url, records in signals.items()
    ]

```

## Schedule monitoring tasks

For scheduling the monitoring task, we will use Celery Beat, the built-in periodic task scheduler implementation of Celery.

### Scheduling with Celery

Before we schedule any task, we need to configure Celery. In the `app` package, create a new `celery.py` which will contain the Celery and beat schedule configuration. Import `Celery` for creating tasks, and `crontab` for constructing Unix-like crontabs for our tasks.
The task is the dotted path representation of the function which is executed by Celery (`app.tasks.monitor`) and sent to queues handled by Redis.

The only thing left is to configure the beat schedule, which is a simple dictionary. 
We give a name for the schedule, define the dotted path pointing to the task (function), and specify the schedule itself:

```python
# celery.py

from celery import Celery
from celery.schedules import crontab

MONITORING_TASK = "app.tasks.monitor"

celery_app = Celery("tasks", broker="redis://localhost:6379/0")

# Set a queue for task routes
celery_app.conf.task_routes = {
  MONITORING_TASK: "main-queue"
}

# Schedule the monitoring task
celery_app.conf.beat_schedule = {
    "monitor": { # Name of the schedule
        "task": MONITORING_TASK, # Register the monitoring task
        "schedule": crontab(
            minute=f"*/1" # Run the task every minute
        ),
    }
}
```

### Create a monitoring task

And the last part: creating the monitoring task. In the previous section, we talked about the "monitoring task" multiple times, but we didn't see the concrete implementation.

In this final backend related section, you will implement the task which will check the availability of the desired website or service and saves the results as records in QuestDB. The monitoring task is a simple `HTTP HEAD` request and saving the response to the database. We see the implementation in pieces of the `tasks.py` referenced in celery as the dotted path before.

First, we start with imports:

```python
# tasks.py

from datetime import datetime

import requests

from app.celery import celery_app
from app.db import engine
from app.models import Signal

# ...
```

We import `celery_app` which represents the Celery application, an `engine` to save the results in the database, and finally `Signal` to construct the record we will save. As the necessary imports are in place, we can define the `monitor` task.

```python
# tasks.py

# ...

@celery_app.task # register the function as a Celery task
def monitor():
    try:
        response = requests.head("https://questdb.io")
    except Exception as exc: # handle any exception which may occur due to connection errors
        query = f"""
            INSERT INTO signals(received,url,http_status,available)
            VALUES(systimestamp(), 'https://questdb.io', -1, False);
            """

        # Open a connection and execute the query
        with engine.connect() as conn:
            conn.execute(query)

        # Re-raise the exception to not hide issues
        raise exc

# ...
```

As you can see, we send a request to the desired website and store the response for later use. In case the website is down and unreachable, an exception will be raised by requests or any underlying packages. As we need to log that the request does not finish, we catch the exception, save a record in the database, and re-raise the exception to not hide anything. Next, we construct a signal to save.

```python
# ...

@celery_app.task
def monitor():
  	# ...

		signal = Signal(
        url="https://questdb.io",
        http_status=response.status_code,
        received=datetime.now(),
        available=response.status_code >= 200 and response.status_code < 400,
    )
    
    # ...
```

We don't do anything special here, though the following step is more interesting: inserting the result in the database. Finally, we prepare and execute the query based on the `signal`.

```python
# ...

@celery_app.task
def monitor():
    # ...
    
    query = f"""
    INSERT INTO signals(received,url,http_status,available)
    VALUES(systimestamp(), '{signal.url}', {signal.http_status}, {signal.available});
    """

    with engine.connect() as conn:
        conn.execute(query)
```

Congratulations! You just arrived at the last part of the backend service implementation. We did many things and built a service that can periodically check the website's status, save it in the database, and expose the results through an API.

The very last thing we need to address is to allow connections initiated by the frontend later on. As it will run on localhost:3000 and we don't use domain names, the port is different hence all requests will be rejected with errors related to [Cross-Origin Resource Sharing](https://developer.mozilla.org/en-US/docs/Web/HTTP/CORS).

To address this issue, add the following middleware to the application which will allow us to connect at [http://localhost:3000](http://localhost:3000):

```python
# main.py

# Other imports ...
from fastapi.middleware.cors import CORSMiddleware

# app = FastAPI ...

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ...
```

## Implement the frontend

### Setting up frontend

To build the frontend, we will use Nuxt.js. We will use `yarn` to set up the starter project by running `yarn` and selecting the answers detailed below.

```shell
$ yarn create nuxt-app frontend

[...]

? Project name: frontend
? Programming language: JavaScript
? Package manager: Yarn
? UI framework: Tailwind CSS
? Nuxt.js modules: Axios
? Linting tools: (Press <space> to select, <a> to toggle all, <i> to invert selection)
? Testing framework: None
? Rendering mode: Single Page App
? Deployment target: Static (Static/JAMStack hosting)
? Development tools: (Press <space> to select, <a> to toggle all, <i> to invert selection)
? What is your GitHub username? gabor-boros
? Version control system: Git
```

The project root now looks like this:

```
status-page
├── app/
├── frontend/
├── docker-compose.yml
├── poetry.lock
└── pyproject.toml
```

### Cleaning up generated project

Since we don't need any styling delivered by the project generation, we need to get rid of them. Open `frontend/layouts/default.vue` and replace its content with

```vue
<!-- frontend/layouts/default.vue -->

<template>
  <div>
    <Nuxt />
  </div>
</template>
```

Now, we will change `frontend/pages/index.vue` and call the backend service. Let's begin with `<scripts>`.

```vue
<!-- frontend/pages/index.vue -->

<!-- template ... -->

<script>
const LIMIT = 60;

async function fetchSignals($axios, limit) {
  const signals = await $axios.$get(`http://localhost:8000/signals?limit=${limit}`)
  return signals
}

export default { 
  data() {
    return {
      signals: []
    }
  },

  // Handle initial call
  async asyncData({ $axios }) {
    const signals = await fetchSignals($axios, LIMIT)
    return { signals }
  },

  methods: {
    // Calculate uptime based on the signals belongs to a URL
    uptime: (records) => {
      let availableRecords = records.filter(record => record.available).length;
      return ((availableRecords / records.length) * 100).toFixed(2)
    }
  },

  // Set up periodic calls when the component is mounted
  mounted() {
    let that = this
    const axios = this.$axios;

    setInterval(() => {
      Promise.resolve(fetchSignals(axios, LIMIT)).then((signals) => {
        that.signals = signals
      });
    }, 1000 * LIMIT);
  }
}
</script>

```

At the first sight, it might look a lot, but if we check the most important parts in pieces everything will be crystal clear.

We define `fetchSignals` to reduce code duplication later on. Then, we set up initial `signals` data, where we will store the periodically fetched responses returned by the backed. After that, as part of `asyncData`, we initiate an async call towards the backend to get the initial signals to show.

The last part is to define a periodic call to the backend when the component is `mounted`. Right, we have the logic which will call backend and keep the data up to date. Now we have to display the results.

```vue
<!-- frontend/pages/index.vue -->

<template>
  <div class="p-8 h-screen text-center">
    <h1 class="text-2xl font-light">QuestDB website status</h1>
    <h2 class="text-lg font-thin">service uptime in the past 60 minutes</h2>

    <div class="h-8 mt-12 flex justify-center" v-if="signals.length > 0">
      
      <!-- Iterate over the signals belongs to records -->
      <div class="w-1/4" v-for="(signal, s) in signals" :key="s">
        <div class="flex mb-1 text-sm">
          <p class="flex-1 text-left font-normal">{{ signal.url }}</p>
          <p class="flex-1 text-right font-thin">{{ uptime(signal.records) }}% uptime</p>
        </div>
        <div class="grid grid-flow-col auto-cols-max gap-x-1">
          
          <!-- Draw a green or yellow bar depending on service availability -->
          <div 
            v-for="(signal, r) in signal.records"
            :key="r"
            :class="`w-1 bg-${signal.available ? 'green' : 'yellow'}-700`"
          >&nbsp;</div>
        </div>
      </div>
    </div>

    <!-- In case we have no records yet, show an informative message -->
    <div v-else>
      <p>No signals found</p>
    </div>
  </div>
</template>

<!-- scripts ... -->
```

## Run the project

We reached the end of the tutorial. We have both the backend and the frontend. It is time to try everything out.
Run the following commands in different shells from the project root:

```shell
# Shell 1 - Start the application
$ docker-compose up -d
$ poetry run uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

# Shell 2 - Start the worker process
$ poetry run celery --app=app.tasks worker --beat -l info -Q main-queue -c 1

# Shell 3 - Start the frontend
$ cd frontend
$ yarn dev
```

Navigate to [http://localhost:3000](http://localhost:3000) to see the backend reporting the status of the monitored URL.
The first task to check the system status is executed when the scheduler and worker starts and
the status of the website over time can be seen after a few minutes on the page or when you check back at a later stage:

![end-result-2](./post/img/end-result-2.png)

## Summary

We've successfully built a pretty status page that can be publicly-visible to users or used for internal teams to monitor an application's uptime. We've learned how to queue and schedule tasks and store the responses in a time-series database and make use of low-latency queries. Engineers can modify this demo to monitor a website's HTTP response code or multiple endpoints or services for a robust overview of an entire system's status.

Thank you for your attention!

_The containerized source code is available at https://github.com/gabor-boros/questdb-statuspage._

