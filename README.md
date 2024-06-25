# Monitoring Applications using OpenAI API and GPT Models With OpenTelemetry and Splunk

As a developer building an AI assistant application with OpenAI APIs and GPT Models, I quickly realized how essential monitoring is to ensure smooth performance and reliability. My main goal was to determine which GPT model would be the best fit for my application. Naturally, when I started thinking about gathering the right metrics to understand performance and accuracy, the first tool that came to mind was Splunk. As a dedicated Splunker, I knew Splunk Observability Cloud, with its powerful monitoring and observability features, would be perfect for the job. Here’s a step-by-step guide on how I brought this vision to life.


## Introduction: Why Monitoring Matters

When you're working with advanced APIs like those from OpenAI, ensuring that your application runs seamlessly is paramount. Application performance monitoring (APM) plays a crucial role in identifying performance bottlenecks, understanding user interactions, and maintaining overall system health. Splunk, with its comprehensive observability solutions, offered the perfect platform to achieve these goals.
Setting Up the Environment

To start, I used the Instrumented Python frameworks for Splunk Observability Cloud to build my application. Here's a brief rundown of the steps involved:

### Building the Application with Flask

```
from flask import (
   Flask,
   render_template,
   request,
   Response,
   stream_with_context,
   jsonify,
)

import openai

client = openai.OpenAI()

app = Flask(__name__)

chat_history = [
   {"role": "system", "content": "Hello, I'm Shelly's Assistant; I (actually) run The Splunk T-Shirt Company. AMA"},
]

@app.route("/", methods=["GET"])
def index():
   return render_template("index.html", chat_history=chat_history)

@app.route("/chat", methods=["POST"])
def chat():
   content = request.json["message"]
   chat_history.append({"role": "user", "content": content})
   return jsonify(success=True)

@app.route("/stream", methods=["GET"])
def stream():...

@app.route("/reset", methods=["POST"])
def reset_chat():...
   global chat_history
   chat_history = [
       {"role": "system",
        "content": "Hello, I'm Shelly's Assistant; I (actually) run The Splunk T-Shirt Company. AMA"},
   ]
   return jsonify(success=True)
```

### Instrumenting with OpenTelemetry
Integrating OpenTelemetry into the Flask app to capture traces and spans:
The Splunk distribution of OpenTelemetry Python Instrumentation provides a Python agent that automatically instruments your Python application to capture and report distributed traces to the Splunk Observability Cloud APM.

```
$ pip install splunk-opentelemetry[all]

# otel imports
from opentelemetry import trace
from opentelemetry.metrics import MeterProvider
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter


# setup otel tracing
resource = Resource(attributes={
   SERVICE_NAME: "splunk-shelly-AI-Assistant"
})
provider = TracerProvider(resource=resource)
trace.set_tracer_provider(provider)
tracer = trace.get_tracer(__name__)
otlp_exporter = OTLPSpanExporter(endpoint="http://localhost:4317", insecure=True)
span_processor = BatchSpanProcessor(otlp_exporter)
provider.add_span_processor(span_processor)


# Adding custom attributes to span in the stream() function 
@app.route("/stream", methods=["GET"])
def stream():
  def generate():...
    with tracer.start_as_current_span("call_gpt_model") as span:
      with client.chat.completions.create(
                    messages=chat_history,
                    stream=True,
                    model=GPT_model,
                    temperature=GPT_temperature,
                    top_p=GPT_top_p,
            ) as stream:...


      span.set_attribute("id", chunk.id)
      span.set_attribute("GPT-model", chunk.model)
      span.set_attribute("GPT-temperature", GPT_temperature)
      span.set_attribute("GPT-top_p", GPT_top_p)
      span.set_attribute("prompt", prompt)
      span.set_attribute("response", result)
      span.set_attribute("latency", duration)
      span.set_attribute("tokens_used", tokens_used)
      span.set_attribute("completion_tokens", completion_tokens)

```

## Configuring Splunk Distribution of OpenTelemetry Collector

