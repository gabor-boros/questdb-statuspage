![geoffroy-hauwen-i3tiM7n9_CE-unsplash](./post/img/geoffroy-hauwen-i3tiM7n9_CE-unsplash.png)

_Photo by Geoffroy Hauwen from Unsplash.com_

# Building a status page for your application with QuestDB and Python

As a software developer, our role is to design highly available services which serve millions of request every minute, especially in case of a software or platform as a service company. Even if we design the most reliable systems, sometimes we cannot avoid an incident and in that case, we must provide as much information to our users as possible.

The most convenient way to give visibility to our clients about our services' status is to provide a status page for them. Although the page's responsibility is to provide information, it can reduce the load on the support team and eliminate duplicate support tickets. Status pages are part of the incident management and usually, other teams enjoy its benefits like client and service owners when they need to refer to SLAs.

In this tutorial, I'll show you how to build a simple yet powerful status page, which can be easily extended to be more robust.

## What we will build

### Overview

As mentioned above we will build a simple status page which is built up from two parts: the backend which monitors our service and a front end which shows the status of our services on an hourly scale.

![end-result](./post/img/end-result.png)

For this tutorial, you will need some experience in Python, JavaScript, and basic SQL knowledge. To build our service, we will use FastAPI an ultra-fast Python web framework, Celery for scheduling monitoring tasks, QuestDB, the fastest open-source time series database, to store monitoring results, and NuxtJs to display them.

We will have a busy hour now, so let's jump right into it.

### Prerequisites

You will need to have the following installed on your machine:

* Python 3.8
* NodeJS 14+
* Docker
* Docker Compose

## Setting up the environment

### Create a new project

First things first, we create a directory, called `status-page`, this will be our project root, from now on, we will work within this directory. Also, we need to create another directory, called `app` which will contain the backend code. After following these steps, you should have a project structure like this.

```
status-page (project root)
└── app (backend service directory)
```

### Installing QuestDB & Redis

Great, we did the first step! Now, we will install QuestDB and Redis. The latter one will be used as a message broker between the backend application and the workers which will do the scheduled monitoring.

To install these services, we will use Docker and Docker Compose. We are going to simply create a `docker-compose.yml` file within the project root with the following content:

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

Voila! When we run `docker-compose up`, QuestDB and Redis start, and we can access QuestDB's interactive console on http://127.0.0.1:9000.

### Install backend dependencies

Now, we have the project structure and we can run the belonging services, so we need to set up our backend service to collect data about the website or service we would like to monitor. During this tutorial we will use poetry to manage Python dependencies, so let's start by installing that.

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

As we did the necessary setup for the project itself, we can install project dependencies by executing `poetry add python fastapi pydantic uvicorn requests psycopg2-binary "databases[postgresql]" "celery[redis]"`. As you may assume by checking the requirements, we will use QuestDB's Postgres interface to connect.

When `poetry` finishes its job it will add the dependencies to `pyproject.toml` and we can start to implement the backend service.

After the installation completes, your dependencies will look similar to this:

```toml
# ...

[tool.poetry.dependencies]
python = "^3.8"
celery = {extras = ["redis"], version = "^5.0.5"}
databases = {version = "^0.4.1", extras = ["postgresql"]}
fastapi = "^0.62.0"
psycopg2 = "^2.8.6"
pydantic = "^1.7.3"
requests = "^2.25.1"
uvicorn = "^0.13.0"

# ...
```

## Create a simple API

The time has come, let's create the backend service, but step-by-step.

Within the `app` directory, create an `__init__.py` and `main.py`. The first one will be responsible for making the `app` directory to a package, while the latter one will define the APIs our service exposes. Open `main.py` for edit and add the following:

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
INFO:     Started reloader process [61948] using statreload
INFO:     Started server process [61972]
INFO:     Waiting for application startup.
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

What did we do above? We the API endpoint which will serve the monitoring data we collect. If you open http://127.0.0.1:8000/redoc, you can check the generated documentation for the endpoint, or you can check it working at http://127.0.0.1:8000/signals, though it won't return any data.

It is time to have fun, we are going to integrate QuestDB with our shiny new backend service.

## Integrate QuestDB with FastAPI

Integrating QuestDB with FastAPI is easier than you think. Thanks to QuestDB's [Postgres compatibility](https://questdb.io/docs/develop/connect), you can use the standard or popular third-party libraries of any programming language which implements Postgres capabilities.

### Set up the table

The very first step is to create the table in QuestDB. As said before, our approach is simple, so the table will be simple too. Assuming that QuestDB is running, open the interactive console running at http://127.0.0.1:9000 and create a new table by running

```sql
CREATE TABLE
    signals(url STRING, http_status INT, received TIMESTAMP, available BOOLEAN)
    timestamp(received);
```

The query executes, and after refreshing the table list on the left, you can see the table we created.

![Interactive Console](./post/img/interactive-console.png))

### Connect QuestDB and FastAPI

As we have the table in the database, it is time to connect to QuestDB and query some data to return through the API. In order to connect, we will use the Postgres interface of QuestDB and SQLAlchemy to connect to it.

To be able to reuse the engine, later on, we create a new file in the `app` package which is responsible for defining how to connect and name it `db.py`:

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

