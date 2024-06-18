from flask import (
    Flask,
    render_template,
    request,
    Response,
    stream_with_context,
    jsonify,
)
import time
import openai
from opentelemetry import trace
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

client = openai.OpenAI()

app = Flask(__name__)

# Set up OpenTelemetry tracing
resource = Resource(attributes={
    SERVICE_NAME: "splunk-shelli"
})
provider = TracerProvider(resource=resource)
trace.set_tracer_provider(provider)
tracer = trace.get_tracer(__name__)
otlp_exporter = OTLPSpanExporter(endpoint="http://localhost:4317", insecure=True)
span_processor = BatchSpanProcessor(otlp_exporter)
provider.add_span_processor(span_processor)

chat_history = [
    {"role": "system", "content": "Hello, I'm Shelli; I (actually) run The Splunk T-Shirt Company. AMA"},
]

GPT_model = "gpt-3.5-turbo"

@app.route("/", methods=["GET"])
def index():
    return render_template("index.html", chat_history=chat_history)


@app.route("/chat", methods=["POST"])
def chat():
    content = request.json["message"]
    global GPT_model
    GPT_model = request.json["model"]
    chat_history.append({"role": "user", "content": content})
    return jsonify(success=True)


@app.route("/stream", methods=["GET"])
def stream():
    def generate():
        assistant_response_content = ""
        start_time = time.time()
        with tracer.start_as_current_span("call_gpt_model") as span:
            result = ""
            tokens_used = 0
            completion_tokens = 0
            with client.chat.completions.create(
                model=GPT_model,
                messages=chat_history,
                stream=True,
                temperature=2.0,
            ) as stream:
                for chunk in stream:
                    if chunk.choices[0].delta and chunk.choices[0].delta.content:
                        token_text = chunk.choices[0].delta.content
                        result += token_text
                        tokens_used += len(token_text.split())
                        completion_tokens += 1  # Assuming each streamed token is counted separately
                        # Set span attributes for each streamed part
                        span.set_attribute("id", chunk.id)
                        span.set_attribute("model", chunk.model)
                        span.set_attribute("response_partial", token_text)
                        span.set_attribute("tokens_used_partial", tokens_used)
                        span.set_attribute("completion_tokens_partial", completion_tokens)
                        # Accumulate the content only if it's not None
                        assistant_response_content += chunk.choices[0].delta.content
                        yield f"data: {chunk.choices[0].delta.content}\n\n"
                    if chunk.choices[0].finish_reason == "stop":
                        break  # Stop if the finish reason is 'stop'

                end_time = time.time()
                latency = end_time - start_time
                span.set_attribute("response", result)
                span.set_attribute("latency", latency)
                span.set_attribute("tokens_used", tokens_used)
                span.set_attribute("completion_tokens", completion_tokens)

            # Once the loop is done, append the full message to chat_history
            chat_history.append(
                {"role": "assistant", "content": assistant_response_content}
            )

    return Response(stream_with_context(generate()), mimetype="text/event-stream")


@app.route("/reset", methods=["POST"])
def reset_chat():
    global chat_history
    chat_history = [
        {"role": "system", "content": "Hello, I'm Shelli; I (actually) run The Splunk T-Shirt Company. AMA"},
    ]
    return jsonify(success=True)