Configure the Splunk Distribution of Otel Collector to receive and export metrics and traces to Splunk Observability Cloud.

If you plan to run the collector on Linux, Windows, or Kubernetes, installing the collector is straightforward and all instructions are available here.

If you’re like me, developing on a Mac, you have to build the custom binary. All steps to build and execute are available here. I have also included the agent and gateway configuration in my GitHub repo to help. Modify the parameters as you see fit.

And don’t forget to set the following environment variables.

```
OPENAI_API_KEY=<OPENAI-API-KEY>
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
OTEL_RESOURCE_ATTRIBUTES=deployment.environment=dev,service.version=0.0.1
OTEL_SERVICE_NAME=Splunk-Shelly-AI-Assistant
```

Once you have configured the Otel Collector and specified the correct Splunk Observability Cloud endpoint URL and the API token, you’re all set to go.

Start your collector with the proper configuration

```sudo SPLUNK_ACCESS_TOKEN=<TOKEN> SPLUNK_REALM=<REALM> ./otelcol --config=/etc/otel/collector/agent_config.yaml```

Prefix your service run command splunk-py-trace to enable instrumentation

```splunk-py-trace python -m flask run --host=0.0.0.0 --port=5000```

![Screenshot 2024-06-23 at 2 08 42 PM](https://github.com/anushjay/splunk-chatgpt-integration/assets/654200/7e5c95ae-608e-4f15-b784-6c750a26e3e0)


## Analyzing Data in Splunk Observability Cloud
By adding all the data as attributes within spans, we can send it to our Splunk Observability Cloud OTLP endpoint. The benefit of doing this is that you can easily use the data in searches, build dashboards, and create visualizations to monitor performance. In my case, to determine the best GPT model for my application, I implemented custom spans and attributes that provided deeper insights into model performance and accuracy. These metrics included response latency, temperature, top_p, and completion tokens. Along with API performance and GPT model-related metrics, I also captured user satisfaction scores for every response from each model.

1. Below are the Service Map and workflows showing the stream() function invoking the OpenAI API completions call
![blog-1](https://github.com/anushjay/splunk-chatgpt-integration/assets/654200/e4eb3548-ef22-4f31-8edf-0b929bf5863c)

2. Below is the Tag Spotlight of the service with a variety of metrics along with custom metrics like GPT model, temperature, and top_p parameters that we set in each request sent to the respective GPT models. The custom metrics help analyze and filter data based on requests to respective models.
![blog-3](https://github.com/anushjay/splunk-chatgpt-integration/assets/654200/ebaed577-4f1f-4747-b8d7-b28d3fb9a7ab)


3. Below is the Tag Spotlight of the service displaying latency for each GPT-model. These metrics and visualizations would be extremely helpful in making decisions on what model is doing well and suited for the type of application.
![blog-2](https://github.com/anushjay/splunk-chatgpt-integration/assets/654200/829c1fae-de4b-4853-8b9a-e1f73d30ec3a)  

4. Finally, I was able to deep dive into a single trace to understand span performance and tie them to specific model attributes such as prompt tokens and completion tokens along with user satisfaction scores.
![Screenshot 2024-06-23 at 2 16 05 PM](https://github.com/anushjay/splunk-chatgpt-integration/assets/654200/413a52c8-06b4-4335-9170-85945ebe7b74)


## Conclusion: The Journey Ahead
By leveraging OpenTelemetry and Splunk Observability Cloud, I gained valuable insights into my application's performance and the effectiveness of different GPT models. The integration provided a comprehensive monitoring solution, ensuring my application's reliability and responsiveness.
As I continue this journey to build an AI assistant, my next goal is to explore other models and monitoring frameworks like LangChain using Splunk. Stay tuned for an upcoming blog post where I'll dive deeper into advanced monitoring techniques and share more insights on optimizing application performance. If you haven't tried it yet, take advantage of the Splunk Observability Cloud trial to experience these powerful monitoring capabilities for yourself.

Keep experimenting, keep monitoring, and keep optimizing!