Let's stop here for a moment and talk through what we did in the past couple of minutes. We set up the API which will serve the requests coming from the front end, created a table in QuestDB, set up the required connection, though we did not connect yet, and implemented the schema which will be used to serialize the results returned by the database.

The next step is to initiate a connection and return the results from the database. We are going to extend the function which serve the `/signals` endpoint. First, import the `engine` and`Signal` schema.

```python
# main.py

# Other imports ...
from app.db import engine
from app.models import Signal
```

Then, create a response schema for the API, which will be handy in the future when we implement the front end.

```python
# main.py

# Other imports ...
from typing import List
from pydantic import BaseModel

class SignalResponse(BaseModel):
    url: str
    records: List[Signal]
```

Now, we have everything to finish the implementation of the `/signals` endpoint. Let's replace the 

```python
# main.py

# ...

@app.get(path="/signals", tags=["Monitoring"])
async def get_signals():
  return {}
```

by the final implementation of the endpoint

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

    # Return the response which will be validated against the `response_model` schema
    return [
        SignalResponse(url=url, records=list(reversed(records)))
        for url, records in signals.items()
    ]
```

Wow! We did a lot in this section, but before going on, make sure that everything in the right place. Starting from top to bottom, we added `defaultdict` import which will be explained later. After that we just extended the function decorator to use `response_model=List[SignalResponse]`, the response model we defined above. Also, we changed the function signature to include a `limit` parameter and set its default value to `60`. For now, we will use `limit` to ensure only the latest 60 records are returned. Since we will monitor the desired website (`https://questdb.io`) every minute, this implementation means that the last 60-minute results will be returned.

Then, we select the records from the database and prepare a dictionary for the parsed `Signal`s. You may ask why to group the returned records per URL. Although we will monitor only one URL for the sake of simplicity, I challenge you to change the implementation later and explore QuestDB to handle the monitoring of multiple URLs.

In the following lines, we are connecting to the database, executing the query, and populates the dictionary, which we will use in the last 4 lines to construct the `SignalResponse`. The result should be similar to this:

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

    # Return the response which will be validated against the `response_model` schema
    return [
        SignalResponse(url=url, records=list(reversed(records)))
        for url, records in signals.items()
    ]

```

## Schedule monitoring tasks

For scheduling the monitoring task, we will use Celery Beat which is the built-in periodic task scheduler implementation of Celery.

### Scheduling with Celery

Before we schedule any task, we need to configure Celery. In the `app` package, create a new `celery.py` which will contain the Celery and beat schedule configuration.

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

Let's talk through what we wrote above. In the first two lines, we import `Celery` and a `crontab`. The first one will be used for creating a Celery application while the latter one is responsible for construct a Unix-like crontab for task scheduling.

From the implementation above, you may realize that we define a "task". The task is the dotted path representation of the function which will be executed by Celery. The tasks are sent to queues, which is defined in the second part of the code:

```python
# celery.py

# ...

MONITORING_TASK = "app.tasks.monitor"

celery_app = Celery("tasks", broker="redis://redis:6379/0")

# Set a queue for task routes
celery_app.conf.task_routes = {
  MONITORING_TASK: "main-queue"
}

# ...
```

The only thing left is to configure the beat schedule, which is a simple dictionary. We give a name for the schedule, define the dotted path pointing to the task (function), and specify the schedule itself. This is the part where the above-mentioned `crontab` is used:

```python
# celery.py

# ...

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

And the last part: creating the monitoring task. In the previous section we talked about the "monitoring task" multiple times, but we didn't see the concrete implementation of that.

In this final backend related section, you will implement the task which will check the availability of the desired website or service and saves the results in QuestDB. The monitoring task will be a simple `HTTP HEAD` request and saving the result to the database. Let's see the implementation in pieces of the `tasks.py` we referenced in celery as the dotted path before.

First, we start with imports

```python
# tasks.py

from datetime import datetime

import requests

from app.celery import celery_app
from app.db import engine
from app.models import Signal

# ...
```

We import `celery_app` which represents the Celery application, `engine` to save the results in the database, and finally `Signal` to construct the record we are going to save. As the necessary imports are in place, we can define the `monitor` task.

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

Congratulations! You just arrived at the last part of the backend service implementation. We did a lot of things and built a service that can periodically check the website's status, saves it in the database, and exposes the results through an API.

The very last thing we need to address is to allow connections initiated by the front end later on. As it will run on http://127.0.0.1:3000 and we don't use domain names, the port will be different hence all request will be rejected with errors related to [Cross-Origin Resource Sharing](https://developer.mozilla.org/en-US/docs/Web/HTTP/CORS).

To address this issue, add the following middleware to the application:

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

The middleware above will let us connect from http://localhost:3000.

## Implement the front end

### Setting up front end

To build the front end, we will use Nuxt.js. We will use `yarn` to set up the starter project by running `yarn` and selecting the answers detailed below.

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

We reached the end of the tutorial. We have both the backend and the front end. It is time to try everything out.

To start the backend we will need to start the API server and the worker process. To do that, run the following commands in different shells from the project root.

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

Now, open http://localhost:3000 and wait some minutes. After some minutes, you will see that the backend is reporting the status of the monitored URL.

![end-result-2](./post/img/end-result-2.png)

Thank you for your attention!

_The containerized source code is available at https://github.com/gabor-boros/questdb-statuspage._
